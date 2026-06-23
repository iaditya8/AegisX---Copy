import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { workflowService } from '../services/workflows';
import { QUERY_KEYS } from '../lib/queryKeys';
import { WorkflowCreate, WorkflowStartRequest } from '../types/workflow';

const TERMINAL_STATES = ['completed', 'failed', 'cancelled'] as const;

export function useWorkflows(params?: { page?: number; page_size?: number; owner_id?: string }) {
  return useQuery({
    queryKey: [...QUERY_KEYS.workflows.list, params],
    queryFn: () => workflowService.getWorkflows(params),
  });
}

export function useWorkflowDetails(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.workflows.detail(id),
    queryFn: () => workflowService.getWorkflowDetails(id),
    enabled: !!id,
  });
}

export function useWorkflowEvents(id: string, params?: { page?: number; page_size?: number }) {
  return useQuery({
    queryKey: [...QUERY_KEYS.workflows.events(id), params],
    queryFn: () => workflowService.getWorkflowEvents(id, params),
    enabled: !!id,
  });
}

export function useScanRunDetails(id: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: QUERY_KEYS.scanRuns.detail(id),
    queryFn: () => workflowService.getScanRunDetails(id),
    enabled: !!id && (options?.enabled ?? true),
    refetchInterval: (query) => {
      const data = query?.state?.data?.data;
      return data?.status && TERMINAL_STATES.includes(data.status as any)
        ? false
        : 5000;
    },
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowCreate) => workflowService.createWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workflows.list });
    },
  });
}

export function useStartWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowStartRequest }) =>
      workflowService.startWorkflow(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workflows.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.workflows.events(variables.id) });
    },
  });
}

export function useCancelScanRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowService.cancelScanRun(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.scanRuns.detail(id) });
    },
  });
}
