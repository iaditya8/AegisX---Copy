import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import ThreatIntel from './app/threat-intel/page';
import GraphExplorer from './app/graph/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/threat-intel',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 41 Threat Intel Center Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders Threat Intel page with threats list and details panel', async () => {
    renderWithProviders(<ThreatIntel />);

    await waitFor(() => {
      expect(screen.getByText('Threat Intelligence Center')).toBeDefined();
      expect(screen.getAllByText('APT29 Spearphishing Campaign').length).toBeGreaterThan(0);
      expect(screen.getByText('Adversary Profile')).toBeDefined();
    });
  });

  it('allows confidence threshold changes and updates scores successfully via mutation', async () => {
    renderWithProviders(<ThreatIntel />);

    await waitFor(() => {
      expect(screen.getByText('Apply Threshold')).toBeDefined();
    });

    const applyButton = screen.getByText('Apply Threshold');
    fireEvent.click(applyButton);

    await waitFor(() => {
      expect(screen.getByText(/Threat Fusion score successfully updated to 80%/i)).toBeDefined();
    });
  });
});

describe('Sprint 41 Topology Graph Explorer Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders Topology Graph Explorer page with search and controls', async () => {
    renderWithProviders(<GraphExplorer />);

    await waitFor(() => {
      expect(screen.getByText('Topology Graph Explorer')).toBeDefined();
      expect(screen.getByText('Path Tracer')).toBeDefined();
      expect(screen.getByText('Interactive Topology Canvas')).toBeDefined();
    });
  });

  it('performs node search and node inspector clicks', async () => {
    renderWithProviders(<GraphExplorer />);

    // Wait for the select options to be populated (indicates data is fully loaded)
    await waitFor(() => {
      const options = screen.getAllByRole('option');
      const hasThreatOption = options.some((opt) => opt.textContent === 'APT29 Spearphishing Campaign');
      expect(hasThreatOption).toBe(true);
    });

    const searchInput = screen.getByPlaceholderText('Type hostname, IP, threat...');
    fireEvent.change(searchInput, { target: { value: 'APT29' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'APT29 Spearphishing Campaign' })).toBeDefined();
    });

    // Clicking search result pivots / sets center
    const searchResult = screen.getByRole('button', { name: 'APT29 Spearphishing Campaign' });
    fireEvent.click(searchResult);

    // Zoom/Pan controls should be present on Canvas
    expect(screen.getByTitle('Zoom In (+)')).toBeDefined();
    expect(screen.getByTitle('Zoom Out (-)')).toBeDefined();
  });

  it('runs path tracing and displays traced route metrics', async () => {
    renderWithProviders(<GraphExplorer />);

    // Wait for options to load
    await waitFor(() => {
      const options = screen.getAllByRole('option');
      const hasThreatOption = options.some((opt) => opt.textContent === 'APT29 Spearphishing Campaign');
      expect(hasThreatOption).toBe(true);
    });

    // Query selects using accessible labels
    const sourceSelect = screen.getByLabelText('Source Node:');
    const targetSelect = screen.getByLabelText('Target Node:');

    fireEvent.change(sourceSelect, { target: { value: 'threat-123' } });
    fireEvent.change(targetSelect, { target: { value: 'asset-123' } });

    const traceButton = screen.getByText('Trace Path');
    fireEvent.click(traceButton);

    await waitFor(() => {
      expect(screen.getByText('Path Cost:')).toBeDefined();
      expect(screen.getByText('1.5')).toBeDefined();
    });
  });
});
