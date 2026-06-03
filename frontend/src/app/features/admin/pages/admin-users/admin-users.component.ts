import {
  ChangeDetectionStrategy,
  Component,
  inject,
  OnDestroy,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { TranslatePipe, TranslateService } from '@ngx-translate/core';
import { AdminApiService } from '../../services/admin-api.service';
import { AdminUserListResponse, AdminUserResponse } from '../../models/admin.models';
import { Role } from '../../../auth/models/auth.models';
import { AuthStorageService } from '../../../../core/services/auth-storage.service';
import { TextInputComponent } from '../../../../shared/ui/text-input/text-input.component';
import { PasswordInputComponent } from '../../../../shared/ui/password-input/password-input.component';
import { ToastService } from '../../../../shared/ui/toast/toast.service';

const PAGE_SIZE = 20;

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, TextInputComponent, PasswordInputComponent, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './admin-users.component.html',
  styleUrls: ['./admin-users.component.scss'],
})
export class AdminUsersComponent implements OnInit, OnDestroy {
  private readonly api = inject(AdminApiService);
  private readonly fb = inject(FormBuilder);
  private readonly authStorage = inject(AuthStorageService);
  private readonly toast = inject(ToastService);
  private readonly translate = inject(TranslateService);
  private readonly searchSubject = new Subject<string>();

  readonly users = signal<AdminUserListResponse | null>(null);
  readonly loading = signal(false);
  readonly loadError = signal('');
  readonly page = signal(1);
  readonly roleFilter = signal('');
  readonly searchQuery = signal('');
  readonly showAddModal = signal(false);
  readonly confirmDelete = signal<AdminUserResponse | null>(null);
  readonly saving = signal(false);

  readonly showRoleDropdown = signal(false);
  readonly showSearch = signal(false);
  readonly roleLabel = signal('admin.users.filterAllRoles');

  readonly roleOptions = [
    { value: '', labelKey: 'admin.users.filterAllRoles' },
    { value: 'voter', labelKey: 'admin.users.roleVoter' },
    { value: 'organizer', labelKey: 'admin.users.roleOrganizer' },
    { value: 'auditor', labelKey: 'admin.users.roleAuditor' },
    { value: 'global_admin', labelKey: 'admin.users.roleAdmin' },
  ];

  readonly showModalRoleDropdown = signal(false);
  readonly modalRoleLabel = signal('admin.users.roleVoter');
  readonly openRoleDropdown = signal<string | null>(null);
  readonly dropdownPos = signal<{ top: number; left: number } | null>(null);

  readonly modalRoleOptions = [
    { value: 'voter', labelKey: 'admin.users.roleVoter' },
    { value: 'organizer', labelKey: 'admin.users.roleOrganizer' },
    { value: 'auditor', labelKey: 'admin.users.roleAuditor' },
    { value: 'global_admin', labelKey: 'admin.users.roleAdmin' },
  ];

