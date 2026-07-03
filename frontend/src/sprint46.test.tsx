import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React from 'react';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { useAuthStore } from './stores/auth';
import AdminSso from './app/admin/sso/page';

const mockPush = vi.fn();

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => '/admin/sso',
}));

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 46 SaaS Multi-Tenancy & SSO Page', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
  });

  it('blocks non-admin roles (operator) from accessing the SSO console', async () => {
    useAuthStore.getState().setUser({
      id: 'user-op',
      username: 'ops_guy',
      role: 'operator',
    });

    renderWithProviders(<AdminSso />);

    await waitFor(() => {
      expect(screen.queryByText('SaaS Multi-Tenancy & SSO Console')).toBeNull();
      expect(mockPush).toHaveBeenCalledWith('/403');
    });
  });

  it('renders SSO console with tenant workspaces list for admin users', async () => {
    useAuthStore.getState().setUser({
      id: 'user-admin',
      username: 'sys_admin',
      role: 'admin',
    });

    renderWithProviders(<AdminSso />);

    await waitFor(() => {
      expect(screen.getByText('SaaS Multi-Tenancy & SSO Console')).toBeDefined();
      expect(screen.getByText('Aegis Corp Primary')).toBeDefined();
      expect(screen.getByText(/Domain: aegiscorp.com/i)).toBeDefined();
    });
  });

  it('allows provisioning new tenant workspaces', async () => {
    useAuthStore.getState().setUser({
      id: 'user-admin',
      username: 'sys_admin',
      role: 'admin',
    });

    renderWithProviders(<AdminSso />);

    await waitFor(() => {
      expect(screen.getByLabelText('Workspace Name:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Provision Tenant' })).toBeDefined();
    });

    const nameInput = screen.getByLabelText('Workspace Name:');
    const domainInput = screen.getByLabelText('Allowed Domain Pattern:');
    const provisionBtn = screen.getByRole('button', { name: 'Provision Tenant' });

    fireEvent.change(nameInput, { target: { value: 'Acme West' } });
    fireEvent.change(domainInput, { target: { value: 'acmewest.com' } });
    fireEvent.click(provisionBtn);

    await waitFor(() => {
      expect(screen.getByText(/Workspace directory "Acme West" successfully created/i)).toBeDefined();
    });
  });

  it('allows updating SAML SSO settings configurations', async () => {
    useAuthStore.getState().setUser({
      id: 'user-admin',
      username: 'sys_admin',
      role: 'admin',
    });

    renderWithProviders(<AdminSso />);

    await waitFor(() => {
      expect(screen.getByLabelText('Identity Provider (IdP) Entity ID:')).toBeDefined();
      expect(screen.getByRole('button', { name: 'Save Configuration' })).toBeDefined();
    });

    const entityInput = screen.getByLabelText('Identity Provider (IdP) Entity ID:');
    const ssoUrlInput = screen.getByLabelText('IdP SSO Target Login URL:');
    const certInput = screen.getByLabelText('X.509 Signature Public Certificate:');
    const saveBtn = screen.getByRole('button', { name: 'Save Configuration' });

    fireEvent.change(entityInput, { target: { value: 'urn:idp:new-cognito' } });
    fireEvent.change(ssoUrlInput, { target: { value: 'https://new-idp.com/adfs/' } });
    fireEvent.change(certInput, { target: { value: '-----BEGIN CERTIFICATE-----\nNEW_MOCK_CERT\n-----END CERTIFICATE-----' } });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText(/SAML\/OIDC SSO Configuration successfully updated/i)).toBeDefined();
    });
  });
});
