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
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { PublicHeaderComponent } from '../../shared/layout/public-header/public-header.component';
import { PublicFooterComponent } from '../../shared/layout/public-footer/public-footer.component';
import { ElectionsApiService } from '../elections/services/elections-api.service';
import { ElectionListResponse, ElectionResponse } from '../elections/models/elections.models';
import { AuthStorageService } from '../../core/services/auth-storage.service';
import { LanguageService } from '../../core/services/language.service';

@Component({
  selector: 'app-my-votings',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe, PublicHeaderComponent, PublicFooterComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './my-votings.component.html',
  styleUrls: ['./my-votings.component.scss'],
})
export class MyVotingsComponent implements OnInit {
  private readonly electionsApi = inject(ElectionsApiService);
  private readonly router = inject(Router);
  private readonly authStorage = inject(AuthStorageService);
  private readonly el = inject(ElementRef);
  private readonly translate = inject(TranslateService);
  private readonly language = inject(LanguageService);

  private readonly currentUserId = this.getCurrentUserId();

  readonly elections = signal<ElectionResponse[]>([]);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly page = signal(1);
  readonly total = signal(0);
  readonly searchQuery = signal('');
  readonly statusFilter = signal('');
  readonly showStatusDropdown = signal(false);
  readonly statusLabel = signal('myVotings.statusAll');
  readonly showSearch = signal(false);
  readonly confirmAction = signal<{ type: 'delete' | 'archive'; election: ElectionResponse } | null>(null);

  readonly statusOptions = [
    { value: '', labelKey: 'myVotings.statusAll' },
    { value: 'active', labelKey: 'myVotings.statusActive' },
    { value: 'published', labelKey: 'myVotings.statusUpcoming' },
    { value: 'draft', labelKey: 'myVotings.statusDraft' },
    { value: 'finished', labelKey: 'myVotings.statusConcluded' },
    { value: 'archived', labelKey: 'myVotings.statusArchived' },
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
          this.error.set(err?.error?.detail ?? this.translate.instant('myVotings.errorLoad'));
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
    const locale = this.language.currentLang() === 'uk' ? 'uk-UA' : 'en-US';
    return new Date(iso).toLocaleString(locale, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  getStatusLabel(status: string): string {
    const map: Record<string, string> = {
      active: 'myVotings.badgeActive',
      published: 'myVotings.badgeUpcoming',
      finished: 'myVotings.badgeConcluded',
      draft: 'myVotings.badgeDraft',
      archived: 'myVotings.badgeArchived',
    };
    return map[status] ?? 'myVotings.badgeArchived';
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

  selectStatus(value: string, labelKey: string): void {
    this.statusLabel.set(labelKey);
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

  onDeleteClick(election: ElectionResponse): void {
    this.confirmAction.set({ type: 'delete', election });
  }

  onArchiveClick(election: ElectionResponse): void {
    this.confirmAction.set({ type: 'archive', election });
  }

  confirmActionExecute(): void {
    const action = this.confirmAction();
    if (!action) return;
    const { type, election } = action;
    if (type === 'delete') {
      this.electionsApi.deleteVoting(election.id).subscribe({
        next: () => {
          this.confirmAction.set(null);
          this.loadElections();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.error.set(err?.error?.detail ?? this.translate.instant('myVotings.errorDelete'));
          this.confirmAction.set(null);
        },
      });
    } else {
      this.electionsApi.archiveVoting(election.id).subscribe({
        next: () => {
          this.confirmAction.set(null);
          this.loadElections();
        },
        error: (err: { error?: { detail?: string } }) => {
          this.error.set(err?.error?.detail ?? this.translate.instant('myVotings.errorArchive'));
          this.confirmAction.set(null);
        },
      });
    }
  }

  cancelAction(): void {
    this.confirmAction.set(null);
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
