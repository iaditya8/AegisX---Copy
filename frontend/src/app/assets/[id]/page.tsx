'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft, Server, Calendar, Hash } from 'lucide-react';
import { Sidebar } from '../../../components/navigation/Sidebar';
import { Topbar } from '../../../components/navigation/Topbar';
import { RouteGuard } from '../../../components/auth/RouteGuard';
import { AssetTabs } from '../../../components/assets/AssetTabs';
import { LoadingState } from '../../../components/shared/LoadingState';
import { ErrorState } from '../../../components/shared/ErrorState';
import { useAssetDetails, useAssetRelationships, useAssetHistory, useAssetReport } from '../../../hooks/useAssets';

interface PageProps {
  params: Promise<{ id: string }>;
}

function AssetDetailContent({ params }: PageProps) {
  const { id } = React.use(params);

  // Queries
  const { data: assetRes, isLoading: loadingAsset, error: assetErr } = useAssetDetails(id);
  const { data: relsRes, isLoading: loadingRels } = useAssetRelationships(id);
  const { data: historyRes, isLoading: loadingHistory } = useAssetHistory(id);
  const { data: reportRes, isLoading: loadingReport } = useAssetReport(id);

  const asset = assetRes?.data;
  const relationships = relsRes?.data || [];
  const history = historyRes?.data || [];
  const report = reportRes?.data || null;

  const isLoading = loadingAsset || loadingRels || loadingHistory || loadingReport;

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 flex items-center justify-center">
            <LoadingState message="Fetching asset intelligence..." />
          </div>
        </div>
      </div>
    );
  }

  if (assetErr || !asset) {
    return (
      <div className="flex h-screen w-screen bg-zinc-950 text-zinc-200">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Topbar />
          <div className="flex-1 p-6">
            <ErrorState message={assetErr?.message || 'Specified asset records not found on server.'} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Breadcrumb Navigation */}
          <div className="flex items-center gap-2">
            <Link
              href="/assets"
              className="flex items-center gap-1 text-xs font-semibold text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to Inventory
            </Link>
          </div>

          {/* Asset Summary Header Card */}
          <div className="p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="p-3.5 bg-indigo-600/10 border border-indigo-500/20 rounded-xl text-indigo-400">
                <Server className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h1 className="text-xl font-bold text-white tracking-tight">{asset.host || 'unknown-host'}</h1>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400 font-mono">
                  <span className="bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700/50 text-[10px] uppercase font-semibold text-zinc-300">
                    {asset.asset_type || 'host'}
                  </span>
                  <span>IP: {asset.ip || 'N/A'}</span>
                </div>
              </div>
            </div>

            {/* Quick stats on the right */}
            <div className="grid grid-cols-2 gap-4 text-xs font-mono text-zinc-500 bg-zinc-950/40 p-4 rounded-xl border border-zinc-900/60 min-w-[280px]">
              <div className="flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5 text-zinc-600" />
                <div>
                  <span className="text-[10px] text-zinc-600 block uppercase">First Evaluated</span>
                  <span className="text-zinc-400">
                    {asset.first_seen ? new Date(asset.first_seen).toLocaleDateString() : '-'}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <Hash className="h-3.5 w-3.5 text-zinc-600" />
                <div>
                  <span className="text-[10px] text-zinc-600 block uppercase">vulnerabilities</span>
                  <span className="text-red-400 font-bold">
                    {report?.findings?.length || 0} active
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Details & Tabs */}
          <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
            <AssetTabs
              asset={asset}
              relationships={relationships}
              history={history}
              report={report}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

export default function AssetDetailPage({ params }: PageProps) {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <AssetDetailContent params={params} />
    </RouteGuard>
  );
}
