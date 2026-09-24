import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { errorMessage } from "../api/client";
import { datasetsApi, type DatasetSummary } from "../api/endpoints";

export default function DashboardPage() {
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [industry, setIndustry] = useState("");
  const [department, setDepartment] = useState("");

  useEffect(() => {
    datasetsApi
      .list()
      .then((res) => setDatasets(res.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  async function handleUpload(file: File) {
    setError("");
    setUploading(true);
    try {
      const res = await datasetsApi.upload(file, industry || undefined, department || undefined);
      navigate(`/datasets/${res.data.id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  }

  async function handleDelete(id: number) {
    try {
      await datasetsApi.remove(id);
      setDatasets((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      <h1 className="page-title">Datasets</h1>
      <p className="page-subtitle">Upload a dataset to profile, analyze, and clean it.</p>

      {error && <div className="error-banner">{error}</div>}

      <div
        className={`upload-dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <div className="upload-icon">↑</div>
        <p style={{ margin: "0 0 4px", fontSize: 16, fontWeight: 600, color: "var(--text)" }}>
          Drag &amp; drop a dataset here
        </p>
        <p style={{ margin: "0 0 16px", fontSize: 13 }}>CSV • XLSX • XLS</p>
        <button className="btn btn-primary" onClick={() => fileInput.current?.click()} disabled={uploading}>
          {uploading ? "Uploading…" : "Upload Dataset"}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.xlsx,.xls"
          style={{ display: "none" }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
            e.target.value = "";
          }}
        />
        <div style={{ display: "flex", gap: 12, marginTop: 16, justifyContent: "center" }}>
          <div className="form-field" style={{ marginBottom: 0, width: 180 }}>
            <input placeholder="Industry (optional)" value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </div>
          <div className="form-field" style={{ marginBottom: 0, width: 180 }}>
            <input placeholder="Department (optional)" value={department} onChange={(e) => setDepartment(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h2 className="section-title">Your datasets</h2>
        {loading ? (
          <p className="loading">Loading…</p>
        ) : datasets.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>No datasets yet — upload one above.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>File</th>
                <th>Industry</th>
                <th>Department</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link to={`/datasets/${d.id}`} style={{ color: "var(--accent)", fontWeight: 500 }}>
                      {d.name}
                    </Link>
                  </td>
                  <td>{d.original_filename}</td>
                  <td>{d.industry ?? "—"}</td>
                  <td>{d.department ?? "—"}</td>
                  <td>{new Date(d.created_at).toLocaleString()}</td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btn-danger" onClick={() => handleDelete(d.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
