import { apiClient } from './api';
import { StandardResponse } from '../types/common';
import { Scope, ScopeCreate, ScopeUpdate } from '../types/scope';
import { Asset } from '../types/asset';
import { mapScope, mapScopes } from '../mappers/scopeMapper';
import { mapAssets } from '../mappers/assetMapper';

export const scopeService = {
  async getScopes(params?: {
    page?: number;
    page_size?: number;
    owner_id?: string;
  }): Promise<StandardResponse<Scope[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>('/scopes', { params });
    return {
      ...response,
      data: mapScopes(response.data),
    };
  },

  async createScope(data: ScopeCreate): Promise<StandardResponse<Scope>> {
    const response = await apiClient.post<any, StandardResponse<any>>('/scopes', data);
    return {
      ...response,
      data: mapScope(response.data),
    };
  },

  async getScopeDetails(id: string): Promise<StandardResponse<Scope>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/scopes/${id}`);
    return {
      ...response,
      data: mapScope(response.data),
    };
  },

  async updateScope(id: string, data: ScopeUpdate): Promise<StandardResponse<Scope>> {
    const response = await apiClient.put<any, StandardResponse<any>>(`/scopes/${id}`, data);
    return {
      ...response,
      data: mapScope(response.data),
    };
  },

  async deleteScope(id: string): Promise<StandardResponse<boolean>> {
    const response = await apiClient.delete<any, StandardResponse<boolean>>(`/scopes/${id}`);
    return response;
  },

  async getScopeAssets(
    id: string,
    params?: { page?: number; page_size?: number; host?: string; ip?: string }
  ): Promise<StandardResponse<Asset[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>(`/scopes/${id}/assets`, { params });
    return {
      ...response,
      data: mapAssets(response.data),
    };
  },
};
