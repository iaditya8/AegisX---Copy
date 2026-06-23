export interface Finding {
  id: string;
  asset_id: string;
  asset_port_id?: string | null;
  asset_service_id?: string | null;
  title: string;
  description?: string | null;
  severity: string;
  status: string;
  template_id: string;
  template_name: string;
  source_plugin: string;
  first_seen: string;
  last_seen: string;
  created_at: string;
  updated_at: string;
  fingerprint: string;
  metadata_json?: Record<string, any> | null;
}

export interface FindingEvidence {
  id: string;
  finding_id: string;
  evidence_type: string;
  raw_request?: string | null;
  raw_response?: string | null;
  matched_at?: string | null;
  matcher_name?: string | null;
  matcher_value?: string | null;
  metadata_json?: Record<string, any> | null;
  evidence_hash: string;
  created_at: string;
}
