import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import { useCopilotStore } from './stores/copilot';
import { Topbar } from './components/navigation/Topbar';

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/dashboard',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 48 Security Intelligence Copilot Drawer', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: 'user-admin',
      username: 'analyst_admin',
      role: 'admin',
    });
    useScopeStore.getState().setSelectedScopeId('scope-123');
    useCopilotStore.getState().setIsOpen(false);
    useCopilotStore.getState().clearMessages();
  });

  it('toggles copilot drawer layout from Topbar trigger', async () => {
    renderWithProviders(<Topbar />);

    // Click Copilot toggle button
    const copilotBtn = screen.getByRole('button', { name: 'Copilot' });
    fireEvent.click(copilotBtn);

    // Verify drawer headers and safety warnings
    await waitFor(() => {
      expect(screen.getByText('AegisX AI Copilot')).toBeDefined();
      expect(screen.getByText('Advisory Only')).toBeDefined();
      expect(screen.getByPlaceholderText('Ask advisory question...')).toBeDefined();
    });
  });

  it('posts prompts and renders simulated advisory answers with interactive citations', async () => {
    renderWithProviders(<Topbar />);

    // Toggle drawer
    const copilotBtn = screen.getByRole('button', { name: 'Copilot' });
    fireEvent.click(copilotBtn);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Ask advisory question...')).toBeDefined();
    });

    const input = screen.getByPlaceholderText('Ask advisory question...');
    const sendBtn = screen.getByRole('button', { name: 'Send Message' });

    fireEvent.change(input, { target: { value: 'Explain current DB threat exposure' } });
    fireEvent.click(sendBtn);

    // Check message renders
    await waitFor(() => {
      expect(screen.getByText('Explain current DB threat exposure')).toBeDefined();
      expect(screen.getByText(/Based on risk audits, I recommend verifying/i)).toBeDefined();
      expect(screen.getByText('MFA Disabled on Admin Account')).toBeDefined();
      expect(screen.getByText('Primary DB Instance')).toBeDefined();
    });

    // Test clicking a citation tag triggers Inspector view
    const citationLink = screen.getByRole('button', { name: /MFA Disabled on Admin Account/i });
    fireEvent.click(citationLink);

    await waitFor(() => {
      expect(screen.getByText('Citation Inspector: finding')).toBeDefined();
      expect(screen.getByText('Entity ID Reference Key: posture-123')).toBeDefined();
    });
  });

  it('allows clicking quick query suggestions tags to trigger inquiries', async () => {
    renderWithProviders(<Topbar />);

    // Toggle drawer
    const copilotBtn = screen.getByRole('button', { name: 'Copilot' });
    fireEvent.click(copilotBtn);

    await waitFor(() => {
      expect(screen.getByText('Suggested Prompts:')).toBeDefined();
    });

    const suggestion = screen.getByText('What are the critical posture drift items?');
    fireEvent.click(suggestion);

    await waitFor(() => {
      expect(screen.getAllByText('What are the critical posture drift items?').length).toBeGreaterThanOrEqual(1);
    });
  });
});
