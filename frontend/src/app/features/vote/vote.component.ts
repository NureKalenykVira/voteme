import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { ElectionsApiService } from '../elections/services/elections-api.service';
import {
  BallotOptionResponse,
  MyVoteResponse,
  VotingDetailResponse,
} from '../elections/models/elections.models';

type SubmitState = 'idle' | 'submitting' | 'submitted' | 'error';
type Step = 1 | 2 | 3;

@Component({
  selector: 'app-vote',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './vote.component.html',
  styleUrls: ['./vote.component.scss'],
})
export class VoteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);

  readonly election = signal<VotingDetailResponse | null>(null);
  readonly options = signal<BallotOptionResponse[]>([]);
  readonly notFound = signal(false);

  readonly selectedOptionId = signal<string | null>(null);
  readonly submitState = signal<SubmitState>('idle');
  readonly errorMessage = signal<string>('');
  readonly alreadyVoted = signal(false);
  readonly commitmentHash = signal<string | null>(null);

  readonly step = signal<Step>(1);
  readonly copiedHash = signal(false);

  readonly canSubmit = computed(
    () => this.selectedOptionId() !== null && this.submitState() === 'idle' && !this.alreadyVoted(),
  );

  readonly selectedOption = computed<BallotOptionResponse | null>(() => {
    const id = this.selectedOptionId();
    if (!id) return null;
    return this.options().find((o) => o.id === id) ?? null;
  });

  readonly selectedOptionIndex = computed<number>(() => {
    const id = this.selectedOptionId();
    if (!id) return -1;
    return this.options().findIndex((o) => o.id === id);
  });

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    if (!id) {
      this.notFound.set(true);
      return;
    }

    this.electionsApi.getDetail(id).subscribe({
      next: (data) => {
        this.election.set(data);
        this.options.set(data.options);
        this.loadMyVote(id);
      },
      error: () => this.notFound.set(true),
    });
  }

  private loadMyVote(electionId: string): void {
    this.electionsApi.getMyVote(electionId).subscribe({
      next: (mv: MyVoteResponse) => {
        if (mv.has_voted) {
          this.alreadyVoted.set(true);
          this.commitmentHash.set(mv.commitment_hash ?? null);
          if (mv.option_id) {
            this.selectedOptionId.set(mv.option_id);
          }
          this.submitState.set('submitted');
          this.step.set(3);
        }
      },
      error: () => {
        // GET /my-vote 404 only fires when the election was deleted; ignore silently.
      },
    });
  }

  photoUrl(url: string | undefined): string | null {
    if (!url) return null;
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  }

  selectOption(optionId: string): void {
    if (this.alreadyVoted() || this.submitState() === 'submitting') return;
    this.selectedOptionId.set(optionId);
    if (this.submitState() === 'error') {
      this.submitState.set('idle');
      this.errorMessage.set('');
    }
  }

  isSelected(optionId: string): boolean {
    return this.selectedOptionId() === optionId;
  }

  goToPreview(): void {
    if (!this.canSubmit()) return;
    this.step.set(2);
  }

  backToStep1(): void {
    if (this.alreadyVoted()) return;
    this.step.set(1);
  }

  confirmVote(): void {
    const electionId = this.election()?.id;
    const optionId = this.selectedOptionId();
    if (!electionId || !optionId || !this.canSubmit()) return;

    this.submitState.set('submitting');
    this.errorMessage.set('');

    this.electionsApi.submitVote(electionId, { option_id: optionId }).subscribe({
      next: (resp) => {
        this.submitState.set('submitted');
        this.alreadyVoted.set(true);
        this.commitmentHash.set(resp.commitment_hash);
        this.step.set(3);
      },
      error: (err: HttpErrorResponse) => {
        this.submitState.set('error');
        const detail =
          typeof err.error === 'object' && err.error && 'detail' in err.error
            ? String((err.error as { detail: unknown }).detail)
            : 'Failed to submit vote. Please try again.';
        this.errorMessage.set(detail);
        if (err.status === 409 && detail.toLowerCase().includes('already')) {
          this.alreadyVoted.set(true);
          this.step.set(3);
        }
      },
    });
  }

  goHome(): void {
    this.router.navigate(['/my-votings']);
  }

  copyHash(hash: string): void {
    navigator.clipboard.writeText(hash).then(() => {
      this.copiedHash.set(true);
      setTimeout(() => this.copiedHash.set(false), 2000);
    });
  }
}
