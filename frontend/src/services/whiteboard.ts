import { apiClient } from './api';

export interface WhiteboardElement {
  id: string;
  type: 'asset' | 'threat' | 'finding' | 'custom';
  label: string;
  x: number;
  y: number;
  properties?: Record<string, any>;
}

export interface WhiteboardNote {
  id: string;
  note_text: string;
  author: string;
  created_at: string;
}

export interface WhiteboardWorkspace {
  id: string;
  title: string;
  description: string;
  elements: WhiteboardElement[];
  notes: WhiteboardNote[];
  created_by: string;
  created_at: string;
}

export const whiteboardService = {
  async getWhiteboards(): Promise<WhiteboardWorkspace[]> {
    const response = await apiClient.get<any, any>('/whiteboards');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getWhiteboardDetails(id: string): Promise<WhiteboardWorkspace> {
    const response = await apiClient.get<any, any>(`/whiteboards/${id}`);
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async createWhiteboard(
    title: string,
    description: string,
    elements: WhiteboardElement[]
  ): Promise<WhiteboardWorkspace> {
    const response = await apiClient.post<any, any>('/whiteboards', {
      title,
      description,
      elements,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async addWhiteboardNote(
    id: string,
    noteText: string,
    author: string
  ): Promise<WhiteboardNote> {
    const response = await apiClient.post<any, any>(`/whiteboards/${id}/notes`, {
      note_text: noteText,
      author,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
