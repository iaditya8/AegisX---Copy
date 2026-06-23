import { Scope } from '../types/scope';

export const mapScope = (data: any): Scope => ({
  id: data.id,
  name: data.name,
  type: data.type,
  definition: data.definition || {},
  owner_id: data.owner_id || null,
  created_at: data.created_at,
  deleted_at: data.deleted_at || null,
  deleted_by: data.deleted_by || null,
});

export const mapScopes = (data: any[]): Scope[] => {
  if (!Array.isArray(data)) return [];
  return data.map(mapScope);
};
