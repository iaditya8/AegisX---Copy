import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { postureService } from '../services/posture';
import { QUERY_KEYS } from '../lib/queryKeys';

export function usePostureSummary(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.posture.summary(scopeId),
    queryFn: () => postureService.getPostureSummary(scopeId),
  });
}

export function useSecurityPostures() {
  return useQuery({
    queryKey: QUERY_KEYS.posture.list,
    queryFn: () => postureService.getPostures(),
  });
}

export function useCheckPostureDrift() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scopeId?: string) => postureService.checkPostureDrift(scopeId),
    onSuccess: (_, scopeId) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.posture.summary(scopeId) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.posture.list });
    },
  });
}

export function useUpdatePostureStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: 'accept' | 'mitigate' | 'close';
    }) => postureService.updatePostureStatus(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.posture.list });
    },
  });
}
