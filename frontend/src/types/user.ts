export interface UserProfile {
  id: string;
  username: string;
  display_name?: string | null;
  email?: string | null;
  role: 'admin' | 'operator' | 'reader';
  created_at: string;
  last_login?: string | null;
  deleted_at?: string | null;
}
