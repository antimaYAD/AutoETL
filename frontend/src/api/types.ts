export interface User {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DatasetVersion {
  id: number;
  version_number: number;
  label: string;
  row_count: number | null;
  column_count: number | null;
  status: string;
  source_sheets: string[] | null;
  created_at: string;
}

export interface Dataset {
  id: number;
  name: string;
  original_filename: string;
  industry: string | null;
  department: string | null;
  created_at: string;
  versions: DatasetVersion[];
}

export interface ColumnProfile {
  column: string;
  inferred_type: string;
  null_count: number;
  null_percentage: number;
  unique_count: number;
  duplicate_value_count: number;
  sample_values: (string | null)[];
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
  string_length_min: number | null;
  string_length_max: number | null;
  string_length_mean: number | null;
  date_format_candidates: string[];
  category_frequencies: Record<string, number> | null;
  mixed_types: boolean;
}

export interface DatasetProfile {
  dataset_version_id: number;
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
}

export interface DataIssue {
  issue_type: string;
  column: string | null;
  affected_rows: number;
  severity: "low" | "medium" | "high";
  confidence: number;
  description: string;
}

export interface DatasetIssues {
  dataset_version_id: number;
  issue_count: number;
  quality_score: number;
  issues: DataIssue[];
}

export interface TransformationStep {
  operation: string;
  column: string | null;
  params: Record<string, unknown>;
}

export interface TransformationPreview {
  operation: string;
  column: string | null;
  rows_affected: number;
  sample_before: Record<string, unknown>[];
  sample_after: Record<string, unknown>[];
}

export interface TransformResult {
  new_dataset_version_id: number;
  applied_steps: string[];
  rows_before: number;
  rows_after: number;
  validation: {
    steps: Record<string, unknown>[];
    issue_count: number;
    quality_score: number;
    issues: DataIssue[];
  };
}
