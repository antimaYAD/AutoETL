import type { DataIssue } from "./types";

/** Maps detected issue types to recommended registry operations. */
const ISSUE_TO_OPERATIONS: Record<string, string[]> = {
  MISSING_VALUES: ["fill_null", "drop_null_rows"],
  WHITESPACE: ["trim_whitespace"],
  DUPLICATE_ROWS: ["remove_duplicates"],
  CASE_INCONSISTENCY: ["lowercase_text"],
  INVALID_EMAIL: ["normalize_email"],
  INVALID_PHONE: ["normalize_phone"],
  CURRENCY_SYMBOL: ["normalize_numeric"],
  MIXED_NUMERIC_FORMAT: ["normalize_numeric"],
  INCONSISTENT_DATE: ["parse_date"],
};

export const OPERATION_LABELS: Record<string, string> = {
  trim_whitespace: "Trim whitespace",
  lowercase_text: "Lowercase text",
  uppercase_text: "Uppercase text",
  titlecase_text: "Title case",
  normalize_email: "Normalize emails",
  normalize_phone: "Normalize phones",
  parse_date: "Parse dates",
  normalize_numeric: "Normalize numbers",
  fill_null: "Fill nulls",
  drop_null_rows: "Drop null rows",
  remove_duplicates: "Remove duplicates",
  normalize_category: "Normalize categories",
};

export interface RecommendedTransformation {
  operation: string;
  label: string;
  column: string | null;
  confidence: number;
  forIssue: string;
}

/**
 * Derives recommended transformations from detected issues.
 * Returns one entry per issue (a column-scoped operation where the issue
 * named a column), deduplicated by operation+column.
 */
export function recommendTransformations(issues: DataIssue[]): RecommendedTransformation[] {
  const seen = new Set<string>();
  const recommendations: RecommendedTransformation[] = [];

  for (const issue of issues) {
    const ops = ISSUE_TO_OPERATIONS[issue.issue_type] ?? [];
    for (const operation of ops) {
      const key = `${operation}:${issue.column ?? "*"}`;
      if (seen.has(key)) continue;
      seen.add(key);
      recommendations.push({
        operation,
        label: OPERATION_LABELS[operation] ?? operation,
        column: issue.column,
        confidence: issue.confidence,
        forIssue: issue.issue_type,
      });
    }
  }

  return recommendations.sort((a, b) => b.confidence - a.confidence);
}
