import { Asset, AssetRelationship, AssetHistory } from '../types/asset';

export const mapAsset = (data: any): Asset => ({
  id: data.id,
  scope_id: data.scope_id || null,
  host: data.host || null,
  ip: data.ip || null,
  asset_type: data.asset_type || null,
  metadata_json: data.metadata_json || {},
  first_seen: data.first_seen,
  last_seen: data.last_seen,
  fingerprint: data.fingerprint || null,
  deleted_at: data.deleted_at || null,
  deleted_by: data.deleted_by || null,
});

export const mapAssets = (data: any[]): Asset[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapAsset);
};

export const mapAssetRelationship = (data: any): AssetRelationship => ({
  id: data.id,
  source_asset_id: data.source_asset_id,
  target_asset_id: data.target_asset_id,
  relationship_type: data.relationship_type,
  metadata_json: data.metadata_json || {},
  created_at: data.created_at,
});

export const mapAssetRelationships = (data: any[]): AssetRelationship[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapAssetRelationship);
};

export const mapAssetHistory = (data: any): AssetHistory => ({
  id: data.id,
  asset_id: data.asset_id,
  change_type: data.change_type,
  old_value: data.old_value || null,
  new_value: data.new_value || null,
  timestamp: data.timestamp,
});

export const mapAssetHistoryList = (data: any[]): AssetHistory[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapAssetHistory);
};
