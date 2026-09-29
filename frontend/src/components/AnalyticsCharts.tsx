import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { ChartSpec } from "../api/endpoints";

export const PALETTE = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#a855f7", "#ec4899", "#64748b"];
const GRID = "#e2e8f0";
const AXIS = "#94a3b8";
const TICK = { fontSize: 12, fill: "#475569" };
const CHART_HEIGHT = 340;

const compactFmt = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 });
const fullFmt = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });

export function formatValue(v: unknown, format: ChartSpec["format"] = "number", compact = false): string {
  const n = typeof v === "number" ? v : Number(v);
  if (v === null || v === undefined || Number.isNaN(n)) return "—";
  if (format === "percent") return `${fullFmt.format(n)}%`;
  if (format === "count") return compact ? compactFmt.format(n) : fullFmt.format(Math.round(n));
  return compact ? compactFmt.format(n) : fullFmt.format(n);
}

function truncate(s: unknown, max = 22): string {
  const str = String(s);
  return str.length > max ? `${str.slice(0, max - 1)}…` : str;
}

function xLabel(text?: string) {
  return text ? { value: text, position: "insideBottom" as const, offset: -6, style: { fontSize: 12, fill: "#334155", fontWeight: 600 } } : undefined;
}

function yLabel(text?: string) {
  return text
    ? { value: text, angle: -90, position: "insideLeft" as const, offset: 4, style: { textAnchor: "middle" as const, fontSize: 12, fill: "#334155", fontWeight: 600 } }
    : undefined;
}

