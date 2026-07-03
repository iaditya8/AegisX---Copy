import { apiClient } from './api';

export interface GraphNode {
  id: string;
  node_type: string;
  entity_id: string;
  scope_id?: string;
  status: string;
}

export interface GraphEdge {
  id: string;
  source_id: string;
  target_id: string;
  edge_type: string;
  weight: number;
  scope_id?: string;
  status: string;
}

export interface GraphTopology {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const graphService = {
  async getTopology(): Promise<GraphTopology> {
    const response = await apiClient.get<any, any>('/security-intelligence-graph/topology');
    const data = response.success !== undefined ? response.data : (response.data || response);
    return data || { nodes: [], edges: [] };
  },

  async getPath(sourceId: string, targetId: string): Promise<GraphTopology> {
    const response = await apiClient.get<any, any>('/security-intelligence-graph/paths', {
      params: {
        source_node_id: sourceId,
        target_node_id: targetId,
      },
    });
    const data = response.success !== undefined ? response.data : (response.data || response);
    return data || { nodes: [], edges: [] };
  },
};
