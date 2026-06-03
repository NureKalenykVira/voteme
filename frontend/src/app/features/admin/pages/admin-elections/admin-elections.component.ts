import {
  ChangeDetectionStrategy,
  Component,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminApiService } from '../../services/admin-api.service';
import { AdminElectionListResponse, AdminElectionResponse } from '../../models/admin.models';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

const PAGE_SIZE = 20;

@Component({
  selector: 'app-admin-elections',
  standalone: true,
  imports: [CommonModule, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admin-elections.component.html',
  styleUrls: ['./admin-elections.component.scss'],
})
export class AdminElectionsComponent implements OnInit, OnDestroy {
  private readonly adminApi = inject(AdminApiService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);
  private readonly searchSubject = new Subject<string>();

  readonly elections = signal<AdminElectionListResponse | null>(null);
  readonly loading = signal(false);
  readonly loadError = signal('');
  readonly page = signal(1);
  readonly statusFilter = signal('');
  readonly searchQuery = signal('');
  readonly showStatusDropdown = signal(false);
  readonly showSearch = signal(false);
  readonly statusLabel = signal('admin.elections.filterAllStatuses');
  readonly confirmDelete = signal<AdminElectionResponse | null>(null);

  readonly statusOptions = [
    { value: '', labelKey: 'admin.elections.filterAllStatuses' },
    { value: 'draft', labelKey: 'admin.elections.statusDraft' },
    { value: 'published', labelKey: 'admin.elections.statusPublished' },
    { value: 'active', labelKey: 'admin.elections.statusActive' },
    { value: 'finished', labelKey: 'admin.elections.statusFinished' },
    { value: 'archived', labelKey: 'admin.elections.statusArchived' },
  ];

  ngOnInit(): void {
    this.searchSubject.pipe(debounceTime(300), distinctUntilChanged()).subscribe((q) => {
      this.searchQuery.set(q);
      this.page.set(1);
      this.loadElections();
    });
    this.loadElections();
  }

  ngOnDestroy(): void {
    this.searchSubject.complete();
  }

  loadElections(): void {
    this.loading.set(true);
    this.adminApi
      .listElections({
        page: this.page(),
        page_size: PAGE_SIZE,
        status: this.statusFilter() || undefined,
        search: this.searchQuery() || undefined,
      })
      .subscribe({
        next: (data) => {
          this.elections.set(data);
          this.loadError.set('');
          this.loading.set(false);
        },
        error: (err) => {
          this.loadError.set(err?.error?.detail ?? 'Failed to load elections');
          this.loading.set(false);
        },
      });
  }

  toggleStatusDropdown(): void {
    this.showStatusDropdown.update((v) => !v);
  }

  selectStatus(value: string, labelKey: string): void {
    this.statusLabel.set(labelKey);
    this.statusFilter.set(value);
    this.showStatusDropdown.set(false);
    this.page.set(1);
    this.loadElections();
  }

  getElectionStatusKey(status: string): string {
    const map: Record<string, string> = {
      draft: 'admin.elections.statusDraft',
      published: 'admin.elections.statusPublished',
      active: 'admin.elections.statusActive',
      finished: 'admin.elections.statusFinished',
      archived: 'admin.elections.statusArchived',
    };
    return map[status] ?? status.toUpperCase();
  }

  onSearch(event: Event): void {
    this.searchSubject.next((event.target as HTMLInputElement).value);
  }

  closeSearch(): void {
    this.showSearch.set(false);
    this.searchQuery.set('');
    this.page.set(1);
    this.loadElections();
  }

  goToResults(id: string): void {
    this.router.navigate(['/elections', id, 'results']);
  }

  goToEventLog(id: string): void {
    this.router.navigate(['/event-log'], { queryParams: { voting_id: id } });
  }

  onDelete(election: AdminElectionResponse): void {
    this.confirmDelete.set(election);
  }

  confirmDeleteElection(): void {
    const election = this.confirmDelete();
    if (!election) return;
    this.adminApi.forceDeleteElection(election.id).subscribe({
      next: () => {
        this.confirmDelete.set(null);
        this.toast.success('Election deleted');
        this.loadElections();
      },
      error: (err) => {
        this.confirmDelete.set(null);
        this.toast.error(err?.error?.detail ?? 'Failed to delete election');
      },
    });
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.loadElections();
  }

  nextPage(): void {
    if (!this.hasNext()) return;
    this.page.update((p) => p + 1);
    this.loadElections();
  }

  hasNext(): boolean {
    const e = this.elections();
    if (!e) return false;
    return this.page() * PAGE_SIZE < e.total;
  }
}
