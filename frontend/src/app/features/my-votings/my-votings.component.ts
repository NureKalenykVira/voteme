import {
  ChangeDetectionStrategy,
  Component,
  computed,
  ElementRef,
  HostListener,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';
import { ElectionsApiService } from '../elections/services/elections-api.service';
import { ElectionListResponse, ElectionResponse } from '../elections/models/elections.models';
import { AuthStorageService } from '../../core/services/auth-storage.service';

@Component({
  selector: 'app-my-votings',
  standalone: true,
  imports: [CommonModule, FormsModule, PublicHeaderComponent, PublicFooterComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './my-votings.component.html',
  styleUrls: ['./my-votings.component.scss'],
})
export class MyVotingsComponent implements OnInit {
  private readonly electionsApi = inject(ElectionsApiService);
  private readonly router = inject(Router);
  private readonly authStorage = inject(AuthStorageService);
  private readonly el = inject(ElementRef);

  private readonly currentUserId = this.getCurrentUserId();

  readonly elections = signal<ElectionResponse[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly page = signal(1);
  readonly total = signal(0);
  readonly searchQuery = signal('');
  readonly statusFilter = signal('');
  readonly showStatusDropdown = signal(false);
  readonly statusLabel = signal('All');
  readonly showSearch = signal(false);

  readonly statusOptions = [
    { value: '', label: 'All' },
    { value: 'active', label: 'Active' },
    { value: 'published', label: 'Upcoming' },
    { value: 'draft', label: 'Draft' },
    { value: 'finished', label: 'Concluded' },
    { value: 'archived', label: 'Archived' },
  ];

  readonly pageSize = 10;

  readonly totalPages = computed(() => Math.max(1, Math.ceil(this.total() / this.pageSize)));
  readonly hasPrev = computed(() => this.page() > 1);
  readonly hasNext = computed(() => this.page() < this.totalPages());

  readonly filteredElections = computed(() => {
    const query = this.searchQuery().toLowerCase().trim();
    if (!query) return this.elections();
    return this.elections().filter((e) => e.title.toLowerCase().includes(query));
  });

  ngOnInit(): void {
    this.loadElections();
  }

  loadElections(): void {
    this.loading.set(true);
    this.error.set('');
    this.electionsApi
      .listMy(this.page(), this.pageSize, this.statusFilter() || undefined)
      .subscribe({
        next: (resp: ElectionListResponse) => {
          this.elections.set(resp.items);
          this.total.set(resp.total);
          this.loading.set(false);
        },
        error: (err: { error?: { detail?: string } }) => {
          this.error.set(err?.error?.detail ?? 'Failed to load votings');
          this.loading.set(false);
        },
      });
  }

  prevPage(): void {
    if (!this.hasPrev()) return;
    this.page.update((p) => p - 1);
    this.loadElections();
  }

  nextPage(): void {
    if (!this.hasNext()) return;
    this.page.update((p) => p + 1);
    this.loadElections();
  }

  navigateEdit(id: string): void {
    this.router.navigate([`/elections/${id}/edit`]);
  }

  navigateDetail(code: string | undefined, id: string): void {
    if (code) {
      this.router.navigate([`/join/${code}`]);
    } else {
      this.router.navigate([`/elections/${id}/edit`]);
    }
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  }

  getStatusLabel(status: string): string {
    const map: Record<string, string> = {
      active: 'ACTIVE',
      published: 'UPCOMING',
      finished: 'CONCLUDED',
      draft: 'DRAFT',
      archived: 'ARCHIVED',
    };
    return map[status] ?? status.toUpperCase();
  }

  getCardClass(status: string): string {
    const map: Record<string, string> = {
      active: 'card--active',
      published: 'card--upcoming',
      finished: 'card--concluded',
      draft: 'card--draft',
      archived: 'card--archived',
    };
    return map[status] ?? 'card--archived';
  }

  isLightCard(status: string): boolean {
    return status === 'finished';
  }

  toggleStatusDropdown(): void {
    this.showStatusDropdown.update((v) => !v);
  }

  selectStatus(value: string, label: string): void {
    this.statusLabel.set(label);
    this.statusFilter.set(value);
    this.page.set(1);
    this.showStatusDropdown.set(false);
    this.loadElections();
  }

  @HostListener('document:click', ['$event'])
  closeDropdown(e: MouseEvent): void {
    if (!this.el.nativeElement.contains(e.target)) {
      this.showStatusDropdown.set(false);
    }
  }

  toggleSearch(): void {
    this.showSearch.set(true);
  }

  closeSearch(): void {
    this.showSearch.set(false);
    this.searchQuery.set('');
  }

  onStatusChange(e: Event): void {
    const value = (e.target as HTMLSelectElement).value;
    this.statusFilter.set(value);
    this.page.set(1);
    this.loadElections();
  }

  onSearchInput(e: Event): void {
    const value = (e.target as HTMLInputElement).value;
    this.searchQuery.set(value);
  }

  isOrganizer(election: ElectionResponse): boolean {
    return !!this.currentUserId && election.created_by === this.currentUserId;
  }

  private getCurrentUserId(): string | null {
    const token = this.authStorage.getToken();
    if (!token) return null;
    try {
      const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(base64)) as { sub?: string };
      return payload.sub ?? null;
    } catch {
      return null;
    }
  }
}
