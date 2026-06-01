export interface AuditLogEntry {
  id: string;
  created_at: string;
  action: string;
  details?: string;
  voting_id?: string;
  voting_title?: string;
  tx_hash?: string;
}

export interface AuditLogResponse {
  items: AuditLogEntry[];
  total: number;
  votes_cast: number;
  blockchain_records: number;
  page: number;
  page_size: number;
}

export interface VerifyChainResponse {
  status?: 'ok';
  broken_at?: number;
}
