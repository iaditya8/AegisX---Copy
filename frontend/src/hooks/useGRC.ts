import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { grcService } from '../services/grc';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useGRCAssessments() {
  return useQuery({
    queryKey: QUERY_KEYS.grc.assessments,
    queryFn: () => grcService.getAssessments(),
  });
}

export function useGRCFrameworks() {
  return useQuery({
    queryKey: QUERY_KEYS.grc.frameworks,
    queryFn: () => grcService.getFrameworks(),
  });
}

export function useGRCGaps(assessmentId: string) {
  return useQuery({
    queryKey: QUERY_KEYS.grc.gaps(assessmentId),
    queryFn: () => grcService.getGaps(assessmentId),
    enabled: !!assessmentId,
  });
}

export function useGRCSummary(scopeId?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.grc.summary(scopeId),
    queryFn: () => grcService.getSummary(scopeId),
  });
}

export function useCreateAssessment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      description,
      framework,
      scopeId,
    }: {
      name: string;
      description: string;
      framework: string;
      scopeId?: string;
    }) => grcService.createAssessment(name, description, framework, scopeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.grc.assessments });
    },
  });
}

export function useUpdateAssessmentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: 'review' | 'compliant' | 'non-compliant' | 'close';
    }) => grcService.updateAssessmentStatus(id, status),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.grc.assessments });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.grc.gaps(variables.id) });
    },
  });
}

export function useUploadEvidence() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      assessmentId,
      fileName,
      fileHash,
    }: {
      assessmentId: string;
      fileName: string;
      fileHash: string;
    }) => grcService.uploadEvidence(assessmentId, fileName, fileHash),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.grc.assessments });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.grc.gaps(variables.assessmentId) });
    },
  });
}
