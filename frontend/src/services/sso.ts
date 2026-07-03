import { apiClient } from './api';

export interface TenantWorkspace {
  id: string;
  name: string;
  domain_pattern: string;
  subscription_plan: 'starter' | 'enterprise' | 'custom';
  status: 'active' | 'suspended' | 'provisioning';
  created_at: string;
}

export interface SSOConfiguration {
  id: string;
  saml_enabled: boolean;
  idp_entity_id: string;
  idp_sso_url: string;
  x509_certificate: string;
  auto_provision_users: boolean;
  enforce_sso_for_operators: boolean;
  session_timeout_hours: number;
}

export const ssoService = {
  async getTenants(): Promise<TenantWorkspace[]> {
    const response = await apiClient.get<any, any>('/tenants');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async createTenant(
    name: string,
    domain: string,
    plan: string
  ): Promise<TenantWorkspace> {
    const response = await apiClient.post<any, any>('/tenants', {
      name,
      domain_pattern: domain,
      subscription_plan: plan,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getSSOConfig(): Promise<SSOConfiguration> {
    const response = await apiClient.get<any, any>('/sso/config');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async updateSSOConfig(config: Partial<SSOConfiguration>): Promise<SSOConfiguration> {
    const response = await apiClient.post<any, any>('/sso/config', config);
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
