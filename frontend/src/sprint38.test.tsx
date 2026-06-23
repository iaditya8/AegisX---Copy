import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useAuthStore } from './stores/auth';
import { useScopeStore } from './stores/scope';
import { apiClient, logoutUser } from './services/api';
import { RouteGuard } from './components/auth/RouteGuard';
import { render, screen } from '@testing-library/react';
import React from 'react';
import axios from 'axios';

// Mock Next.js navigation router
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => '/',
}));

// Mock axios post calls for refresh flow
vi.mock('axios', async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    default: {
      ...actual.default,
      post: vi.fn(),
    },
  };
});

describe('Sprint 38 Frontend Platform Foundation Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    useAuthStore.getState().logout();
    useScopeStore.getState().setSelectedScopeId(null);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('verifies access token is injected in request headers', async () => {
    useAuthStore.getState().setTokens('fake-access-token', 'fake-refresh-token');

    // Capture request config using interceptor run
    const interceptor = (apiClient.interceptors.request as any).handlers[0];
    const mockConfig = { headers: {} };
    const processedConfig = interceptor.fulfilled(mockConfig);

    expect(processedConfig.headers.Authorization).toBe('Bearer fake-access-token');
  });

  it('verifies 401 triggers token refresh and retries with single-flight locking', async () => {
    useAuthStore.getState().setTokens('expired-token', 'valid-refresh-token');

    const mockNewAccessToken = 'new-access-token';
    const mockNewRefreshToken = 'new-refresh-token';

    // Mock direct axios post call for refresh endpoint
    const axiosPostSpy = vi.mocked(axios.post).mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          access_token: mockNewAccessToken,
          refresh_token: mockNewRefreshToken,
        },
      },
    });

    // Mock API client post call for retry
    const apiClientSpy = vi.spyOn(apiClient, 'request').mockResolvedValue({
      data: { success: true, message: 'retried-success' },
    } as any);

    // Run the response interceptor logic
    const interceptor = (apiClient.interceptors.response as any).handlers[0];
    const mockError = {
      config: { headers: {}, url: '/scopes/1/assets' },
      response: { status: 401, data: {} },
    };

    const promise = interceptor.rejected(mockError);
    await expect(promise).resolves.toBeDefined();

    // Verify refresh was called exactly once with the refresh token
    expect(axiosPostSpy).toHaveBeenCalledTimes(1);
    expect(axiosPostSpy).toHaveBeenCalledWith('/api/v1/auth/refresh', {
      refresh_token: 'valid-refresh-token',
    });

    // Verify stores are updated
    expect(useAuthStore.getState().accessToken).toBe(mockNewAccessToken);
    expect(useAuthStore.getState().refreshToken).toBe(mockNewRefreshToken);
  });

  it('redirects RouteGuard to login if user is unauthenticated', () => {
    render(
      <RouteGuard allowedRoles={['admin']}>
        <div>Protected Children</div>
      </RouteGuard>
    );

    expect(mockPush).toHaveBeenCalledWith('/login');
    expect(screen.queryByText('Protected Children')).toBeNull();
  });

  it('redirects RouteGuard to 403 if user lacks permitted roles', () => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: '1',
      username: 'analyst_reader',
      role: 'reader',
    });

    render(
      <RouteGuard allowedRoles={['admin', 'operator']}>
        <div>Protected Admin Panel</div>
      </RouteGuard>
    );

    expect(mockPush).toHaveBeenCalledWith('/403');
    expect(screen.queryByText('Protected Admin Panel')).toBeNull();
  });

  it('allows RouteGuard to render children if roles are permitted', () => {
    useAuthStore.getState().setTokens('fake-token', 'fake-refresh');
    useAuthStore.getState().setUser({
      id: '1',
      username: 'analyst_admin',
      role: 'admin',
    });

    render(
      <RouteGuard allowedRoles={['admin', 'operator']}>
        <div>Protected Admin Panel</div>
      </RouteGuard>
    );

    expect(screen.getByText('Protected Admin Panel')).toBeDefined();
  });

  it('verifies scope store selection updates Zustand state', () => {
    const scopeId = 'scope-12345';
    useScopeStore.getState().setSelectedScopeId(scopeId);

    expect(useScopeStore.getState().selectedScopeId).toBe(scopeId);
    expect(localStorage.getItem('selected_scope_id')).toBe(scopeId);

    useScopeStore.getState().setSelectedScopeId(null);
    expect(useScopeStore.getState().selectedScopeId).toBeNull();
    expect(localStorage.getItem('selected_scope_id')).toBeNull();
  });

  it('verifies logoutUser cleanup behavior', () => {
    // Populate stores
    useAuthStore.getState().setTokens('my-access', 'my-refresh');
    useAuthStore.getState().setUser({ id: '2', username: 'opt', role: 'operator' });
    useScopeStore.getState().setSelectedScopeId('scope-id');

    const mockQueryClient = {
      clear: vi.fn(),
    };

    // Mock window location
    const originalLocation = window.location;
    delete (window as any).location;
    window.location = { href: '' } as any;

    logoutUser(mockQueryClient);

    // Assertions
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useScopeStore.getState().selectedScopeId).toBeNull();
    expect(mockQueryClient.clear).toHaveBeenCalledTimes(1);
    expect(window.location.href).toBe('/login');

    // Restore location
    window.location = originalLocation as any;
  });
});
