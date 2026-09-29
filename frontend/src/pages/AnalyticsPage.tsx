import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { toPng } from "html-to-image";

import { errorMessage } from "../api/client";
import { datasetsApi, type AnalyticsResult, type ChartSpec } from "../api/endpoints";
import { ChartBody, formatValue } from "../components/AnalyticsCharts";

const WIDE_KINDS = new Set(["line", "forecast", "pareto"]);

function exportPng(el: HTMLElement | null, filename: string) {
  if (!el) return;
  toPng(el, {
    backgroundColor: "#ffffff",
    pixelRatio: 2,
    filter: (node) => !(node instanceof HTMLElement && node.dataset.noExport !== undefined),
  })
    .then((url) => {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
    })
    .catch(() => alert("Export failed"));
}

function downloadText(text: string, filename: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

function chartToCsv(spec: ChartSpec): string {
  if (spec.kind === "heatmap" && spec.columns && spec.matrix) {
    return [["", ...spec.columns].join(","), ...spec.matrix.map((r, i) => [spec.columns![i], ...r].join(","))].join("\n");
  }
  const rows = spec.data ?? [];
  if (!rows.length) return "";
  const keys = Object.keys(rows[0]);
  const esc = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  return [keys.join(","), ...rows.map((r) => keys.map((k) => esc(r[k])).join(","))].join("\n");
}

function ChartCard({ spec }: { spec: ChartSpec }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <div className="card" ref={ref} style={WIDE_KINDS.has(spec.kind) ? { gridColumn: "1 / -1" } : undefined}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 6 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{spec.title}</h3>
          {spec.description && <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--text-muted)" }}>{spec.description}</p>}
        </div>
        <div data-no-export style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => exportPng(ref.current, `${slug(spec.title)}.png`)}>
            PNG
          </button>
          <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => downloadText(chartToCsv(spec), `${slug(spec.title)}.csv`, "text/csv")}>
            CSV
          </button>
        </div>
      </div>
      <ChartBody spec={spec} />
    </div>
  );
}

const th: React.CSSProperties = { textAlign: "right", whiteSpace: "nowrap" };
const td: React.CSSProperties = { textAlign: "right", whiteSpace: "nowrap" };

function KpiValue({ value, unit }: { value: number | string; unit: string }) {
  if (typeof value === "string") return <>{value}</>;
  const compact = Math.abs(value) >= 100000;
  return (
    <span title={value.toLocaleString()}>
      {formatValue(value, "number", compact)}
      {unit && <span style={{ fontSize: 14, color: "var(--text-muted)" }}>{unit}</span>}
    </span>
  );
}

