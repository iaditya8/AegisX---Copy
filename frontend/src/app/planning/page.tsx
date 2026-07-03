'use client';

import React, { useState, useMemo } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { useRecommendedDecisions, useCommitDecision, usePlans, useApprovePlan } from '../../hooks/useWorkspace';
import { 
  TrendingDown, 
  Activity, 
  CheckCircle, 
  Calendar, 
  DollarSign, 
  AlertTriangle, 
  Cpu, 
  Clock, 
  ArrowRight, 
  ShieldCheck 
} from 'lucide-react';

// Static metrics mapping for decisions in scatterplot visualization
interface DecisionMetric {
  cost: number;
  riskReduction: number;
  priority: 'low' | 'medium' | 'high' | 'critical';
}

const DECISION_METRICS: Record<string, DecisionMetric> = {
  'decision-123': { cost: 2500, riskReduction: 65, priority: 'high' },
  'decision-456': { cost: 8000, riskReduction: 90, priority: 'critical' },
  'decision-789': { cost: 1200, riskReduction: 30, priority: 'medium' },
};

// Static task items to render in Gantt workbench
interface GanttTask {
  id: string;
  name: string;
  startDay: number;
  durationDays: number;
  owner: string;
  status: 'completed' | 'in_progress' | 'pending';
}

const MOCK_GANTT_TASKS: GanttTask[] = [
  { id: 'task-1', name: 'Vulnerability Analysis', startDay: 0, durationDays: 2, owner: 'SecOps Analyst', status: 'completed' },
  { id: 'task-2', name: 'Patch Staging Verification', startDay: 2, durationDays: 2, owner: 'DevOps Lead', status: 'in_progress' },
  { id: 'task-3', name: 'Production Patch Rollout', startDay: 4, durationDays: 2, owner: 'SysAdmin', status: 'pending' },
  { id: 'task-4', name: 'Post-Deployment Scan Validation', startDay: 6, durationDays: 1, owner: 'Security QA', status: 'pending' },
];

