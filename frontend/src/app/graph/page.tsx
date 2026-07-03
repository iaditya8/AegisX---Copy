'use client';

import React, { useState, useMemo } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { useScopeStore } from '../../stores/scope';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useGraphTopology, useGraphPath, useThreats } from '../../hooks/useWorkspace';
import { useFindings } from '../../hooks/useFindings';
import GraphCanvas, { GraphNode as CanvasNode, GraphEdge as CanvasEdge } from '../../components/graph/GraphCanvas';
import { 
  Network, 
  Search, 
  MapPin, 
  Info,
  GitFork,
  ArrowRight,
  Cpu,
  Bug,
  AlertTriangle,
  Shield,
  X
} from 'lucide-react';

function GraphExplorerContent() {
  const { selectedScopeId } = useScopeStore();
  
  // State
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sourcePathId, setSourcePathId] = useState('');
  const [targetPathId, setTargetPathId] = useState('');
  const [showPathResult, setShowPathResult] = useState(false);
  const [inspectedNode, setInspectedNode] = useState<any | null>(null);

  // Queries
  const { data: topology, isLoading: isLoadingTopology } = useGraphTopology();
  const { data: assetsResponse } = useQuery<any>({
    queryKey: ['assets', 'list', { scopeId: selectedScopeId }],
    queryFn: () => apiClient.get(`/scopes/${selectedScopeId}/assets`),
    enabled: !!selectedScopeId,
  });
  const assets = assetsResponse?.data || [];

  const { data: findingsRes } = useFindings();
  const findings = findingsRes?.data || [];

  const { data: threats = [] } = useThreats(selectedScopeId || undefined);

  // Path Search hook
  const { data: pathData, isLoading: isLoadingPath } = useGraphPath(
    showPathResult ? sourcePathId : '',
    showPathResult ? targetPathId : ''
  );

  // Map Entity IDs to Labels and metadata
  const entityMap = useMemo(() => {
    const map: Record<string, { label: string; type: string; details: any }> = {};

    assets.forEach((asset: any) => {
      map[asset.id] = {
        label: asset.host || asset.ip || 'Asset Target',
        type: 'asset',
        details: asset,
      };
    });

    findings.forEach((finding: any) => {
      map[finding.id] = {
        label: `${finding.title} (${finding.severity.toUpperCase()})`,
        type: 'finding',
        details: finding,
      };
    });

    threats.forEach((threat: any) => {
      map[threat.id] = {
        label: threat.value,
        type: 'threat',
        details: threat,
      };
    });

    // Fallback for default GRC control
    map['grc-iso-27001'] = {
      label: 'ISO 27001 compliance check',
      type: 'compliance',
      details: {
        id: 'grc-iso-27001',
        title: 'ISO 27001: A.12.6.1 compliance check',
        framework: 'ISO 27001',
        status: 'compliant',
      },
    };

    return map;
  }, [assets, findings, threats]);

  // Nodes and edges available in scope
  const availableNodes = useMemo(() => {
    if (!topology || !topology.nodes) return [];
    return topology.nodes.map((n: any) => ({
      id: n.entity_id,
      type: n.node_type,
      label: entityMap[n.entity_id]?.label || `Node (${n.node_type})`,
      status: n.status,
    }));
  }, [topology, entityMap]);

  const defaultCenterId = useMemo(() => {
    const assetNode = availableNodes.find((n) => n.type === 'asset');
    return assetNode ? assetNode.id : (availableNodes[0]?.id || null);
  }, [availableNodes]);

  const activeCenterId = selectedNodeId || defaultCenterId;

  // Filtered canvas node and edge lists based on center pivoting
  const canvasData = useMemo(() => {
    if (!topology || !activeCenterId) {
      return { centerNode: null, adjacentNodes: [], edges: [] };
    }

    const centerNodeObj = availableNodes.find((n) => n.id === activeCenterId);
    if (!centerNodeObj) return { centerNode: null, adjacentNodes: [], edges: [] };

    const center: CanvasNode = {
      id: centerNodeObj.id,
      label: centerNodeObj.label,
      type: centerNodeObj.type,
    };

    // Find edges connected to the center node
    const connectedEdges = (topology.edges || []).filter(
      (e: any) => e.source_id === activeCenterId || e.target_id === activeCenterId
    );

    const adjacent: CanvasNode[] = [];
    const canvasEdges: CanvasEdge[] = [];

    connectedEdges.forEach((edge: any) => {
      const isSourceCenter = edge.source_id === activeCenterId;
      const targetId = isSourceCenter ? edge.target_id : edge.source_id;

      const adjNode = availableNodes.find((n) => n.id === targetId);
      if (adjNode) {
        adjacent.push({
          id: adjNode.id,
          label: adjNode.label,
          type: adjNode.type,
        });

        // Determine if edge lies on the highlighted path
        const isOnPath = pathData?.edges?.some(
          (pe: any) => pe.source_id === edge.source_id && pe.target_id === edge.target_id
        );

        canvasEdges.push({
          source: edge.source_id,
          target: edge.target_id,
          label: edge.edge_type.replace('_', ' '),
          isCritical: isOnPath || edge.weight > 70,
        });
      }
    });

    return {
      centerNode: center,
      adjacentNodes: adjacent,
      edges: canvasEdges,
    };
  }, [topology, activeCenterId, availableNodes, pathData]);

  // Node Click Handlers
  const handleNodeClick = (node: CanvasNode) => {
    const detailsObj = entityMap[node.id];
    if (detailsObj) {
      setInspectedNode({
        id: node.id,
        label: detailsObj.label,
        type: detailsObj.type,
        details: detailsObj.details,
      });
    }
  };

  const handleNodeDoubleClick = (node: CanvasNode) => {
    setSelectedNodeId(node.id);
  };

  // Search filter
  const filteredNodes = useMemo(() => {
    if (!searchQuery) return [];
    return availableNodes.filter((n) =>
      n.label.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery, availableNodes]);

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
                <Network className="w-6 h-6 text-indigo-500" />
                Topology Graph Explorer
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Explore multi-hop relationships between asset endpoints, vulnerability findings, and active threat profiles.
              </p>
            </div>
          </div>

          {/* Main Layout Grid */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Column: Search & Path Tracer Controls */}
            <div className="col-span-3 flex flex-col gap-4 overflow-hidden">
              {/* Node Search Panel */}
              <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-4 flex flex-col space-y-3 shrink-0">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Search className="w-4 h-4 text-indigo-500" />
                  Search Node Entity
                </h2>
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Type hostname, IP, threat..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-zinc-950 border border-zinc-900 focus:border-indigo-500 text-xs px-3 py-2 pl-8 rounded-lg outline-none text-zinc-300"
                  />
                  <Search className="w-3.5 h-3.5 text-zinc-650 absolute top-2.5 left-2.5" />
                </div>
                {searchQuery && (
                  <div className="max-h-[120px] overflow-y-auto border border-zinc-900 bg-zinc-950/80 rounded-lg p-1.5 space-y-1">
                    {filteredNodes.length > 0 ? (
                      filteredNodes.map((n) => (
                        <button
                          key={n.id}
                          onClick={() => {
                            setSelectedNodeId(n.id);
                            setSearchQuery('');
                          }}
                          className="w-full text-left text-[11px] hover:bg-zinc-900 text-zinc-300 hover:text-white px-2 py-1.5 rounded truncate transition-all"
                        >
                          {n.label}
                        </button>
                      ))
                    ) : (
                      <span className="text-[10px] text-zinc-600 block text-center py-2">No matching nodes</span>
                    )}
                  </div>
                )}
              </div>

              {/* Path Tracer Panel */}
              <div className="bg-zinc-900/20 border border-zinc-900 rounded-xl p-4 flex flex-col space-y-3 overflow-y-auto">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <GitFork className="w-4 h-4 text-rose-500" />
                  Path Tracer
                </h2>
                <div className="space-y-2 text-xs">
                  <div className="space-y-1">
                    <label htmlFor="source-node-select" className="text-zinc-500 block">Source Node:</label>
                    <select
                      id="source-node-select"
                      value={sourcePathId}
                      onChange={(e) => {
                        setSourcePathId(e.target.value);
                        setShowPathResult(false);
                      }}
                      className="w-full bg-zinc-950 border border-zinc-900 focus:border-rose-500 text-zinc-300 px-2 py-1.5 rounded outline-none"
                    >
                      <option value="">Select source...</option>
                      {availableNodes.map((n) => (
                        <option key={n.id} value={n.id}>{n.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label htmlFor="target-node-select" className="text-zinc-500 block">Target Node:</label>
                    <select
                      id="target-node-select"
                      value={targetPathId}
                      onChange={(e) => {
                        setTargetPathId(e.target.value);
                        setShowPathResult(false);
                      }}
                      className="w-full bg-zinc-950 border border-zinc-900 focus:border-rose-500 text-zinc-300 px-2 py-1.5 rounded outline-none"
                    >
                      <option value="">Select target...</option>
                      {availableNodes.map((n) => (
                        <option key={n.id} value={n.id}>{n.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <button
                  onClick={() => setShowPathResult(true)}
                  disabled={!sourcePathId || !targetPathId}
                  className="w-full bg-rose-600 hover:bg-rose-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                >
                  Trace Path
                </button>

                {showPathResult && pathData && (
                  <div className="border-t border-zinc-900 pt-3 space-y-3">
                    <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
                      <span>Path Cost:</span>
                      <span className="text-rose-400 font-semibold">{pathData.metrics?.cost || 0}</span>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Traced Route:</span>
                      <div className="space-y-2">
                        {pathData.nodes?.map((n: any, idx: number) => (
                          <div key={n.id} className="flex items-center gap-1.5 text-[11px]">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                            <span className="truncate text-zinc-300 font-medium">
                              {entityMap[n.entity_id]?.label || 'Node'}
                            </span>
                            {idx < pathData.nodes.length - 1 && (
                              <ArrowRight className="w-3 h-3 text-zinc-700 shrink-0 mx-0.5" />
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Center Panel: Full Graph Visualizer */}
            <div className="col-span-6 bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden p-5 flex flex-col space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <h2 className="text-sm font-bold text-white tracking-tight">Interactive Topology Canvas</h2>
                  <p className="text-[11px] text-zinc-500 mt-0.5">
                    Click node to inspect metadata. Double-click any node to pivot graph center.
                  </p>
                </div>
              </div>

              <div className="flex-1 flex items-center justify-center">
                <div className="w-full">
                  <GraphCanvas
                    centerNode={canvasData.centerNode}
                    adjacentNodes={canvasData.adjacentNodes}
                    edges={canvasData.edges}
                    onNodeClick={handleNodeClick}
                    onNodeDoubleClick={handleNodeDoubleClick}
                  />
                </div>
              </div>
            </div>

            {/* Right Column: Node Inspector Drawer */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Info className="w-4 h-4 text-indigo-500" />
                  Node Inspector
                </h2>
                {inspectedNode && (
                  <button onClick={() => setInspectedNode(null)} className="text-zinc-500 hover:text-zinc-200">
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {inspectedNode ? (
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {/* Entity Type Badge */}
                  <div className="flex items-center gap-2">
                    {inspectedNode.type === 'asset' && <Cpu className="w-4 h-4 text-blue-400" />}
                    {inspectedNode.type === 'finding' && <Bug className="w-4 h-4 text-red-400" />}
                    {inspectedNode.type === 'threat' && <AlertTriangle className="w-4 h-4 text-amber-400" />}
                    {inspectedNode.type === 'compliance' && <Shield className="w-4 h-4 text-emerald-400" />}
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-400">
                      {inspectedNode.type} Details
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-white leading-snug">{inspectedNode.label}</h3>

                  <div className="border-t border-zinc-900 pt-4 space-y-3.5 text-xs text-zinc-400">
                    {inspectedNode.type === 'asset' && (
                      <>
                        <div className="flex justify-between">
                          <span>IP Address:</span>
                          <span className="text-zinc-200">{inspectedNode.details.ip || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Asset Type:</span>
                          <span className="text-zinc-200 uppercase">{inspectedNode.details.asset_type || 'Unknown'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Criticality:</span>
                          <span className="text-zinc-200 font-semibold">{inspectedNode.details.metadata?.criticality || 'medium'}</span>
                        </div>
                      </>
                    )}

                    {inspectedNode.type === 'finding' && (
                      <>
                        <div className="flex justify-between">
                          <span>Severity:</span>
                          <span className="text-rose-400 uppercase font-semibold">{inspectedNode.details.severity || 'low'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Exploit Available:</span>
                          <span className="text-zinc-200">{inspectedNode.details.exploit_available ? 'Yes' : 'No'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Remediation Status:</span>
                          <span className="text-zinc-200 uppercase font-mono">{inspectedNode.details.status || 'open'}</span>
                        </div>
                      </>
                    )}

                    {inspectedNode.type === 'threat' && (
                      <>
                        <div className="flex justify-between">
                          <span>Indicator Type:</span>
                          <span className="text-zinc-200 uppercase">{inspectedNode.details.indicator_type || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Intelligence Source:</span>
                          <span className="text-zinc-200">{inspectedNode.details.source || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Fusion Confidence:</span>
                          <span className="text-amber-400 font-semibold">{inspectedNode.details.fusion_score || 'N/A'}%</span>
                        </div>
                      </>
                    )}

                    {inspectedNode.type === 'compliance' && (
                      <>
                        <div className="flex justify-between">
                          <span>Framework:</span>
                          <span className="text-zinc-200">{inspectedNode.details.framework || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Compliance Status:</span>
                          <span className="text-emerald-400 font-semibold uppercase">{inspectedNode.details.status || 'compliant'}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center p-4 text-center">
                  <p className="text-xs text-zinc-650 italic leading-relaxed">
                    Click any node in the topology map to load configuration and telemetry inspect details here.
                  </p>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function GraphExplorer() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <GraphExplorerContent />
    </RouteGuard>
  );
}
