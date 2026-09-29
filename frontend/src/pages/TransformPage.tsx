import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { errorMessage } from "../api/client";
import { transformApi } from "../api/endpoints";
import type { TransformationPreview, TransformationStep } from "../api/types";

const OPERATIONS: {
  value: string;
  label: string;
  description: string;
  needsColumn: boolean;
  paramField?: { key: string; label: string; placeholder: string };
}[] = [
  { value: "trim_whitespace", label: "Trim whitespace", description: "Remove leading/trailing spaces from all text columns", needsColumn: false },
  { value: "lowercase_text", label: "Lowercase text", description: "Normalize text values to lowercase", needsColumn: false },
  { value: "uppercase_text", label: "Uppercase text", description: "Normalize text values to uppercase", needsColumn: false },
  { value: "titlecase_text", label: "Title case", description: "Normalize names/text to Title Case", needsColumn: false },
  { value: "normalize_email", label: "Normalize emails", description: "Trim + lowercase email values", needsColumn: false },
  { value: "normalize_phone", label: "Normalize phones", description: "Strip formatting characters, keep digits and +", needsColumn: false },
  { value: "parse_date", label: "Parse dates", description: "Convert mixed date formats to ISO YYYY-MM-DD", needsColumn: true },
  { value: "normalize_numeric", label: "Normalize numbers", description: "Strip currency/commas, convert to numeric", needsColumn: true },
  {
    value: "fill_null",
    label: "Fill nulls",
    description: "Replace missing values — pick a column and a fill value (0 for numbers, e.g. 'Unknown' for text)",
    needsColumn: true,
    paramField: { key: "value", label: "Fill value", placeholder: "0" },
  },
  { value: "drop_null_rows", label: "Drop null rows", description: "Remove rows containing missing values", needsColumn: false },
  { value: "remove_duplicates", label: "Remove duplicates", description: "Drop exact duplicate rows", needsColumn: false },
];

interface DraftStep extends TransformationStep {
  enabled: boolean;
}

