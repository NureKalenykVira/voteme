import {
  ChangeDetectionStrategy,
  Component,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';
import { ButtonComponent } from '../../shared/ui/button/button.component';
import { ElectionsApiService } from '../elections/services/elections-api.service';
import {
  BallotOptionResponse,
  VotingJoinResponse,
} from '../elections/models/elections.models';
import { AuthStorageService } from '../../core/services/auth-storage.service';
import { environment } from '../../../environments/environment';

type ButtonState = 'cast_vote' | 'cast_vote_disabled' | 'already_voted' | 'go_to_results' | 'edit';

@Component({
  selector: 'app-voting-detail',
  standalone: true,
  imports: [CommonModule, PublicHeaderComponent, PublicFooterComponent, ButtonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './voting-detail.component.html',
  styleUrls: ['./voting-detail.component.scss'],
})
export class VotingDetailComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly electionsApi = inject(ElectionsApiService);
  readonly authStorage = inject(AuthStorageService);

  readonly election = signal<VotingJoinResponse | null>(null);
  readonly options = signal<BallotOptionResponse[]>([]);
  readonly notFound = signal(false);
  readonly hours = signal(0);
  readonly minutes = signal(0);
  readonly seconds = signal(0);
  readonly descExpanded = signal(false);

  private intervalId?: ReturnType<typeof setInterval>;

  get buttonState(): ButtonState {
    const e = this.election();
    if (!e) return 'cast_vote_disabled';
    if (e.status === 'concluded') return 'go_to_results';
    if (e.is_organizer && e.status !== 'active') return 'edit';
    if (e.user_has_voted) return 'already_voted';
    if (e.status === 'published' || e.status === 'draft') return 'cast_vote_disabled';
    return 'cast_vote';
  }

  toggleDesc(): void {
    this.descExpanded.set(!this.descExpanded());
  }

  cardClass(index: number): string {
    return `option-card--variant-${index % 4}`;
  }

  photoUrl(url: string | undefined): string | null {
    if (!url) return null;
    return url.startsWith('/') ? `${environment.apiUrl}${url}` : url;
  }

  ngOnInit(): void {
    const code = this.route.snapshot.paramMap.get('code') ?? '';
    this.electionsApi.getByCode(code).subscribe({
      next: (data) => {
        this.election.set(data);
        this.options.set(data.options);
        this.initTimer(data);
      },
      error: () => this.notFound.set(true),
    });
  }

  private initTimer(e: VotingJoinResponse): void {
    if (e.status === 'concluded') {
      this.hours.set(0);
      this.minutes.set(0);
      this.seconds.set(0);
      return;
    }

    if (e.status === 'published' || e.status === 'draft') {
      // show static voting duration (end - start)
      const diff = new Date(e.end_date_time).getTime() - new Date(e.start_date_time).getTime();
      this.hours.set(Math.floor(diff / 3600000));
      this.minutes.set(Math.floor((diff % 3600000) / 60000));
      this.seconds.set(Math.floor((diff % 60000) / 1000));
      return;
    }

    // active — countdown to end
    const tick = () => {
      const diff = new Date(e.end_date_time).getTime() - Date.now();
      if (diff <= 0) {
        this.hours.set(0);
        this.minutes.set(0);
        this.seconds.set(0);
        clearInterval(this.intervalId);
        return;
      }
      this.hours.set(Math.floor(diff / 3600000));
      this.minutes.set(Math.floor((diff % 3600000) / 60000));
      this.seconds.set(Math.floor((diff % 60000) / 1000));
    };
    tick();
    this.intervalId = setInterval(tick, 1000);
  }

  formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  onPrimaryAction(): void {
    const e = this.election();
    if (!e) return;

    if (this.buttonState === 'go_to_results') {
      this.router.navigate(['/elections', e.id, 'results']);
      return;
    }

    if (this.buttonState === 'edit') {
      this.router.navigate(['/elections', e.id, 'edit']);
      return;
    }

    if (this.buttonState === 'cast_vote') {
      if (!this.authStorage.isAuthenticated()) {
        this.router.navigate(['/auth/login'], {
          queryParams: { redirect: this.router.url },
        });
        return;
      }
      this.router.navigate(['/vote', e.id]);
    }
  }

  ngOnDestroy(): void {
    clearInterval(this.intervalId);
  }
}
