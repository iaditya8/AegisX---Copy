import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { threatService } from '../services/threats';
import { riskService } from '../services/risk';
import { decisionService } from '../services/decisions';
import { graphService } from '../services/graph';
import { planningService } from '../services/planning';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useThreats(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.threats.list(scopeId),
    queryFn: () => threatService.getThreats(scopeId),
  });
}

export function useActiveThreats() {
  return useQuery({
    queryKey: QUERY_KEYS.threats.active,
    queryFn: () => threatService.getActiveThreats(),
  });
}

export function useFuseThreat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, confidence }: { id: string; confidence: number }) =>
      threatService.fuseThreat(id, confidence),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.threats.active });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph.topology });
    },
  });
}

export function useRisks(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.risk.list(scopeId),
    queryFn: () => riskService.getRisks(scopeId),
  });
}

export function useForecasts(riskId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.risk.forecasts(riskId),
    queryFn: () => riskService.getForecasts(riskId),
    enabled: !!riskId,
  });
}

export function useDecisions() {
  return useQuery({
    queryKey: QUERY_KEYS.decisions.list,
    queryFn: () => decisionService.getDecisions(),
  });
}

export function useRecommendedDecisions() {
  return useQuery({
    queryKey: QUERY_KEYS.decisions.recommended,
    queryFn: () => decisionService.getRecommendedDecisions(),
  });
}

export function useCommitDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => decisionService.commitDecision(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.decisions.list });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.decisions.recommended });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.graph.topology });
    },
  });
}

export function useGraphTopology() {
  return useQuery({
    queryKey: QUERY_KEYS.graph.topology,
    queryFn: () => graphService.getTopology(),
  });
}

export function useGraphPath(sourceId: string, targetId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.graph.path(sourceId, targetId),
    queryFn: () => graphService.getPath(sourceId, targetId),
    enabled: !!sourceId && !!targetId,
  });
}

export function usePlans() {
  return useQuery({
    queryKey: QUERY_KEYS.planning.list,
    queryFn: () => planningService.getPlans(),
  });
}

export function useApprovePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => planningService.approvePlan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.planning.list });
    },
  });
}
