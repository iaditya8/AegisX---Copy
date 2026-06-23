import { create } from 'zustand';

interface ScopeState {
  selectedScopeId: string | null;
  setSelectedScopeId: (id: string | null) => void;
}

export const useScopeStore = create<ScopeState>((set) => ({
  selectedScopeId: typeof window !== 'undefined' ? localStorage.getItem('selected_scope_id') : null,
  setSelectedScopeId: (id) => {
    if (typeof window !== 'undefined') {
      if (id) localStorage.setItem('selected_scope_id', id);
      else localStorage.removeItem('selected_scope_id');
    }
    set({ selectedScopeId: id });
  },
}));
