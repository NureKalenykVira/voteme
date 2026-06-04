import { ChangeDetectionStrategy, ChangeDetectorRef, Component, computed, inject, OnInit, signal } from '@angular/core';
import { CommonModule, Location } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { take } from 'rxjs/operators';
import { TranslateService, TranslatePipe } from '@ngx-translate/core';
import { AuditApiService } from '../../services/audit-api.service';
import { AuditLogResponse, VerifyChainResponse } from '../../models/audit.models';
import { PublicFooterComponent } from '../../../../shared/layout/public-footer/public-footer.component';
import { LanguageService } from '../../../../core/services/language.service';

@Component({
  selector: 'app-event-log',
  standalone: true,
  imports: [CommonModule, RouterLink, PublicFooterComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './event-log.component.html',
  styleUrls: ['./event-log.component.scss'],
})
export class EventLogComponent implements OnInit {
  private readonly auditApi = inject(AuditApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly translate = inject(TranslateService);
  private readonly language = inject(LanguageService);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly location = inject(Location);

  readonly data = signal<AuditLogResponse | null>(null);
  readonly chainStatus = signal<VerifyChainResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly page = signal(1);
  readonly actionFilter = signal('');
  readonly searchQuery = signal('');
  readonly votingIdFilter = signal('');

  private readonly pageSize = 20;

  readonly locale = computed(() => this.language.currentLang() === 'uk' ? 'uk-UA' : 'en-US');

  readonly showActionDropdown = signal(false);
  readonly actionLabel = signal('eventLog.filterAll');
  readonly showSearch = signal(false);

  readonly actionOptions = [
    { value: '', labelKey: 'eventLog.filterAll' },
    { value: 'VOTE_SUBMITTED', labelKey: 'eventLog.actions.VOTE_SUBMITTED' },
    { value: 'ELECTION_CREATED', labelKey: 'eventLog.actions.ELECTION_CREATED' },
    { value: 'ELECTION_PUBLISHED', labelKey: 'eventLog.actions.ELECTION_PUBLISHED' },
    { value: 'ELECTION_ACTIVATED', labelKey: 'eventLog.actions.ELECTION_ACTIVATED' },
    { value: 'ELECTION_FINISHED', labelKey: 'eventLog.actions.ELECTION_FINISHED' },
    { value: 'ELECTION_ARCHIVED', labelKey: 'eventLog.actions.ELECTION_ARCHIVED' },
    { value: 'VOTER_ADDED', labelKey: 'eventLog.actions.VOTER_ADDED' },
    { value: 'VOTER_REMOVED', labelKey: 'eventLog.actions.VOTER_REMOVED' },
    { value: 'VOTER_BULK_IMPORTED', labelKey: 'eventLog.actions.VOTER_BULK_IMPORTED' },
    { value: 'BLOCKCHAIN_RECORD', labelKey: 'eventLog.actions.BLOCKCHAIN_RECORD' },
  ];

  ngOnInit(): void {
    this.route.queryParams.pipe(take(1)).subscribe((params) => {
      if (params['voting_id']) {
        this.votingIdFilter.set(params['voting_id']);
      }
      this.loadData();
    });
    this.auditApi.verifyChain().subscribe({
      next: (r) => this.chainStatus.set(r),
      error: () => {},
    });
    this.translate.onLangChange.subscribe(() => {
      this.cdr.markForCheck();
    });
  }

  private loadData(): void {
    this.loading.set(true);
    this.error.set(false);
    this.auditApi
      .getLog({
        page: this.page(),
        page_size: this.pageSize,
        action: this.actionFilter() || undefined,
        search: this.searchQuery() || undefined,
        voting_id: this.votingIdFilter() || undefined,
      })
      .subscribe({
        next: (resp) => {
          this.data.set(resp);
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }

  applyFilter(): void {
    this.page.set(1);
    this.loadData();
  }

  toggleActionDropdown(): void {
    this.showActionDropdown.update((v) => !v);
  }

  selectAction(value: string, labelKey: string): void {
    this.actionLabel.set(labelKey);
    this.actionFilter.set(value);
    this.showActionDropdown.set(false);
    this.applyFilter();
  }

  toggleSearch(): void {
    this.showSearch.set(true);
  }

  closeSearch(): void {
    this.showSearch.set(false);
    this.searchQuery.set('');
    this.applyFilter();
  }

  onSearchInput(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.loadData();
  }

  nextPage(): void {
    if (this.page() >= this.totalPages()) return;
    this.page.update((p) => p + 1);
    this.loadData();
  }

  totalPages(): number {
    const d = this.data();
    if (!d || d.total === 0) return 1;
    return Math.ceil(d.total / this.pageSize);
  }

  formatAction(action: string): string {
    const key = `eventLog.actions.${action}`;
    return this.translate.instant(key) !== key
      ? this.translate.instant(key)
      : action.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
  }

  formatDate(iso: string, locale = this.locale()): string {
    return new Date(iso).toLocaleString(locale, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  formatDetails(details: string | null | undefined): string {
    if (!details) return '—';
    const match = details.match(/^(\d+) voters added$/);
    if (match) {
      return this.translate.instant('eventLog.votersAdded', { count: match[1] });
    }
    return details;
  }

  truncateHash(hash: string): string {
    return hash.slice(0, 18) + '...' + hash.slice(-6);
  }

  etherscanUrl(hash: string): string {
    return `https://sepolia.etherscan.io/tx/${hash}`;
  }
}
