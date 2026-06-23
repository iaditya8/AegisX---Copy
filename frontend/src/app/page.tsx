'use client';

import { useQuery } from '@tanstack/react-query';
import { useScopeStore } from '../stores/scope';
import { useAuthStore } from '../stores/auth';
import { apiClient } from '../services/api';
import { RouteGuard } from '../components/auth/RouteGuard';
import { Sidebar } from '../components/navigation/Sidebar';
import { Topbar } from '../components/navigation/Topbar';
import { Target, Server, ShieldCheck, ArrowRight } from 'lucide-react';
import Link from 'next/link';

function DashboardContent() {
  const { user } = useAuthStore();
  const { selectedScopeId } = useScopeStore();

  // Query details of the selected scope
  const { data: scopeDetailsResponse, isLoading: isLoadingScope } = useQuery<any>({
    queryKey: ['scopes', 'detail', selectedScopeId],
    queryFn: () => apiClient.get(`/scopes/${selectedScopeId}`),
    enabled: !!selectedScopeId,
  });

  const activeScope = scopeDetailsResponse?.data || null;

  // Query assets list inside the selected scope
  const { data: assetsResponse, isLoading: isLoadingAssets } = useQuery<any>({
    queryKey: ['assets', 'list', { scopeId: selectedScopeId }],
    queryFn: () => apiClient.get(`/scopes/${selectedScopeId}/assets`),
    enabled: !!selectedScopeId,
  });

  const assetsCount = assetsResponse?.data?.length || 0;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      {/* Sidebar navigation */}
      <Sidebar />

      {/* Main layout container */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar navigation context */}
        <Topbar />

        {/* Dashboard inner content */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Welcome Banner */}
          <div className="bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 p-6 rounded-xl border border-zinc-900 shadow-xl">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Welcome back, {user?.display_name || user?.username || 'Analyst'}
            </h1>
            <p className="text-zinc-400 text-sm mt-1">
              Exposure Decision Support Platform is active. Set a scope context to evaluate vulnerability telemetry.
            </p>
          </div>

          {/* Context Snapshot Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Active Scope Card */}
            <div className="bg-zinc-900/40 p-6 rounded-xl border border-zinc-900 flex flex-col justify-between h-40">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Active Context Scope
                </span>
                <Target className="h-5 w-5 text-indigo-500" />
              </div>
              <div className="mt-2">
                {isLoadingScope ? (
                  <div className="h-6 w-32 bg-zinc-800 animate-pulse rounded"></div>
                ) : activeScope ? (
                  <div>
                    <h3 className="text-lg font-bold text-white leading-tight">
                      {activeScope.name}
                    </h3>
                    <span className="text-xs text-indigo-400 mt-1 inline-block uppercase font-mono bg-indigo-500/10 px-2 py-0.5 rounded">
                      {activeScope.type}
                    </span>
                  </div>
                ) : (
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-500">
                      No Scope Selected
                    </h3>
                    <p className="text-xs text-zinc-600 mt-1">
                      Select a scope in the header dropdown to view assets count.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Total Discoveries Card */}
            <div className="bg-zinc-900/40 p-6 rounded-xl border border-zinc-900 flex flex-col justify-between h-40">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Discovered Assets
                </span>
                <Server className="h-5 w-5 text-indigo-500" />
              </div>
              <div className="mt-2">
                {isLoadingAssets ? (
                  <div className="h-8 w-16 bg-zinc-800 animate-pulse rounded"></div>
                ) : (
                  <div>
                    <h2 className="text-3xl font-extrabold text-white tracking-tight">
                      {selectedScopeId ? assetsCount : 0}
                    </h2>
                    <p className="text-xs text-zinc-500 mt-1">
                      {selectedScopeId ? 'Assets linked to selected scope' : 'Please select an active scope'}
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Security Posture Status */}
            <div className="bg-zinc-900/40 p-6 rounded-xl border border-zinc-900 flex flex-col justify-between h-40">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                  Decision Engine status
                </span>
                <ShieldCheck className="h-5 w-5 text-indigo-500 animate-pulse" />
              </div>
              <div className="mt-2">
                <h3 className="text-base font-bold text-emerald-400 flex items-center gap-1.5 leading-none">
                  ONLINE / READ-ONLY
                </h3>
                <p className="text-xs text-zinc-500 mt-2">
                  System components verified. Operations analytical scorecards are currently disabled.
                </p>
              </div>
            </div>
          </div>

          {/* Quick Shortcuts Section */}
          <div className="bg-zinc-900/20 p-6 rounded-xl border border-zinc-900">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">
              Platform Actions
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Link
                href="/scopes"
                className="group flex items-center justify-between p-4 bg-zinc-900/50 hover:bg-indigo-600/10 border border-zinc-800 rounded-lg transition-all duration-200"
              >
                <div className="text-left">
                  <h4 className="text-sm font-semibold text-white group-hover:text-indigo-400">
                    Onboard & Configure Scopes
                  </h4>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Define target domains, schedules, and scanner plugins.
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-zinc-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
              </Link>

              <Link
                href="/assets"
                className="group flex items-center justify-between p-4 bg-zinc-900/50 hover:bg-indigo-600/10 border border-zinc-800 rounded-lg transition-all duration-200"
              >
                <div className="text-left">
                  <h4 className="text-sm font-semibold text-white group-hover:text-indigo-400">
                    Explore Assets Directory
                  </h4>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    View active hostnames, IP interfaces, and normalized services.
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-zinc-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
              </Link>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Dashboard() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <DashboardContent />
    </RouteGuard>
  );
}
