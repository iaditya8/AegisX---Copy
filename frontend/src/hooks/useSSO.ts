import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ssoService, SSOConfiguration } from '../services/sso';
import { QUERY_KEYS } from '../lib/queryKeys';

export function useTenantsList() {
  return useQuery({
    queryKey: QUERY_KEYS.tenants.list,
    queryFn: () => ssoService.getTenants(),
  });
}

export function useSSOConfiguration() {
  return useQuery({
    queryKey: QUERY_KEYS.sso.config,
    queryFn: () => ssoService.getSSOConfig(),
  });
}

export function useCreateTenantWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      name,
      domain,
      plan,
    }: {
      name: string;
      domain: string;
      plan: string;
    }) => ssoService.createTenant(name, domain, plan),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.tenants.list });
    },
  });
}

export function useUpdateSSOConfiguration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (config: Partial<SSOConfiguration>) => ssoService.updateSSOConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.sso.config });
    },
  });
}
