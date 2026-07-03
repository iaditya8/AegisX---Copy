import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import Whiteboards from './app/whiteboards/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/whiteboards',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 47 Saved Whiteboards Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-admin',
      username: 'analyst_admin',
      role: 'admin',
    });
  });

  it('renders whiteboards lists and details of selected board workspace', async () => {
    renderWithProviders(<Whiteboards />);

    await waitFor(() => {
      expect(screen.getByText('Saved Investigation Whiteboards & Exporters')).toBeDefined();
      expect(screen.getByText('APT-41 Exploit Path Analysis')).toBeDefined();
    });

    const activeBoard = screen.getByText('APT-41 Exploit Path Analysis');
    fireEvent.click(activeBoard);

    await waitFor(() => {
      expect(screen.getByText('Primary DB Instance')).toBeDefined();
      expect(screen.getByText('Threat Entity Nodes:')).toBeDefined();
      expect(screen.getByText('Threat correlation shows APT-41 actors leveraging exposed SSH ports.')).toBeDefined();
    });
  });

  it('provisions new whiteboard workspaces', async () => {
    renderWithProviders(<Whiteboards />);

    await waitFor(() => {
      expect(screen.getByLabelText('Board Title:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Create Board' })).toBeDefined();
    });

    const titleInput = screen.getByLabelText('Board Title:');
    const descInput = screen.getByLabelText('Description Summary:');
    const createBtn = screen.getByRole('button', { name: 'Create Board' });

    fireEvent.change(titleInput, { target: { value: 'Root Access Exposures' } });
    fireEvent.change(descInput, { target: { value: 'Exposed access key credential analysis.' } });
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(screen.getByText(/Whiteboard "Root Access Exposures" successfully created/i)).toBeDefined();
    });
  });

  it('allows customizing and exporting custom report formats', async () => {
    renderWithProviders(<Whiteboards />);

    await waitFor(() => {
      expect(screen.getByText('APT-41 Exploit Path Analysis')).toBeDefined();
    });

    const activeBoard = screen.getByText('APT-41 Exploit Path Analysis');
    fireEvent.click(activeBoard);

    await waitFor(() => {
      expect(screen.getByText('Include Scorecard Metric Grade')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Export Report' })).toBeDefined();
    });

    const heatmapCheckbox = screen.getByLabelText('Include Risk Heatmap coordinates');
    const exportBtn = screen.getByRole('button', { name: 'Export Report' });

    // Toggle heatmap checkbox
    fireEvent.click(heatmapCheckbox);
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(screen.getByText(/Custom Exporter successfully generated/i)).toBeDefined();
    });
  });

  it('allows posting comments to the investigation collaboration timeline', async () => {
    renderWithProviders(<Whiteboards />);

    await waitFor(() => {
      expect(screen.getByText('APT-41 Exploit Path Analysis')).toBeDefined();
    });

    const activeBoard = screen.getByText('APT-41 Exploit Path Analysis');
    fireEvent.click(activeBoard);

    await waitFor(() => {
      expect(screen.getByLabelText('Post Analyst Note:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Post Note' })).toBeDefined();
    });

    const noteInput = screen.getByLabelText('Post Analyst Note:');
    const postBtn = screen.getByRole('button', { name: 'Post Note' });

    fireEvent.change(noteInput, { target: { value: 'Primary database replication is offline.' } });
    fireEvent.click(postBtn);

    await waitFor(() => {
      expect(screen.getByText(/Collaboration note added to investigation timeline/i)).toBeDefined();
    });
  });
});
