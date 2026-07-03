import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { whiteboardService, WhiteboardElement } from '../services/whiteboard';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useWhiteboardsList() {
  return useQuery({
    queryKey: QUERY_KEYS.whiteboard.list,
    queryFn: () => whiteboardService.getWhiteboards(),
  });
}

export function useWhiteboardDetail(id?: string) {
  return useQuery({
    queryKey: QUERY_KEYS.whiteboard.detail(id || ''),
    queryFn: () => whiteboardService.getWhiteboardDetails(id || ''),
    enabled: !!id,
  });
}

export function useCreateWhiteboardWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      title,
      description,
      elements = [],
    }: {
      title: string;
      description: string;
      elements?: WhiteboardElement[];
    }) => whiteboardService.createWhiteboard(title, description, elements),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.whiteboard.list });
    },
  });
}

export function useAddWhiteboardAnalystNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      noteText,
      author,
    }: {
      id: string;
      noteText: string;
      author: string;
    }) => whiteboardService.addWhiteboardNote(id, noteText, author),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.whiteboard.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.whiteboard.list });
    },
  });
}
