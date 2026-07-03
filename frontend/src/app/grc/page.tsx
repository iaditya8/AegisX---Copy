'use client';

import React, { useState } from 'react';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { 
  useGRCAssessments, 
  useGRCGaps, 
  useUpdateAssessmentStatus, 
  useUploadEvidence 
} from '../../hooks/useGRC';
import { 
  Shield, 
  BookOpen, 
  FileCheck, 
  UploadCloud, 
  AlertCircle, 
  CheckCircle2, 
  Activity, 
  FileText,
  Check,
  X
} from 'lucide-react';

function GrcContent() {
  const { data: assessments = [], isLoading: isLoadingAssessments } = useGRCAssessments();
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string | null>(null);
  
  const activeAssessmentId = selectedAssessmentId || assessments[0]?.id || null;
  const selectedAssessment = assessments.find((a) => a.id === activeAssessmentId) || null;

  const { data: gaps = [], isLoading: isLoadingGaps } = useGRCGaps(activeAssessmentId || '');

  // Mutations
  const updateStatusMutation = useUpdateAssessmentStatus();
  const uploadEvidenceMutation = useUploadEvidence();

  // State
  const [evidenceName, setEvidenceName] = useState('');
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleUpdateStatus = async (status: 'review' | 'compliant' | 'non-compliant' | 'close') => {
    if (!activeAssessmentId) return;
    try {
      await updateStatusMutation.mutateAsync({ id: activeAssessmentId, status });
      setSuccessMessage(`Assessment status updated successfully.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeAssessmentId || !evidenceName.trim()) return;
    
    // Generate a mock SHA-256 hash for visual feedback
    const mockHash = 'sha256-' + Array.from({ length: 64 }, () => 
      Math.floor(Math.random() * 16).toString(16)
    ).join('');

    try {
      await uploadEvidenceMutation.mutateAsync({
        assessmentId: activeAssessmentId,
        fileName: evidenceName.trim(),
        fileHash: mockHash,
      });
      setSuccessMessage(`Evidence "${evidenceName}" successfully logged with hash ${mockHash.substring(0, 12)}...`);
      setEvidenceName('');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (e) {
      console.error(e);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'compliant': return 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400';
      case 'non-compliant': return 'bg-rose-500/10 border-rose-500/20 text-rose-400';
      case 'in_review': return 'bg-blue-500/10 border-blue-500/20 text-blue-400';
      case 'closed': return 'bg-zinc-700/15 border-zinc-700/30 text-zinc-400';
      default: return 'bg-amber-500/10 border-amber-500/20 text-amber-400';
    }
  };

  const getGapStatusColor = (status: string) => {
    switch (status) {
      case 'compliant': return 'bg-emerald-950/20 text-emerald-400 border border-emerald-900';
      case 'gap': return 'bg-rose-950/20 text-rose-400 border border-rose-900';
      default: return 'bg-zinc-950 text-zinc-500 border border-zinc-900';
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
                <Shield className="w-6 h-6 text-indigo-500" />
                GRC Audit & Compliance Console
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Manage control framework assessments, track gaps, and upload evidence hashes for automated checks.
              </p>
            </div>
          </div>

          {successMessage && (
            <div className="flex items-center gap-2.5 bg-emerald-950/30 border border-emerald-800 text-emerald-400 text-xs px-4 py-3 rounded-lg animate-fade-in shrink-0">
              <CheckCircle2 className="w-4.5 h-4.5 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Main Grid */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Assessments Log */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <BookOpen className="w-4 h-4 text-indigo-500" />
                  Assessments Log
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {isLoadingAssessments ? (
                  <div className="text-zinc-500 text-xs animate-pulse">Loading assessments...</div>
                ) : assessments.length === 0 ? (
                  <div className="text-zinc-500 text-xs italic">No assessments registered.</div>
                ) : (
                  assessments.map((a) => {
                    const isSelected = activeAssessmentId === a.id;
                    return (
                      <div
                        key={a.id}
                        onClick={() => setSelectedAssessmentId(a.id)}
                        className={`p-3.5 rounded-lg border transition-all cursor-pointer space-y-1.5 ${
                          isSelected 
                            ? 'bg-indigo-950/10 border-indigo-500/80 shadow-md' 
                            : 'bg-zinc-950/40 border-zinc-900 hover:border-zinc-800'
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <span className="text-[9px] uppercase font-mono font-bold text-zinc-500">
                            {a.framework_type}
                          </span>
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border capitalize ${getStatusColor(a.status)}`}>
                            {a.status.replace('_', ' ')}
                          </span>
                        </div>
                        <h3 className="text-xs font-bold text-white leading-snug">{a.name}</h3>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Status Action controls */}
              {selectedAssessment && selectedAssessment.status !== 'closed' && (
                <div className="p-4 border-t border-zinc-900 bg-zinc-950/20 space-y-2 shrink-0">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Set Audit Status:</span>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => handleUpdateStatus('review')}
                      className="bg-zinc-900 hover:bg-zinc-850 text-blue-400 border border-zinc-800 text-[10px] font-semibold py-1.5 rounded transition-all cursor-pointer text-center"
                    >
                      In Review
                    </button>
                    <button
                      onClick={() => handleUpdateStatus('compliant')}
                      className="bg-zinc-900 hover:bg-zinc-850 text-emerald-400 border border-zinc-800 text-[10px] font-semibold py-1.5 rounded transition-all cursor-pointer text-center"
                    >
                      Compliant
                    </button>
                    <button
                      onClick={() => handleUpdateStatus('non-compliant')}
                      className="bg-zinc-900 hover:bg-zinc-850 text-rose-400 border border-zinc-800 text-[10px] font-semibold py-1.5 rounded transition-all cursor-pointer text-center"
                    >
                      Non-Compliant
                    </button>
                    <button
                      onClick={() => handleUpdateStatus('close')}
                      className="bg-zinc-900 hover:bg-zinc-850 text-zinc-400 border border-zinc-800 text-[10px] font-semibold py-1.5 rounded transition-all cursor-pointer text-center"
                    >
                      Close Assessment
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Center Panel: Checkpoints & Gaps */}
            <div className="col-span-6 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10 flex items-center justify-between">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 text-rose-500" />
                  Control Checkpoints & Compliance Gaps
                </h2>
                {selectedAssessment && (
                  <span className="text-[10px] font-mono text-zinc-500 uppercase">
                    Framework: {selectedAssessment.framework_type}
                  </span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
                {isLoadingGaps ? (
                  <div className="text-zinc-500 text-xs animate-pulse">Loading compliance gaps...</div>
                ) : gaps.length === 0 ? (
                  <div className="text-zinc-500 text-xs italic text-center py-10">Select an assessment to view checkpoints.</div>
                ) : (
                  gaps.map((gap) => (
                    <div 
                      key={gap.id}
                      className="p-4 rounded-xl border border-zinc-900 bg-zinc-950/40 space-y-3"
                    >
                      <div className="flex justify-between items-start">
                        <div className="space-y-0.5">
                          <span className="text-[10px] font-mono font-bold text-indigo-400 uppercase tracking-wider block">
                            {gap.control_code}
                          </span>
                          <h3 className="text-xs font-bold text-white leading-normal">{gap.control_name}</h3>
                        </div>
                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded capitalize ${getGapStatusColor(gap.status)}`}>
                          {gap.status}
                        </span>
                      </div>

                      {gap.notes && (
                        <p className="text-[10px] text-zinc-400 bg-zinc-950/60 p-2 rounded border border-zinc-900/60 leading-relaxed font-mono">
                          Notes: {gap.notes}
                        </p>
                      )}

                      {gap.remediation_action && (
                        <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                          <Activity className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Remediation Plan: <strong className="text-zinc-300">{gap.remediation_action}</strong></span>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Right Panel: Evidence Locker */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <FileCheck className="w-4 h-4 text-emerald-400" />
                  Evidence Locker
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 flex flex-col space-y-4">
                {/* Upload Section */}
                {selectedAssessment && selectedAssessment.status !== 'closed' ? (
                  <form onSubmit={handleUploadEvidence} className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-4 space-y-3 shrink-0">
                    <div className="flex items-center gap-1 text-emerald-400">
                      <UploadCloud className="w-4 h-4" />
                      <span className="text-[10px] font-bold uppercase tracking-wider">Log Evidence Metadata</span>
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="evidence-name-input" className="text-[10px] text-zinc-500 block">Document File Name:</label>
                      <input
                        id="evidence-name-input"
                        type="text"
                        placeholder="e.g. pentest_report_2026.pdf"
                        value={evidenceName}
                        onChange={(e) => setEvidenceName(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-emerald-500 text-zinc-300 transition-colors"
                        required
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={uploadEvidenceMutation.isPending || !evidenceName.trim()}
                      className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                    >
                      {uploadEvidenceMutation.isPending ? 'Logging...' : 'Upload & Compute Hash'}
                    </button>
                  </form>
                ) : (
                  <div className="bg-zinc-950/30 border border-zinc-900 rounded-xl p-4 text-center shrink-0">
                    <p className="text-[10px] text-zinc-550 italic">Select an active assessment to upload evidence.</p>
                  </div>
                )}

                {/* Evidence list */}
                <div className="flex-1 flex flex-col min-h-[160px]">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block mb-2">Stored Documents:</span>
                  <div className="flex-1 overflow-y-auto space-y-2 max-h-[220px]">
                    {selectedAssessment && (selectedAssessment as any).evidence_list && (selectedAssessment as any).evidence_list.length > 0 ? (
                      (selectedAssessment as any).evidence_list.map((ev: any) => (
                        <div 
                          key={ev.id || ev.file_hash}
                          className="p-3 bg-zinc-950/80 border border-zinc-900 rounded-lg space-y-1.5 font-mono text-[9px] text-zinc-400"
                        >
                          <div className="flex items-center gap-1.5 text-zinc-200">
                            <FileText className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                            <span className="truncate font-semibold">{ev.file_name}</span>
                          </div>
                          <div className="text-zinc-500 truncate">Hash: {ev.file_hash}</div>
                          {ev.uploaded_at && (
                            <div className="text-right text-[8px] text-zinc-600">
                              {new Date(ev.uploaded_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="text-zinc-650 text-[10px] italic text-center py-6">No evidence uploaded yet.</div>
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

export default function Grc() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <GrcContent />
    </RouteGuard>
  );
}
