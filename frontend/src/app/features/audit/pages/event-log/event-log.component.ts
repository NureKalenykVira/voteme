import { ChangeDetectionStrategy, Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { AuditApiService } from '../../services/audit-api.service';
import { AuditLogResponse, VerifyChainResponse } from '../../models/audit.models';
import { PublicFooterComponent } from '../../../../shared/layout/public-footer/public-footer.component';

@Component({
  selector: 'app-event-log',
  standalone: true,
  imports: [CommonModule, RouterLink, PublicFooterComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './event-log.component.html',
  styleUrls: ['./event-log.component.scss'],
})
export class EventLogComponent implements OnInit {
  private readonly auditApi = inject(AuditApiService);

  readonly data = signal<AuditLogResponse | null>(null);
  readonly chainStatus = signal<VerifyChainResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly page = signal(1);
  readonly actionFilter = signal('');
  readonly searchQuery = signal('');

  private readonly pageSize = 20;

  readonly showActionDropdown = signal(false);
  readonly actionLabel = signal('All');
  readonly showSearch = signal(false);

  readonly actionOptions = [
    { value: '', label: 'All' },
    { value: 'VOTE_SUBMITTED', label: 'Vote submitted' },
    { value: 'ELECTION_CREATED', label: 'Election created' },
    { value: 'ELECTION_PUBLISHED', label: 'Election published' },
    { value: 'ELECTION_ACTIVATED', label: 'Election activated' },
    { value: 'ELECTION_FINISHED', label: 'Election finished' },
    { value: 'ELECTION_ARCHIVED', label: 'Election archived' },
    { value: 'VOTER_ADDED', label: 'Voter added' },
    { value: 'VOTER_REMOVED', label: 'Voter removed' },
    { value: 'VOTER_BULK_IMPORTED', label: 'Voters imported' },
    { value: 'BLOCKCHAIN_RECORD', label: 'Blockchain record' },
  ];

  ngOnInit(): void {
    this.loadData();
    this.auditApi.verifyChain().subscribe({
      next: (r) => this.chainStatus.set(r),
      error: () => {},
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

  selectAction(value: string, label: string): void {
    this.actionLabel.set(label);
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
    const text = action.replace(/_/g, ' ').toLowerCase();
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  formatDate(iso: string): string {
    const date = new Date(iso);
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    const month = months[date.getMonth()];
    const day = date.getDate();
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${month} ${day}, ${year} ${hours}:${minutes}`;
  }

  truncateHash(hash: string): string {
    return hash.slice(0, 18) + '...' + hash.slice(-6);
  }

  etherscanUrl(hash: string): string {
    return `https://sepolia.etherscan.io/tx/${hash}`;
  }
}
