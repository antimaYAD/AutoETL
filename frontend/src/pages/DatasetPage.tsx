import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { errorMessage } from "../api/client";
import { analysisApi, datasetsApi } from "../api/endpoints";
import type { Dataset, DatasetIssues, DatasetProfile } from "../api/types";

const SEVERITY_BADGE: Record<string, string> = {
  low: "badge badge-low",
  medium: "badge badge-medium",
  high: "badge badge-high",
};

export default function DatasetPage() {
  const { id } = useParams<{ id: string }>();
  const datasetId = Number(id);

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [versionId, setVersionId] = useState<number | undefined>();
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [issues, setIssues] = useState<DatasetIssues | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    datasetsApi
      .get(datasetId)
      .then((res) => {
        setDataset(res.data);
        const latest = res.data.versions[res.data.versions.length - 1];
        if (latest) setVersionId(latest.id);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [datasetId]);

  useEffect(() => {
    if (!dataset || versionId === undefined) return;
    setProfile(null);
    setIssues(null);
    analysisApi.profile(datasetId, versionId).then((res) => setProfile(res.data)).catch(() => {});
    analysisApi.issues(datasetId, versionId).then((res) => setIssues(res.data)).catch(() => {});
  }, [dataset, datasetId, versionId]);

  async function runAnalysis() {
    setBusy("analyze");
    setError("");
    try {
      const res = await analysisApi.analyze(datasetId, versionId);
      setIssues(res.data);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy("");
    }
  }

  if (!dataset) return <div className="loading">{error || "Loading…"}</div>;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">{dataset.original_filename}</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            {dataset.industry && `Industry: ${dataset.industry} · `}
            {dataset.department && `Department: ${dataset.department} · `}
            Uploaded {new Date(dataset.created_at).toLocaleString()}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <select
            value={versionId ?? ""}
            onChange={(e) => setVersionId(Number(e.target.value))}
            style={{ padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius)" }}
          >
            {dataset.versions.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number} — {v.label}
              </option>
            ))}
          </select>
          <Link className="btn btn-primary" to={`/datasets/${datasetId}/transform${versionId ? `?version=${versionId}` : ""}`}>
            Review Transformations
          </Link>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {profile ? (
        <div className="stat-grid" style={{ marginTop: 20 }}>
          <div className="stat-card">
            <div className="stat-value">{profile.row_count.toLocaleString()}</div>
            <div className="stat-label">Rows</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{profile.column_count}</div>
            <div className="stat-label">Columns</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{issues?.issue_count ?? "—"}</div>
            <div className="stat-label">Issues</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{issues ? `${issues.quality_score}%` : "—"}</div>
            <div className="stat-label">Quality</div>
          </div>
        </div>
      ) : (
        <div className="loading">Profiling…</div>
      )}

      {profile && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h2 className="section-title">Column Profile</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th>Nulls</th>
                <th>Unique</th>
                <th>Min / Max</th>
                <th>Mean</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {profile.columns.map((c) => (
                <tr key={c.column}>
                  <td style={{ fontWeight: 500 }}>{c.column}</td>
                  <td>
                    <span className="badge badge-status">{c.inferred_type}</span>
                  </td>
                  <td>
                    {c.null_count} ({c.null_percentage}%)
                  </td>
                  <td>{c.unique_count}</td>
                  <td>
                    {c.min != null && c.max != null ? `${c.min} / ${c.max}` : "—"}
                  </td>
                  <td>{c.mean ?? "—"}</td>
                  <td>{c.mixed_types ? "⚠ mixed types" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 className="section-title" style={{ margin: 0 }}>
            Detected Issues
          </h2>
          <button className="btn" onClick={runAnalysis} disabled={busy === "analyze"}>
            {issues ? "Re-run analysis" : busy === "analyze" ? "Analyzing…" : "Run analysis"}
          </button>
        </div>
        {!issues ? (
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
            Run analysis to detect data-quality issues.
          </p>
        ) : issues.issues.length === 0 ? (
          <p style={{ color: "var(--success)", fontSize: 14 }}>No issues detected.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Issue</th>
                <th>Column</th>
                <th>Rows</th>
                <th>Severity</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {issues.issues.map((issue, i) => (
                <tr key={i}>
                  <td>
                    <span style={{ fontWeight: 500 }}>{issue.issue_type}</span>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{issue.description}</div>
                  </td>
                  <td>{issue.column ?? "—"}</td>
                  <td>{issue.affected_rows}</td>
                  <td>
                    <span className={SEVERITY_BADGE[issue.severity]}>{issue.severity}</span>
                  </td>
                  <td>{Math.round(issue.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
