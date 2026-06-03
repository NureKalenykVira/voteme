import { inject, Injectable, signal } from '@angular/core';
import { catchError, finalize, of } from 'rxjs';
import { AdminApiService } from './admin-api.service';
import {
  AdminUserListResponse,
  SettingsResponse,
  StatsResponse,
} from '../models/admin.models';

@Injectable({ providedIn: 'root' })
export class AdminStorageService {
  private readonly api = inject(AdminApiService);

  readonly users = signal<AdminUserListResponse | null>(null);
  readonly stats = signal<StatsResponse | null>(null);
  readonly settings = signal<SettingsResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  loadUsers(params: { page: number; page_size: number; role?: string; search?: string }): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .getUsers(params)
      .pipe(
        catchError(() => {
          this.error.set('Failed to load users');
          return of(null);
        }),
        finalize(() => this.loading.set(false)),
      )
      .subscribe((data) => {
        if (data) this.users.set(data);
      });
  }

  loadStats(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .getStats()
      .pipe(
        catchError(() => {
          this.error.set('Failed to load statistics');
          return of(null);
        }),
        finalize(() => this.loading.set(false)),
      )
      .subscribe((data) => {
        if (data) this.stats.set(data);
      });
  }

  loadSettings(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api
      .getSettings()
      .pipe(
        catchError(() => {
          this.error.set('Failed to load settings');
          return of(null);
        }),
        finalize(() => this.loading.set(false)),
      )
      .subscribe((data) => {
        if (data) this.settings.set(data);
      });
  }
}
