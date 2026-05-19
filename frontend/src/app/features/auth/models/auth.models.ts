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
}

export interface ConfirmEmailResponse {
  message: string;
}
