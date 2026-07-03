import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { executiveService } from '../services/executive';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useExecutiveReports() {
  return useQuery({
    queryKey: QUERY_KEYS.executive.reports,
    queryFn: () => executiveService.getReports(),
  });
}

export function useExecutiveScorecard(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.executive.scorecard(scopeId),
    queryFn: () => executiveService.getScorecard(scopeId),
  });
}

export function useExecutiveHeatmap(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.executive.heatmap(scopeId),
    queryFn: () => executiveService.getHeatmap(scopeId),
  });
}

export function useCreateExecutiveReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      title,
      description,
      period,
      type,
      scopeId,
    }: {
      title: string;
      description: string;
      period: string;
      type: string;
      scopeId?: string;
    }) => executiveService.createReport(title, description, period, type, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.executive.reports });
    },
  });
}

export function useTransitionReportStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: 'draft' | 'published' | 'archived';
    }) => executiveService.transitionReportStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.executive.reports });
    },
  });
}
