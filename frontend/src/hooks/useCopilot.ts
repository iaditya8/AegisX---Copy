import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { copilotService } from '../services/copilot';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useAskCopilot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ prompt, scopeId }: { prompt: string; scopeId?: string }) =>
      copilotService.askCopilot(prompt, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.copilot.history });
    },
  });
}

export function useCopilotHistoryList() {
  return useQuery({
    queryKey: QUERY_KEYS.copilot.history,
    queryFn: () => copilotService.getCopilotHistory(),
  });
}
