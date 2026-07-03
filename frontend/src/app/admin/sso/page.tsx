'use client';

import React, { useState, useEffect } from 'react';
import { RouteGuard } from '../../../components/auth/RouteGuard';
import { Sidebar } from '../../../components/navigation/Sidebar';
import { Topbar } from '../../../components/navigation/Topbar';
import { 
  useTenantsList, 
  useSSOConfiguration, 
  useCreateTenantWorkspace, 
  useUpdateSSOConfiguration 
} from '../../../hooks/useSSO';
import { 
  Server, 
  Building2, 
  Lock, 
  KeyRound, 
  ToggleLeft, 
  ToggleRight, 
  Plus, 
  CheckCircle2, 
  AlertTriangle,
  Clock,
  ShieldCheck
} from 'lucide-react';

function AdminSsoContent() {
  const { data: tenants = [], isLoading: isLoadingTenants } = useTenantsList();
  const { data: ssoConfig = null, isLoading: isLoadingConfig } = useSSOConfiguration();

  // Mutations
  const createTenantMutation = useCreateTenantWorkspace();
  const updateSSOMutation = useUpdateSSOConfiguration();

  // States
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Tenant Form
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantDomain, setNewTenantDomain] = useState('');
  const [newTenantPlan, setNewTenantPlan] = useState<'starter' | 'enterprise' | 'custom'>('starter');

  // SSO Form States (populated from ssoConfig)
  const [samlEnabled, setSamlEnabled] = useState(false);
  const [idpEntityId, setIdpEntityId] = useState('');
  const [idpSsoUrl, setIdpSsoUrl] = useState('');
  const [x509Cert, setX509Cert] = useState('');

  // Policy States
  const [autoProvision, setAutoProvision] = useState(false);
  const [enforceSso, setEnforceSso] = useState(false);
  const [sessionTimeout, setSessionTimeout] = useState(12);

  // Sync state with fetched config
  useEffect(() => {
    if (ssoConfig) {
      setSamlEnabled(ssoConfig.saml_enabled);
      setIdpEntityId(ssoConfig.idp_entity_id);
      setIdpSsoUrl(ssoConfig.idp_sso_url);
      setX509Cert(ssoConfig.x509_certificate);
      setAutoProvision(ssoConfig.auto_provision_users);
      setEnforceSso(ssoConfig.enforce_sso_for_operators);
      setSessionTimeout(ssoConfig.session_timeout_hours);
    }
  }, [ssoConfig]);

  const handleCreateTenant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTenantName.trim() || !newTenantDomain.trim()) return;

    try {
      await createTenantMutation.mutateAsync({
        name: newTenantName.trim(),
        domain: newTenantDomain.trim(),
        plan: newTenantPlan,
      });
      setSuccessMsg(`Workspace directory "${newTenantName}" successfully created.`);
      setNewTenantName('');
      setNewTenantDomain('');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveSSOConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await updateSSOMutation.mutateAsync({
        saml_enabled: samlEnabled,
        idp_entity_id: idpEntityId,
        idp_sso_url: idpSsoUrl,
        x509_certificate: x509Cert,
        auto_provision_users: autoProvision,
        enforce_sso_for_operators: enforceSso,
        session_timeout_hours: Number(sessionTimeout),
      });
      setSuccessMsg('SAML/OIDC SSO Configuration successfully updated.');
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const getPlanColor = (plan: string) => {
    switch (plan) {
      case 'enterprise': return 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400';
      case 'custom': return 'bg-purple-500/10 border-purple-500/20 text-purple-400';
      default: return 'bg-zinc-700/15 border-zinc-700/30 text-zinc-400';
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-200">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />

        <main className="flex-1 overflow-hidden p-6 flex flex-col space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between bg-zinc-900/40 border border-zinc-800/80 px-6 py-4 rounded-xl backdrop-blur-md">
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                <Server className="w-6 h-6 text-indigo-500" />
                SaaS Multi-Tenancy & SSO Console
              </h1>
              <p className="text-zinc-500 text-xs mt-0.5">
                Manage organization workspaces, configure SAML/OIDC Single Sign-On, and enforce user access isolation policies.
              </p>
            </div>
          </div>

          {successMsg && (
            <div className="flex items-center gap-2.5 bg-indigo-950/30 border border-indigo-800 text-indigo-400 text-xs px-4 py-3 rounded-lg animate-fade-in shrink-0">
              <CheckCircle2 className="w-4.5 h-4.5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Three-Panel Grid */}
          <div className="flex-1 grid grid-cols-12 gap-5 overflow-hidden">
            {/* Left Panel: Tenants Directory (30% width) */}
            <div className="col-span-4 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-indigo-500" />
                  Tenants & Workspaces
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {/* Add Tenant mini-form */}
                <form onSubmit={handleCreateTenant} className="bg-zinc-950/50 border border-zinc-900 rounded-xl p-4 space-y-3 shrink-0">
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider block">Provision Workspace</span>
                  <div className="space-y-1.5">
                    <label htmlFor="tenant-name-input" className="text-[10px] text-zinc-500 block">Workspace Name:</label>
                    <input
                      id="tenant-name-input"
                      type="text"
                      placeholder="e.g. Acme Corp Primary"
                      value={newTenantName}
                      onChange={(e) => setNewTenantName(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="tenant-domain-input" className="text-[10px] text-zinc-500 block">Allowed Domain Pattern:</label>
                    <input
                      id="tenant-domain-input"
                      type="text"
                      placeholder="e.g. acme.com"
                      value={newTenantDomain}
                      onChange={(e) => setNewTenantDomain(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="tenant-plan-select" className="text-[10px] text-zinc-500 block">Plan:</label>
                    <select
                      id="tenant-plan-select"
                      value={newTenantPlan}
                      onChange={(e) => setNewTenantPlan(e.target.value as any)}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors"
                    >
                      <option value="starter">Starter</option>
                      <option value="enterprise">Enterprise</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>
                  <button
                    type="submit"
                    disabled={createTenantMutation.isPending || !newTenantName.trim()}
                    className="w-full bg-indigo-650 hover:bg-indigo-600 disabled:bg-zinc-800 disabled:text-zinc-650 text-white font-semibold text-xs py-2 rounded-lg transition-all cursor-pointer text-center"
                  >
                    {createTenantMutation.isPending ? 'Provisioning...' : 'Provision Tenant'}
                  </button>
                </form>

                {/* Directory List */}
                <div className="space-y-2">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Workspaces Directory:</span>
                  <div className="space-y-2.5">
                    {isLoadingTenants ? (
                      <div className="text-zinc-550 text-xs animate-pulse">Loading directory...</div>
                    ) : tenants.length === 0 ? (
                      <div className="text-zinc-650 text-[10px] italic">No active workspaces logged.</div>
                    ) : (
                      tenants.map((t, idx) => (
                        <div 
                          key={t.id || idx}
                          className="p-3 bg-zinc-950/40 border border-zinc-900 hover:border-zinc-800 rounded-lg space-y-1.5 transition-all"
                        >
                          <div className="flex justify-between items-start">
                            <h3 className="text-xs font-bold text-white">{t.name}</h3>
                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded capitalize ${getPlanColor(t.subscription_plan)}`}>
                              {t.subscription_plan}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-[9px] text-zinc-550 font-mono">
                            <span>Domain: {t.domain_pattern}</span>
                            <span className="text-emerald-400 capitalize">{t.status}</span>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Center Panel: SAML/OIDC Single Sign-On Form (50% width) */}
            <div className="col-span-5 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <KeyRound className="w-4 h-4 text-indigo-400" />
                  SAML 2.0 / OIDC Configuration
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-5">
                {isLoadingConfig ? (
                  <div className="text-zinc-550 text-xs animate-pulse">Loading configuration parameters...</div>
                ) : (
                  <form onSubmit={handleSaveSSOConfig} className="space-y-5">
                    {/* Toggle SAML */}
                    <div className="flex items-center justify-between bg-zinc-950/30 border border-zinc-900 p-4 rounded-xl">
                      <div className="space-y-0.5">
                        <span className="text-xs font-bold text-white block">Enable SAML Single Sign-On (SSO)</span>
                        <p className="text-[10px] text-zinc-550 leading-relaxed">
                          Redirect non-admin workspace logins to the configured Identity Provider (IdP).
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSamlEnabled(!samlEnabled)}
                        className="text-zinc-300 focus:outline-none cursor-pointer"
                      >
                        {samlEnabled ? (
                          <ToggleRight className="w-8 h-8 text-indigo-500" />
                        ) : (
                          <ToggleLeft className="w-8 h-8 text-zinc-650" />
                        )}
                      </button>
                    </div>

                    {samlEnabled && (
                      <div className="space-y-4 animate-fade-in">
                        <div className="space-y-1.5">
                          <label htmlFor="idp-entity-id-input" className="text-[10px] text-zinc-500 block">Identity Provider (IdP) Entity ID:</label>
                          <input
                            id="idp-entity-id-input"
                            type="text"
                            placeholder="urn:amazon:cognito:sp:aegisx"
                            value={idpEntityId}
                            onChange={(e) => setIdpEntityId(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2.5 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors font-mono"
                            required
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="idp-sso-url-input" className="text-[10px] text-zinc-500 block">IdP SSO Target Login URL:</label>
                          <input
                            id="idp-sso-url-input"
                            type="url"
                            placeholder="https://idp.aegiscorp.com/adfs/ls/"
                            value={idpSsoUrl}
                            onChange={(e) => setIdpSsoUrl(e.target.value)}
                            className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2.5 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors font-mono"
                            required
                          />
                        </div>

                        <div className="space-y-1.5">
                          <label htmlFor="x509-cert-input" className="text-[10px] text-zinc-500 block">X.509 Signature Public Certificate:</label>
                          <textarea
                            id="x509-cert-input"
                            placeholder="-----BEGIN CERTIFICATE-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END CERTIFICATE-----"
                            value={x509Cert}
                            onChange={(e) => setX509Cert(e.target.value)}
                            rows={4}
                            className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-2.5 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 transition-colors font-mono resize-none leading-relaxed"
                            required
                          />
                        </div>
                      </div>
                    )}

                    <button
                      type="submit"
                      disabled={updateSSOMutation.isPending}
                      className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-zinc-850 text-white font-semibold text-xs py-2.5 px-6 rounded-lg cursor-pointer transition-all shrink-0"
                    >
                      {updateSSOMutation.isPending ? 'Saving...' : 'Save Configuration'}
                    </button>
                  </form>
                )}
              </div>
            </div>

            {/* Right Panel: Workspace Isolation Policies (30% width) */}
            <div className="col-span-3 flex flex-col bg-zinc-900/20 border border-zinc-900 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-zinc-900 bg-zinc-900/10">
                <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Lock className="w-4 h-4 text-emerald-400" />
                  Isolation & Security Policies
                </h2>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-5">
                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-4">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">Access Controls</span>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <span className="text-[11px] font-semibold text-white block">Auto Provision Users</span>
                      <span className="text-[9px] text-zinc-550 block">Auto-create local profile on SSO sign in</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAutoProvision(!autoProvision)}
                      className="text-zinc-300 focus:outline-none cursor-pointer"
                    >
                      {autoProvision ? (
                        <ToggleRight className="w-7 h-7 text-indigo-500" />
                      ) : (
                        <ToggleLeft className="w-7 h-7 text-zinc-650" />
                      )}
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <span className="text-[11px] font-semibold text-white block">Enforce SSO Operators</span>
                      <span className="text-[9px] text-zinc-550 block">Block credentials login for operators</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setEnforceSso(!enforceSso)}
                      className="text-zinc-300 focus:outline-none cursor-pointer"
                    >
                      {enforceSso ? (
                        <ToggleRight className="w-7 h-7 text-indigo-500" />
                      ) : (
                        <ToggleLeft className="w-7 h-7 text-zinc-650" />
                      )}
                    </button>
                  </div>
                </div>

                <div className="bg-zinc-950/40 border border-zinc-900 rounded-xl p-4 space-y-3">
                  <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-zinc-400" />
                    Session Durations
                  </span>
                  <div className="space-y-1.5">
                    <label htmlFor="session-timeout-input" className="text-[9px] text-zinc-550 block">Absolute Timeout Hours:</label>
                    <input
                      id="session-timeout-input"
                      type="number"
                      value={sessionTimeout}
                      onChange={(e) => setSessionTimeout(Number(e.target.value))}
                      className="w-full bg-zinc-900 border border-zinc-800 text-xs px-3 py-1.5 rounded-lg outline-none focus:border-indigo-500 text-zinc-300 font-mono"
                      min={1}
                      max={72}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default function AdminSso() {
  return (
    <RouteGuard allowedRoles={['admin']}>
      <AdminSsoContent />
    </RouteGuard>
  );
}
