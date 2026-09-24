import { api } from "./client";
import type {
  Dataset,
  DatasetIssues,
  DatasetProfile,
  TransformationPreview,
  TransformationStep,
  TransformResult,
  User,
} from "./types";

export interface DatasetSummary extends Omit<Dataset, "versions"> {}

export const authApi = {
  register: (email: string, password: string, fullName?: string) =>
    api.post<User>("/auth/register", { email, password, full_name: fullName }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string }>(
      "/auth/login",
      new URLSearchParams({ username: email, password }),
      { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
    ),
  me: () => api.get<User>("/auth/me"),
};

export const datasetsApi = {
  upload: (file: File, industry?: string, department?: string) => {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams();
    if (industry) params.set("industry", industry);
    if (department) params.set("department", department);
    const query = params.toString();
    return api.post<Dataset>(`/datasets/upload${query ? `?${query}` : ""}`, form);
  },
  list: () => api.get<DatasetSummary[]>("/datasets"),
  get: (id: number) => api.get<Dataset>(`/datasets/${id}`),
  remove: (id: number) => api.delete(`/datasets/${id}`),
};

export const analysisApi = {
  profile: (datasetId: number, versionId?: number) =>
    api.post<DatasetProfile>(
      `/datasets/${datasetId}/profile${versionId ? `?version_id=${versionId}` : ""}`,
    ),
  analyze: (datasetId: number, versionId?: number) =>
    api.post<DatasetIssues>(
      `/datasets/${datasetId}/analyze${versionId ? `?version_id=${versionId}` : ""}`,
    ),
  issues: (datasetId: number, versionId?: number) =>
    api.get<DatasetIssues>(
      `/datasets/${datasetId}/issues${versionId ? `?version_id=${versionId}` : ""}`,
    ),
};

export const transformApi = {
  preview: (datasetId: number, steps: TransformationStep[], versionId?: number) =>
    api.post<{ dataset_version_id: number; previews: TransformationPreview[] }>(
      `/datasets/${datasetId}/preview${versionId ? `?version_id=${versionId}` : ""}`,
      { steps },
    ),
  apply: (datasetId: number, steps: TransformationStep[], versionId?: number) =>
    api.post<TransformResult>(
      `/datasets/${datasetId}/transform${versionId ? `?version_id=${versionId}` : ""}`,
      { steps },
    ),
};
