export interface CreateElectionRequest {
  title: string;
  description?: string;
  access_type: 'public' | 'private';
  is_anonymous: boolean;
  start_date_time: string;
  end_date_time: string;
}

export interface BallotOptionCreateRequest {
  title: string;
  description?: string;
}

export interface BallotOptionUpdateRequest {
  title?: string;
  description?: string;
  order_index?: number;
}

export interface ElectionResponse {
  id: string;
  title: string;
  description?: string;
  status: string;
  access_type: string;
  is_anonymous: boolean;
  start_date_time: string;
  end_date_time: string;
  invitation_code?: string;
  created_by?: string;
}

export interface BallotOptionResponse {
  id: string;
  voting_id: string;
  title: string;
  description?: string;
  photo_url?: string;
  order_index: number;
  created_at: string;
}

export interface VotingDetailResponse {
  id: string;
  title: string;
  description?: string;
  access_type: string;
  is_anonymous: boolean;
  invitation_code?: string;
  start_date_time: string;
  end_date_time: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  options: BallotOptionResponse[];
}

export interface VotingJoinResponse {
  id: string;
  title: string;
  description?: string;
  status: string;
  is_anonymous: boolean;
  start_date_time: string;
  end_date_time: string;
  created_by: string;
  created_by_name?: string;
  voters_invited: number;
  already_voted: number;
  participation_pct: number;
  options: BallotOptionResponse[];
  is_organizer: boolean;
  user_has_voted: boolean;
}

export interface VoterResponse {
  id: string;
  email: string;
  name?: string;
  status: 'invited' | 'voted';
}

export interface VoterListResponse {
  items: VoterResponse[];
  total: number;
  page: number;
  page_size: number;
  voters_invited: number;
  already_voted: number;
  participation_pct: number;
}

export interface AddVoterRequest {
  email: string;
}

export interface ElectionListResponse {
  items: ElectionResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface CsvImportInvalidRow {
  row: number;
  email: string;
  reason: string;
}

export interface CsvImportResult {
  total_rows: number;
  added_count: number;
  duplicate_count: number;
  invalid_count: number;
  invalid_rows: CsvImportInvalidRow[];
}
