import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import Dashboard from './app/page';
import { threatService } from './services/threats';
import { riskService } from './services/risk';
import { decisionService } from './services/decisions';
import { graphService } from './services/graph';
import { planningService } from './services/planning';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 40 Service Integrations with MSW Mocks', () => {
  it('verifies threats service endpoint integration', async () => {
    const threats = await threatService.getThreats();
    expect(threats.length).toBeGreaterThan(0);
    expect(threats[0].value).toBe('APT29 Spearphishing Campaign');
    expect(threats[0].fusion_score).toBe(82);

    const fused = await threatService.fuseThreat('threat-123', 95);
    expect(fused.status).toBe('fused');
    expect(fused.fusion_score).toBe(95);
  });

  it('verifies risk service endpoint integration', async () => {
    const risks = await riskService.getRisks();
    expect(risks.length).toBeGreaterThan(0);
    expect(risks[0].title).toBe('Database Ransomware Exposure');
    expect(risks[0].exposure_value).toBe(250000);

    const forecasts = await riskService.getForecasts('risk-123');
    expect(forecasts.length).toBeGreaterThan(0);
    expect(forecasts[0].p50_loss).toBe(110000);

    const trends = await riskService.getTrends('risk-123');
    expect(trends.length).toBe(4);
    expect(trends[0]).toBe(85.5);

    const summary = await riskService.getSummary('scope-123');
    expect(summary.total_risk_scenarios).toBe(1);
    expect(summary.average_inherent_score).toBe(85.5);
  });

  it('verifies decisions service endpoint integration', async () => {
    const decisions = await decisionService.getDecisions();
    expect(decisions.length).toBeGreaterThan(0);
    expect(decisions[0].option_name).toBe('Deploy WAF & Restrict Ingress Port 8080');

    const committed = await decisionService.commitDecision('decision-123');
    expect(committed.status).toBe('committed');
  });

  it('verifies graph service endpoint integration', async () => {
    const topology = await graphService.getTopology();
    expect(topology.nodes.length).toBeGreaterThan(0);
    expect(topology.nodes.some(n => n.id === 'asset-123')).toBe(true);
  });

  it('verifies planning service endpoint integration', async () => {
    const plans = await planningService.getPlans();
    expect(plans.length).toBeGreaterThan(0);
    expect(plans[0].name).toBe('Autonomous Patching for Port 8080 Vulnerability');

    const approved = await planningService.approvePlan('plan-123');
    expect(approved.status).toBe('approved');
  });
});

describe('Sprint 40 Workspace Panel UI Render and Interaction Tests', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('verifies full page renders with left panel inventory, center topology, and right risk card', async () => {
    renderWithProviders(<Dashboard />);

    // Left Panel Checks
    await waitFor(() => {
      expect(screen.getByText(/attack surface context/i)).toBeDefined();
      expect(screen.getByText('host.example.com')).toBeDefined();
    });

    // Center Panel Checks
    expect(screen.getByText(/security topology map/i)).toBeDefined();

    // Right Panel Checks
    expect(screen.getByText(/quantitative risk profile/i)).toBeDefined();
    expect(screen.getByText(/estimated mean loss exposure/i)).toBeDefined();
  });

  it('verifies Commit Mitigation Plan button sends request and displays success feedback', async () => {
    renderWithProviders(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Commit Mitigation Plan')).toBeDefined();
    });

    const commitButton = screen.getByText('Commit Mitigation Plan');
    fireEvent.click(commitButton);

    await waitFor(() => {
      expect(screen.getByText('Mitigation plan successfully committed to security orchestration queue.')).toBeDefined();
    });
  });
});
