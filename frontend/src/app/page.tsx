'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useScopeStore } from '../stores/scope';
import { useAuthStore } from '../stores/auth';
import { apiClient } from '../services/api';
import { RouteGuard } from '../components/auth/RouteGuard';
import { Sidebar } from '../components/navigation/Sidebar';
import { Topbar } from '../components/navigation/Topbar';
import {
  Target,
  Server,
  ShieldCheck,
  AlertTriangle,
  Flame,
  TrendingUp,
  Cpu,
  Layers,
  ArrowRight,
  TrendingDown,
  CheckCircle,
} from 'lucide-react';
import GraphCanvas, { GraphNode as CanvasNode, GraphEdge as CanvasEdge } from '../components/graph/GraphCanvas';
import { useGraphTopology, useDecisions, useCommitDecision, useRisks } from '../hooks/useWorkspace';
import { useFindings } from '../hooks/useFindings';

function DashboardContent() {
  const { user } = useAuthStore();
  const { selectedScopeId } = useScopeStore();
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<any | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Queries
  const { data: scopeDetailsResponse, isLoading: isLoadingScope } = useQuery<any>({
    queryKey: ['scopes', 'detail', selectedScopeId],
    queryFn: () => apiClient.get(`/scopes/${selectedScopeId}`),
    enabled: !!selectedScopeId,
  });

  const activeScope = scopeDetailsResponse?.data || null;

  const { data: assetsResponse, isLoading: isLoadingAssets } = useQuery<any>({
    queryKey: ['assets', 'list', { scopeId: selectedScopeId }],
    queryFn: () => apiClient.get(`/scopes/${selectedScopeId}/assets`),
    enabled: !!selectedScopeId,
  });

  const assets = assetsResponse?.data || [];
  const assetsCount = assets.length || 0;

  // Selected Asset Details
  useEffect(() => {
    if (selectedAssetId) {
      const asset = assets.find((a: any) => a.id === selectedAssetId);
      if (asset) setSelectedAsset(asset);
    } else if (assets.length > 0) {
      setSelectedAssetId(assets[0].id);
      setSelectedAsset(assets[0]);
    } else {
      setSelectedAsset(null);
    }
  }, [selectedAssetId, assets]);

  // Topology Graph
  const { data: topology } = useGraphTopology();

  // Findings
  const { data: findingsRes } = useFindings(
    selectedAssetId ? { asset_id: selectedAssetId } : undefined
  );
  const findings = findingsRes?.data || [];

  // Risks
  const { data: risks } = useRisks(selectedScopeId || undefined);

  // Decisions
  const { data: decisions } = useDecisions();
  const commitDecisionMutation = useCommitDecision();

  // Calculate statistics
  const managedAssets = useMemo(() => {
    return assets.filter((a: any) => a.metadata?.managed ?? true).length;
  }, [assets]);

  const unmanagedAssets = assetsCount - managedAssets;

  const unmanagedRatio = useMemo(() => {
    if (assetsCount === 0) return 0;
    return Math.round((unmanagedAssets / assetsCount) * 100);
  }, [assetsCount, unmanagedAssets]);

  // Attack Surface Changes (Simulated recent modifications based on asset updates)
  const attackSurfaceChanges = useMemo(() => {
    if (!selectedScopeId) return [];
    return [
      { id: '1', type: 'discovery', message: 'New unmanaged subdomain dev.corp.local discovered', time: '1h ago' },
      { id: '2', type: 'port', message: 'Port 8080 (HTTP) exposed on production API host', time: '4h ago' },
      { id: '3', type: 'threat', message: 'Active scanning detected from associated threat group APT29', time: '1d ago' },
    ];
  }, [selectedScopeId]);

  // Graph Data Construction based on Selected Asset
  const graphData = useMemo(() => {
    if (!selectedAsset) return { centerNode: null, adjacentNodes: [], edges: [] };

    const center: CanvasNode = {
      id: selectedAsset.id,
      label: selectedAsset.host || selectedAsset.ip || 'Asset Target',
      type: 'asset',
    };

    const adjacent: CanvasNode[] = [];
    const connectionEdges: CanvasEdge[] = [];

    // Add findings nodes
    findings.slice(0, 3).forEach((finding: any) => {
      adjacent.push({
        id: finding.id,
        label: `${finding.title} (${finding.severity.toUpperCase()})`,
        type: 'finding',
        severity: finding.severity.toLowerCase() as any,
      });
      connectionEdges.push({
        source: selectedAsset.id,
        target: finding.id,
        label: 'exposes',
        isCritical: finding.severity.toLowerCase() === 'critical' || finding.severity.toLowerCase() === 'high',
      });
    });

    // Add general/related risks or compliance
    if (risks && risks.length > 0) {
      risks.slice(0, 2).forEach((risk: any) => {
        adjacent.push({
          id: risk.id,
          label: risk.title,
          type: 'threat',
        });
        connectionEdges.push({
          source: selectedAsset.id,
          target: risk.id,
          label: 'threatens',
          isCritical: risk.inherent_risk_score > 75,
        });
      });
    }

    // Add a standard compliance node to represent GRC posture
    adjacent.push({
      id: 'grc-iso-27001',
      label: 'ISO 27001: A.12.6.1 compliance check',
      type: 'compliance',
    });
    connectionEdges.push({
      source: selectedAsset.id,
      target: 'grc-iso-27001',
      label: 'governed_by',
      isCritical: false,
    });

    return {
      centerNode: center,
      adjacentNodes: adjacent,
      edges: connectionEdges,
    };
  }, [selectedAsset, findings, risks]);

  // FAIR Loss Expectancy calculations
  const lossExpectancy = useMemo(() => {
    if (!selectedAsset) return { min: 0, max: 0, mean: 0 };
    // Simulated FAIR quantitative risk model details
    const baseMultiplier = selectedAsset.metadata?.criticality === 'high' ? 1.8 : 0.9;
    const activeFindingsCount = findings.length;
    const threatFactor = 50000;
    
    const mean = Math.round(activeFindingsCount * threatFactor * baseMultiplier);
    return {
      min: Math.round(mean * 0.4),
      max: Math.round(mean * 1.7),
      mean: mean,
    };
  }, [selectedAsset, findings]);

  const handleCommitPlan = async (decisionId: string) => {
    try {
      await commitDecisionMutation.mutateAsync(decisionId);
      setSuccessMessage('Mitigation plan successfully committed to security orchestration queue.');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Welcome and Status Header */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">
                Security Decision Intelligence Console
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Targeting and assessing unmanaged attack vector vulnerabilities for actionable orchestration.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="flex h-2.5 w-2.5 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              <span className="text-[10px] uppercase font-mono tracking-wider text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Decision Intelligence Engine Online
              </span>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-emerald-950/30 border border-emerald-800 text-emerald-400 text-xs px-4 py-3 rounded-lg animate-fade-in">
              <CheckCircle className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Flags Flagship Layout */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Attack Surface & ASM Context */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  Attack Surface Context
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Scope Stats */}
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-lg p-3 space-y-2.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-zinc-500">Active Scope:</span>
                    <span className="text-zinc-300 font-medium truncate max-w-[120px]">
                      {activeScope?.name || 'No selection'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-zinc-500">Total Assets:</span>
                    <span className="text-white font-semibold font-mono">{assetsCount}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-zinc-500">
                      <span>Managed: {managedAssets}</span>
                      <span>Unmanaged: {unmanagedAssets} ({unmanagedRatio}%)</span>
                    </div>
                    <div className="w-full bg-zinc-900 h-1.5 rounded-full overflow-hidden flex">
                      <div className="bg-indigo-500 h-full" style={{ width: `${100 - unmanagedRatio}%` }} />
                      <div className="bg-amber-500 h-full" style={{ width: `${unmanagedRatio}%` }} />
                    </div>
                  </div>
                </div>

                {/* Delta Changes */}
                <div className="space-y-2">
                  <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                    Attack Surface Deltas
                  </h3>
                  {attackSurfaceChanges.length > 0 ? (
                    <div className="space-y-2">
                      {attackSurfaceChanges.map((change) => (
                        <div
                          key={change.id}
                          className="text-[11px] p-2 bg-zinc-900/30 border border-zinc-800/40 rounded flex items-start gap-2"
                        >
                          <Flame className="w-3.5 h-3.5 text-amber-500 shrink-0 mt-0.5" />
                          <div className="flex-1 space-y-0.5">
                            <p className="text-zinc-300 font-medium leading-normal">{change.message}</p>
                            <span className="text-zinc-600 text-[9px] block font-mono">{change.time}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-600 italic">No delta changes registered.</p>
                  )}
                </div>

                {/* Target Assets */}
                <div className="space-y-2">
                  <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                    Target Inventory
                  </h3>
                  <div className="space-y-1.5 max-h-[180px] overflow-y-auto pr-1">
                    {assets.map((asset: any) => (
                      <button
                        key={asset.id}
                        onClick={() => setSelectedAssetId(asset.id)}
                        className={`w-full text-left p-2.5 rounded-lg border text-xs flex items-center justify-between transition-all ${
                          selectedAssetId === asset.id
                            ? 'bg-indigo-950/20 border-indigo-500/80 text-white font-medium shadow-sm shadow-indigo-950'
                            : 'bg-zinc-900/20 border-zinc-850 hover:bg-zinc-900/50 text-zinc-400'
                        }`}
                      >
                        <span className="truncate">{asset.host || asset.ip}</span>
                        {asset.metadata?.managed === false && (
                          <span className="text-[8px] bg-amber-500/10 border border-amber-500/20 text-amber-400 px-1 rounded uppercase tracking-wider font-semibold">
                            unmanaged
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Center Panel: SVG Topology Map */}
            <div className="col-span-6 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden p-5 space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-sm font-bold text-white tracking-tight">Security Topology Map</h2>
                  <p className="text-[11px] text-zinc-500 mt-0.5">
                    Live relational view mapping selected asset vulnerabilities and GRC controls.
                  </p>
                </div>
              </div>

              <div className="flex-1 flex items-center justify-center">
                <div className="w-full">
                  <GraphCanvas
                    centerNode={graphData.centerNode}
                    adjacentNodes={graphData.adjacentNodes}
                    edges={graphData.edges}
                  />
                </div>
              </div>

              {/* Node Details (Hovering/Selected Sub-context) */}
              <div className="bg-zinc-950/60 border border-zinc-900 rounded-lg p-3.5 flex items-start gap-3">
                <Cpu className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
                <div className="space-y-1 flex-1">
                  <h3 className="text-xs font-bold text-white leading-tight">
                    {selectedAsset?.host || selectedAsset?.ip || 'No target selected'}
                  </h3>
                  <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500">
                    <span>IP: {selectedAsset?.ip || 'N/A'}</span>
                    <span>•</span>
                    <span>Type: {selectedAsset?.asset_type || 'Unknown'}</span>
                    <span>•</span>
                    <span>Criticality: {selectedAsset?.metadata?.criticality || 'medium'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Right Panel: Risk & Decision Commits */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <TrendingUp className="w-4 h-4 text-rose-500" />
                  Quantitative Risk Profile
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* FAIR Estimates */}
                <div className="bg-gradient-to-br from-rose-950/20 via-zinc-900/50 to-zinc-900/30 border border-rose-900/20 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-rose-400 font-mono">
                      FAIR Projections (Annualized Loss)
                    </span>
                    <AlertTriangle className="w-4 h-4 text-rose-500" />
                  </div>
                  <div>
                    <h3 className="text-2xl font-extrabold text-white font-mono leading-none tracking-tight">
                      ${lossExpectancy.mean.toLocaleString()}
                    </h3>
                    <p className="text-[10px] text-zinc-500 mt-1">Estimated Mean Loss Exposure</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 border-t border-zinc-800/60 pt-2.5">
                    <div>
                      <span className="text-[9px] text-zinc-500 block uppercase">Min Loss</span>
                      <span className="text-xs font-semibold text-zinc-300 font-mono">
                        ${lossExpectancy.min.toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-[9px] text-zinc-500 block uppercase">Max Loss</span>
                      <span className="text-xs font-semibold text-zinc-300 font-mono">
                        ${lossExpectancy.max.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Mitigation Decisions */}
                <div className="space-y-2">
                  <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider">
                    Recommended Mitigation Actions
                  </h3>
                  <div className="space-y-2">
                    {decisions && decisions.length > 0 ? (
                      decisions.map((decision: any) => (
                        <div
                          key={decision.id}
                          className="bg-zinc-950/50 border border-zinc-900 rounded-lg p-3 space-y-2.5 flex flex-col hover:border-zinc-800 transition-all"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider font-mono">
                              {decision.decision_type.replace('_', ' ')}
                            </span>
                            {decision.status === 'committed' && (
                              <span className="text-[8px] bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                                committed
                              </span>
                            )}
                          </div>
                          <div>
                            <h4 className="text-xs font-bold text-white">{decision.option_name}</h4>
                            <p className="text-[10px] text-zinc-500 mt-1">
                              Deploying control reduces mean annualized loss to residual projection level.
                            </p>
                          </div>
                          {decision.status !== 'committed' && (
                            <button
                              onClick={() => handleCommitPlan(decision.id)}
                              disabled={commitDecisionMutation.isPending}
                              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-[10px] py-1.5 rounded transition-all cursor-pointer shadow-sm text-center flex items-center justify-center gap-1"
                            >
                              <span>Commit Mitigation Plan</span>
                              <ArrowRight className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-zinc-600 italic">No recommendations available.</p>
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

export default function Dashboard() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <DashboardContent />
    </RouteGuard>
  );
}