export default function AnalyticsPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const versionId = searchParams.get("version") ? Number(searchParams.get("version")) : undefined;

  const [data, setData] = useState<AnalyticsResult | null>(null);
  const [error, setError] = useState("");
  const dashRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    datasetsApi
      .analytics(Number(id), versionId)
      .then((res) => setData(res.data))
      .catch((err) => setError(errorMessage(err)));
  }, [id, versionId]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!data) return <p style={{ color: "var(--text-muted)" }}>Running analysis…</p>;

  const { insights } = data;
  const groups = ["Performance", "Data quality"].map((g) => ({ name: g, items: data.kpis.filter((k) => k.group === g) })).filter((g) => g.items.length);
  const sections: { title: string; items: string[] }[] = [
    { title: "Observed facts", items: insights.facts },
    { title: "Statistical relationships", items: insights.relationships },
    { title: "Predictions", items: insights.predictions },
    { title: "Recommended actions", items: insights.actions },
  ];
  const kpiCsv = ["group,kpi,value,unit,note", ...data.kpis.map((k) => [k.group, k.label, k.value, k.unit, k.note].map((v) => `"${String(v)}"`).join(","))].join("\n");

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>Analytics Dashboard</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            {data.row_count.toLocaleString()} rows · {data.column_count} columns
            {data.date_range && ` · ${data.date_range.start} → ${data.date_range.end}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => downloadText(kpiCsv, "kpis.csv", "text/csv")}>Export KPIs (CSV)</button>
          <button className="btn" onClick={() => downloadText(JSON.stringify(data, null, 2), "analytics.json", "application/json")}>Export JSON</button>
          <button className="btn btn-primary" onClick={() => exportPng(dashRef.current, `dashboard_v${versionId ?? "latest"}.png`)}>
            Download Dashboard
          </button>
        </div>
      </div>

      <div ref={dashRef} style={{ background: "var(--bg)", padding: 4 }}>
        <div style={{ margin: "12px 0 16px" }}>
          <span className="badge" style={{ fontSize: 13, padding: "6px 14px" }}>Domain: {data.domain.domain}</span>
          {data.domain.confidence > 0 && (
            <span style={{ fontSize: 13, color: "var(--text-muted)", marginLeft: 10 }}>
              {Math.round(data.domain.confidence * 100)}% confidence
              {data.domain.matched_terms.length > 0 && ` · matched: ${data.domain.matched_terms.join(", ")}`}
            </span>
          )}
        </div>

        {insights.headline && (
          <div className="card" style={{ marginBottom: 20, borderLeft: "4px solid #6366f1" }}>
            <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", marginBottom: 4 }}>Summary</div>
            <div style={{ fontSize: 15 }}>{insights.headline}</div>
          </div>
        )}

        {data.preparation.length > 0 && (
          <div className="card" style={{ marginBottom: 20, background: "#f8fafc" }}>
            <h2 className="section-title" style={{ marginBottom: 6 }}>Data preparation</h2>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 8px" }}>
              Your file was tidied in memory before analysis. The stored dataset is unchanged.
            </p>
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {data.preparation.map((n, i) => (
                <li key={i} style={{ fontSize: 13, marginBottom: 3 }}>{n}</li>
              ))}
            </ul>
          </div>
        )}

        {groups.map((g) => (
          <div key={g.name} style={{ marginBottom: 20 }}>
            <h2 className="section-title" style={{ marginBottom: 10 }}>{g.name}</h2>
            <div className="stat-grid">
              {g.items.map((k) => (
                <div className="stat-card" key={k.key}>
                  <div className="stat-value" style={{ fontSize: typeof k.value === "string" ? 16 : 24 }}>
                    <KpiValue value={k.value} unit={k.unit} />
                  </div>
                  <div className="stat-label">{k.label}</div>
                  {k.note && <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{k.note}</div>}
                </div>
              ))}
            </div>
          </div>
        ))}

        <div className="card" style={{ marginBottom: 24 }}>
          <h2 className="section-title">Insights</h2>
          {sections.map((s) =>
            s.items.length === 0 ? null : (
              <div key={s.title} style={{ marginBottom: 14 }}>
                <h3 style={{ fontSize: 13, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", margin: "0 0 6px" }}>{s.title}</h3>
                <ul style={{ margin: 0, paddingLeft: 20 }}>
                  {s.items.map((it, i) => (
                    <li key={i} style={{ fontSize: 14, marginBottom: 4 }}>{it}</li>
                  ))}
                </ul>
              </div>
            ),
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(460px, 1fr))", gap: 20, marginBottom: 24 }}>
          {data.charts.map((spec, i) => (
            <ChartCard key={i} spec={spec} />
          ))}
        </div>

        {data.stats.length > 0 && (
          <div className="card" style={{ marginBottom: 24 }}>
            <h2 className="section-title">Numeric column statistics</h2>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Column</th>
                    {["Count", "Missing", "Sum", "Mean", "Median", "Std dev", "Min", "25%", "75%", "95%", "Max", "Skew"].map((h) => (
                      <th key={h} style={th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.stats.map((s) => (
                    <tr key={s.column}>
                      <td style={{ fontWeight: 600 }}>{s.column}</td>
                      <td style={td}>{s.count.toLocaleString()}</td>
                      <td style={td}>{s.missing_pct}%</td>
                      {[s.sum, s.mean, s.median, s.std, s.min, s.p25, s.p75, s.p95, s.max].map((v, i) => (
                        <td key={i} style={td} title={v === null ? "" : String(v)}>{formatValue(v, "number", true)}</td>
                      ))}
                      <td style={td}>{s.skew === null ? "—" : s.skew.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {data.anomalies.length > 0 && (
          <div className="card" style={{ marginBottom: 24 }}>
            <h2 className="section-title">Outliers & anomalies</h2>
            <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 8px" }}>
              Mild = outside 1.5 × IQR; extreme = outside 3 × IQR. Skewed business data often has many legitimate large values, so review before removing anything.
            </p>
            <div style={{ overflowX: "auto" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th style={th}>Outliers</th>
                    <th style={th}>% of rows</th>
                    <th style={th}>Extreme</th>
                    <th style={th}>Expected range</th>
                    <th style={th}>Largest values</th>
                  </tr>
                </thead>
                <tbody>
                  {data.anomalies.map((a) => (
                    <tr key={a.column}>
                      <td style={{ fontWeight: 600 }}>{a.column}</td>
                      <td style={td}>{a.outlier_count.toLocaleString()}</td>
                      <td style={td}>{a.outlier_pct}%</td>
                      <td style={td}>{a.extreme_count.toLocaleString()}</td>
                      <td style={td}>{formatValue(a.lower_bound, "number", true)} – {formatValue(a.upper_bound, "number", true)}</td>
                      <td style={td}>{a.examples.map((v) => formatValue(v, "number", true)).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {data.categories.length > 0 && (
          <div className="card" style={{ marginBottom: 24 }}>
            <h2 className="section-title">Category breakdown</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20 }}>
              {data.categories.map((c) => (
                <div key={c.column}>
                  <h3 style={{ fontSize: 14, margin: "0 0 6px" }}>
                    {c.column} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>({c.unique.toLocaleString()} unique)</span>
                  </h3>
                  {c.top.map((t) => (
                    <div key={t.value} style={{ marginBottom: 6 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                        <span title={t.value}>{t.value.length > 30 ? `${t.value.slice(0, 29)}…` : t.value}</span>
                        <span style={{ color: "var(--text-muted)" }}>{t.count.toLocaleString()} · {t.share_pct}%</span>
                      </div>
                      <div style={{ height: 6, background: "#e2e8f0", borderRadius: 3 }}>
                        <div style={{ width: `${Math.min(t.share_pct, 100)}%`, height: "100%", background: "#6366f1", borderRadius: 3 }} />
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
