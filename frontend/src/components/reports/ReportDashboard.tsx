import React, { useState } from 'react';
import { Download, FileJson, FileSpreadsheet, Layers, ShieldAlert, AlertTriangle, Monitor, Network } from 'lucide-react';
import { DashboardSummary, DashboardTrends, ExposureReport } from '../../types/report';
import { reportService } from '../../services/reports';
import { downloadBlob } from '../../lib/download';
import { StatusBadge } from '../shared/StatusBadge';

interface ReportDashboardProps {
  summary: DashboardSummary;
  trends: DashboardTrends | null;
  exposure: ExposureReport | null;
}

export function ReportDashboard({ summary, trends, exposure }: ReportDashboardProps) {
  const [isExporting, setIsExporting] = useState<string | null>(null);

  const handleExport = async (format: 'json' | 'csv') => {
    setIsExporting(format);
    try {
      const blob =
        format === 'json'
          ? await reportService.exportExecutiveReportJson()
          : await reportService.exportExecutiveReportCsv();
      downloadBlob(blob, `executive_report_${new Date().toISOString().split('T')[0]}.${format}`);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Failed to generate report export. Please check platform health.');
    } finally {
      setIsExporting(null);
    }
  };

  // Severity metrics mappings
  const severities = [
    { label: 'Critical', count: summary.findings.critical, color: 'bg-red-500', text: 'text-red-400' },
    { label: 'High', count: summary.findings.high, color: 'bg-orange-500', text: 'text-orange-400' },
    { label: 'Medium', count: summary.findings.medium, color: 'bg-amber-500', text: 'text-amber-400' },
    { label: 'Low', count: summary.findings.low, color: 'bg-emerald-500', text: 'text-emerald-400' },
    { label: 'Info', count: summary.findings.info, color: 'bg-blue-500', text: 'text-blue-400' },
  ];

  const totalFindings =
    summary.findings.critical +
    summary.findings.high +
    summary.findings.medium +
    summary.findings.low +
    summary.findings.info;

  return (
    <div className="space-y-6">
      {/* Platform Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Total Assets */}
        <div className="bg-zinc-950/40 p-5 rounded-xl border border-zinc-900 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Total Assets</span>
            <h3 className="text-2xl font-bold text-white tracking-tight mt-1">{summary.asset_count}</h3>
          </div>
          <div className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800 text-indigo-400">
            <Layers className="h-5 w-5" />
          </div>
        </div>

        {/* Exposed Assets */}
        <div className="bg-zinc-950/40 p-5 rounded-xl border border-zinc-900 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Exposed Interfaces</span>
            <h3 className="text-2xl font-bold text-white tracking-tight mt-1">{summary.internet_exposed_assets}</h3>
          </div>
          <div className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800 text-red-400">
            <Network className="h-5 w-5 animate-pulse" />
          </div>
        </div>

        {/* Ports */}
        <div className="bg-zinc-950/40 p-5 rounded-xl border border-zinc-900 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Open Ports</span>
            <h3 className="text-2xl font-bold text-white tracking-tight mt-1">{summary.open_ports}</h3>
          </div>
          <div className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800 text-amber-400">
            <Monitor className="h-5 w-5" />
          </div>
        </div>

        {/* Total Vulnerabilities */}
        <div className="bg-zinc-950/40 p-5 rounded-xl border border-zinc-900 flex items-center justify-between">
          <div>
            <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Vulnerabilities</span>
            <h3 className="text-2xl font-bold text-white tracking-tight mt-1">{totalFindings}</h3>
          </div>
          <div className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800 text-red-500">
            <ShieldAlert className="h-5 w-5" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Severity distribution bar */}
        <div className="bg-zinc-950/40 p-6 rounded-xl border border-zinc-900 md:col-span-2 space-y-6">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Vulnerability severity Distribution</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Distribution of security posture findings.</p>
          </div>

          <div className="space-y-4">
            {severities.map((sev) => {
              const percentage = totalFindings > 0 ? (sev.count / totalFindings) * 105 : 0;
              return (
                <div key={sev.label} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-zinc-300">{sev.label}</span>
                    <span className={`font-mono font-bold ${sev.text}`}>{sev.count}</span>
                  </div>
                  <div className="h-2 w-full bg-zinc-900 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${sev.color} rounded-full transition-all duration-500`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Exporter Card */}
        <div className="bg-zinc-950/40 p-6 rounded-xl border border-zinc-900 flex flex-col justify-between">
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-white tracking-tight">Platform Exports</h4>
            <p className="text-xs text-zinc-500 leading-relaxed">
              Export verified platform metrics and discovered vulnerabilities data payloads.
            </p>
          </div>

          <div className="space-y-3 mt-6">
            <button
              onClick={() => handleExport('json')}
              disabled={isExporting !== null}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-xs font-semibold text-zinc-300 hover:text-white transition-all cursor-pointer disabled:opacity-40"
            >
              <FileJson className="h-4 w-4" />
              {isExporting === 'json' ? 'Generating JSON...' : 'Export Platform JSON'}
            </button>
            <button
              onClick={() => handleExport('csv')}
              disabled={isExporting !== null}
              className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-xs font-semibold text-zinc-300 hover:text-white transition-all cursor-pointer disabled:opacity-40"
            >
              <FileSpreadsheet className="h-4 w-4" />
              {isExporting === 'csv' ? 'Generating CSV...' : 'Export Platform CSV'}
            </button>
          </div>
        </div>
      </div>

      {/* Network Exposure Breakdown */}
      {exposure && (
        <div className="bg-zinc-950/40 p-6 rounded-xl border border-zinc-900 space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-white tracking-tight">Internet Exposure Breakdown</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Asset structural layout categorization.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-zinc-900/20 p-4 rounded-lg border border-zinc-900">
              <span className="text-[10px] text-zinc-500 uppercase block font-semibold">External assets</span>
              <span className="text-lg font-bold text-white font-mono mt-1 block">
                {exposure.external_assets?.length || 0}
              </span>
            </div>
            <div className="bg-zinc-900/20 p-4 rounded-lg border border-zinc-900">
              <span className="text-[10px] text-zinc-500 uppercase block font-semibold">Internal interfaces</span>
              <span className="text-lg font-bold text-white font-mono mt-1 block">
                {exposure.internal_assets?.length || 0}
              </span>
            </div>
            <div className="bg-zinc-900/20 p-4 rounded-lg border border-zinc-900">
              <span className="text-[10px] text-zinc-500 uppercase block font-semibold">Internet Exposed Count</span>
              <span className="text-lg font-bold text-red-400 font-mono mt-1 block">
                {exposure.internet_exposed_count || 0}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