export default function TransformPage() {
  const { id } = useParams<{ id: string }>();
  const datasetId = Number(id);
  const [searchParams] = useSearchParams();
  const versionId = searchParams.get("version") ? Number(searchParams.get("version")) : undefined;
  const navigate = useNavigate();

  const [steps, setSteps] = useState<DraftStep[]>(() => {
    // ops query param comes from the dataset analysis page as JSON:
    // [{"op":"fill_null","col":"salary"}, ...]
    const raw = searchParams.get("ops") ?? "";
    let recommended = new Map<string, string | null>();
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        for (const entry of parsed) {
          if (entry && typeof entry.op === "string") {
            recommended.set(entry.op, entry.col ?? null);
          }
        }
      }
    } catch {
      // Fallback: plain comma-separated operation names
      for (const op of raw.split(",").filter(Boolean)) recommended.set(op, null);
    }
    return OPERATIONS.map((op) => ({
      operation: op.value,
      column: recommended.get(op.value) ?? null,
      params: {},
      enabled: recommended.has(op.value),
    }));
  });
  const [previews, setPreviews] = useState<TransformationPreview[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const selectedSteps = steps.filter((s) => s.enabled);

  function toggle(index: number) {
    setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, enabled: !s.enabled } : s)));
    setPreviews(null);
  }

  function setColumn(index: number, column: string) {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, column: column || null } : s)),
    );
    setPreviews(null);
  }

  function setParam(index: number, key: string, rawValue: string) {
    // Keep it simple: numbers parse as numbers, everything else stays a string.
    const parsed = rawValue !== "" && !isNaN(Number(rawValue)) ? Number(rawValue) : rawValue;
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, params: { ...s.params, [key]: parsed } } : s)),
    );
    setPreviews(null);
  }

  function buildSteps(): TransformationStep[] {
    return selectedSteps.map((s) => ({ operation: s.operation, column: s.column, params: s.params }));
  }

  async function handlePreview() {
    setError("");
    setBusy("preview");
    try {
      const res = await transformApi.preview(datasetId, buildSteps(), versionId);
      setPreviews(res.data.previews);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy("");
    }
  }

  async function handleApply() {
    setError("");
    setBusy("apply");
    try {
      const res = await transformApi.apply(datasetId, buildSteps(), versionId);
      navigate(`/datasets/${datasetId}/results/${res.data.new_dataset_version_id}`, {
        state: { result: res.data },
      });
    } catch (err) {
      setError(errorMessage(err));
      setBusy("");
    }
  }

  return (
    <>
      <h1 className="page-title">Recommended Transformations</h1>
      <p className="page-subtitle">
        Select the operations to apply. Preview first — applying creates a new dataset version; the original is
        never modified.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <h2 className="section-title" style={{ margin: 0 }}>
            Available transformations
          </h2>
          <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
            {selectedSteps.length} selected
          </span>
        </div>

        <table className="table">
          <thead>
            <tr>
              <th style={{ width: 40 }}></th>
              <th>Transformation</th>
              <th style={{ width: 220 }}>Column</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((step, i) => {
              const op = OPERATIONS[i];
              return (
                <tr key={op.value} style={{ opacity: step.enabled ? 1 : 0.65 }}>
                  <td>
                    <input
                      type="checkbox"
                      checked={step.enabled}
                      onChange={() => toggle(i)}
                      style={{ width: 16, height: 16, accentColor: "var(--accent)", cursor: "pointer" }}
                    />
                  </td>
                  <td>
                    <div style={{ fontWeight: 600 }}>{op.label}</div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{op.description}</div>
                  </td>
                  <td>
                    {step.enabled ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <input
                          type="text"
                          placeholder={op.needsColumn ? "column name" : "* (all)"}
                          value={step.column ?? ""}
                          onChange={(e) => setColumn(i, e.target.value)}
                          style={{ width: "100%" }}
                        />
                        {op.paramField && (
                          <input
                            type="text"
                            placeholder={`${op.paramField.label} (e.g. ${op.paramField.placeholder})`}
                            value={String(step.params[op.paramField.key] ?? "")}
                            onChange={(e) => setParam(i, op.paramField!.key, e.target.value)}
                            style={{ width: "100%" }}
                          />
                        )}
                      </div>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: 13 }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {previews && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2 className="section-title">Preview</h2>
          {previews.map((p, i) => (
            <div key={i} style={{ marginBottom: 16 }}>
              <p style={{ fontWeight: 500, marginBottom: 8 }}>
                {p.operation} {p.column && p.column !== "*" ? `on ${p.column}` : ""} —{" "}
                <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{p.rows_affected} rows affected</span>
              </p>
              <div style={{ overflowX: "auto" }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th></th>
                      {p.sample_before[0] && Object.keys(p.sample_before[0]).map((k) => <th key={k}>{k}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {p.sample_before.slice(0, 3).map((row, ri) => (
                      <tr key={`b${ri}`}>
                        <td style={{ color: "var(--text-muted)", fontSize: 12 }}>before</td>
                        {Object.values(row).map((v, vi) => (
                          <td key={vi}>{v === null ? "∅" : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                    {p.sample_after.slice(0, 3).map((row, ri) => (
                      <tr key={`a${ri}`} style={{ background: "#f0fdf4" }}>
                        <td style={{ color: "var(--success)", fontSize: 12 }}>after</td>
                        {Object.values(row).map((v, vi) => (
                          <td key={vi}>{v === null ? "∅" : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn" onClick={handlePreview} disabled={busy !== "" || selectedSteps.length === 0}>
          {busy === "preview" ? "Previewing…" : "Preview Changes"}
        </button>
        <button className="btn btn-primary" onClick={handleApply} disabled={busy !== "" || selectedSteps.length === 0}>
          {busy === "apply" ? "Applying…" : `Apply Selected (${selectedSteps.length})`}
        </button>
      </div>
    </>
  );
}
