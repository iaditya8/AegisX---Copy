import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import Soc from './app/soc/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/soc',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 44 SOC & Resilience Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders SOC Operations & Cyber Resilience console dashboards', async () => {
    renderWithProviders(<Soc />);

    await waitFor(() => {
      expect(screen.getByText('SOC Operations & Cyber Resilience Console')).toBeDefined();
      expect(screen.getByText('SOC Performance & Queues')).toBeDefined();
      expect(screen.getByText('Sarah Connor')).toBeDefined();
      expect(screen.getByText('John Miller')).toBeDefined();
      expect(screen.getByText('DNS Failover Switchover Time')).toBeDefined();
      expect(screen.getByText('Data Integrity Sync Check')).toBeDefined();
      expect(screen.getAllByText('Primary Database Failover Drill').length).toBeGreaterThan(0);
    });
  });

  it('allows activating a resilience plan via action center', async () => {
    renderWithProviders(<Soc />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Activate Plan' })).toBeDefined();
    });

    const activateBtn = screen.getByRole('button', { name: 'Activate Plan' });
    fireEvent.click(activateBtn);

    await waitFor(() => {
      expect(screen.getByText(/Service resilience plan status updated: ACTIVATE/i)).toBeDefined();
    });
  });
});
