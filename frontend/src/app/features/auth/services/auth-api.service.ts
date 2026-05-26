import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  BecomeOrganizerResponse,
  ConfirmEmailResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
} from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthApiService {
  private readonly http = inject(HttpClient);

  register(req: RegisterRequest): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${environment.apiUrl}/auth/register`, req);
  }

  login(req: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiUrl}/auth/login`, req);
  }

  confirmEmail(token: string): Observable<ConfirmEmailResponse> {
    return this.http.get<ConfirmEmailResponse>(`${environment.apiUrl}/auth/confirm-email`, {
      params: { token },
    });
  }

  me(): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${environment.apiUrl}/auth/me`);
  }

  updateProfile(data: { full_name: string | null }): Observable<UserResponse> {
    return this.http.patch<UserResponse>(`${environment.apiUrl}/auth/me`, data);
  }

  uploadAvatar(file: File): Observable<UserResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<UserResponse>(`${environment.apiUrl}/auth/me/avatar`, formData);
  }

  deleteAccount(): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/auth/me`);
  }

  forgotPassword(email: string): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/auth/forgot-password`, { email });
  }

  resetPassword(token: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${environment.apiUrl}/auth/reset-password`, {
      token,
      new_password: newPassword,
    });
  }

  becomeOrganizer(): Observable<BecomeOrganizerResponse> {
    return this.http.post<BecomeOrganizerResponse>(
      `${environment.apiUrl}/auth/become-organizer`,
      {},
    );
  }
}
