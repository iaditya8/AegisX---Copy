'use client';

import React, { useMemo, useState } from 'react';
import { Shield, AlertTriangle, Bug, Award, Cpu } from 'lucide-react';

export interface GraphNode {
  id: string;
  label: string;
  type: 'asset' | 'finding' | 'threat' | 'compliance';
  status?: string;
  severity?: 'critical' | 'high' | 'medium' | 'low';
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
  isCritical?: boolean;
}

interface GraphCanvasProps {
  centerNode: GraphNode | null;
  adjacentNodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  onNodeDoubleClick?: (node: GraphNode) => void;
}

export default function GraphCanvas({
  centerNode,
  adjacentNodes,
  edges,
  onNodeClick,
  onNodeDoubleClick,
}: GraphCanvasProps) {
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  // Layout calculations
  const width = 600;
  const height = 400;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = 140; // Ring radius for adjacent nodes

  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    if (!centerNode) return positions;

    // Center node position
    positions[centerNode.id] = { x: centerX, y: centerY };

    // Position outer nodes in a circle
    adjacentNodes.forEach((node, index) => {
      const angle = (index / adjacentNodes.length) * 2 * Math.PI - Math.PI / 2; // start from top
      positions[node.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    });

    return positions;
  }, [centerNode, adjacentNodes, centerX, centerY, radius]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsPanning(true);
    setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({
      x: e.clientX - panStart.x,
      y: e.clientY - panStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    const panStep = 20;
    const zoomStep = 0.1;
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setPan((p) => ({ ...p, y: p.y - panStep }));
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setPan((p) => ({ ...p, y: p.y + panStep }));
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setPan((p) => ({ ...p, x: p.x - panStep }));
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setPan((p) => ({ ...p, x: p.x + panStep }));
    } else if (e.key === '+' || e.key === '=') {
      e.preventDefault();
      setZoom((z) => Math.min(2, z + zoomStep));
    } else if (e.key === '-') {
      e.preventDefault();
      setZoom((z) => Math.max(0.5, z - zoomStep));
    }
  };

  const handleZoomIn = () => setZoom((z) => Math.min(2, z + 0.1));
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, z - 0.1));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'asset':
        return <Cpu className="w-5 h-5 text-blue-400 pointer-events-none" />;
      case 'finding':
        return <Bug className="w-5 h-5 text-red-400 pointer-events-none" />;
      case 'threat':
        return <AlertTriangle className="w-5 h-5 text-amber-400 pointer-events-none" />;
      case 'compliance':
        return <Shield className="w-5 h-5 text-emerald-400 pointer-events-none" />;
      default:
        return <Award className="w-5 h-5 text-slate-400 pointer-events-none" />;
    }
  };

  const getNodeColor = (node: GraphNode) => {
    if (node.type === 'asset') return 'border-blue-500 bg-blue-950/80 text-blue-300';
    if (node.type === 'finding') return 'border-red-500 bg-red-950/80 text-red-300';
    if (node.type === 'threat') return 'border-amber-500 bg-amber-950/80 text-amber-300';
    return 'border-emerald-500 bg-emerald-950/80 text-emerald-300';
  };

  if (!centerNode) {
    return (
      <div className="flex flex-col items-center justify-center h-[400px] border border-slate-800 rounded-xl bg-slate-950/30 backdrop-blur-md">
        <Cpu className="w-12 h-12 text-slate-600 animate-pulse mb-3" />
        <p className="text-slate-400 text-sm">Select an asset to view its security topology map</p>
      </div>
    );
  }

  return (
    <div className="relative w-full border border-slate-800 rounded-xl bg-slate-950/40 backdrop-blur-md overflow-hidden p-4">
      {/* Legend */}
      <div className="absolute top-4 left-4 flex flex-col gap-1.5 text-xs text-slate-400 bg-slate-900/60 p-3 rounded-lg border border-slate-800/80 backdrop-blur-sm z-10 select-none pointer-events-none">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
          <span>Asset (Center)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
          <span>Vulnerability Findings</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
          <span>Threat Indicators</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          <span>GRC Controls</span>
        </div>
      </div>

      {/* Zoom/Pan Controls */}
      <div className="absolute bottom-4 right-4 flex gap-1.5 z-30">
        <button
          onClick={handleZoomIn}
          className="bg-slate-900 border border-slate-800 text-slate-300 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 hover:text-white transition-all cursor-pointer font-bold select-none"
          title="Zoom In (+)"
        >
          +
        </button>
        <button
          onClick={handleZoomOut}
          className="bg-slate-900 border border-slate-800 text-slate-300 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 hover:text-white transition-all cursor-pointer font-bold select-none"
          title="Zoom Out (-)"
        >
          -
        </button>
        <button
          onClick={handleReset}
          className="bg-slate-900 border border-slate-800 text-[10px] text-slate-300 px-2 h-8 flex items-center justify-center rounded-lg hover:bg-slate-800 hover:text-white transition-all cursor-pointer select-none"
          title="Reset"
        >
          Reset
        </button>
      </div>

      <div
        className={`relative w-full h-[400px] outline-none ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
        tabIndex={0}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onKeyDown={handleKeyDown}
      >
        <div
          className="w-full h-full relative"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center',
            transition: isPanning ? 'none' : 'transform 0.15s ease-out',
          }}
        >
          {/* SVG Connections Layer */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox={`0 0 ${width} ${height}`}>
            <defs>
              {/* Glowing filter for critical connections */}
              <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
              </filter>
              
              {/* Pulsating animation */}
              <style>
                {`
                  .pulsate {
                    stroke-dasharray: 8, 4;
                    animation: dash 30s linear infinite;
                  }
                  @keyframes dash {
                    to {
                      stroke-dashoffset: -1000;
                    }
                  }
                `}
              </style>
            </defs>

            {edges.map((edge, index) => {
              const start = nodePositions[edge.source];
              const end = nodePositions[edge.target];
              if (!start || !end) return null;

              const isHovered = hoveredNodeId === edge.source || hoveredNodeId === edge.target;

              return (
                <g key={index}>
                  <line
                    x1={start.x}
                    y1={start.y}
                    x2={end.x}
                    y2={end.y}
                    stroke={edge.isCritical ? '#ef4444' : '#475569'}
                    strokeWidth={edge.isCritical ? 2.5 : 1.5}
                    opacity={hoveredNodeId ? (isHovered ? 0.9 : 0.2) : 0.6}
                    className={edge.isCritical ? 'pulsate' : ''}
                    filter={edge.isCritical ? 'url(#glow)' : undefined}
                  />
                  {edge.label && (
                    <text
                      x={(start.x + end.x) / 2}
                      y={(start.y + end.y) / 2 - 6}
                      fill={edge.isCritical ? '#fca5a5' : '#94a3b8'}
                      fontSize="9"
                      textAnchor="middle"
                      opacity={hoveredNodeId ? (isHovered ? 1 : 0.1) : 0.7}
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Nodes Layer (Absolute elements for easy React interaction and crisp rendering) */}
          {Object.entries(nodePositions).map(([id, pos]) => {
            const node = [centerNode, ...adjacentNodes].find((n) => n.id === id);
            if (!node) return null;

            const isCenter = node.id === centerNode.id;
            const size = isCenter ? 54 : 44;
            const isHovered = hoveredNodeId === node.id;
            const hasActiveHover = hoveredNodeId !== null;

            return (
              <button
                key={node.id}
                onClick={() => onNodeClick?.(node)}
                onDoubleClick={() => onNodeDoubleClick?.(node)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                className={`absolute flex items-center justify-center rounded-full border-2 cursor-pointer transition-all duration-300 z-20 ${getNodeColor(
                  node
                )} ${isHovered ? 'scale-110 shadow-lg shadow-slate-950' : ''}`}
                style={{
                  left: pos.x - size / 2,
                  top: pos.y - size / 2,
                  width: size,
                  height: size,
                  opacity: hasActiveHover ? (isHovered ? 1 : 0.4) : 1,
                }}
              >
                {getNodeIcon(node.type)}
                {isHovered && (
                  <div className="absolute -bottom-7 bg-slate-900 border border-slate-800 text-[10px] text-slate-200 px-2 py-0.5 rounded shadow-md whitespace-nowrap z-30 pointer-events-none">
                    {node.label}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
