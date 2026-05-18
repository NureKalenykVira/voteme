import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
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
}
