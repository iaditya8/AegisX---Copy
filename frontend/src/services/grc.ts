import { apiClient } from './api';

export interface GrcAssessment {
  id: string;
  name: string;
  description: string;
  framework_type: string;
  status: 'draft' | 'in_review' | 'compliant' | 'non-compliant' | 'closed';
  scope_id?: string;
  created_at: string;
  updated_at: string;
}

export interface GrcGap {
  id: string;
  control_code: string;
  control_name: string;
  status: 'compliant' | 'gap' | 'not_applicable';
  notes?: string;
  remediation_action?: string;
}

export interface GrcEvidence {
  id: string;
  file_name: string;
  file_hash: string;
  uploaded_at: string;
}

export const grcService = {
  async getAssessments(): Promise<GrcAssessment[]> {
    const response = await apiClient.get<any, any>('/governance-risk-compliance');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getFrameworks(): Promise<string[]> {
    const response = await apiClient.get<any, any>('/governance-risk-compliance/frameworks');
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getGaps(assessmentId: string): Promise<GrcGap[]> {
    const response = await apiClient.get<any, any>('/governance-risk-compliance/gaps', {
      params: { assessment_id: assessmentId },
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async getSummary(scopeId?: string): Promise<any> {
    const response = await apiClient.get<any, any>('/governance-risk-compliance/summary', {
      params: scopeId ? { scope_id: scopeId } : {},
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async createAssessment(
    name: string,
    description: string,
    framework: string,
    scopeId?: string
  ): Promise<GrcAssessment> {
    const response = await apiClient.post<any, any>('/governance-risk-compliance', {
      name,
      description,
      framework_type: framework,
      scope_id: scopeId || null,
    });
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async updateAssessmentStatus(
    assessmentId: string,
    status: 'review' | 'compliant' | 'non-compliant' | 'close'
  ): Promise<GrcAssessment> {
    const response = await apiClient.post<any, any>(
      `/governance-risk-compliance/${assessmentId}/${status}`
    );
    return response.success !== undefined ? response.data : (response.data || response);
  },

  async uploadEvidence(
    assessmentId: string,
    fileName: string,
    fileHash: string
  ): Promise<GrcEvidence> {
    const response = await apiClient.post<any, any>(
      `/governance-risk-compliance/${assessmentId}/evidence`,
      {
        file_name: fileName,
        file_hash: fileHash,
      }
    );
    return response.success !== undefined ? response.data : (response.data || response);
  },
};
