'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../stores/auth';
import { useScopeStore } from '../../stores/scope';
import { apiClient, logoutUser } from '../../services/api';
import { LogOut, User, Target, Sparkles } from 'lucide-react';
import { useCopilotStore } from '../../stores/copilot';
import { CopilotDrawer } from '../copilot/CopilotDrawer';

interface ScopeItem {
  id: string;
  name: string;
  type: string;
}

export function Topbar() {
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const { selectedScopeId, setSelectedScopeId } = useScopeStore();
  const { toggleOpen } = useCopilotStore();

  // Fetch all scopes the user has access to
  const { data: scopesResponse, isLoading } = useQuery<any>({
    queryKey: ['scopes', 'list'],
    queryFn: () => apiClient.get('/scopes'),
  });

  const scopes: ScopeItem[] = scopesResponse?.data || [];

  const handleLogout = () => {
    logoutUser(queryClient);
  };

  return (
    <header className="h-16 border-b border-zinc-900 bg-zinc-950/80 backdrop-blur-md px-6 flex items-center justify-between select-none">
      {/* Scope Selector dropdown */}
      <div className="flex items-center gap-3">
        <Target className="h-4 w-4 text-indigo-400" />
        <span className="text-sm font-semibold text-zinc-400">Context Scope:</span>
        <select
          value={selectedScopeId || ''}
          onChange={(e) => setSelectedScopeId(e.target.value || null)}
          className="bg-zinc-900 text-zinc-200 border border-zinc-800 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500 max-w-xs cursor-pointer transition-all duration-200"
          disabled={isLoading}
        >
          <option value="">-- Global / No Scope --</option>
          {scopes.map((scope) => (
            <option key={scope.id} value={scope.id}>
              {scope.name} ({scope.type})
            </option>
          ))}
        </select>
        {isLoading && (
          <span className="text-xs text-zinc-500 animate-pulse">Loading scopes...</span>
        )}
      </div>

      {/* User profile & controls */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3 border-r border-zinc-900 pr-6">
          <div className="h-8 w-8 rounded-full bg-zinc-900 flex items-center justify-center border border-zinc-800">
            <User className="h-4 w-4 text-zinc-400" />
          </div>
          <div className="text-left">
            <div className="text-sm font-medium text-zinc-200 leading-none">
              {user?.display_name || user?.username || 'Analyst'}
            </div>
            <div className="text-[10px] font-semibold text-indigo-400 mt-1 uppercase tracking-wide">
              {user?.role || 'Reader'}
            </div>
          </div>
        </div>

        {/* Copilot button */}
        <button
          onClick={toggleOpen}
          className="flex items-center gap-2 text-zinc-500 hover:text-indigo-400 text-sm font-medium transition-colors duration-200 cursor-pointer border-r border-zinc-900 pr-6"
          title="Ask Copilot"
        >
          <Sparkles className="h-4 w-4 text-indigo-400" />
          <span>Copilot</span>
        </button>

        {/* Logout button */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-zinc-500 hover:text-red-400 text-sm font-medium transition-colors duration-200 cursor-pointer"
          title="Sign Out"
        >
          <LogOut className="h-4 w-4" />
          <span>Sign Out</span>
        </button>
      </div>
      <CopilotDrawer />
    </header>
  );
}
