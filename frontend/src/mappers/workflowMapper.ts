import { Workflow, ScanRun, WorkflowEvent } from '../types/workflow';

export const mapWorkflow = (data: any): Workflow => ({
  id: data.id,
  name: data.name,
  definition: data.definition || {},
  owner_id: data.owner_id || null,
  state: data.state || 'draft',
  created_at: data.created_at,
  updated_at: data.updated_at,
});

export const mapWorkflows = (data: any[]): Workflow[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapWorkflow);
};

export const mapScanRun = (data: any): ScanRun => ({
  id: data.id,
  workflow_id: data.workflow_id || null,
  scope_id: data.scope_id || null,
  plugin_id: data.plugin_id || null,
  type: data.type,
  status: data.status,
  start_ts: data.start_ts || null,
  end_ts: data.end_ts || null,
  metrics: data.metrics || null,
  created_at: data.created_at,
});

export const mapWorkflowEvent = (data: any): WorkflowEvent => ({
  id: data.id,
  workflow_id: data.workflow_id,
  event_type: data.event_type,
  correlation_id: data.correlation_id || null,
  payload: data.payload || null,
  timestamp: data.timestamp,
});

export const mapWorkflowEvents = (data: any[]): WorkflowEvent[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapWorkflowEvent);
};
