import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { resilienceService } from '../services/resilience';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useResilienceRecords() {
  return useQuery({
    queryKey: QUERY_KEYS.resilience.list,
    queryFn: () => resilienceService.getResilienceRecords(),
  });
}

export function useResilienceObjectives(resilienceId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.resilience.objectives(resilienceId),
    queryFn: () => resilienceService.getObjectives(resilienceId),
    enabled: !!resilienceId,
  });
}

export function useUpdateResilienceStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: 'activate' | 'validate' | 'complete' | 'close';
    }) => resilienceService.updateResilienceStatus(id, action),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resilience.list });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.resilience.objectives(variables.id) });
    },
  });
}
