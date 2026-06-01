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

    return this.http.get<AuditLogResponse>(this.apiUrl, { params: httpParams });
  }

  verifyChain(): Observable<VerifyChainResponse> {
    return this.http.get<VerifyChainResponse>(`${environment.apiUrl}/audit/verify-chain`);
  }
}
