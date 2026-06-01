import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  AddAuditorRequest,
  AddVoterRequest,
  AuditorListResponse,
  AuditorResponse,
  BallotOptionCreateRequest,
  BallotOptionResponse,
  BallotOptionUpdateRequest,
  CreateElectionRequest,
  CsvImportResult,
  ElectionListResponse,
  ElectionResponse,
  ElectionResultsResponse,
  MyVoteResponse,
  TimelineResponse,
  VoteSubmitRequest,
  VoteSubmitResponse,
  VoterListResponse,
  VoterReceiptResponse,
  VoterResponse,
  VotingDetailResponse,
  VotingJoinResponse,
} from '../models/elections.models';

@Injectable({ providedIn: 'root' })
export class ElectionsApiService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/elections`;

  create(payload: CreateElectionRequest): Observable<ElectionResponse> {
    return this.http.post<ElectionResponse>(this.apiUrl, payload);
  }

  createOption(
    electionId: string,
    payload: BallotOptionCreateRequest,
  ): Observable<BallotOptionResponse> {
    return this.http.post<BallotOptionResponse>(`${this.apiUrl}/${electionId}/options`, payload);
  }

  update(id: string, payload: Partial<CreateElectionRequest>): Observable<ElectionResponse> {
    return this.http.patch<ElectionResponse>(`${this.apiUrl}/${id}`, payload);
  }

  updateOption(
    electionId: string,
    optionId: string,
    payload: BallotOptionUpdateRequest,
  ): Observable<unknown> {
    return this.http.patch(`${this.apiUrl}/${electionId}/options/${optionId}`, payload);
  }

  uploadOptionPhoto(electionId: string, optionId: string, file: File): Observable<unknown> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post(`${this.apiUrl}/${electionId}/options/${optionId}/photo`, formData);
  }

  publish(electionId: string): Observable<unknown> {
    return this.http.post(`${this.apiUrl}/${electionId}/publish`, {});
  }

  getById(id: string): Observable<ElectionResponse> {
    return this.http.get<ElectionResponse>(`${this.apiUrl}/${id}`);
  }

  getDetail(id: string): Observable<VotingDetailResponse> {
    return this.http.get<VotingDetailResponse>(`${this.apiUrl}/${id}`);
  }

  getByCode(code: string): Observable<VotingJoinResponse> {
    return this.http.get<VotingJoinResponse>(`${this.apiUrl}/join/${code}`);
  }

  getVoters(electionId: string, page = 1, pageSize = 20): Observable<VoterListResponse> {
    return this.http.get<VoterListResponse>(`${this.apiUrl}/${electionId}/voters`, {
      params: { page: page.toString(), page_size: pageSize.toString() },
    });
  }

  addVoter(electionId: string, payload: AddVoterRequest): Observable<VoterResponse> {
    return this.http.post<VoterResponse>(`${this.apiUrl}/${electionId}/voters`, payload);
  }

  removeVoter(electionId: string, voterId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${electionId}/voters/${voterId}`);
  }

  getAuditors(electionId: string): Observable<AuditorListResponse> {
    return this.http.get<AuditorListResponse>(`${this.apiUrl}/${electionId}/auditors`);
  }

  addAuditor(electionId: string, payload: AddAuditorRequest): Observable<AuditorResponse> {
    return this.http.post<AuditorResponse>(`${this.apiUrl}/${electionId}/auditors`, payload);
  }

  removeAuditor(electionId: string, userId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${electionId}/auditors/${userId}`);
  }

  importVotersCsv(electionId: string, file: File): Observable<CsvImportResult> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<CsvImportResult>(`${this.apiUrl}/${electionId}/voters/csv`, formData);
  }

  listMy(page = 1, pageSize = 20, status?: string): Observable<ElectionListResponse> {
    const params: Record<string, string> = {
      page: page.toString(),
      page_size: pageSize.toString(),
    };
    if (status) params['status'] = status;
    return this.http.get<ElectionListResponse>(this.apiUrl, { params });
  }

  submitVote(electionId: string, payload: VoteSubmitRequest): Observable<VoteSubmitResponse> {
    return this.http.post<VoteSubmitResponse>(`${this.apiUrl}/${electionId}/vote`, payload);
  }

  getMyVote(electionId: string): Observable<MyVoteResponse> {
    return this.http.get<MyVoteResponse>(`${this.apiUrl}/${electionId}/my-vote`);
  }

  getResults(electionId: string): Observable<ElectionResultsResponse> {
    return this.http.get<ElectionResultsResponse>(`${this.apiUrl}/${electionId}/results`);
  }

  getTimeline(electionId: string): Observable<TimelineResponse> {
    return this.http.get<TimelineResponse>(`${this.apiUrl}/${electionId}/timeline`);
  }

  getReceipt(electionId: string): Observable<VoterReceiptResponse> {
    return this.http.get<VoterReceiptResponse>(`${this.apiUrl}/${electionId}/receipt`);
  }

  archiveVoting(id: string): Observable<ElectionResponse> {
    return this.http.post<ElectionResponse>(`${this.apiUrl}/${id}/archive`, {});
  }

  deleteVoting(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }
}
