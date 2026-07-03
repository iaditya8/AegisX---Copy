import { useQuery } from '@tanstack/react-query';
import { socService } from '../services/soc';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useSOCQueueSummary() {
  return useQuery({
    queryKey: QUERY_KEYS.soc.queues,
    queryFn: () => socService.getQueueSummary(),
  });
}

export function useSOCKPIs() {
  return useQuery({
    queryKey: QUERY_KEYS.soc.kpis,
    queryFn: () => socService.getKPIs(),
  });
}

export function useSOCAnalysts() {
  return useQuery({
    queryKey: QUERY_KEYS.soc.analysts,
    queryFn: () => socService.getAnalysts(),
  });
}
