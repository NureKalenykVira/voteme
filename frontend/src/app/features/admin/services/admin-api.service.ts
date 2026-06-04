import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  AdminElectionListResponse,
  AdminUserListResponse,
  AdminUserResponse,
  BackupResponse,
  CreateUserRequest,
  PatchUserRoleRequest,
  RestoreResponse,
  SettingsResponse,
  StatsResponse,
} from '../models/admin.models';

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/admin`;

  getUsers(params: {
    page: number;
    page_size: number;
    role?: string;
    search?: string;
  }): Observable<AdminUserListResponse> {
    const httpParams: Record<string, string> = {
      page: params.page.toString(),
      page_size: params.page_size.toString(),
    };
    if (params.role) httpParams['role'] = params.role;
    if (params.search) httpParams['search'] = params.search;
    return this.http.get<AdminUserListResponse>(`${this.apiUrl}/users`, { params: httpParams });
  }

  listElections(params: {
    page: number;
    page_size: number;
    status?: string;
    search?: string;
  }): Observable<AdminElectionListResponse> {
    const httpParams: Record<string, string> = {
      page: params.page.toString(),
      page_size: params.page_size.toString(),
    };
    if (params.status) httpParams['status'] = params.status;
    if (params.search) httpParams['search'] = params.search;
    return this.http.get<AdminElectionListResponse>(`${this.apiUrl}/elections`, {
      params: httpParams,
    });
  }

  createUser(payload: CreateUserRequest): Observable<AdminUserResponse> {
    return this.http.post<AdminUserResponse>(`${this.apiUrl}/users`, payload);
  }

  patchUserRole(id: string, payload: PatchUserRoleRequest): Observable<AdminUserResponse> {
    return this.http.patch<AdminUserResponse>(`${this.apiUrl}/users/${id}`, payload);
  }

  deleteUser(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/users/${id}`);
  }

  getStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.apiUrl}/stats`);
  }

  getSettings(): Observable<SettingsResponse> {
    return this.http.get<SettingsResponse>(`${this.apiUrl}/settings`);
  }

  updateSettings(payload: Partial<SettingsResponse>): Observable<SettingsResponse> {
    return this.http.post<SettingsResponse>(`${this.apiUrl}/settings`, payload);
  }

  createBackup(): Observable<BackupResponse> {
    return this.http.post<BackupResponse>(`${this.apiUrl}/backup`, {});
  }

  downloadBackup(): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/backup/latest`, { responseType: 'blob' });
  }

  getBackupInfo(): Observable<BackupResponse | null> {
    return this.http.get<BackupResponse | null>(`${this.apiUrl}/backup/info`);
  }

  restoreBackup(file: File): Observable<RestoreResponse> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<RestoreResponse>(`${this.apiUrl}/restore`, form);
  }

  forceDeleteElection(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/elections/${id}`);
  }
}