export function ChartBody({ spec }: { spec: ChartSpec }) {
  if (spec.kind === "heatmap" && spec.columns && spec.matrix) {
    return <HeatmapTable columns={spec.columns} matrix={spec.matrix} />;
  }
  const data = spec.data ?? [];
  if (data.length === 0) return <p style={{ color: "var(--text-muted)" }}>No data</p>;

  const fmt = spec.format ?? "number";
  const series = spec.series ?? [{ key: "value", label: "Value" }];
  const many = data.length > 8;
  const rotate = data.length > 6;
  const labelOf = (key: unknown) => series.find((s) => s.key === key)?.label ?? String(key);
  const tooltipFormatter = (value: unknown, name: unknown) => [formatValue(value, fmt), labelOf(name)] as [string, string];

  if (spec.kind === "scatter") {
    return (
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 34, left: 24 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" name={spec.x_label} tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, fmt, true)} label={xLabel(spec.x_label)} />
          <YAxis type="number" dataKey="y" name={spec.y_label} tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, fmt, true)} width={64} label={yLabel(spec.y_label)} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v: unknown) => formatValue(v, fmt)} />
          <Scatter data={data} fill={PALETTE[0]} fillOpacity={0.55} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (spec.kind === "line" || spec.kind === "forecast") {
    return (
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <LineChart data={data} margin={{ top: 10, right: 24, bottom: rotate ? 58 : 34, left: 24 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} interval={many ? "preserveStartEnd" : 0} angle={rotate ? -30 : 0} textAnchor={rotate ? "end" : "middle"} height={rotate ? 70 : 40} label={xLabel(spec.x_label)} />
          <YAxis tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, fmt, true)} width={68} label={yLabel(spec.y_label)} />
          <Tooltip formatter={tooltipFormatter} />
          <Legend verticalAlign="top" height={30} />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.faint ? "#a5b4fc" : PALETTE[i % PALETTE.length]}
              strokeWidth={s.faint ? 1.5 : 2.5}
              strokeDasharray={s.dashed ? "6 4" : s.faint ? "2 3" : undefined}
              dot={data.length <= 24 && !s.faint ? { r: 3 } : false}
              activeDot={{ r: 5 }}
              connectNulls={false}
              legendType={s.faint ? "none" : "line"}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (spec.kind === "hbar") {
    const height = Math.max(CHART_HEIGHT, data.length * 34 + 90);
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 6, right: 40, bottom: 34, left: 8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, fmt, true)} label={xLabel(spec.x_label)} />
          <YAxis type="category" dataKey="label" width={150} tick={TICK} axisLine={{ stroke: AXIS }} tickLine={false} tickFormatter={(v) => truncate(v, 22)} label={yLabel(spec.y_label)} />
          <Tooltip
            formatter={(value: unknown, _n: unknown, item: { payload?: { share?: number } }) => [
              `${formatValue(value, fmt)}${item?.payload?.share !== undefined ? ` (${item.payload.share}% of total)` : ""}`,
              spec.series?.[0]?.label ?? "Value",
            ]}
          />
          <Bar dataKey="value" name={spec.series?.[0]?.label} radius={[0, 4, 4, 0]} barSize={20}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[0]} fillOpacity={1 - Math.min(i, 9) * 0.06} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (spec.kind === "pareto") {
    return (
      <ResponsiveContainer width="100%" height={CHART_HEIGHT + 20}>
        <ComposedChart data={data} margin={{ top: 10, right: 24, bottom: 76, left: 24 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} interval={0} angle={-35} textAnchor="end" height={90} tickFormatter={(v) => truncate(v, 16)} label={xLabel(spec.x_label)} />
          <YAxis yAxisId="left" tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, "number", true)} width={68} label={yLabel(spec.y_label)} />
          <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => `${v}%`} width={48} label={{ value: "Cumulative %", angle: 90, position: "insideRight", style: { textAnchor: "middle", fontSize: 12, fill: "#334155", fontWeight: 600 } }} />
          <Tooltip formatter={(value: unknown, name: unknown) => [name === "cumulative" || name === "Cumulative %" ? `${value}%` : formatValue(value), String(name)]} />
          <Legend verticalAlign="top" height={30} />
          <Bar yAxisId="left" dataKey="value" name={spec.series?.[0]?.label ?? "Value"} fill={PALETTE[0]} radius={[4, 4, 0, 0]} />
          <Line yAxisId="right" type="monotone" dataKey="cumulative" name="Cumulative %" stroke={PALETTE[2]} strokeWidth={2.5} dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  if (spec.kind === "donut") {
    return (
      <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="label" innerRadius={70} outerRadius={115} paddingAngle={2} label={(e: { name?: string; payload?: { share?: number } }) => `${truncate(e.name, 12)} ${e.payload?.share ?? ""}%`}>
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value: unknown, name: unknown, item: { payload?: { share?: number } }) => [`${formatValue(value)} (${item?.payload?.share ?? 0}%)`, String(name)]} />
          <Legend verticalAlign="bottom" />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // bar + histogram
  const isHist = spec.kind === "histogram";
  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data} margin={{ top: 10, right: 24, bottom: rotate ? 58 : 34, left: 24 }} barCategoryGap={isHist ? 1 : "20%"}>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} interval={isHist && many ? 1 : 0} angle={rotate ? -30 : 0} textAnchor={rotate ? "end" : "middle"} height={rotate ? 70 : 40} tickFormatter={(v) => truncate(v, 14)} label={xLabel(spec.x_label)} />
        <YAxis tick={TICK} axisLine={{ stroke: AXIS }} tickLine={{ stroke: AXIS }} tickFormatter={(v) => formatValue(v, fmt, true)} width={68} label={yLabel(spec.y_label)} />
        <Tooltip
          labelFormatter={(label: unknown, payload: readonly { payload?: { range?: string } }[]) => payload?.[0]?.payload?.range ?? String(label)}
          formatter={(value: unknown) => [formatValue(value, fmt), spec.series?.[0]?.label ?? "Value"]}
        />
        <Bar dataKey="value" name={spec.series?.[0]?.label} fill={PALETTE[0]} radius={isHist ? [2, 2, 0, 0] : [4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function HeatmapTable({ columns, matrix }: { columns: string[]; matrix: number[][] }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ borderCollapse: "separate", borderSpacing: 3, fontSize: 12, margin: "0 auto" }}>
        <thead>
          <tr>
            <th></th>
            {columns.map((c) => (
              <th key={c} style={{ padding: "4px 6px", textAlign: "center", fontWeight: 600, maxWidth: 110, color: "#334155" }}>
                {truncate(c, 16)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={columns[i]}>
              <td style={{ padding: "4px 8px", fontWeight: 600, textAlign: "right", color: "#334155" }}>{truncate(columns[i], 18)}</td>
              {row.map((v, j) => {
                const alpha = Math.min(Math.abs(v), 1);
                return (
                  <td
                    key={j}
                    title={`${columns[i]} × ${columns[j]}: ${v.toFixed(3)}`}
                    style={{
                      padding: "14px 10px",
                      minWidth: 64,
                      textAlign: "center",
                      borderRadius: 6,
                      fontWeight: 600,
                      background: v >= 0 ? `rgba(99,102,241,${0.08 + alpha * 0.92})` : `rgba(239,68,68,${0.08 + alpha * 0.92})`,
                      color: alpha > 0.55 ? "#fff" : "#0f172a",
                    }}
                  >
                    {v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ display: "flex", justifyContent: "center", gap: 16, marginTop: 10, fontSize: 12, color: "#64748b" }}>
        <span><b style={{ color: "#ef4444" }}>■</b> negative</span>
        <span><b style={{ color: "#6366f1" }}>■</b> positive</span>
        <span>darker = stronger</span>
      </div>
    </div>
  );
}
