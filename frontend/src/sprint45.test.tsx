import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import Executive from './app/executive/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/executive',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 45 Executive Posture Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders executive dashboard with scorecard grade and threat heatmap', async () => {
    renderWithProviders(<Executive />);

    await waitFor(() => {
      expect(screen.getByText('CISO Executive Posture Dashboard & Reports')).toBeDefined();
      expect(screen.getByText('B+')).toBeDefined();
      expect(screen.getByText(/Score Index: 78/i)).toBeDefined();
      expect(screen.getByText('MFA Disabled on Root Account')).toBeDefined();
      expect(screen.getByText('Identity Drift | Source: AWS IAM Audit')).toBeDefined();
    });
  });

  it('allows running on-demand posture drift analysis', async () => {
    renderWithProviders(<Executive />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Run Drift Check' })).toBeDefined();
    });

    const driftBtn = screen.getByRole('button', { name: 'Run Drift Check' });
    fireEvent.click(driftBtn);

    await waitFor(() => {
      expect(screen.getByText(/Posture drift analysis completed. Risk indexes recalculated/i)).toBeDefined();
    });
  });

  it('allows creating a new executive CISO report and publishing it', async () => {
    renderWithProviders(<Executive />);

    await waitFor(() => {
      expect(screen.getByLabelText('Report Title:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Build Report' })).toBeDefined();
    });

    const titleInput = screen.getByLabelText('Report Title:');
    const descInput = screen.getByLabelText('Description Summary:');
    const buildBtn = screen.getByRole('button', { name: 'Build Report' });

    fireEvent.change(titleInput, { target: { value: 'Annual Security Review 2026' } });
    fireEvent.change(descInput, { target: { value: 'Annual posture scorecard metrics.' } });
    fireEvent.click(buildBtn);

    await waitFor(() => {
      expect(screen.getByText(/Executive CISO Report "Annual Security Review 2026" successfully generated/i)).toBeDefined();
    });

    // Test transition publishing
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Publish' })).toBeDefined();
    });

    const publishBtn = screen.getByRole('button', { name: 'Publish' });
    fireEvent.click(publishBtn);

    await waitFor(() => {
      expect(screen.getByText(/Report status updated to PUBLISHED/i)).toBeDefined();
    });
  });
});
