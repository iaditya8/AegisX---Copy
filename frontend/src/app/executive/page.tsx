'use client';

import React, { useState } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { useScopeStore } from '../../stores/scope';
import { 
  useExecutiveReports, 
  useExecutiveScorecard, 
  useExecutiveHeatmap, 
  useCreateExecutiveReport, 
  useTransitionReportStatus 
} from '../../hooks/useExecutive';
import { 
  usePostureSummary, 
  useSecurityPostures, 
  useCheckPostureDrift, 
  useUpdatePostureStatus 
} from '../../hooks/usePosture';
import { 
  TrendingUp, 
  Grid3X3, 
  FileText, 
  AlertOctagon, 
  ShieldCheck, 
  Plus, 
  RefreshCw,
  Award,
  AlertTriangle
} from 'lucide-react';

function ExecutiveContent() {
  const { selectedScopeId } = useScopeStore();
  const scopeId = selectedScopeId || undefined;

  // Executive Queries
  const { data: reports = [], isLoading: isLoadingReports } = useExecutiveReports();
  const { data: scorecard = null, isLoading: isLoadingScorecard } = useExecutiveScorecard(scopeId);
  const { data: heatmap = null, isLoading: isLoadingHeatmap } = useExecutiveHeatmap(scopeId);

  // Posture Queries
  const { data: postureSummary = null, isLoading: isLoadingPostureSummary } = usePostureSummary(scopeId);
  const { data: postures = [], isLoading: isLoadingPostures } = useSecurityPostures();

  // Mutations
  const createReportMutation = useCreateExecutiveReport();
  const transitionReportMutation = useTransitionReportStatus();
  const checkDriftMutation = useCheckPostureDrift();
  const updatePostureStatusMutation = useUpdatePostureStatus();

  // Local Form state
  const [reportTitle, setReportTitle] = useState('');
  const [reportDescription, setReportDescription] = useState('');
  const [reportPeriod, setReportPeriod] = useState('Monthly');
  const [reportType, setReportType] = useState('Executive Posture');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleCreateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportTitle.trim()) return;

    try {
      await createReportMutation.mutateAsync({
        title: reportTitle.trim(),
        description: reportDescription.trim(),
        period: reportPeriod,
        type: reportType,
        scopeId,
      });
      setSuccessMessage(`Executive CISO Report "${reportTitle}" successfully generated.`);
      setReportTitle('');
      setReportDescription('');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleTransitionReport = async (id: string, status: 'published' | 'archived') => {
    try {
      await transitionReportMutation.mutateAsync({ id, status });
      setSuccessMessage(`Report status updated to ${status.toUpperCase()}.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleCheckDrift = async () => {
    try {
      await checkDriftMutation.mutateAsync(scopeId);
      setSuccessMessage("Posture drift analysis completed. Risk indexes recalculated.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdatePosture = async (id: string, action: 'accept' | 'mitigate') => {
    try {
      await updatePostureStatusMutation.mutateAsync({ id, action });
      setSuccessMessage(`Posture finding risk updated successfully.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  // Generate 5x5 Heatmap Matrix cells
  const heatmapCells = [];
  for (let impact = 5; impact >= 1; impact--) {
    for (let likelihood = 1; likelihood <= 5; likelihood++) {
      const coord = heatmap?.coordinates?.find(
        (c) => c.likelihood === likelihood && c.impact === impact
      );
      heatmapCells.push({ likelihood, impact, coord });
    }
  }

  const getHeatmapBg = (likelihood: number, impact: number) => {
    const sum = likelihood + impact;
    if (sum >= 8) return 'bg-red-500/10 border-red-500/20';
    if (sum >= 6) return 'bg-amber-500/10 border-amber-500/20';
    return 'bg-emerald-500/10 border-emerald-500/20';
  };

  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case 'critical': return 'text-red-400 bg-red-950/20 border border-red-900';
      case 'high': return 'text-orange-400 bg-orange-950/20 border border-orange-900';
      case 'medium': return 'text-amber-400 bg-amber-950/20 border border-amber-900';
      default: return 'text-zinc-400 bg-zinc-900 border border-zinc-800';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'published': return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
      case 'archived': return 'bg-zinc-700/15 border-zinc-700/30 text-zinc-400';
      default: return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Header Banner */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <TrendingUp className="w-6 h-6 text-indigo-500" />
                CISO Executive Posture Dashboard & Reports
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Analyze organizational security health scorecard metrics, evaluate threat posture drift, and publish executive CISO report cards.
              </p>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-indigo-950/30 border border-indigo-800 text-indigo-400 text-xs px-4 py-3 rounded-lg animate-fade-in shrink-0">
              <ShieldCheck className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Main Content Layout */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Executive Scorecard & Heatmap (30%) */}
            <div className="col-span-4 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Award className="w-4 h-4 text-indigo-500" />
                  Executive Scorecard & Heatmap
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Letter Grade Scorecard Card */}
                {isLoadingScorecard ? (
                  <div className="text-zinc-500 text-xs animate-pulse">Calculating scorecard...</div>
                ) : scorecard ? (
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 flex items-center gap-5">
                    <div className="w-16 h-16 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center font-mono text-3xl font-extrabold text-indigo-400 shadow-inner">
                      {scorecard.grade}
                    </div>
                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Security Posture Grade</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-white">Score Index: {scorecard.risk_score}/100</span>
                      </div>
                      <span className="text-[9px] text-zinc-500 block">
                        {scorecard.critical_findings_count} Critical, {scorecard.high_findings_count} High active exposures.
                      </span>
                    </div>
                  </div>
                ) : null}

                {/* 5x5 Heatmap Matrix */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Cyber Risk Threat Matrix (5x5):</span>
                    <span className="text-[8px] font-mono text-zinc-650">Y: Impact | X: Likelihood</span>
                  </div>

                  {isLoadingHeatmap ? (
                    <div className="text-zinc-500 text-xs animate-pulse">Calculating coordinates...</div>
                  ) : (
                    <div className="grid grid-cols-5 gap-1.5 aspect-square max-w-[260px] mx-auto bg-zinc-950/20 p-2 rounded-xl border border-zinc-900">
                      {heatmapCells.map((cell, idx) => (
                        <div 
                          key={idx}
                          className={`aspect-square rounded border flex items-center justify-center relative transition-all ${getHeatmapBg(cell.likelihood, cell.impact)}`}
                        >
                          <span className="text-[8px] font-mono text-zinc-700 absolute bottom-0.5 right-1">
                            {cell.likelihood},{cell.impact}
                          </span>
                          {cell.coord && cell.coord.count > 0 && (
                            <div className="w-5 h-5 rounded-full bg-indigo-500 text-white font-mono text-[9px] font-bold flex items-center justify-center animate-pulse">
                              {cell.coord.count}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Center Panel: Posture Drift Findings (45%) */}
            <div className="col-span-5 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Grid3X3 className="w-4 h-4 text-indigo-400" />
                  Threat Posture Drift findings
                </h2>
                <button
                  onClick={handleCheckDrift}
                  disabled={checkDriftMutation.isPending}
                  className="bg-zinc-900 hover:bg-zinc-850 text-indigo-400 border border-zinc-800 text-[10px] font-semibold py-1 px-2.5 rounded transition-all cursor-pointer flex items-center gap-1 shrink-0"
                >
                  <RefreshCw className={`w-3 h-3 ${checkDriftMutation.isPending ? 'animate-spin' : ''}`} />
                  Run Drift Check
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
                {/* Drift snapshot delta block */}
                {postureSummary && (
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 grid grid-cols-2 gap-4 shrink-0">
                    <div className="space-y-1">
                      <span className="text-[9px] text-zinc-550 font-bold uppercase tracking-wider block">Posture Findings Count</span>
                      <div className="text-base font-bold text-white">{postureSummary.open_count} Open Issues</div>
                    </div>
                    {postureSummary.drift_index !== undefined && (
                      <div className="space-y-1">
                        <span className="text-[9px] text-zinc-550 font-bold uppercase tracking-wider block">Threat Drift Index</span>
                        <div className="text-base font-bold text-indigo-400 font-mono">
                          {postureSummary.drift_index > 0 ? `+${postureSummary.drift_index}%` : `${postureSummary.drift_index}%`}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Postures list */}
                <div className="space-y-3 flex-1 flex flex-col">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Active Posture Violations:</span>
                  <div className="flex-1 overflow-y-auto space-y-3 max-h-[300px]">
                    {isLoadingPostures ? (
                      <div className="text-zinc-500 text-xs animate-pulse">Loading posture records...</div>
                    ) : postures.length === 0 ? (
                      <div className="text-zinc-550 text-[10px] italic text-center py-8">No active security postures.</div>
                    ) : (
                      postures.map((p) => (
                        <div 
                          key={p.id}
                          className="p-4 rounded-xl border border-zinc-900 bg-zinc-950/40 space-y-3"
                        >
                          <div className="flex justify-between items-start">
                            <div className="space-y-0.5">
                              <span className="text-[9px] font-mono font-bold text-zinc-500 uppercase tracking-wider block">
                                {p.category} | Source: {p.risk_source}
                              </span>
                              <h3 className="text-xs font-bold text-white leading-snug">{p.title}</h3>
                            </div>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded capitalize ${getSeverityColor(p.severity)}`}>
                              {p.severity}
                            </span>
                          </div>

                          <p className="text-[10px] text-zinc-400 leading-relaxed font-mono">
                            {p.description}
                          </p>

                          {p.status === 'open' && (
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleUpdatePosture(p.id, 'accept')}
                                className="bg-zinc-900 hover:bg-zinc-850 text-[10px] text-amber-500 font-bold border border-zinc-800 py-1 px-3 rounded cursor-pointer transition-all"
                              >
                                Accept Risk
                              </button>
                              <button
                                onClick={() => handleUpdatePosture(p.id, 'mitigate')}
                                className="bg-zinc-900 hover:bg-zinc-850 text-[10px] text-indigo-400 font-bold border border-zinc-800 py-1 px-3 rounded cursor-pointer transition-all"
                              >
                                Mitigate Risk
                              </button>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Right Panel: Executive CISO reports & Generator (25%) */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-indigo-400" />
                  CISO Posture Reports
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col space-y-4">
                {/* Generation form */}
                <form onSubmit={handleCreateReport} className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-4 space-y-3 shrink-0">
                  <div className="flex items-center gap-1 text-indigo-400">
                    <Plus className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase tracking-wider">Generate Executive Report</span>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="report-title-input" className="text-[10px] text-zinc-500 block">Report Title:</label>
                    <input
                      id="report-title-input"
                      type="text"
                      placeholder="e.g. Q2 2026 Security Posture Review"
                      value={reportTitle}
                      onChange={(e) => setReportTitle(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="report-desc-input" className="text-[10px] text-zinc-500 block">Description Summary:</label>
                    <textarea
                      id="report-desc-input"
                      placeholder="Summary notes..."
                      value={reportDescription}
                      onChange={(e) => setReportDescription(e.target.value)}
                      rows={2}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors resize-none"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={createReportMutation.isPending || !reportTitle.trim()}
                    className="w-full bg-indigo-650 hover:bg-indigo-600 disabled:bg-zinc-900 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                  >
                    {createReportMutation.isPending ? 'Generating...' : 'Build Report'}
                  </button>
                </form>

                {/* Stored report items list */}
                <div className="flex-1 flex flex-col min-h-[160px]">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-2">Generated Reports Archive:</span>
                  <div className="flex-1 overflow-y-auto space-y-2 max-h-[180px]">
                    {isLoadingReports ? (
                      <div className="text-zinc-500 text-xs animate-pulse">Loading reports...</div>
                    ) : reports.length === 0 ? (
                      <div className="text-zinc-650 text-[10px] italic text-center py-6">No reports logged yet.</div>
                    ) : (
                      reports.map((r) => (
                        <div 
                          key={r.id}
                          className="p-3 bg-zinc-950/80 border border-zinc-900 rounded-lg space-y-1.5 font-mono text-[9px] text-zinc-400"
                        >
                          <div className="flex justify-between items-start">
                            <span className="text-zinc-200 font-semibold truncate max-w-[120px]">{r.title}</span>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded capitalize ${getStatusColor(r.status)}`}>
                              {r.status}
                            </span>
                          </div>
                          <div className="text-zinc-500 text-[8px]">Period: {r.report_period} | Type: {r.report_type}</div>
                          {r.description && <div className="text-zinc-600 truncate leading-relaxed">{r.description}</div>}

                          {r.status === 'draft' && (
                            <div className="flex gap-1.5 pt-1">
                              <button
                                onClick={() => handleTransitionReport(r.id, 'published')}
                                className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[8px] text-emerald-400 font-bold px-2 py-0.5 rounded cursor-pointer"
                              >
                                Publish
                              </button>
                              <button
                                onClick={() => handleTransitionReport(r.id, 'archived')}
                                className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-[8px] text-zinc-500 font-bold px-2 py-0.5 rounded cursor-pointer"
                              >
                                Archive
                              </button>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Executive() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <ExecutiveContent />
    </RouteGuard>
  );
}
