import React from 'react';
import Link from 'next/link';
import { ArrowRight, Globe, Server } from 'lucide-react';
import { Asset } from '../../types/asset';
import { DataTable, Column } from '../shared/DataTable';

interface AssetTableProps {
  assets: Asset[];
  isLoading: boolean;
}

export function AssetTable({ assets, isLoading }: AssetTableProps) {
  const columns: Column<Asset>[] = [
    {
      key: 'host',
      label: 'Hostname',
      sortable: true,
      render: (asset) => (
        <div className="flex items-center gap-2">
          {asset.asset_type === 'domain' ? (
            <Globe className="h-4 w-4 text-indigo-400" />
          ) : (
            <Server className="h-4 w-4 text-emerald-400" />
          )}
          <span className="font-semibold text-white">{asset.host || 'unknown'}</span>
        </div>
      ),
    },
    {
      key: 'ip',
      label: 'IP Interface',
      sortable: true,
      render: (asset) => <span className="font-mono text-xs">{asset.ip || '-'}</span>,
    },
    {
      key: 'asset_type',
      label: 'Type',
      sortable: true,
      render: (asset) => (
        <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
          {asset.asset_type || 'host'}
        </span>
      ),
    },
    {
      key: 'fingerprint',
      label: 'Signature Fingerprint',
      render: (asset) => (
        <span className="text-xs font-mono text-zinc-500 truncate max-w-xs block">
          {asset.fingerprint || 'No fingerprint signature'}
        </span>
      ),
    },
    {
      key: 'last_seen',
      label: 'Last Evaluated',
      sortable: true,
      render: (asset) => (
        <span className="text-xs font-mono text-zinc-500">
          {asset.last_seen ? new Date(asset.last_seen).toLocaleString() : '-'}
        </span>
      ),
    },
    {
      key: 'details',
      label: 'Details',
      render: (asset) => (
        <Link
          href={`/assets/${asset.id}`}
          className="flex items-center justify-center h-8 w-8 rounded-lg border border-zinc-850 bg-zinc-950 hover:bg-indigo-600/10 hover:text-indigo-400 transition-all cursor-pointer group"
        >
          <ArrowRight className="h-3.5 w-3.5 text-zinc-500 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-transform" />
        </Link>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={assets}
      isLoading={isLoading}
      emptyMessage="No discovered assets in this scope context."
    />
  );
}
