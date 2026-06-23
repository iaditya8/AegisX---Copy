'use client';

import React, { useState } from 'react';
import { Target, Plus } from 'lucide-react';
import { Sidebar } from '../../components/navigation/Sidebar';
import { Topbar } from '../../components/navigation/Topbar';
import { RouteGuard } from '../../components/auth/RouteGuard';
import { ScopeTable } from '../../components/scopes/ScopeTable';
import { ScopeForm } from '../../components/scopes/ScopeForm';
import { useScopes, useCreateScope, useUpdateScope } from '../../hooks/useScopes';
import { useAuthStore } from '../../stores/auth';
import { Scope } from '../../types/scope';

function ScopesContent() {
  const { user } = useAuthStore();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingScope, setEditingScope] = useState<Scope | null>(null);

  const { data: scopesResponse, isLoading, error } = useScopes();
  const createMutation = useCreateScope();
  const updateMutation = useUpdateScope();

  const isWriter = user?.role === 'admin' || user?.role === 'operator';
  const scopes = scopesResponse?.data || [];

  const handleCreateOrUpdate = (data: any) => {
    if (editingScope) {
      updateMutation.mutate(
        { id: editingScope.id, data },
        {
          onSuccess: () => {
            setIsFormOpen(false);
            setEditingScope(null);
          },
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => {
          setIsFormOpen(false);
        },
      });
    }
  };

  const handleEditTrigger = (scope: Scope) => {
    setEditingScope(scope);
    setIsFormOpen(true);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Header Panel */}
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-gradient-to-r from-zinc-900 via-zinc-900 to-indigo-950/20 rounded-xl border border-zinc-900 shadow-xl">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-indigo-500" />
                <h1 className="text-2xl font-bold text-white tracking-tight">Scope Configurator</h1>
              </div>
              <p className="text-zinc-400 text-xs leading-normal max-w-xl">
                Define the asset target borders. Configure network cidr, DNS entries, and target groups.
              </p>
            </div>
            {isWriter && (
              <button
                onClick={() => {
                  setEditingScope(null);
                  setIsFormOpen(true);
                }}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-lg shadow-indigo-900/20 cursor-pointer transition-colors"
              >
                <Plus className="h-4 w-4" />
                Onboard Scope
              </button>
            )}
          </div>

          {/* Table Container */}
          {error ? (
            <div className="p-6 rounded-xl border border-red-950 bg-red-950/10 text-red-400 text-xs font-mono">
              System request failed: {error.message || 'Could not fetch scopes'}
            </div>
          ) : (
            <div className="bg-zinc-950/20 rounded-xl border border-zinc-900 p-6 shadow-xl">
              <ScopeTable scopes={scopes} isLoading={isLoading} onEdit={handleEditTrigger} />
            </div>
          )}
        </main>
      </div>

      <ScopeForm
        isOpen={isFormOpen}
        onClose={() => {
          setIsFormOpen(false);
          setEditingScope(null);
        }}
        onSubmit={handleCreateOrUpdate}
        initialData={editingScope}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />
    </div>
  );
}

export default function ScopesPage() {
  return (
    <RouteGuard allowedRoles={['admin', 'operator', 'reader']}>
      <ScopesContent />
    </RouteGuard>
  );
}
