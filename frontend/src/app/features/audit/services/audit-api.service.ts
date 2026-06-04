import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuditLogResponse, VerifyChainResponse } from '../models/audit.models';

@Injectable({ providedIn: 'root' })
export class AuditApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/audit/log`;

  getLog(params: {
    page: number;
    page_size: number;
    action?: string;
    search?: string;
    voting_id?: string;
  }): Observable<AuditLogResponse> {
    let httpParams = new HttpParams()
      .set('page', params.page.toString())
      .set('page_size', params.page_size.toString());

    if (params.action) {
      httpParams = httpParams.set('action', params.action);
    }
    if (params.search) {
      httpParams = httpParams.set('search', params.search);
    }
    if (params.voting_id) {
      httpParams = httpParams.set('voting_id', params.voting_id);
    }

    return this.http.get<AuditLogResponse>(this.apiUrl, { params: httpParams });
  }

  verifyChain(): Observable<VerifyChainResponse> {
    return this.http.get<VerifyChainResponse>(`${environment.apiUrl}/audit/verify-chain`);
  }
}
