import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scopeService } from '../services/scopes';
import { QUERY_KEYS } from '../lib/queryKeys';
import { ScopeCreate, ScopeUpdate } from '../types/scope';

export function useScopes(params?: { page?: number; page_size?: number; owner_id?: string }) {
  return useQuery({
    queryKey: [...QUERY_KEYS.scopes.list, params],
    queryFn: () => scopeService.getScopes(params),
  });
}

export function useScopeDetails(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.scopes.detail(id),
    queryFn: () => scopeService.getScopeDetails(id),
    enabled: !!id,
  });
}

export function useScopeAssets(
  id: string,
  params?: { page?: number; page_size?: number; host?: string; ip?: string }
) {
  return useQuery({
    queryKey: QUERY_KEYS.scopes.assets(id, params || {}),
    queryFn: () => scopeService.getScopeAssets(id, params),
    enabled: !!id,
  });
}

export function useCreateScope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScopeCreate) => scopeService.createScope(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scopes.list });
    },
  });
}

export function useUpdateScope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScopeUpdate }) =>
      scopeService.updateScope(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scopes.list });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scopes.detail(variables.id) });
    },
  });
}

export function useDeleteScope() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scopeService.deleteScope(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scopes.list });
    },
  });
}
