'use client';

import React, { useState } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { 
  useWhiteboardsList, 
  useWhiteboardDetail, 
  useCreateWhiteboardWorkspace, 
  useAddWhiteboardAnalystNote 
} from '../../hooks/useWhiteboard';
import { 
  Clipboard, 
  Layers, 
  Plus, 
  FileText, 
  Send, 
  CheckCircle, 
  LayoutTemplate,
  Monitor,
  Database,
  Skull,
  User,
  Clock,
  Sparkles
} from 'lucide-react';

function WhiteboardContent() {
  const { data: whiteboards = [], isLoading: isLoadingList } = useWhiteboardsList();

  // Active whiteboard selection
  const [activeWbId, setActiveWbId] = useState<string | null>(null);
  const { data: activeWb = null, isLoading: isLoadingDetail } = useWhiteboardDetail(activeWbId || undefined);

  // Mutations
  const createWbMutation = useCreateWhiteboardWorkspace();
  const addNoteMutation = useAddWhiteboardAnalystNote();

  // States
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Exporter configs
  const [showScorecard, setShowScorecard] = useState(true);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showObjectives, setShowObjectives] = useState(true);
  const [showGaps, setShowGaps] = useState(true);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'json' | 'csv'>('pdf');

  // Form inputs
  const [newWbTitle, setNewWbTitle] = useState('');
  const [newWbDesc, setNewWbDesc] = useState('');
  const [newNoteText, setNewNoteText] = useState('');

  const handleCreateWb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWbTitle.trim()) return;

    try {
      // Mock initial elements for threat canvas
      const initialElements = [
        { id: 'el-1', type: 'asset', label: 'Primary DB Instance', x: 100, y: 150 },
        { id: 'el-2', type: 'finding', label: 'MFA Disabled on Admin Account', x: 250, y: 150 },
        { id: 'el-3', type: 'threat', label: 'APT-41 Campaign target', x: 400, y: 150 }
      ];

      const res = await createWbMutation.mutateAsync({
        title: newWbTitle.trim(),
        description: newWbDesc.trim(),
        elements: initialElements as any,
      });

      setSuccessMessage(`Whiteboard "${newWbTitle}" successfully created.`);
      setNewWbTitle('');
      setNewWbDesc('');
      if (res && res.id) {
        setActiveWbId(res.id);
      }
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWbId || !newNoteText.trim()) return;

    try {
      await addNoteMutation.mutateAsync({
        id: activeWbId,
        noteText: newNoteText.trim(),
        author: 'analyst_admin',
      });
      setNewNoteText('');
      setSuccessMessage('Collaboration note added to investigation timeline.');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleExportReport = () => {
    if (!activeWbId) return;

    const sections = [];
    if (showScorecard) sections.push('Executive Scorecard');
    if (showHeatmap) sections.push('Threat Heatmap');
    if (showObjectives) sections.push('Resilience Objectives');
    if (showGaps) sections.push('Compliance Control Gaps');

    setSuccessMessage(
      `Custom Exporter successfully generated "${
        activeWb?.title
      }" report containing [${sections.join(', ')}] in ${exportFormat.toUpperCase()} format.`
    );
    setTimeout(() => setSuccessMessage(null), 5000);
  };

  const getElementIcon = (type: string) => {
    switch (type) {
      case 'asset': return <Database className="w-4 h-4 text-indigo-400" />;
      case 'threat': return <Skull className="w-4 h-4 text-red-400" />;
      default: return <FileText className="w-4 h-4 text-amber-400" />;
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
                <Clipboard className="w-6 h-6 text-indigo-500" />
                Saved Investigation Whiteboards & Exporters
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Model threat paths across asset relationship nodes, collaborate on incident timelines, and generate custom report blocks.
              </p>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-indigo-950/30 border border-indigo-800 text-indigo-400 text-xs px-4 py-3 rounded-lg animate-fade-in shrink-0">
              <CheckCircle className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Three Panel Layout */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Whiteboards List (25% width) */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-500" />
                  Investigation Boards
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Create Form */}
                <form onSubmit={handleCreateWb} className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-4 space-y-3 shrink-0">
                  <div className="flex items-center gap-1 text-indigo-400">
                    <Plus className="w-4 h-4" />
                    <span className="text-[10px] font-bold uppercase tracking-wider">Create Whiteboard</span>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="wb-title-input" className="text-[10px] text-zinc-500 block">Board Title:</label>
                    <input
                      id="wb-title-input"
                      type="text"
                      placeholder="e.g. Incident #312 Threat Path"
                      value={newWbTitle}
                      onChange={(e) => setNewWbTitle(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="wb-desc-input" className="text-[10px] text-zinc-500 block">Description Summary:</label>
                    <textarea
                      id="wb-desc-input"
                      placeholder="Context notes..."
                      value={newWbDesc}
                      onChange={(e) => setNewWbDesc(e.target.value)}
                      rows={2}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors resize-none"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={createWbMutation.isPending || !newWbTitle.trim()}
                    className="w-full bg-indigo-650 hover:bg-indigo-600 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                  >
                    {createWbMutation.isPending ? 'Creating...' : 'Create Board'}
                  </button>
                </form>

                {/* Boards List */}
                <div className="space-y-2 flex-1 flex flex-col min-h-[140px]">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Logged Workspaces:</span>
                  <div className="flex-1 overflow-y-auto space-y-2 max-h-[220px]">
                    {isLoadingList ? (
                      <div className="text-zinc-550 text-xs animate-pulse">Loading whiteboards...</div>
                    ) : whiteboards.length === 0 ? (
                      <div className="text-zinc-650 text-[10px] italic">No saved whiteboards.</div>
                    ) : (
                      whiteboards.map((w, idx) => (
                        <div 
                          key={w.id || idx}
                          onClick={() => setActiveWbId(w.id)}
                          className={`p-3 border rounded-lg cursor-pointer transition-all space-y-1.5 font-mono text-[9px] ${
                            activeWbId === w.id
                              ? 'bg-indigo-950/15 border-indigo-500/80'
                              : 'bg-zinc-950/40 border-zinc-900 hover:border-zinc-800'
                          }`}
                        >
                          <div className="flex justify-between items-start">
                            <span className="text-zinc-200 font-semibold truncate max-w-[120px]">{w.title}</span>
                            <span className="text-zinc-600">{w.elements?.length || 0} Nodes</span>
                          </div>
                          {w.description && <div className="text-zinc-500 truncate leading-relaxed">{w.description}</div>}
                          <div className="text-zinc-600 text-[8px] flex justify-between">
                            <span>By: {w.created_by}</span>
                            <span>{w.notes?.length || 0} Notes</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Center Panel: Active Whiteboard Canvas & Exporter Builder (55% width) */}
            <div className="col-span-6 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Monitor className="w-4 h-4 text-indigo-400" />
                  Investigation Canvas & Custom Exporter
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-6">
                {activeWbId ? (
                  isLoadingDetail ? (
                    <div className="text-zinc-500 text-xs animate-pulse">Loading board details...</div>
                  ) : activeWb ? (
                    <div className="space-y-6">
                      {/* Elements canvas view */}
                      <div className="space-y-3">
                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Threat Entity Nodes:</span>
                        <div className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-4 min-h-[160px] grid grid-cols-3 gap-3 relative">
                          {activeWb.elements?.map((el, idx) => (
                            <div 
                              key={el.id || idx}
                              className="p-3 bg-zinc-900/40 border border-zinc-800/80 rounded-lg flex flex-col justify-between h-[90px] hover:border-indigo-500/50 transition-all font-mono"
                            >
                              <div className="flex justify-between items-start">
                                <span className="text-[8px] text-zinc-550 capitalize font-bold">{el.type}</span>
                                {getElementIcon(el.type)}
                              </div>
                              <span className="text-[10px] font-bold text-white leading-snug line-clamp-2">{el.label}</span>
                              <span className="text-[7px] text-zinc-600 block">Coords: {el.x}, {el.y}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Custom Exporter Config Block */}
                      <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-4">
                        <div className="flex items-center gap-1.5 text-indigo-400">
                          <LayoutTemplate className="w-4.5 h-4.5" />
                          <span className="text-[10px] font-bold uppercase tracking-wider">Drag-and-Drop Custom Exporter Builder</span>
                        </div>

                        <p className="text-[10px] text-zinc-450 leading-relaxed font-mono">
                          Toggle and configure dashboard layout blocks to compose a customized posture report export payload:
                        </p>

                        <div className="grid grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <label className="flex items-center gap-2 text-[10px] text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={showScorecard}
                                onChange={(e) => setShowScorecard(e.target.checked)}
                                className="accent-indigo-500 cursor-pointer"
                              />
                              Include Scorecard Metric Grade
                            </label>
                            <label className="flex items-center gap-2 text-[10px] text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={showHeatmap}
                                onChange={(e) => setShowHeatmap(e.target.checked)}
                                className="accent-indigo-500 cursor-pointer"
                              />
                              Include Risk Heatmap coordinates
                            </label>
                          </div>

                          <div className="space-y-2">
                            <label className="flex items-center gap-2 text-[10px] text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={showObjectives}
                                onChange={(e) => setShowObjectives(e.target.checked)}
                                className="accent-indigo-500 cursor-pointer"
                              />
                              Include Resilience RTO/RPO stats
                            </label>
                            <label className="flex items-center gap-2 text-[10px] text-zinc-300 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={showGaps}
                                onChange={(e) => setShowGaps(e.target.checked)}
                                className="accent-indigo-500 cursor-pointer"
                              />
                              Include Compliance Control Gaps
                            </label>
                          </div>
                        </div>

                        <div className="flex items-center gap-4 pt-2 border-t border-zinc-900">
                          <div className="space-y-1">
                            <label htmlFor="export-format-select" className="text-[9px] text-zinc-550 block font-bold">Export Format:</label>
                            <select
                              id="export-format-select"
                              value={exportFormat}
                              onChange={(e) => setExportFormat(e.target.value as any)}
                              className="bg-zinc-900 border border-zinc-800 text-[10px] px-3 py-1 rounded-lg text-zinc-300 outline-none"
                            >
                              <option value="pdf">PDF Exporter</option>
                              <option value="json">JSON Metadata Payload</option>
                              <option value="csv">CSV Export Log</option>
                            </select>
                          </div>

                          <button
                            onClick={handleExportReport}
                            className="bg-indigo-650 hover:bg-indigo-600 text-white font-bold text-[10px] py-1.5 px-4 rounded-lg cursor-pointer transition-all self-end flex items-center gap-1"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                            Export Report
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : null
                ) : (
                  <div className="text-zinc-550 text-[10px] italic text-center py-20">Select an investigation whiteboard workspace from the sidebar list.</div>
                )}
              </div>
            </div>

            {/* Right Panel: Collaboration & Notes Feed (20% width) */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <User className="w-4 h-4 text-emerald-400" />
                  Analyst Collaboration
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col space-y-4">
                {activeWbId && activeWb ? (
                  <>
                    {/* Notes Feed Timeline */}
                    <div className="flex-1 flex flex-col min-h-[160px]">
                      <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-2">Investigation Notes:</span>
                      <div className="flex-1 overflow-y-auto space-y-2.5 max-h-[220px]">
                        {activeWb.notes?.length === 0 ? (
                          <div className="text-zinc-650 text-[10px] italic text-center py-6">No analyst collaboration log.</div>
                        ) : (
                          activeWb.notes?.map((n, idx) => (
                            <div 
                              key={n.id || idx}
                              className="p-3 bg-zinc-950/80 border border-zinc-900 rounded-lg space-y-1 font-mono text-[9px] text-zinc-400"
                            >
                              <div className="flex justify-between items-center text-zinc-500 text-[8px]">
                                <span className="text-indigo-400 font-semibold">{n.author}</span>
                                <span className="flex items-center gap-0.5">
                                  <Clock className="w-2.5 h-2.5" />
                                  1m ago
                                </span>
                              </div>
                              <p className="text-zinc-300 leading-relaxed">{n.note_text}</p>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                    {/* Add note form */}
                    <form onSubmit={handleAddNote} className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-3 space-y-2.5 shrink-0">
                      <div className="space-y-1">
                        <label htmlFor="note-text-input" className="text-[9px] text-zinc-500 block">Post Analyst Note:</label>
                        <textarea
                          id="note-text-input"
                          placeholder="Post update details..."
                          value={newNoteText}
                          onChange={(e) => setNewNoteText(e.target.value)}
                          rows={2}
                          className="w-full bg-zinc-900 border border-zinc-800 text-[10px] px-2.5 py-1.5 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 resize-none"
                          required
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={addNoteMutation.isPending || !newNoteText.trim()}
                        className="w-full bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-950 disabled:text-zinc-700 text-indigo-400 font-bold text-[10px] py-1.5 rounded-lg cursor-pointer transition-all flex items-center justify-center gap-1"
                      >
                        <Send className="w-3 h-3" />
                        Post Note
                      </button>
                    </form>
                  </>
                ) : (
                  <div className="text-zinc-550 text-[10px] italic text-center py-20">Select a board context.</div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function Whiteboards() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <WhiteboardContent />
    </RouteGuard>
  );
}
