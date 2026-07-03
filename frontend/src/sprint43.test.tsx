import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import Grc from './app/grc/page';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/grc',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 43 GRC Audit Console Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-123',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
  });

  it('renders GRC Compliance dashboard with assessments and checkpoints', async () => {
    renderWithProviders(<Grc />);

    await waitFor(() => {
      expect(screen.getByText('GRC Audit & Compliance Console')).toBeDefined();
      expect(screen.getAllByText('ISO 27001 Compliance Audit').length).toBeGreaterThan(0);
      expect(screen.getByText('Control Checkpoints & Compliance Gaps')).toBeDefined();
      expect(screen.getByText('A.12.6.1')).toBeDefined();
      expect(screen.getByText('Management of technical vulnerabilities')).toBeDefined();
    });
  });

  it('allows changing assessment audit status', async () => {
    renderWithProviders(<Grc />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Compliant' })).toBeDefined();
    });

    const compliantBtn = screen.getByRole('button', { name: 'Compliant' });
    fireEvent.click(compliantBtn);

    await waitFor(() => {
      expect(screen.getByText(/Assessment status updated successfully/i)).toBeDefined();
    });
  });

  it('allows uploading compliance evidence file names and generates mock hash log', async () => {
    renderWithProviders(<Grc />);

    await waitFor(() => {
      expect(screen.getByLabelText('Document File Name:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Upload & Compute Hash' })).toBeDefined();
    });

    const fileInput = screen.getByLabelText('Document File Name:');
    const uploadBtn = screen.getByRole('button', { name: 'Upload & Compute Hash' });

    fireEvent.change(fileInput, { target: { value: 'iso27001_evidence_report.pdf' } });
    fireEvent.click(uploadBtn);

    await waitFor(() => {
      expect(screen.getByText(/Evidence "iso27001_evidence_report.pdf" successfully logged with hash/i)).toBeDefined();
    });
  });
});
