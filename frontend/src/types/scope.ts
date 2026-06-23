export interface Scope {
  id: string;
  name: string;
  type: 'domain' | 'cidr' | 'asset-group';
  definition: Record<string, any>;
  owner_id?: string | null;
  created_at: string;
  deleted_at?: string | null;
  deleted_by?: string | null;
}

export interface ScopeCreate {
  name: string;
  type: 'domain' | 'cidr' | 'asset-group';
  definition: Record<string, any>;
}

export interface ScopeUpdate {
  name?: string;
  type?: 'domain' | 'cidr' | 'asset-group';
  definition?: Record<string, any>;
}
