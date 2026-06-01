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
  publish_tx_hash?: string;
  finalize_tx_hash?: string;
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
  can_vote?: boolean;
  publish_tx_hash?: string;
  finalize_tx_hash?: string;
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

export interface AddAuditorRequest {
  email: string;
}

export interface AuditorResponse {
  user_id: string;
  email: string;
}

export interface AuditorListResponse {
  items: AuditorResponse[];
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

export interface VoteSubmitRequest {
  option_id: string;
}

export interface VoteSubmitResponse {
  vote_id: string;
  commitment_hash: string;
  tx_status: 'pending' | 'confirmed' | 'failed';
  tx_hash?: string;
  submitted_at: string;
}

export interface MyVoteResponse {
  has_voted: boolean;
  option_id?: string;
  submitted_at?: string;
  commitment_hash?: string;
  tx_status?: 'pending' | 'confirmed' | 'failed';
  tx_hash?: string;
}

export interface OptionResultResponse {
  option_id: string;
  title: string;
  description?: string;
  photo_url?: string;
  votes_count: number;
  percentage: number;
}

export interface ElectionResultsResponse {
  voting_id: string;
  title: string;
  status: string;
  total_votes: number;
  voters_invited: number;
  already_voted: number;
  participation_pct: number;
  options: OptionResultResponse[];
  finalize_tx_hash?: string;
  is_organizer: boolean;
  start_date_time?: string;
  end_date_time?: string;
  organizer_name?: string;
}

export interface TimelineBucket {
  label: string;
  votes: number;
}

export interface TimelineResponse {
  buckets: TimelineBucket[];
  date_range: string;
}

export interface VoterReceiptResponse {
  commitment: string;
  nonce: string;
  voting_id: string;
  leaf_index: number;
  merkle_proof: string[];
  expected_root: string;
  etherscan_url?: string;
}
