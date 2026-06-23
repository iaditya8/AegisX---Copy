import { useQuery } from '@tanstack/react-query';
import { reportService } from '../services/reports';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useDashboardSummary() {
  return useQuery({
    queryKey: QUERY_KEYS.reports.dashboardSummary,
    queryFn: () => reportService.getDashboardSummary(),
  });
}

export function useDashboardTrends(days = 30) {
  return useQuery({
    queryKey: QUERY_KEYS.reports.trends(days),
    queryFn: () => reportService.getDashboardTrends({ days }),
  });
}

export function useExecutiveReport() {
  return useQuery({
    queryKey: QUERY_KEYS.reports.executive,
    queryFn: () => reportService.getExecutiveReport(),
  });
}

export function useFindingsReport(filters?: {
  severity?: string;
  status?: string;
  template?: string;
  asset_id?: string;
}) {
  return useQuery({
    queryKey: QUERY_KEYS.reports.findings(filters || {}),
    queryFn: () => reportService.getFindingsReport(filters),
  });
}

export function useRiskReport() {
  return useQuery({
    queryKey: ['reports', 'risk'] as const,
    queryFn: () => reportService.getRiskReport(),
  });
}

export function useExposureReport() {
  return useQuery({
    queryKey: QUERY_KEYS.reports.exposure,
    queryFn: () => reportService.getExposureReport(),
  });
}
