import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { environment } from '../../../environments/environment';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { ElectionsApiService } from '../elections/services/elections-api.service';
import { BallotOptionResponse, VotingDetailResponse } from '../elections/models/elections.models';

@Component({
  selector: 'app-vote',
  standalone: true,
  imports: [CommonModule, PublicHeaderComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './vote.component.html',
  styleUrls: ['./vote.component.scss'],
})
export class VoteComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly electionsApi = inject(ElectionsApiService);

  readonly election = signal<VotingDetailResponse | null>(null);
  readonly options = signal<BallotOptionResponse[]>([]);
  readonly notFound = signal(false);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.electionsApi.getDetail(id).subscribe({
      next: (data) => {
        this.election.set(data);
        this.options.set(data.options);
      },
      error: () => this.notFound.set(true),
    });
  }

  photoUrl(url: string | undefined): string | null {
    if (!url) return null;
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  }

  cardClass(index: number): string {
    return `option-card--variant-${index % 4}`;
  }

  castVote(): void {
    console.log('cast vote', this.election()?.id);
  }
}
