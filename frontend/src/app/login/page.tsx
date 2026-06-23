'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '../../stores/auth';
import { apiClient } from '../../services/api';
import { Shield, Lock, User, AlertCircle } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      // Step 1: Request JWT tokens
      const tokenRes: any = await apiClient.post('/auth/token', {
        username,
        password,
      });

      const { access_token, refresh_token } = tokenRes.data;
      setTokens(access_token, refresh_token);

      // Step 2: Request user details to populate user object inside store
      const userRes: any = await apiClient.get('/users/me');
      setUser(userRes.data);

      // Step 3: Redirect to dashboard
      router.push('/');
    } catch (err: any) {
      setErrorMsg(err.message || 'Login failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex h-screen w-screen items-center justify-center bg-zinc-950 px-4 select-none">
      <div className="w-full max-w-md space-y-8 bg-zinc-900/40 p-8 rounded-xl border border-zinc-900 backdrop-blur-xl shadow-2xl">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="h-12 w-12 rounded-lg bg-indigo-600/10 flex items-center justify-center border border-indigo-500/20 shadow-lg shadow-indigo-600/5">
              <Shield className="h-6 w-6 text-indigo-500" />
            </div>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            AegisX Decision Platform
          </h2>
          <p className="text-sm text-zinc-400">
            Sign in with credentials to manage exposure decisions
          </p>
        </div>

        {errorMsg && (
          <div className="flex items-center gap-2 p-3 bg-red-950/20 border border-red-500/20 rounded-lg text-red-400 text-xs leading-normal">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-2">
                Username
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-zinc-500">
                  <User className="h-4 w-4" />
                </span>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-zinc-950 text-zinc-200 border border-zinc-800 rounded-lg pl-10 pr-3 py-2 text-sm placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="analyst_username"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-400 mb-2">
                Password
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-zinc-500">
                  <Lock className="h-4 w-4" />
                </span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-zinc-950 text-zinc-200 border border-zinc-800 rounded-lg pl-10 pr-3 py-2 text-sm placeholder-zinc-600 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="••••••••"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition-all duration-200 shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                <span>Signing in...</span>
              </>
            ) : (
              <span>Sign In</span>
            )}
          </button>
        </form>
      </div>
    </main>
  );
}
