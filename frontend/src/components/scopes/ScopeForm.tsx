import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Scope, ScopeCreate } from '../../types/scope';

interface ScopeFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: ScopeCreate) => void;
  initialData?: Scope | null;
  isLoading?: boolean;
}

export function ScopeForm({ isOpen, onClose, onSubmit, initialData, isLoading = false }: ScopeFormProps) {
  const [name, setName] = useState('');
  const [type, setType] = useState<'domain' | 'cidr' | 'asset-group'>('domain');
  const [definitionRaw, setDefinitionRaw] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialData) {
      setName(initialData.name);
      setType(initialData.type);
      setDefinitionRaw(JSON.stringify(initialData.definition, null, 2));
    } else {
      setName('');
      setType('domain');
      setDefinitionRaw('{\n  "targets": []\n}');
    }
    setError(null);
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Scope name is required.');
      return;
    }

    try {
      const parsedDef = JSON.parse(definitionRaw);
      onSubmit({
        name: name.trim(),
        type,
        definition: parsedDef,
      });
    } catch (err: any) {
      setError(`Invalid JSON definition: ${err.message || 'JSON Syntax Error'}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Container */}
      <div className="relative w-full max-w-lg rounded-xl border border-zinc-900 bg-zinc-950 p-6 shadow-2xl animate-in fade-in zoom-in-95">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        <h3 className="text-lg font-bold text-white tracking-tight mb-4">
          {initialData ? 'Modify Context Scope' : 'Onboard New target Scope'}
        </h3>

        {error && (
          <div className="mb-4 p-3 rounded-lg border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Scope Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Corp External Assets"
              className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg p-2.5 text-sm text-white placeholder-zinc-600 transition-all outline-none"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
              Scope Target Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as any)}
              className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg p-2.5 text-sm text-white transition-all outline-none"
            >
              <option value="domain">Domain Target</option>
              <option value="cidr">CIDR Subnet Block</option>
              <option value="asset-group">Arbitrary Asset Group</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                Configuration Payload (JSON)
              </label>
              <span className="text-[10px] text-zinc-600 font-mono">Key-value parameters</span>
            </div>
            <textarea
              value={definitionRaw}
              onChange={(e) => setDefinitionRaw(e.target.value)}
              rows={6}
              className="w-full bg-zinc-900/60 border border-zinc-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg p-2.5 text-sm font-mono text-zinc-300 placeholder-zinc-700 transition-all outline-none resize-none"
              required
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-zinc-900">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white bg-transparent hover:bg-zinc-900/50 border border-zinc-800 rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md shadow-indigo-900/20 transition-colors cursor-pointer flex items-center gap-1.5"
            >
              {isLoading && (
                <span className="h-3 w-3 animate-spin rounded-full border-t-white border-r-transparent border-b-white border-l-transparent border" />
              )}
              {initialData ? 'Save Changes' : 'Onboard Scope'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