  readonly addUserForm = this.fb.group({
    full_name: [''],
    email: ['', [Validators.required, Validators.email]],
    role: ['voter' as Role, Validators.required],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  ngOnInit(): void {
    this.searchSubject.pipe(debounceTime(300), distinctUntilChanged()).subscribe((q) => {
      this.searchQuery.set(q);
      this.page.set(1);
      this.loadUsers();
    });
    this.loadUsers();
  }

  ngOnDestroy(): void {
    this.searchSubject.complete();
  }

  loadUsers(): void {
    this.loading.set(true);
    const params: { page: number; page_size: number; role?: string; search?: string } = {
      page: this.page(),
      page_size: PAGE_SIZE,
    };
    if (this.roleFilter()) params['role'] = this.roleFilter();
    if (this.searchQuery()) params['search'] = this.searchQuery();

    this.api.getUsers(params).subscribe({
      next: (data) => {
        this.users.set(data);
        this.loadError.set('');
        this.loading.set(false);
      },
      error: (err) => {
        this.loadError.set(err?.error?.detail ?? 'Failed to load users');
        this.loading.set(false);
      },
    });
  }

  onRoleChange(userId: string, role: string): void {
    this.api.patchUserRole(userId, { role: role as Role }).subscribe({
      next: (updated) => {
        const current = this.users();
        if (!current) return;
        this.users.set({
          ...current,
          items: current.items.map((u) => (u.id === userId ? updated : u)),
        });
        this.toast.success('Role updated');
      },
      error: (err) => this.toast.error(err?.error?.detail ?? 'Failed to change role'),
    });
  }

  onDelete(user: AdminUserResponse): void {
    if (this.isCurrentUser(user.id)) return;
    this.confirmDelete.set(user);
  }

  isCurrentUser(id: string): boolean {
    return this.authStorage.getCurrentUserId() === id;
  }

  confirmDeleteUser(): void {
    const user = this.confirmDelete();
    if (!user) return;
    this.api.deleteUser(user.id).subscribe({
      next: () => {
        this.confirmDelete.set(null);
        this.toast.success('User deleted');
        this.loadUsers();
      },
      error: (err) => {
        this.confirmDelete.set(null);
        this.toast.error(err?.error?.detail ?? 'Failed to delete user');
      },
    });
  }

  submitAddUser(): void {
    if (this.addUserForm.invalid || this.saving()) return;
    this.saving.set(true);
    const val = this.addUserForm.getRawValue();
    this.api
      .createUser({
        email: val.email!,
        role: val.role as Role,
        password: val.password!,
        full_name: val.full_name || undefined,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.showAddModal.set(false);
          this.addUserForm.reset({ role: 'voter' });
          this.modalRoleLabel.set('admin.users.roleVoter');
          this.toast.success('User created');
          this.loadUsers();
        },
        error: (err) => {
          this.saving.set(false);
          this.toast.error(err?.error?.detail ?? 'Failed to create user');
        },
      });
  }

  setRoleFilter(role: string): void {
    this.roleFilter.set(role);
    this.page.set(1);
    this.loadUsers();
  }

  toggleRoleDropdown(): void {
    this.showRoleDropdown.update((v) => !v);
  }

  selectRole(value: string, labelKey: string): void {
    this.roleLabel.set(labelKey);
    this.showRoleDropdown.set(false);
    this.setRoleFilter(value);
  }

  toggleRowRoleDropdown(userId: string, event: MouseEvent): void {
    if (this.openRoleDropdown() === userId) {
      this.openRoleDropdown.set(null);
      this.dropdownPos.set(null);
      return;
    }
    const btn = event.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
    this.dropdownPos.set({ top: rect.bottom + 4, left: rect.left });
    this.openRoleDropdown.set(userId);
  }

  getUserRole(userId: string): string {
    return this.users()?.items.find((u) => u.id === userId)?.role ?? '';
  }

  selectRowRole(userId: string, role: string): void {
    this.openRoleDropdown.set(null);
    this.onRoleChange(userId, role);
  }

  getRoleLabel(role: string): string {
    const key = this.modalRoleOptions.find((o) => o.value === role)?.labelKey;
    return key ? this.translate.instant(key) : role;
  }

  selectModalRole(value: string, labelKey: string): void {
    this.addUserForm.patchValue({ role: value as Role });
    this.modalRoleLabel.set(labelKey);
    this.showModalRoleDropdown.set(false);
  }

  closeSearch(): void {
    this.showSearch.set(false);
    this.searchQuery.set('');
    this.page.set(1);
    this.loadUsers();
  }

  onSearch(event: Event): void {
    this.searchSubject.next((event.target as HTMLInputElement).value);
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.loadUsers();
  }

  nextPage(): void {
    if (!this.hasNext()) return;
    this.page.update((p) => p + 1);
    this.loadUsers();
  }

  hasNext(): boolean {
    const u = this.users();
    if (!u) return false;
    return this.page() * PAGE_SIZE < u.total;
  }
}
