import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { findingService } from '../services/findings';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useFindings(filters?: {
  severity?: string;
  scanner?: string;
  scope_id?: string;
  asset_id?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: QUERY_KEYS.findings.list(filters || {}),
    queryFn: () => findingService.getFindings(filters),
  });
}

export function useFindingDetails(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.findings.detail(id),
    queryFn: () => findingService.getFindingDetails(id),
    enabled: !!id,
  });
}

export function useFindingEvidence(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.findings.evidence(id),
    queryFn: () => findingService.getFindingEvidence(id),
    enabled: !!id,
  });
}

export function useAcknowledgeFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => findingService.acknowledgeFinding(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['findings', 'list'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.findings.detail(id) });
      queryClient.invalidateQueries({ queryKey: ['reports', 'findings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
    },
  });
}

export function useResolveFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => findingService.resolveFinding(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['findings', 'list'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.findings.detail(id) });
      queryClient.invalidateQueries({ queryKey: ['reports', 'findings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
    },
  });
}

export function useSuppressFinding() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => findingService.suppressFinding(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['findings', 'list'] });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.findings.detail(id) });
      queryClient.invalidateQueries({ queryKey: ['reports', 'findings'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary'] });
    },
  });
}
