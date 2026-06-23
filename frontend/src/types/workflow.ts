export interface Workflow {
  id: string;
  name: string;
  definition: Record<string, any>;
  owner_id?: string | null;
  state: 'draft' | 'active' | 'disabled';
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreate {
  name: string;
  definition: Record<string, any>;
}

export interface WorkflowUpdate {
  name?: string;
  definition?: Record<string, any>;
  state?: 'draft' | 'active' | 'disabled';
}

export interface ScanRun {
  id: string;
  workflow_id?: string | null;
  scope_id?: string | null;
  plugin_id?: string | null;
  type: string;
  status: string;
  start_ts?: string | null;
  end_ts?: string | null;
  metrics?: Record<string, any> | null;
  created_at: string;
}

export interface WorkflowEvent {
  id: string;
  workflow_id: string;
  event_type: string;
  correlation_id?: string | null;
  payload?: Record<string, any> | null;
  timestamp: string;
}

export interface WorkflowStartRequest {
  scope_id: string;
  options?: Record<string, any>;
}

export interface WorkflowStartResponse {
  workflow_id: string;
  run_id: string;
  status: string;
}
