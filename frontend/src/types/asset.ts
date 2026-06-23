export interface Asset {
  id: string;
  scope_id?: string | null;
  host?: string | null;
  ip?: string | null;
  asset_type?: string | null;
  metadata_json?: Record<string, any> | null;
  first_seen: string;
  last_seen: string;
  fingerprint?: string | null;
  deleted_at?: string | null;
  deleted_by?: string | null;
}

export interface AssetRelationship {
  id: string;
  source_asset_id: string;
  target_asset_id: string;
  relationship_type: string;
  metadata_json?: Record<string, any> | null;
  created_at: string;
}

export interface AssetHistory {
  id: string;
  asset_id: string;
  change_type: string;
  old_value?: Record<string, any> | null;
  new_value?: Record<string, any> | null;
  timestamp: string;
}
