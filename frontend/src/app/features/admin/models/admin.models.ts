import { Role } from '../../auth/models/auth.models';

export interface AdminUserResponse {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  is_confirmed: boolean;
  is_deleted: boolean;
  created_at: string;
}

export interface AdminUserListResponse {
  items: AdminUserResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreateUserRequest {
  full_name?: string;
  email: string;
  role: Role;
  password: string;
}

export interface PatchUserRoleRequest {
  role: Role;
}

export interface SettingsResponse {
  max_free_votings_per_month: number;
  maintenance_mode: boolean;
  require_email_verification: boolean;
  session_timeout_minutes: number;
}

export interface StatsResponse {
  total_users: number;
  total_votings: number;
  votes_cast: number;
  active_votings: number;
  new_users_this_month: number;
  avg_participation_pct: number;
  votings_per_day: { date: string; count: number }[];
  votes_per_day: { date: string; count: number }[];
  users_by_role: { role: string; count: number }[];
  top_votings: { title: string; votes_count: number }[];
  blockchain_total: number;
  blockchain_confirmed: number;
  blockchain_failed: number;
  blockchain_published: number;
  blockchain_finalized: number;
  emails_total: number;
  emails_sent: number;
  emails_failed: number;
}

export interface BackupResponse {
  filename: string;
  created_at: string;
}

export interface RestoreResponse {
  users_imported: number;
  users_skipped: number;
  votings_imported: number;
  votings_skipped: number;
}

export interface AdminElectionResponse {
  id: string;
  title: string;
  status: string;
  created_by: string;
  organizer_email?: string;
  organizer_name?: string;
  start_date_time: string;
  end_date_time: string;
  votes_count?: number;
}

export interface AdminElectionListResponse {
  items: AdminElectionResponse[];
  total: number;
  page: number;
  page_size: number;
}
