import React, { useState } from 'react';
import { Edit2, Trash2, CheckCircle2, Circle } from 'lucide-react';
import { Scope } from '../../types/scope';
import { useAuthStore } from '../../stores/auth';
import { useScopeStore } from '../../stores/scope';
import { DataTable, Column } from '../shared/DataTable';
import { StatusBadge } from '../shared/StatusBadge';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { useUpdateScope, useDeleteScope } from '../../hooks/useScopes';

interface ScopeTableProps {
  scopes: Scope[];
  isLoading: boolean;
  onEdit: (scope: Scope) => void;
}

export function ScopeTable({ scopes, isLoading, onEdit }: ScopeTableProps) {
  const { user } = useAuthStore();
  const { selectedScopeId, setSelectedScopeId } = useScopeStore();
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const deleteMutation = useDeleteScope();

  const isWriter = user?.role === 'admin' || user?.role === 'operator';

  const handleDeleteConfirm = () => {
    if (deleteId) {
      deleteMutation.mutate(deleteId, {
        onSuccess: () => {
          if (selectedScopeId === deleteId) {
            setSelectedScopeId(null);
          }
          setDeleteId(null);
        },
      });
    }
  };

  const columns: Column<Scope>[] = [
    {
      key: 'active',
      label: 'Context',
      render: (scope) => {
        const isActive = selectedScopeId === scope.id;
        return (
          <button
            onClick={() => setSelectedScopeId(isActive ? null : scope.id)}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
              isActive
                ? 'bg-indigo-600/10 border-indigo-500/30 text-indigo-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
            }`}
          >
            {isActive ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5" />
                Active
              </>
            ) : (
              <>
                <Circle className="h-3.5 w-3.5" />
                Select
              </>
            )}
          </button>
        );
      },
    },
    {
      key: 'name',
      label: 'Scope Name',
      sortable: true,
      render: (scope) => <span className="font-semibold text-white">{scope.name}</span>,
    },
    {
      key: 'type',
      label: 'Type',
      sortable: true,
      render: (scope) => <StatusBadge value={scope.type} />,
    },
    {
      key: 'definition',
      label: 'Targets Summary',
      render: (scope) => {
        const targets = scope.definition?.targets || [];
        const count = targets.length;
        return (
          <span className="text-xs text-zinc-400 font-mono">
            {count} targets configured
          </span>
        );
      },
    },
    {
      key: 'created_at',
      label: 'Registered On',
      sortable: true,
      render: (scope) => (
        <span className="text-xs text-zinc-500 font-mono">
          {scope.created_at ? new Date(scope.created_at).toLocaleDateString() : '-'}
        </span>
      ),
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (scope) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => onEdit(scope)}
            disabled={!isWriter}
            title={isWriter ? 'Edit Scope' : 'Unauthorized to Edit'}
            className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-zinc-400 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          >
            <Edit2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setDeleteId(scope.id)}
            disabled={!isWriter || deleteMutation.isPending}
            title={isWriter ? 'Delete Scope' : 'Unauthorized to Delete'}
            className="p-1.5 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-red-950/20 text-zinc-400 hover:text-red-400 hover:border-red-950 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={scopes}
        isLoading={isLoading}
        emptyMessage="No scopes defined yet. Click onboarding button to add target hosts."
      />

      <ConfirmDialog
        isOpen={!!deleteId}
        title="Delete target Scope"
        description="Are you sure you want to delete this scope? All asset associations will be removed from context selector."
        confirmLabel="Delete Scope"
        isDestructive
        isLoading={deleteMutation.isPending}
        onConfirm={handleDeleteConfirm}
        onClose={() => setDeleteId(null)}
      />
    </>
  );
}
