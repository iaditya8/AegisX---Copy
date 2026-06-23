import React from 'react';
import Link from 'next/link';
import { ArrowRight, AlertTriangle } from 'lucide-react';
import { Finding } from '../../types/finding';
import { DataTable, Column } from '../shared/DataTable';
import { StatusBadge } from '../shared/StatusBadge';

interface FindingTableProps {
  findings: Finding[];
  isLoading: boolean;
}

export function FindingTable({ findings, isLoading }: FindingTableProps) {
  const columns: Column<Finding>[] = [
    {
      key: 'severity',
      label: 'Severity',
      sortable: true,
      render: (finding) => <StatusBadge value={finding.severity} />,
    },
    {
      key: 'title',
      label: 'Vulnerability Title',
      sortable: true,
      render: (finding) => (
        <div className="flex flex-col text-left">
          <span className="font-semibold text-white tracking-tight">{finding.title}</span>
          <span className="text-[10px] text-zinc-500 font-mono truncate max-w-xs md:max-w-md">
            ID: {finding.id}
          </span>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (finding) => (
        <span className={`text-[10px] font-mono px-2 py-0.5 rounded border uppercase font-semibold ${
          finding.status === 'open'
            ? 'bg-red-500/10 border-red-500/20 text-red-400'
            : finding.status === 'acknowledged'
            ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
            : finding.status === 'resolved'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            : 'bg-zinc-800 border-zinc-800 text-zinc-400'
        }`}>
          {finding.status}
        </span>
      ),
    },
    {
      key: 'source_plugin',
      label: 'Scanner Engine',
      sortable: true,
      render: (finding) => (
        <span className="text-xs font-mono text-zinc-400 bg-zinc-900 border border-zinc-800/80 px-2 py-0.5 rounded">
          {finding.source_plugin || 'system'}
        </span>
      ),
    },
    {
      key: 'last_seen',
      label: 'Last Seen',
      sortable: true,
      render: (finding) => (
        <span className="text-xs font-mono text-zinc-500">
          {finding.last_seen ? new Date(finding.last_seen).toLocaleString() : '-'}
        </span>
      ),
    },
    {
      key: 'details',
      label: 'Details',
      render: (finding) => (
        <Link
          href={`/findings/${finding.id}`}
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
      data={findings}
      isLoading={isLoading}
      emptyMessage="No vulnerability findings identified in this active scope."
    />
  );
}
