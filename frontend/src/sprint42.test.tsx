import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import Planning from './app/planning/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/planning',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 42 Decision Tradeoffs & Gantt Workbench Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_operator',
      role: 'operator',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders planning workbench page with scatterplot plot and Gantt chart', async () => {
    renderWithProviders(<Planning />);

    await waitFor(() => {
      expect(screen.getByText('Remediation & Planning Workbench')).toBeDefined();
      expect(screen.getByText('Cost vs. Risk Reduction Tradeoffs')).toBeDefined();
      expect(screen.getByText('Active Remediation Plans & Gantt Timelines')).toBeDefined();
      expect(screen.getByText('Tradeoff Scatterplot (Cost vs Risk-Reduction)')).toBeDefined();
    });
  });

  it('verifies recommended decisions list and allows committing selection via mutation', async () => {
    renderWithProviders(<Planning />);

    await waitFor(() => {
      expect(screen.getAllByText('Deploy WAF & Restrict Ingress Port 8080').length).toBeGreaterThan(0);
      expect(screen.getByRole('button', { name: 'Commit Decision' })).toBeDefined();
    });

    const commitBtn = screen.getByRole('button', { name: 'Commit Decision' });
    fireEvent.click(commitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Decision committed: "Deploy WAF & Restrict Ingress Port 8080" has been scheduled/i)).toBeDefined();
    });
  });

  it('verifies Gantt charts timeline task items and allows plan execution approval', async () => {
    renderWithProviders(<Planning />);

    await waitFor(() => {
      expect(screen.getAllByText('Autonomous Patching for Port 8080 Vulnerability').length).toBeGreaterThan(0);
      expect(screen.getByText('Vulnerability Analysis')).toBeDefined();
      expect(screen.getByText('Patch Staging Verification')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Approve & Execute' })).toBeDefined();
    });

    const approveBtn = screen.getByRole('button', { name: 'Approve & Execute' });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(screen.getByText(/Remediation Plan "Autonomous Patching for Port 8080 Vulnerability" has been approved/i)).toBeDefined();
    });
  });
});
