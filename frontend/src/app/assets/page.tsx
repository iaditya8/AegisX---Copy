'use client';

import React from 'react';
import { Terminal, ShieldAlert } from 'lucide-react';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { AssetTable } from '../../components/assets/AssetTable';
import { EmptyState } from '../../components/shared/EmptyState';
import { useScopeAssets } from '../../hooks/useScopes';
import { useScopeStore } from '../../stores/scope';

function AssetsContent() {
  const { selectedScopeId } = useScopeStore();

  const { data: assetsResponse, isLoading, error } = useScopeAssets(selectedScopeId || '');

  const assets = assetsResponse?.data || [];

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Header Panel */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Terminal className="h-5 w-5 text-indigo-500" />
                <h1 className="text-2xl font-bold text-white tracking-tight">Assets Inventory</h1>
              </div>
              <p className="text-zinc-400 text-xs leading-normal max-w-xl">
                Browse discovered ports, networks, hostnames, and services mapped to active scope targets.
              </p>
            </div>
          </div>

          {/* Core Content */}
          {!selectedScopeId ? (
            <div className="h-[50vh] flex items-center justify-center bg-zinc-950/20 rounded-xl border border-zinc-900 p-8 shadow-xl">
              <EmptyState
                title="No Active Scope Context Selected"
                description="Select a scope context from the header dropdown menu to inspect discovered targets."
                icon={<ShieldAlert className="h-10 w-10 text-indigo-500" />}
              />
            </div>
          ) : error ? (
            <div className="p-6 rounded-xl border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
              System request failed: {error.message || 'Could not fetch assets'}
            </div>
          ) : (
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
              <AssetTable assets={assets} isLoading={isLoading} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function AssetsPage() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <AssetsContent />
    </RouteGuard>
  );
}
