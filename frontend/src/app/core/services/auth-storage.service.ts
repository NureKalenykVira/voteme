import { computed, Injectable, signal } from '@angular/core';
import { Signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AuthStorageService {
  private readonly _token = signal<string | null>(localStorage.getItem('auth_token'));

  readonly isAuthenticated: Signal<boolean> = computed(() => this._token() !== null);

  getToken(): string | null {
    return this._token();
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
