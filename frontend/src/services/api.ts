import axios from 'axios';
import { useAuthStore } from '../stores/auth';
import { useScopeStore } from '../stores/scope';

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: any) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Global logout routine that cleans stores and handles page redirection
export const logoutUser = (queryClient?: any) => {
  useAuthStore.getState().logout();
  useScopeStore.getState().setSelectedScopeId(null);
  
  if (queryClient) {
    queryClient.clear();
  }

  if (typeof window !== 'undefined') {
    window.location.href = '/login';
  }
};

apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => {
    // Unpack response envelope if standard success payload exists
    if (response.data && response.data.success !== undefined) {
      return response.data;
    }
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    
    // Check if error is 401 and request has not already been retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === '/auth/refresh') {
        // If the refresh endpoint itself failed with 401, clean state and logout
        logoutUser();
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token) => {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(apiClient.request(originalRequest));
            },
            reject: (err) => {
              reject(err);
            },
          });
        });
      }

      isRefreshing = true;

      try {
        const refresh = useAuthStore.getState().refreshToken;
        if (!refresh) {
          throw new Error('No refresh token available');
        }

        // Call the refresh endpoint directly with raw axios to bypass request interceptor
        const res = await axios.post('/api/v1/auth/refresh', {
          refresh_token: refresh,
        });

        // Unpack payload
        const tokens = res.data?.data;
        if (!tokens || !tokens.access_token) {
          throw new Error('Failed to retrieve new tokens');
        }

        // Update stores
        useAuthStore.getState().setTokens(tokens.access_token, tokens.refresh_token || refresh);
        
        isRefreshing = false;
        processQueue(null, tokens.access_token);

        originalRequest.headers.Authorization = `Bearer ${tokens.access_token}`;
        return apiClient.request(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        processQueue(refreshError, null);
        logoutUser();
        return Promise.reject(refreshError);
      }
    }

    // Standardize error formats based on backend error shapes
    const backendError = error.response?.data?.error;
    if (backendError) {
      return Promise.reject(new Error(backendError.message || 'API Error'));
    }
    
    return Promise.reject(error);
  }
);
