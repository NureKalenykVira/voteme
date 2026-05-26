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
import { ElectionsApiService } from '../../services/elections-api.service';
import { VoterResponse } from '../../models/elections.models';
import { QRCodeComponent } from 'angularx-qrcode';

@Component({
  selector: 'app-manage-voters',
  standalone: true,
  imports: [CommonModule, QRCodeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './manage-voters.component.html',
  styleUrls: ['./manage-voters.component.scss'],
})
export class ManageVotersComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);

  readonly electionId = this.route.snapshot.paramMap.get('id') ?? '';

  readonly electionTitle = signal('');
  readonly voters = signal<VoterResponse[]>([]);
  readonly loading = signal(true);
  readonly error = signal('');

  readonly page = signal(1);
  readonly pageSize = 20;
  readonly total = signal(0);

  readonly votersInvited = signal(0);
  readonly alreadyVoted = signal(0);
  readonly participationPct = signal(0);

  readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize)));
  readonly hasPrev = computed(() => this.page() > 1);
  readonly hasNext = computed(() => this.page() < this.totalPages());

  readonly inviteCode = signal('');
  readonly inviteLink = signal('');
  readonly copiedCode = signal(false);
  readonly copiedLink = signal(false);
  readonly csvFile = signal<File | null>(null);
  readonly isDragOver = signal(false);
  readonly showAddModal = signal(false);

  ngOnInit(): void {
    if (!this.electionId) {
      this.error.set('Missing election id');
      this.loading.set(false);
      return;
    }

    this.electionsApi.getById(this.electionId).subscribe({
      next: (election) => {
        this.electionTitle.set(election.title ?? '');
        this.inviteCode.set(election.invitation_code ?? '');
        this.inviteLink.set(`${window.location.origin}/join/${election.invitation_code ?? ''}`);
      },
    });

    this.loadVoters();
  }

  loadVoters(): void {
    this.loading.set(true);
    this.error.set('');
    this.electionsApi.getVoters(this.electionId, this.page(), this.pageSize).subscribe({
      next: (resp) => {
        this.voters.set(resp.items);
        this.total.set(resp.total);
        this.votersInvited.set(resp.voters_invited);
        this.alreadyVoted.set(resp.already_voted);
        this.participationPct.set(resp.participation_pct);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load voters');
        this.loading.set(false);
      },
    });
  }

  openAddModal(): void {
    this.showAddModal.set(true);
  }

  closeAddModal(): void {
    this.showAddModal.set(false);
  }

  copyCode(): void {
    navigator.clipboard.writeText(this.inviteCode()).then(() => {
      this.copiedCode.set(true);
      setTimeout(() => this.copiedCode.set(false), 2000);
    });
  }

  copyLink(): void {
    navigator.clipboard.writeText(this.inviteLink()).then(() => {
      this.copiedLink.set(true);
      setTimeout(() => this.copiedLink.set(false), 2000);
    });
  }

  downloadQr(): void {
    const canvas = document.querySelector('.add-modal qrcode canvas') as HTMLCanvasElement;
    if (!canvas) return;
    const a = document.createElement('a');
    a.download = 'vote-qr.png';
    a.href = canvas.toDataURL('image/png');
    a.click();
  }

  onFileSelected(e: Event): void {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) this.csvFile.set(f);
  }

  onDragOver(e: DragEvent): void {
    e.preventDefault();
    this.isDragOver.set(true);
  }

  onDragLeave(): void {
    this.isDragOver.set(false);
  }

  onDrop(e: DragEvent): void {
    e.preventDefault();
    this.isDragOver.set(false);
    const f = e.dataTransfer?.files?.[0];
    if (f) this.csvFile.set(f);
  }

  removeVoter(voter: VoterResponse): void {
    if (voter.status === 'voted') return;
    this.electionsApi.removeVoter(this.electionId, voter.id).subscribe({
      next: () => this.loadVoters(),
      error: (err) => this.error.set(err?.error?.detail ?? 'Failed to remove voter'),
    });
  }

  prevPage(): void {
    if (!this.hasPrev()) return;
    this.page.update((p) => p - 1);
    this.loadVoters();
  }

  nextPage(): void {
    if (!this.hasNext()) return;
    this.page.update((p) => p + 1);
    this.loadVoters();
  }

  backToVotings(): void {
    this.router.navigate(['/my-votings']);
  }
}
