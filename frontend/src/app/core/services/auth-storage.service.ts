import { computed, Injectable, signal } from '@angular/core';
import { Signal } from '@angular/core';
import { Role } from '../../features/auth/models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthStorageService {
  private readonly _token = signal<string | null>(localStorage.getItem('auth_token'));

  readonly isAuthenticated: Signal<boolean> = computed(() => this._token() !== null);

  getToken(): string | null {
    return this._token();
  }

  getRole(): Role | null {
    const token = this._token();
    if (!token) return null;
    try {
      const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      const payload = JSON.parse(atob(base64)) as { role?: string };
      return (payload.role as Role) ?? null;
    } catch {
      return null;
    }
  }

  setToken(token: string): void {
    localStorage.setItem('auth_token', token);
    this._token.set(token);
  }

  clearToken(): void {
    localStorage.removeItem('auth_token');
    this._token.set(null);
  }
}
