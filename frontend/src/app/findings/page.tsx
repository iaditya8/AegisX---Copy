'use client';

import React, { useState } from 'react';
import { AlertTriangle, Filter, Search } from 'lucide-react';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { FindingTable } from '../../components/findings/FindingTable';
import { useFindings } from '../../hooks/useFindings';
import { useScopeStore } from '../../stores/scope';

function FindingsContent() {
  const { selectedScopeId } = useScopeStore();
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [scannerFilter, setScannerFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Queries
  const { data: findingsRes, isLoading, error } = useFindings({
    scope_id: selectedScopeId || undefined,
    severity: severityFilter || undefined,
    scanner: scannerFilter || undefined,
  });

  const findings = findingsRes?.data || [];

  // Client-side local search match
  const filteredFindings = findings.filter((f) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      f.title.toLowerCase().includes(query) ||
      f.id.toLowerCase().includes(query) ||
      (f.description && f.description.toLowerCase().includes(query))
    );
  });

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
                <AlertTriangle className="h-5 w-5 text-indigo-500" />
                <h1 className="text-2xl font-bold text-white tracking-tight">Findings Log</h1>
              </div>
              <p className="text-zinc-400 text-xs leading-normal max-w-xl">
                Master database log for all identified security vulnerabilities, exposure triggers, and certificate anomalies.
              </p>
            </div>
          </div>

          {/* Filter Toolbar Card */}
          <div className="p-4 bg-zinc-950/40 rounded-xl border border-zinc-900 flex flex-wrap items-center gap-4 justify-between">
            <div className="flex flex-wrap items-center gap-3">
              {/* Severity filter */}
              <div className="flex items-center gap-2">
                <Filter className="h-3.5 w-3.5 text-zinc-500" />
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="bg-zinc-900 border border-zinc-800 focus:border-indigo-500 rounded-lg py-1 px-3 text-xs text-zinc-300 outline-none cursor-pointer"
                >
                  <option value="">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="info">Info</option>
                </select>
              </div>

              {/* Scanner filter */}
              <input
                type="text"
                placeholder="Filter by Scanner..."
                value={scannerFilter}
                onChange={(e) => setScannerFilter(e.target.value)}
                className="bg-zinc-900 border border-zinc-800 focus:border-indigo-500 rounded-lg py-1 px-3 text-xs text-zinc-300 outline-none w-40 placeholder-zinc-600"
              />
            </div>

            {/* General Search Input */}
            <div className="relative w-full md:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-600" />
              <input
                type="text"
                placeholder="Search Title, ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-zinc-900/40 border border-zinc-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-zinc-600 outline-none transition-all"
              />
            </div>
          </div>

          {/* Active Context Warn banner */}
          {!selectedScopeId && (
            <div className="p-3 bg-indigo-950/20 border border-indigo-900/30 rounded-lg text-indigo-400 text-xs font-mono text-center">
              Active context scope is not selected. Displaying platform-wide findings database log.
            </div>
          )}

          {/* Table Container */}
          {error ? (
            <div className="p-6 rounded-xl border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
              System request failed: {error.message || 'Could not fetch vulnerability logs'}
            </div>
          ) : (
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
              <FindingTable findings={filteredFindings} isLoading={isLoading} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function FindingsPage() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <FindingsContent />
    </RouteGuard>
  );
}
