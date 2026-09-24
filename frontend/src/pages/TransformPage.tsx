import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { errorMessage } from "../api/client";
import { transformApi } from "../api/endpoints";
import type { TransformationPreview, TransformationStep } from "../api/types";

const OPERATIONS: { value: string; label: string; description: string }[] = [
  { value: "trim_whitespace", label: "Trim whitespace", description: "Remove leading/trailing spaces" },
  { value: "lowercase_text", label: "Lowercase text", description: "Normalize to lowercase" },
  { value: "uppercase_text", label: "Uppercase text", description: "Normalize to uppercase" },
  { value: "titlecase_text", label: "Title case", description: "Normalize names/text to Title Case" },
  { value: "normalize_email", label: "Normalize emails", description: "Trim + lowercase email values" },
  { value: "normalize_phone", label: "Normalize phones", description: "Strip formatting characters" },
  { value: "parse_date", label: "Parse dates", description: "Convert to ISO YYYY-MM-DD" },
  { value: "normalize_numeric", label: "Normalize numbers", description: "Strip currency/commas, convert to number" },
  { value: "fill_null", label: "Fill nulls", description: "Replace missing values" },
  { value: "drop_null_rows", label: "Drop null rows", description: "Remove rows with missing values" },
  { value: "remove_duplicates", label: "Remove duplicates", description: "Drop exact duplicate rows" },
];

interface DraftStep {
  operation: string;
  column: string;
}

export default function TransformPage() {
  const { id } = useParams<{ id: string }>();
  const datasetId = Number(id);
  const [searchParams] = useSearchParams();
  const versionId = searchParams.get("version") ? Number(searchParams.get("version")) : undefined;
  const navigate = useNavigate();

  const [steps, setSteps] = useState<DraftStep[]>([{ operation: "trim_whitespace", column: "*" }]);
  const [previews, setPreviews] = useState<TransformationPreview[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    setPreviews(null);
  }, [steps]);

  function updateStep(index: number, patch: Partial<DraftStep>) {
    setSteps((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function addStep() {
    setSteps((prev) => [...prev, { operation: "trim_whitespace", column: "*" }]);
  }

  function removeStep(index: number) {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  }

  function buildSteps(): TransformationStep[] {
    return steps.map((s) => ({ operation: s.operation, column: s.column || null, params: {} }));
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
        Select operations to apply. Preview first — applying creates a new dataset version; the original is never
        modified.
      </p>

      {error && <div className="error-banner">{error}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <h2 className="section-title">Transformation steps</h2>
        {steps.map((step, i) => (
          <div className="step-row" key={i}>
            <select
              value={step.operation}
              onChange={(e) => updateStep(i, { operation: e.target.value })}
              style={{ flex: 1, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
            >
              {OPERATIONS.map((op) => (
                <option key={op.value} value={op.value}>
                  {op.label} — {op.description}
                </option>
              ))}
            </select>
            <input
              placeholder="Column (or * for all)"
              value={step.column}
              onChange={(e) => updateStep(i, { column: e.target.value })}
              style={{ width: 200, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
            />
            <button className="btn btn-danger" onClick={() => removeStep(i)} disabled={steps.length <= 1}>
              Remove
            </button>
          </div>
        ))}
        <div style={{ marginTop: 12 }}>
          <button className="btn" onClick={addStep}>
            + Add step
          </button>
        </div>
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
        <button className="btn" onClick={handlePreview} disabled={busy !== ""}>
          {busy === "preview" ? "Previewing…" : "Preview Changes"}
        </button>
        <button className="btn btn-primary" onClick={handleApply} disabled={busy !== ""}>
          {busy === "apply" ? "Applying…" : "Apply Selected"}
        </button>
      </div>
    </>
  );
}
