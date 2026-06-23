import { useQuery } from '@tanstack/react-query';
import { assetService } from '../services/assets';
import { reportService } from '../services/reports';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useAssetDetails(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.assets.detail(id),
    queryFn: () => assetService.getAssetDetails(id),
    enabled: !!id,
  });
}

export function useAssetRelationships(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.assets.relationships(id),
    queryFn: () => assetService.getAssetRelationships(id),
    enabled: !!id,
  });
}

export function useAssetHistory(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.assets.history(id),
    queryFn: () => assetService.getAssetRevisionHistory(id),
    enabled: !!id,
  });
}

export function useAssetReport(id: string) {
  return useQuery({
    queryKey: QUERY_KEYS.assets.report(id),
    queryFn: () => reportService.getAssetReport(id),
    enabled: !!id,
  });
}
