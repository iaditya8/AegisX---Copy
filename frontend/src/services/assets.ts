import { apiClient } from './api';
import { StandardResponse } from '../types/common';
import { Asset, AssetRelationship, AssetHistory } from '../types/asset';
import { mapAsset, mapAssetRelationships, mapAssetHistoryList } from '../mappers/assetMapper';

export const assetService = {
  async getAssetDetails(id: string): Promise<StandardResponse<Asset>> {
    const response = await apiClient.get<any, StandardResponse<any>>(`/assets/${id}`);
    return {
      ...response,
      data: mapAsset(response.data),
    };
  },

  async getAssetRelationships(id: string): Promise<StandardResponse<AssetRelationship[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>(`/assets/${id}/relationships`);
    return {
      ...response,
      data: mapAssetRelationships(response.data),
    };
  },

  async getAssetRevisionHistory(id: string): Promise<StandardResponse<AssetHistory[]>> {
    const response = await apiClient.get<any, StandardResponse<any[]>>(`/assets/${id}/history`);
    return {
      ...response,
      data: mapAssetHistoryList(response.data),
    };
  },
};
