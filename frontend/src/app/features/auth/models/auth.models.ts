export type Role = 'global_admin' | 'organizer' | 'voter' | 'auditor';

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string | null;
  role: Role;
  is_confirmed: boolean;
  created_at: string;
  avatar_url?: string | null;
  is_election_auditor?: boolean;
  votes_cast_count?: number;
}

export interface ConfirmEmailResponse {
  message: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface BecomeOrganizerResponse {
  access_token: string;
  token_type: string;
}
