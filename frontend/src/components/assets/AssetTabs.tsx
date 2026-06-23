import React, { useState } from 'react';
import { Network, History, FileText, Database, ArrowRight } from 'lucide-react';
import { Asset, AssetRelationship, AssetHistory } from '../../types/asset';
import { AssetReport } from '../../types/report';
import { EmptyState } from '../shared/EmptyState';

interface AssetTabsProps {
  asset: Asset;
  relationships: AssetRelationship[];
  history: AssetHistory[];
  report: AssetReport | null;
}

export function AssetTabs({ asset, relationships, history, report }: AssetTabsProps) {
  const [activeTab, setActiveTab] = useState<'metadata' | 'relationships' | 'history' | 'report'>('metadata');

  const tabs = [
    { id: 'metadata', label: 'Telemetry Metadata', icon: <Database className="h-4 w-4" /> },
    { id: 'relationships', label: 'Asset Graph Relationships', icon: <Network className="h-4 w-4" /> },
    { id: 'history', label: 'Revision Audit Logs', icon: <History className="h-4 w-4" /> },
    { id: 'report', label: 'Vulnerability telemetry', icon: <FileText className="h-4 w-4" /> },
  ] as const;

  return (
    <div className="space-y-4">
      {/* Tabs list */}
      <div className="flex border-b border-zinc-900 bg-zinc-950/20 p-1 rounded-lg gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === tab.id
                ? 'bg-indigo-600/10 text-indigo-400 border border-indigo-500/20 shadow-sm'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Telemetry Metadata Tab */}
      {activeTab === 'metadata' && (
        <div className="bg-zinc-950/40 border border-zinc-900 p-6 rounded-xl space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Structured Metadata</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Asset scan metadata signatures.</p>
          </div>
          {Object.keys(asset.metadata_json || {}).length > 0 ? (
            <pre className="bg-zinc-900/60 border border-zinc-800/80 rounded-lg p-4 text-xs font-mono text-indigo-300 overflow-x-auto max-h-80 select-all">
              {JSON.stringify(asset.metadata_json, null, 2)}
            </pre>
          ) : (
            <EmptyState
              title="No Metadata Signatures"
              description="No additional properties or signatures were extracted for this asset during scans."
            />
          )}
        </div>
      )}

      {/* Asset Graph Relationships Tab */}
      {activeTab === 'relationships' && (
        <div className="bg-zinc-950/40 border border-zinc-900 p-6 rounded-xl space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Asset Relationships</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Structural graph connections.</p>
          </div>
          {relationships.length > 0 ? (
            <div className="space-y-3">
              {relationships.map((rel) => (
                <div
                  key={rel.id}
                  className="flex items-center justify-between p-3.5 bg-zinc-900/40 border border-zinc-850 hover:border-zinc-800 rounded-lg transition-colors text-xs font-mono text-zinc-300"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-zinc-500">Source:</span>
                    <span className="text-indigo-400 font-semibold truncate max-w-[150px]">
                      {rel.source_asset_id}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-zinc-600" />
                    <span className="text-zinc-500">Target:</span>
                    <span className="text-indigo-400 font-semibold truncate max-w-[150px]">
                      {rel.target_asset_id}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 uppercase text-[10px] font-semibold border border-zinc-700/50">
                      {rel.relationship_type}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No Graph Relationships"
              description="No dependency links or parent-child mappings exist for this asset in the graph database."
            />
          )}
        </div>
      )}

      {/* Revision Audit Logs Tab */}
      {activeTab === 'history' && (
        <div className="bg-zinc-950/40 border border-zinc-900 p-6 rounded-xl space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Revision Audit History</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Change tracking delta logs.</p>
          </div>
          {history.length > 0 ? (
            <div className="relative border-l border-zinc-900 pl-4 space-y-6">
              {history.map((log) => (
                <div key={log.id} className="relative space-y-1">
                  {/* Timeline point */}
                  <div className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-indigo-500 ring-4 ring-indigo-950" />
                  <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                    <span>{new Date(log.timestamp).toLocaleString()}</span>
                    <span>•</span>
                    <span className="text-indigo-400 uppercase font-semibold">{log.change_type}</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-zinc-900/30 border border-zinc-900/80 p-3 rounded-lg font-mono">
                    <div>
                      <span className="text-[10px] text-zinc-600 block mb-1">Old State</span>
                      <pre className="text-red-400 overflow-x-auto text-[11px]">
                        {JSON.stringify(log.old_value || 'None', null, 2)}
                      </pre>
                    </div>
                    <div>
                      <span className="text-[10px] text-zinc-600 block mb-1">New State</span>
                      <pre className="text-emerald-400 overflow-x-auto text-[11px]">
                        {JSON.stringify(log.new_value || 'None', null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No Revision Audits"
              description="This asset is currently at its initial revision. No state changes have been recorded."
            />
          )}
        </div>
      )}

      {/* Vulnerability Report Details Tab */}
      {activeTab === 'report' && (
        <div className="bg-zinc-950/40 border border-zinc-900 p-6 rounded-xl space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Active Vulnerabilities</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Discovered scan occurrences.</p>
          </div>
          {report && report.findings && report.findings.length > 0 ? (
            <div className="space-y-3">
              {report.findings.map((finding, idx) => (
                <div
                  key={finding.id || idx}
                  className="flex items-center justify-between p-3.5 bg-zinc-900/40 border border-zinc-850 hover:border-zinc-800 rounded-lg transition-colors"
                >
                  <div className="space-y-0.5 text-left">
                    <span className="text-xs font-semibold text-white tracking-tight block">
                      {finding.title}
                    </span>
                    <span className="text-[10px] text-zinc-500 font-mono">
                      Template: {finding.template_name || 'N/A'} • Status: {finding.status}
                    </span>
                  </div>
                  <span className="text-[10px] font-semibold text-red-400 uppercase font-mono px-2 py-0.5 rounded bg-red-950/20 border border-red-950/30">
                    {finding.severity}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="Clean Threat Intel"
              description="No active vulnerabilities or compliance findings are currently mapped to this asset."
            />
          )}
        </div>
      )}
    </div>
  );
}
