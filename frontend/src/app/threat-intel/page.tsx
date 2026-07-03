'use client';

import React, { useState } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { useScopeStore } from '../../stores/scope';
import { useThreats, useFuseThreat } from '../../hooks/useWorkspace';
import { 
  Brain, 
  Flame, 
  Sliders, 
  AlertTriangle, 
  Activity, 
  CheckCircle,
  ShieldAlert,
  Server
} from 'lucide-react';

function ThreatIntelContent() {
  const { selectedScopeId } = useScopeStore();
  const [selectedThreatId, setSelectedThreatId] = useState<string | null>(null);
  const [fusionConfidence, setFusionConfidence] = useState<number>(80);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Fetch threats for the scope
  const { data: threats = [], isLoading } = useThreats(selectedScopeId || undefined);
  const fuseThreatMutation = useFuseThreat();

  const selectedThreat = threats.find((t) => t.id === selectedThreatId) || threats[0] || null;

  const handleFuseThreat = async () => {
    if (!selectedThreat) return;
    try {
      await fuseThreatMutation.mutateAsync({
        id: selectedThreat.id,
        confidence: fusionConfidence,
      });
      setSuccessMessage(`Threat Fusion score successfully updated to ${fusionConfidence}% for ${selectedThreat.value}.`);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const getIndicatorColor = (score?: number) => {
    if (!score) return 'bg-zinc-700 text-zinc-300 border-zinc-650';
    if (score >= 80) return 'bg-rose-500/10 border-rose-500/20 text-rose-400';
    if (score >= 50) return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
    return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Welcome and Header */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <Brain className="w-6 h-6 text-indigo-500 animate-pulse" />
                Threat Intelligence Center
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Monitor threat campaign vectors, assess adversary behavior techniques, and adjust risk fusion rules.
              </p>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-emerald-950/30 border border-emerald-800 text-emerald-400 text-xs px-4 py-3 rounded-lg animate-fade-in">
              <CheckCircle className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Core Layout */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left: Active Threats List */}
            <div className="col-span-8 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Activity className="w-4 h-4 text-rose-500" />
                  Active Threat Indicators
                </h2>
                <span className="text-[10px] font-mono text-zinc-500">
                  {threats.length} Active Targets
                </span>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {isLoading ? (
                  <div className="text-center py-8 text-zinc-500 text-sm animate-pulse">Loading threat campaigns...</div>
                ) : threats.length === 0 ? (
                  <div className="text-center py-8 text-zinc-500 text-sm italic">No active threat campaigns found for selected scope.</div>
                ) : (
                  threats.map((threat) => (
                    <div
                      key={threat.id}
                      onClick={() => {
                        setSelectedThreatId(threat.id);
                        if (threat.fusion_score) {
                          setFusionConfidence(threat.fusion_score);
                        }
                      }}
                      className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                        (selectedThreatId === threat.id || (!selectedThreatId && threats[0].id === threat.id))
                          ? 'bg-indigo-950/10 border-indigo-500/80 shadow-md shadow-indigo-950/20'
                          : 'bg-zinc-900/20 border-zinc-900 hover:border-zinc-800'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <Flame className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
                        <div className="space-y-1">
                          <h3 className="text-sm font-bold text-white leading-snug">{threat.value}</h3>
                          <div className="flex flex-wrap gap-2 items-center text-[10px] text-zinc-500">
                            <span>Source: {threat.source}</span>
                            <span>•</span>
                            <span className="uppercase font-mono">{threat.indicator_type}</span>
                            <span>•</span>
                            <span>Status: {threat.status}</span>
                          </div>
                          <div className="flex gap-1.5 mt-2">
                            {threat.tags.map((tag) => (
                              <span key={tag} className="text-[9px] bg-zinc-850 text-zinc-400 px-1.5 py-0.5 rounded">
                                #{tag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className="text-right flex flex-col items-end gap-1.5">
                        <span className={`text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getIndicatorColor(threat.fusion_score)}`}>
                          Fusion Score: {threat.fusion_score || 'N/A'}
                        </span>
                        <span className="text-[9px] text-zinc-600 font-mono">
                          {new Date(threat.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right: Threat Context & Fusion Controls */}
            <div className="col-span-4 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Sliders className="w-4 h-4 text-indigo-500" />
                  Adversary & Fusion Context
                </h2>
              </div>

              {selectedThreat ? (
                <div className="flex-1 overflow-y-auto p-4 space-y-5">
                  {/* Actor Details Card */}
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-3">
                    <div className="flex items-center gap-2 text-rose-400">
                      <ShieldAlert className="w-4 h-4" />
                      <span className="text-[10px] uppercase font-bold tracking-wider font-mono">Adversary Profile</span>
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-md font-bold text-white">{selectedThreat.value}</h3>
                      <p className="text-xs text-zinc-400 leading-normal">
                        Active targeting identified against internet-facing endpoints and cloud directories within scope context. Represents high-impact threat techniques.
                      </p>
                    </div>
                    <div className="border-t border-zinc-900 pt-3 space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-zinc-500">Targeting Tactics:</span>
                        <span className="text-zinc-300">Initial Access, Persistence</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-zinc-500">MITRE Techniques:</span>
                        <span className="text-zinc-300 font-mono">T1566, T1190</span>
                      </div>
                    </div>
                  </div>

                  {/* Fusion Control Card */}
                  <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-4">
                    <div className="flex items-center gap-2 text-indigo-400">
                      <Sliders className="w-4 h-4" />
                      <span className="text-[10px] uppercase font-bold tracking-wider font-mono">Alert Fusion Rules</span>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs text-zinc-400 flex justify-between">
                        <span>Confidence Threshold:</span>
                        <span className="font-semibold text-white">{fusionConfidence}%</span>
                      </label>
                      <input
                        type="range"
                        min="10"
                        max="100"
                        value={fusionConfidence}
                        onChange={(e) => setFusionConfidence(parseInt(e.target.value))}
                        className="w-full h-1 bg-zinc-900 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                      />
                    </div>
                    <p className="text-[10px] text-zinc-500 leading-relaxed">
                      Adjusting this slider updates the alert threshold in the active graph topology, directly scaling overall Cyber Risk and Annualized Loss models.
                    </p>
                    <button
                      onClick={handleFuseThreat}
                      disabled={fuseThreatMutation.isPending}
                      className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                    >
                      {fuseThreatMutation.isPending ? 'Fusing...' : 'Apply Threshold'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center p-4 text-center">
                  <p className="text-xs text-zinc-600 italic">Select a threat campaign to view details</p>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function ThreatIntel() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <ThreatIntelContent />
    </RouteGuard>
  );
}
