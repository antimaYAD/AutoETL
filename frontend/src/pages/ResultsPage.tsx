import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { API_BASE_URL, tokenStore } from "../api/client";
import { datasetsApi, type DatasetSample } from "../api/endpoints";
import type { TransformResult } from "../api/types";

export default function ResultsPage() {
  const { id, versionId } = useParams<{ id: string; versionId: string }>();
  const location = useLocation();
  const result = (location.state as { result?: TransformResult } | null)?.result;

  const [sample, setSample] = useState<DatasetSample | null>(null);
  const [sampleError, setSampleError] = useState("");

  useEffect(() => {
    datasetsApi
      .sample(Number(id), versionId ? Number(versionId) : undefined)
      .then((res) => setSample(res.data))
      .catch(() => setSampleError("Could not load a preview of the transformed data."));
  }, [id, versionId]);

  async function handleDownload() {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/datasets/${id}/versions/${versionId}/download`,
      { headers: { Authorization: `Bearer ${tokenStore.get()}` } },
    );
    if (!res.ok) {
      alert("Download failed");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cleaned_dataset_v${versionId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <h1 className="page-title">ETL Completed</h1>
      <p className="page-subtitle">Transformation applied successfully. A new dataset version was created.</p>

      <div className="stat-grid" style={{ marginBottom: 24 }}>
        <div className="stat-card">
          <div className="stat-value" style={{ color: "var(--success)" }}>
            {result ? `${result.validation.quality_score}%` : "—"}
          </div>
          <div className="stat-label">Quality Score</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{result?.rows_before.toLocaleString() ?? "—"}</div>
          <div className="stat-label">Rows Before</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{result?.rows_after.toLocaleString() ?? "—"}</div>
          <div className="stat-label">Rows After</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">
            {result ? result.rows_before - result.rows_after : "—"}
          </div>
          <div className="stat-label">Rows Removed</div>
        </div>
      </div>

      {result && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h2 className="section-title">Applied transformations</h2>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {result.applied_steps.map((s) => (
              <li key={s} style={{ fontSize: 14, marginBottom: 4 }}>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 className="section-title" style={{ marginBottom: 4 }}>
            Data preview
          </h2>
          {sample && (
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              showing first {sample.rows.length} of {sample.total_rows.toLocaleString()} rows
            </span>
          )}
        </div>
        {sampleError && <div className="error-banner">{sampleError}</div>}
        {!sample && !sampleError && (
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>Loading preview…</p>
        )}
        {sample && (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead>
                <tr>
                  {sample.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sample.rows.map((row, ri) => (
                  <tr key={ri}>
                    {sample.columns.map((c) => (
                      <td key={c}>{row[c] === null || row[c] === undefined ? "∅" : String(row[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn btn-primary" onClick={handleDownload}>
          Download Clean Data
        </button>
        <Link className="btn" to={`/datasets/${id}/analytics?version=${versionId}`}>
          Open Analytics Dashboard
        </Link>
      </div>
    </>
  );
}
