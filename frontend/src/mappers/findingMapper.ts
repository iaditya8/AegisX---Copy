import { Finding, FindingEvidence } from '../types/finding';

export const mapFinding = (data: any): Finding => ({
  id: data.id,
  asset_id: data.asset_id,
  asset_port_id: data.asset_port_id || null,
  asset_service_id: data.asset_service_id || null,
  title: data.title,
  description: data.description || null,
  severity: data.severity,
  status: data.status,
  template_id: data.template_id,
  template_name: data.template_name,
  source_plugin: data.source_plugin,
  first_seen: data.first_seen,
  last_seen: data.last_seen,
  created_at: data.created_at,
  updated_at: data.updated_at,
  fingerprint: data.fingerprint,
  metadata_json: data.metadata_json || {},
});

export const mapFindings = (data: any[]): Finding[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapFinding);
};

export const mapFindingEvidence = (data: any): FindingEvidence => ({
  id: data.id,
  finding_id: data.finding_id,
  evidence_type: data.evidence_type,
  raw_request: data.raw_request || null,
  raw_response: data.raw_response || null,
  matched_at: data.matched_at || null,
  matcher_name: data.matcher_name || null,
  matcher_value: data.matcher_value || null,
  metadata_json: data.metadata_json || {},
  evidence_hash: data.evidence_hash,
  created_at: data.created_at,
});

export const mapFindingEvidences = (data: any[]): FindingEvidence[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapFindingEvidence);
};
