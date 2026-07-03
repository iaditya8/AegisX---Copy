'use client';

import React, { useState } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { 
  useSOCQueueSummary, 
  useSOCKPIs, 
  useSOCAnalysts 
} from '../../hooks/useSOC';
import { 
  useResilienceRecords, 
  useResilienceObjectives, 
  useUpdateResilienceStatus 
} from '../../hooks/useResilience';
import { 
  Activity, 
  Users, 
  Database, 
  Clock, 
  TrendingUp, 
  ShieldAlert, 
  CheckCircle,
  FileCheck2,
  Play,
  RotateCcw,
  Sparkles
} from 'lucide-react';

function SocContent() {
  // SOC Queries
  const { data: queue = null, isLoading: isLoadingQueue } = useSOCQueueSummary();
  const { data: kpis = [], isLoading: isLoadingKPIs } = useSOCKPIs();
  const { data: analysts = [], isLoading: isLoadingAnalysts } = useSOCAnalysts();

  // Resilience Queries
  const { data: resilienceRecords = [], isLoading: isLoadingResilience } = useResilienceRecords();
  const [selectedResilienceId, setSelectedResilienceId] = useState<string | null>(null);

  const activeResilienceId = selectedResilienceId || resilienceRecords[0]?.id || null;
  const selectedResilience = resilienceRecords.find((r) => r.id === activeResilienceId) || null;

  const { data: objectives = [], isLoading: isLoadingObjectives } = useResilienceObjectives(activeResilienceId || '');

  // Resilience status transition mutation
  const updateStatusMutation = useUpdateResilienceStatus();
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleUpdateStatus = async (action: 'activate' | 'validate' | 'complete' | 'close') => {
    if (!activeResilienceId) return;
    try {
      await updateStatusMutation.mutateAsync({ id: activeResilienceId, action });
      setSuccessMsg(`Service resilience plan status updated: ${action.toUpperCase()}`);
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (e) {
      console.error(e);
    }
  };

  const getCriticalityColor = (crit: string) => {
    switch (crit) {
      case 'critical': return 'bg-rose-950/40 text-rose-400 border border-rose-900';
      case 'high': return 'bg-orange-950/40 text-orange-400 border border-orange-900';
      case 'medium': return 'bg-amber-950/40 text-amber-400 border border-amber-900';
      default: return 'bg-zinc-900 text-zinc-400 border border-zinc-800';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400';
      case 'validated': return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
      case 'completed': return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
      default: return 'bg-zinc-700/15 border-zinc-700/30 text-zinc-400';
    }
  };

  const getObjectiveStatusColor = (status: string) => {
    switch (status) {
      case 'achieved': return 'text-emerald-400 bg-emerald-950/20 border border-emerald-900';
      case 'missed': return 'text-rose-400 bg-rose-950/20 border border-rose-900';
      default: return 'text-zinc-500 bg-zinc-950 border border-zinc-900';
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Top Banner */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <Activity className="w-6 h-6 text-indigo-500" />
                SOC Operations & Cyber Resilience Console
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Monitor incident response queue backlog, track analyst MTTR performance, and validate recovery objectives.
              </p>
            </div>
          </div>

          {successMsg && (
            <div className="flex items-center gap-2.5 bg-indigo-950/30 border border-indigo-800 text-indigo-400 text-xs px-4 py-3 rounded-lg animate-fade-in shrink-0">
              <CheckCircle className="w-4.5 h-4.5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Core Layout Grid */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: SOC Backlog & Performance (30%) */}
            <div className="col-span-4 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-indigo-500" />
                  SOC Performance & Queues
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-5">
                {/* Backlog stats */}
                {isLoadingQueue ? (
                  <div className="text-zinc-500 text-xs animate-pulse">Loading queue metrics...</div>
                ) : queue ? (
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Incident Queue:</span>
                      {queue.backlog_metrics && (
                        <div className="flex items-center gap-1 text-[10px] text-rose-400">
                          <TrendingUp className="w-3.5 h-3.5" />
                          <span>+{queue.backlog_metrics.growth_rate_percent}% Growth</span>
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                      <div className="bg-zinc-900/40 border border-zinc-800/80 p-3 rounded-lg text-center">
                        <span className="text-lg font-bold text-white block">
                          {queue.active_tickets_count}
                        </span>
                        <span className="text-[8px] text-zinc-550 uppercase font-semibold">Active</span>
                      </div>
                      <div className="bg-zinc-900/40 border border-zinc-800/80 p-3 rounded-lg text-center">
                        <span className="text-lg font-bold text-rose-400 block">
                          {queue.critical_tickets_count}
                        </span>
                        <span className="text-[8px] text-rose-500/80 uppercase font-semibold">Critical</span>
                      </div>
                      <div className="bg-zinc-900/40 border border-zinc-800/80 p-3 rounded-lg text-center">
                        <span className="text-lg font-bold text-zinc-400 block">
                          {queue.unassigned_tickets_count}
                        </span>
                        <span className="text-[8px] text-zinc-500 uppercase font-semibold">Unassigned</span>
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* MTTD/MTTR KPIs */}
                <div className="space-y-2.5">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Operational KPIs:</span>
                  {isLoadingKPIs ? (
                    <div className="text-zinc-500 text-xs animate-pulse">Loading KPIs...</div>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      {kpis.map((kpi, idx) => (
                        <div key={kpi.id || idx} className="p-3 bg-zinc-950/40 border border-zinc-900 rounded-lg space-y-1">
                          <span className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider block truncate">{kpi.metric_name}</span>
                          <div className="flex items-baseline gap-1">
                            <span className="text-sm font-bold text-white">{kpi.metric_value}</span>
                            <span className="text-[8px] text-zinc-500">{kpi.unit}</span>
                          </div>
                          <span className="text-[8px] text-zinc-600 block">Target: {kpi.target_value}{kpi.unit}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Analyst performance table */}
                <div className="space-y-2.5">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Active Analysts Response:</span>
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-lg overflow-hidden">
                    {isLoadingAnalysts ? (
                      <div className="p-4 text-zinc-500 text-xs animate-pulse">Loading analysts...</div>
                    ) : (
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-zinc-900/20 border-b border-zinc-900 text-[9px] text-zinc-550 font-bold uppercase tracking-wider">
                            <th className="p-2.5">Analyst</th>
                            <th className="p-2.5 text-center">Cases</th>
                            <th className="p-2.5 text-right">MTTR</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-900 text-[10px]">
                          {analysts.map((an, idx) => (
                            <tr key={an.id || idx} className="hover:bg-zinc-900/10">
                              <td className="p-2.5 font-semibold text-zinc-300">{an.analyst_name}</td>
                              <td className="p-2.5 text-center text-zinc-400">{an.cases_closed}</td>
                              <td className="p-2.5 text-right text-indigo-400 font-mono">{an.mean_time_to_resolution_minutes}m</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Center Panel: Resilience Services list & Objectives tracking (50%) */}
            <div className="col-span-5 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-indigo-400" />
                  Cyber Resilience Services
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Horizontal scroller of services */}
                <div className="flex gap-3 overflow-x-auto pb-2 shrink-0">
                  {isLoadingResilience ? (
                    <div className="text-zinc-500 text-xs animate-pulse">Loading services...</div>
                  ) : resilienceRecords.length === 0 ? (
                    <div className="text-zinc-500 text-xs italic">No resilience records.</div>
                  ) : (
                    resilienceRecords.map((r, idx) => {
                      const isSelected = activeResilienceId === r.id;
                      return (
                        <div
                          key={r.id || idx}
                          onClick={() => setSelectedResilienceId(r.id)}
                          className={`min-w-[180px] p-3 rounded-lg border transition-all cursor-pointer space-y-2 ${
                            isSelected 
                              ? 'bg-indigo-950/10 border-indigo-500/80 shadow-md' 
                              : 'bg-zinc-950/40 border-zinc-900 hover:border-zinc-800'
                          }`}
                        >
                          <div className="flex justify-between items-start">
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase ${getCriticalityColor(r.service_criticality)}`}>
                              {r.service_criticality}
                            </span>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded capitalize ${getStatusColor(r.status)}`}>
                              {r.status}
                            </span>
                          </div>
                          <div>
                            <h3 className="text-xs font-bold text-white line-clamp-1 leading-snug">{r.title}</h3>
                            <span className="text-[9px] text-zinc-500 font-mono block truncate">{r.service_name}</span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Recovery Objectives list */}
                <div className="space-y-3 flex-1 flex flex-col">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Recovery Objectives Metrics (RTO / RPO):</span>
                  
                  <div className="flex-1 overflow-y-auto space-y-3 max-h-[300px]">
                    {isLoadingObjectives ? (
                      <div className="text-zinc-500 text-xs animate-pulse">Loading objectives...</div>
                    ) : objectives.length === 0 ? (
                      <div className="text-zinc-550 text-[10px] italic text-center py-8">Select a resilience record to view objectives.</div>
                    ) : (
                      objectives.map((obj, idx) => (
                        <div 
                          key={obj.id || idx}
                          className="p-4 rounded-xl border border-zinc-900 bg-zinc-950/40 space-y-3"
                        >
                          <div className="flex justify-between items-start">
                            <h4 className="text-xs font-bold text-white leading-normal">{obj.objective_name}</h4>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded uppercase ${getObjectiveStatusColor(obj.status)}`}>
                              {obj.status}
                            </span>
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                              <div className="flex justify-between text-[9px] text-zinc-550 font-semibold uppercase">
                                <span>Recovery Time (RTO)</span>
                                <span>Target: {obj.target_rto_minutes}m</span>
                              </div>
                              <div className="h-2 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800/40">
                                <div 
                                  className={`h-full rounded-full ${
                                    obj.status === 'achieved' ? 'bg-indigo-500' : obj.status === 'missed' ? 'bg-rose-500' : 'bg-zinc-700'
                                  }`}
                                  style={{ width: `${Math.min(((obj.actual_rto_minutes || 0) / obj.target_rto_minutes) * 100, 100)}%` }}
                                ></div>
                              </div>
                              <div className="flex justify-between text-[8px] font-mono text-zinc-500">
                                <span>Actual: {obj.actual_rto_minutes !== undefined ? `${obj.actual_rto_minutes}m` : 'N/A'}</span>
                              </div>
                            </div>

                            <div className="space-y-1">
                              <div className="flex justify-between text-[9px] text-zinc-550 font-semibold uppercase">
                                <span>Recovery Point (RPO)</span>
                                <span>Target: {obj.target_rpo_minutes}m</span>
                              </div>
                              <div className="h-2 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800/40">
                                <div 
                                  className={`h-full rounded-full ${
                                    obj.status === 'achieved' ? 'bg-indigo-500' : obj.status === 'missed' ? 'bg-rose-500' : 'bg-zinc-700'
                                  }`}
                                  style={{ width: `${Math.min(((obj.actual_rpo_minutes || 0) / obj.target_rpo_minutes) * 100, 100)}%` }}
                                ></div>
                              </div>
                              <div className="flex justify-between text-[8px] font-mono text-zinc-500">
                                <span>Actual: {obj.actual_rpo_minutes !== undefined ? `${obj.actual_rpo_minutes}m` : 'N/A'}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Right Panel: Recovery Objectives & Action Center (30%) */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <FileCheck2 className="w-4 h-4 text-emerald-400" />
                  Action Center
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {selectedResilience ? (
                  <div className="space-y-4">
                    <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-2">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Service Metadata</span>
                      <h3 className="text-xs font-bold text-white">{selectedResilience.title}</h3>
                      <p className="text-[10px] text-zinc-400 leading-relaxed">{selectedResilience.description}</p>
                    </div>

                    {selectedResilience.status !== 'closed' && (
                      <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-3">
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Drill Execution Tasks</span>
                        <div className="space-y-2">
                          <button
                            onClick={() => handleUpdateStatus('activate')}
                            disabled={selectedResilience.status !== 'draft'}
                            className="w-full flex items-center justify-center gap-1.5 bg-indigo-650 hover:bg-indigo-600 disabled:bg-zinc-900 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                          >
                            <Play className="w-3.5 h-3.5" />
                            Activate Plan
                          </button>
                          <button
                            onClick={() => handleUpdateStatus('validate')}
                            disabled={selectedResilience.status !== 'active'}
                            className="w-full flex items-center justify-center gap-1.5 bg-blue-650 hover:bg-blue-600 disabled:bg-zinc-900 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                            Validate Objectives
                          </button>
                          <button
                            onClick={() => handleUpdateStatus('complete')}
                            disabled={selectedResilience.status !== 'validated'}
                            className="w-full flex items-center justify-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-900 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                            Complete Resilience Drill
                          </button>
                          <button
                            onClick={() => handleUpdateStatus('close')}
                            disabled={['completed', 'validated'].indexOf(selectedResilience.status) === -1}
                            className="w-full flex items-center justify-center gap-1.5 bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-950 disabled:text-zinc-700 text-zinc-400 border border-zinc-800/80 font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            Close Resilience Plan
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-zinc-550 text-[10px] italic text-center py-10">Select a resilience record to execute action controls.</div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Soc() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <SocContent />
    </RouteGuard>
  );
}
