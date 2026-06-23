import { create } from 'zustand';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: { id: string; username: string; display_name?: string; email?: string; role: 'admin' | 'operator' | 'reader' } | null;
  setTokens: (access: string | null, refresh: string | null) => void;
  setUser: (user: AuthState['user']) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: typeof window !== 'undefined' ? localStorage.getItem('access_token') : null,
  refreshToken: typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null,
  user: typeof window !== 'undefined' ? (() => {
    const raw = localStorage.getItem('user_profile');
    try {
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  })() : null,
  setTokens: (access, refresh) => {
    if (typeof window !== 'undefined') {
      if (access) localStorage.setItem('access_token', access);
      else localStorage.removeItem('access_token');

      if (refresh) localStorage.setItem('refresh_token', refresh);
      else localStorage.removeItem('refresh_token');
    }
    set({ accessToken: access, refreshToken: refresh });
  },
  setUser: (user) => {
    if (typeof window !== 'undefined') {
      if (user) localStorage.setItem('user_profile', JSON.stringify(user));
      else localStorage.removeItem('user_profile');
    }
    set({ user });
  },
  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user_profile');
    }
    set({ accessToken: null, refreshToken: null, user: null });
  },
}));