function PlanningContent() {
  // Queries & Mutations
  const { data: recommendedDecisions = [], isLoading: isLoadingDecisions } = useRecommendedDecisions();
  const { data: plans = [], isLoading: isLoadingPlans } = usePlans();
  const commitDecisionMutation = useCommitDecision();
  const approvePlanMutation = useApprovePlan();

  // State
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Active Selections
  const activeDecisionId = selectedDecisionId || recommendedDecisions[0]?.id || null;
  const selectedDecision = recommendedDecisions.find((d) => d.id === activeDecisionId) || null;

  const activePlanId = selectedPlanId || plans[0]?.id || null;
  const selectedPlan = plans.find((p) => p.id === activePlanId) || null;

  // Compute metrics for active decision
  const activeMetrics = useMemo(() => {
    if (!activeDecisionId) return { cost: 0, riskReduction: 0, priority: 'medium' };
    return DECISION_METRICS[activeDecisionId] || { cost: 3000, riskReduction: 50, priority: 'medium' };
  }, [activeDecisionId]);

  const handleCommitDecision = async () => {
    if (!selectedDecision) return;
    try {
      await commitDecisionMutation.mutateAsync(selectedDecision.id);
      setSuccessMessage(`Decision committed: "${selectedDecision.option_name}" has been scheduled into active plans.`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleApprovePlan = async () => {
    if (!selectedPlan) return;
    try {
      await approvePlanMutation.mutateAsync(selectedPlan.id);
      setSuccessMessage(`Remediation Plan "${selectedPlan.name}" has been approved for automated execution.`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  // SVG Coordinates for scatterplot
  const plotPoints = useMemo(() => {
    return recommendedDecisions.map((d) => {
      const metric = DECISION_METRICS[d.id] || { cost: 3000, riskReduction: 50, priority: 'medium' };
      // Map cost $0 - $10,000 to X-axis 50px - 280px
      const x = 50 + (metric.cost / 10000) * 230;
      // Map risk reduction 0% - 100% to Y-axis 200px - 20px
      const y = 200 - (metric.riskReduction / 100) * 180;
      return { id: d.id, name: d.option_name, x, y, metric };
    });
  }, [recommendedDecisions]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
      case 'high': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      case 'medium': return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      default: return 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <Calendar className="w-6 h-6 text-indigo-500" />
                Remediation & Planning Workbench
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Prioritize recommended tradeoffs, commit assets to mitigation roadmaps, and monitor active Gantt schedules.
              </p>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-emerald-950/30 border border-emerald-800 text-emerald-400 text-xs px-4 py-3 rounded-lg animate-fade-in">
              <CheckCircle className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Main Layout Grid */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Tradeoffs Scatterplot & Decisions */}
            <div className="col-span-5 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <TrendingDown className="w-4 h-4 text-indigo-500" />
                  Cost vs. Risk Reduction Tradeoffs
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
                {/* SVG Scatterplot */}
                <div className="bg-zinc-950/80 border border-zinc-900 rounded-xl p-3.5 flex flex-col items-center justify-center shrink-0">
                  <span className="text-[10px] text-zinc-500 self-start font-mono mb-2">Tradeoff Scatterplot (Cost vs Risk-Reduction)</span>
                  <svg className="w-full h-52 font-mono text-[9px] text-zinc-500" viewBox="0 0 320 220">
                    {/* Grid lines */}
                    <line x1="50" y1="20" x2="50" y2="200" stroke="#27272a" strokeWidth="1" />
                    <line x1="50" y1="200" x2="300" y2="200" stroke="#27272a" strokeWidth="1" />
                    {[50, 100, 150, 200].map((yVal) => (
                      <line key={yVal} x1="50" y1={yVal} x2="300" y2={yVal} stroke="#18181b" strokeWidth="1" strokeDasharray="3,3" />
                    ))}
                    
                    {/* Axes Labels */}
                    <text x="3" y="110" fill="#71717a" transform="rotate(-90 10 110)">Risk Reduction (%)</text>
                    <text x="140" y="215" fill="#71717a">Estimated Cost ($)</text>

                    {/* Y-axis Ticks */}
                    <text x="25" y="24">100%</text>
                    <text x="30" y="114">50%</text>
                    <text x="35" y="204">0%</text>

                    {/* X-axis Ticks */}
                    <text x="45" y="212">$0</text>
                    <text x="160" y="212">$5k</text>
                    <text x="275" y="212">$10k</text>

                    {/* Plot Points */}
                    {plotPoints.map((p) => {
                      const isSelected = activeDecisionId === p.id;
                      return (
                        <g 
                          key={p.id} 
                          onClick={() => setSelectedDecisionId(p.id)}
                          className="cursor-pointer group"
                        >
                          <circle
                            cx={p.x}
                            cy={p.y}
                            r={isSelected ? 7 : 5}
                            fill={isSelected ? '#6366f1' : '#a1a1aa'}
                            stroke={isSelected ? '#c7d2fe' : '#3f3f46'}
                            strokeWidth={2}
                            className="transition-all duration-200"
                          />
                          <title>{p.name} (${p.metric.cost}, {p.metric.riskReduction}%)</title>
                        </g>
                      );
                    })}
                  </svg>
                </div>

                {/* Decisions List & Commitment Controls */}
                <div className="flex-1 flex flex-col min-h-[220px]">
                  {isLoadingDecisions ? (
                    <div className="text-center py-8 text-zinc-500 text-sm animate-pulse flex-1">Loading recommendations...</div>
                  ) : recommendedDecisions.length === 0 ? (
                    <div className="text-center py-8 text-zinc-500 text-sm italic flex-1">No recommended tradeoffs found.</div>
                  ) : (
                    <div className="space-y-3 flex-1 flex flex-col">
                      <div className="space-y-2 overflow-y-auto max-h-[160px] pr-1">
                        {recommendedDecisions.map((d) => {
                          const metric = DECISION_METRICS[d.id] || { cost: 3000, riskReduction: 50, priority: 'medium' };
                          const isSelected = activeDecisionId === d.id;
                          return (
                            <div
                              key={d.id}
                              onClick={() => setSelectedDecisionId(d.id)}
                              className={`p-3 rounded-lg border transition-all cursor-pointer flex justify-between items-center ${
                                isSelected 
                                  ? 'bg-indigo-950/15 border-indigo-500/80' 
                                  : 'bg-zinc-950/30 border-zinc-900 hover:border-zinc-800'
                              }`}
                            >
                              <div className="space-y-0.5 max-w-[70%]">
                                <h3 className="text-xs font-semibold text-white truncate">{d.option_name}</h3>
                                <span className="text-[10px] text-zinc-500 font-mono">Status: {d.status}</span>
                              </div>
                              <div className="text-right text-[10px] font-mono space-y-0.5">
                                <div className="text-emerald-400 font-semibold">+{metric.riskReduction}% Risk Red.</div>
                                <div className="text-zinc-400">${metric.cost.toLocaleString()} Est. Cost</div>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Selected Decision Detail Action Card */}
                      {selectedDecision && (
                        <div className="bg-zinc-950/50 border border-indigo-950/30 rounded-xl p-4 space-y-3 mt-auto">
                          <div className="flex justify-between items-center">
                            <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getPriorityColor(activeMetrics.priority)}`}>
                              {activeMetrics.priority} priority tradeoff
                            </span>
                            <span className="text-[10px] text-zinc-500 font-mono">ID: {selectedDecision.id}</span>
                          </div>
                          <h3 className="text-xs font-bold text-white leading-normal">{selectedDecision.option_name}</h3>
                          <div className="grid grid-cols-2 gap-3 text-xs border-t border-zinc-900 pt-3">
                            <div>
                              <span className="text-zinc-500 block">Est. Cost:</span>
                              <span className="text-zinc-200 font-semibold font-mono">${activeMetrics.cost.toLocaleString()} USD</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block">Projected Risk Reduction:</span>
                              <span className="text-emerald-400 font-semibold font-mono">{activeMetrics.riskReduction}% Reduction</span>
                            </div>
                          </div>
                          <button
                            onClick={handleCommitDecision}
                            disabled={commitDecisionMutation.isPending || selectedDecision.status === 'committed'}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                          >
                            {commitDecisionMutation.isPending ? 'Committing...' : selectedDecision.status === 'committed' ? 'Decision Committed' : 'Commit Decision'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Right Panel: Gantt Workbench */}
            <div className="col-span-7 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-rose-500" />
                  Active Remediation Plans & Gantt Timelines
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
                {/* Active Plans Horizontal Scroller */}
                <div className="flex gap-3 overflow-x-auto pb-2 shrink-0">
                  {isLoadingPlans ? (
                    <div className="text-zinc-500 text-xs animate-pulse">Loading plans...</div>
                  ) : plans.length === 0 ? (
                    <div className="text-zinc-500 text-xs italic">No active remediation plans found.</div>
                  ) : (
                    plans.map((p) => {
                      const isSelected = activePlanId === p.id;
                      return (
                        <div
                          key={p.id}
                          onClick={() => setSelectedPlanId(p.id)}
                          className={`p-3 rounded-lg border transition-all cursor-pointer shrink-0 min-w-[220px] max-w-[260px] space-y-2 ${
                            isSelected 
                              ? 'bg-rose-950/10 border-rose-500/80 shadow-md shadow-rose-950/10' 
                              : 'bg-zinc-950/40 border-zinc-900 hover:border-zinc-800'
                          }`}
                        >
                          <div className="flex justify-between items-start">
                            <span className="text-[9px] uppercase font-mono font-bold px-1.5 py-0.5 rounded bg-zinc-900 text-zinc-400">
                              {p.category}
                            </span>
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                              p.status === 'approved' 
                                ? 'bg-emerald-950/20 text-emerald-400 border border-emerald-950' 
                                : 'bg-amber-950/20 text-amber-400 border border-amber-950'
                            }`}>
                              {p.status.replace('_', ' ')}
                            </span>
                          </div>
                          <h3 className="text-xs font-bold text-white line-clamp-2 leading-tight">{p.name}</h3>
                          <div className="flex justify-between text-[10px] text-zinc-500 border-t border-zinc-900/60 pt-2 font-mono">
                            <span>Priority: {p.priority}</span>
                            <span>{new Date(p.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Selected Plan Gantt Workbench */}
                {selectedPlan ? (
                  <div className="flex-1 border border-zinc-900 bg-zinc-950/30 rounded-xl p-4 flex flex-col space-y-5">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <h3 className="text-sm font-bold text-white">{selectedPlan.name}</h3>
                        <p className="text-[11px] text-zinc-500">
                          Automated execution lifecycle tracker. Milestone sequences scheduled across 7 operational days.
                        </p>
                      </div>

                      {/* Approval Action */}
                      <button
                        onClick={handleApprovePlan}
                        disabled={approvePlanMutation.isPending || selectedPlan.status === 'approved'}
                        className="bg-rose-600 hover:bg-rose-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs px-3 py-2 rounded-lg transition-all cursor-pointer flex items-center gap-1.5"
                      >
                        <ShieldCheck className="w-4 h-4" />
                        {approvePlanMutation.isPending ? 'Approving...' : selectedPlan.status === 'approved' ? 'Plan Approved' : 'Approve & Execute'}
                      </button>
                    </div>

                    {/* Gantt Timeline Visualizer */}
                    <div className="flex-1 flex flex-col border border-zinc-900 rounded-xl p-3.5 bg-zinc-950/80 min-h-[220px]">
                      {/* Timeline Day Header */}
                      <div className="grid grid-cols-12 gap-2 text-[10px] text-zinc-600 font-mono border-b border-zinc-900 pb-2 mb-3">
                        <div className="col-span-4 font-bold uppercase tracking-wider">Milestone Task Name</div>
                        <div className="col-span-8 grid grid-cols-7 gap-1 text-center font-bold">
                          <span>Day 1</span>
                          <span>Day 2</span>
                          <span>Day 3</span>
                          <span>Day 4</span>
                          <span>Day 5</span>
                          <span>Day 6</span>
                          <span>Day 7</span>
                        </div>
                      </div>

                      {/* Tasks Timeline Bars */}
                      <div className="flex-1 space-y-4">
                        {MOCK_GANTT_TASKS.map((t) => (
                          <div key={t.id} className="grid grid-cols-12 gap-2 items-center text-xs">
                            {/* Task Metadata */}
                            <div className="col-span-4 space-y-0.5">
                              <div className="font-semibold text-zinc-300 truncate">{t.name}</div>
                              <div className="text-[10px] text-zinc-500 flex justify-between">
                                <span>{t.owner}</span>
                                <span className={`capitalize ${
                                  t.status === 'completed' ? 'text-emerald-400' : t.status === 'in_progress' ? 'text-blue-400' : 'text-zinc-600'
                                }`}>{t.status.replace('_', ' ')}</span>
                              </div>
                            </div>

                            {/* Gantt Bar Grid Wrapper */}
                            <div className="col-span-8 grid grid-cols-7 gap-1 h-6 relative bg-zinc-900/10 rounded">
                              {/* Horizontal Bar */}
                              <div 
                                style={{
                                  gridColumnStart: t.startDay + 1,
                                  gridColumnEnd: t.startDay + t.durationDays + 1
                                }}
                                className={`rounded h-full flex items-center justify-center font-mono text-[9px] font-semibold tracking-wider transition-all border ${
                                  t.status === 'completed' 
                                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                                    : t.status === 'in_progress' 
                                      ? 'bg-blue-500/10 border-blue-500/20 text-blue-400 animate-pulse'
                                      : 'bg-zinc-800/10 border-zinc-800/20 text-zinc-600'
                                }`}
                              >
                                {t.durationDays}d
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 border border-zinc-900 bg-zinc-950/30 rounded-xl p-4 flex items-center justify-center text-center">
                    <p className="text-xs text-zinc-600 italic">Select a plan from the list to view its Gantt timeline details</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Planning() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator']}>
      <PlanningContent />
    </RouteGuard>
  );
}
