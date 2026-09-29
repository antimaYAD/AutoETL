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

export interface DatasetSample {
  dataset_version_id: number;
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
}

export interface ChartSeries {
  key: string;
  label: string;
  dashed?: boolean;
  faint?: boolean;
}

export interface ChartSpec {
  kind: "line" | "bar" | "hbar" | "histogram" | "scatter" | "heatmap" | "forecast" | "donut" | "pareto";
  title: string;
  description?: string;
  x_key?: string;
  series?: ChartSeries[];
  x_label?: string;
  y_label?: string;
  format?: "number" | "count" | "percent";
  data?: Record<string, unknown>[];
  columns?: string[];
  matrix?: number[][];
}

export interface Kpi {
  key: string;
  label: string;
  value: number | string;
  unit: string;
  note: string;
  group: string;
}

export interface ColumnStat {
  column: string;
  count: number;
  missing_pct: number;
  sum: number | null;
  mean: number | null;
  median: number | null;
  std: number | null;
  min: number | null;
  p25: number | null;
  p75: number | null;
  p95: number | null;
  max: number | null;
  skew: number | null;
}

export interface AnalyticsResult {
  dataset_version_id: number;
  domain: { domain: string; confidence: number; matched_terms: string[] };
  column_roles: Record<string, string[]>;
  columns_used?: Record<string, string>;
  kpis: Kpi[];
  charts: ChartSpec[];
  anomalies: {
    column: string;
    outlier_count: number;
    outlier_pct: number;
    extreme_count: number;
    lower_bound: number | null;
    upper_bound: number | null;
    max_value: number | null;
    examples: (number | null)[];
  }[];
  forecast: {
    measure: string;
    method: string;
    periods: number;
    r2: number;
    confidence: string;
    history: { label: string; value: number }[];
    forecast: { label: string; value: number; lower: number; upper: number }[];
  } | null;
  stats: ColumnStat[];
  categories: { column: string; unique: number; top: { value: string; count: number; share_pct: number; measure_total: number | null }[] }[];
  preparation: string[];
  date_range: { start: string; end: string } | null;
  insights: { headline: string; facts: string[]; relationships: string[]; predictions: string[]; actions: string[] };
  row_count: number;
  column_count: number;
}

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
  sample: (id: number, versionId?: number, limit = 20) =>
    api.get<DatasetSample>(
      `/datasets/${id}/sample?limit=${limit}${versionId ? `&version_id=${versionId}` : ""}`,
    ),
  analytics: (id: number, versionId?: number) =>
    api.get<AnalyticsResult>(
      `/datasets/${id}/analytics${versionId ? `?version_id=${versionId}` : ""}`,
    ),
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
