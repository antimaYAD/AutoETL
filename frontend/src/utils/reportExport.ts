import { toPng } from "html-to-image";

import type { AnalyticsResult } from "../api/endpoints";
import { formatValue } from "../components/AnalyticsCharts";

export interface Block {
  id: string;
  dataUrl: string;
  width: number;
  height: number;
}

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function dataUrlToBytes(dataUrl: string): Uint8Array {
  const bin = atob(dataUrl.split(",")[1]);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

const LOGO_W = 1024;
const LOGO_H = 558;

async function loadLogo(): Promise<{ dataUrl: string; bytes: Uint8Array } | null> {
  try {
    const res = await fetch("/logo.jpg");
    if (!res.ok) return null;
    const bytes = new Uint8Array(await res.arrayBuffer());
    let bin = "";
    for (const b of bytes) bin += String.fromCharCode(b);
    return { dataUrl: `data:image/jpeg;base64,${btoa(bin)}`, bytes };
  } catch {
    return null;
  }
}

/** Screenshot every element marked data-export-block, in document order. */
export async function captureBlocks(root: HTMLElement): Promise<Block[]> {
  const nodes = Array.from(root.querySelectorAll<HTMLElement>("[data-export-block]"));
  const blocks: Block[] = [];
  for (const el of nodes) {
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    const dataUrl = await toPng(el, {
      backgroundColor: "#ffffff",
      pixelRatio: 2,
      filter: (n) => !(n instanceof HTMLElement && n.dataset.noExport !== undefined),
    });
    blocks.push({ id: el.dataset.exportBlock ?? "", dataUrl, width: rect.width, height: rect.height });
  }
  return blocks;
}

function subtitle(data: AnalyticsResult) {
  const range = data.date_range ? ` | ${data.date_range.start} to ${data.date_range.end}` : "";
  return `${data.row_count.toLocaleString()} rows, ${data.column_count} columns | domain: ${data.domain.domain}${range}`;
}

export async function exportPdf(data: AnalyticsResult, blocks: Block[], filename: string) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
  const pageW = 210;
  const pageH = 297;
  const margin = 12;
  const footer = 8;
  const usableW = pageW - margin * 2;
  const usableH = pageH - margin * 2 - footer;
  const gap = 4;

  const logo = await loadLogo();
  let titleX = margin;
  if (logo) {
    const lh = 15;
    const lw = (lh * LOGO_W) / LOGO_H;
    doc.addImage(logo.dataUrl, "JPEG", margin, margin - 3, lw, lh);
    titleX = margin + lw + 5;
  }
  doc.setFont("helvetica", "bold");
  doc.setFontSize(22);
  doc.setTextColor(15, 23, 42);
  doc.text("Analytics Report", titleX, margin + 6);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(100, 116, 139);
  doc.text(subtitle(data), titleX, margin + 13, { maxWidth: pageW - margin - titleX });
  let y = margin + 20;

  for (const b of blocks) {
    let w = usableW;
    let h = (w * b.height) / b.width;
    if (h > usableH) {
      h = usableH;
      w = (h * b.width) / b.height;
    }
    if (y + h > pageH - margin - footer) {
      doc.addPage();
      y = margin;
    }
    doc.addImage(b.dataUrl, "PNG", margin + (usableW - w) / 2, y, w, h, undefined, "FAST");
    y += h + gap;
  }

  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    doc.setFontSize(9);
    doc.setTextColor(148, 163, 184);
    doc.text("AETL - Auto ETL & Analysis", margin, pageH - margin + 2);
    doc.text(`Page ${i} of ${pages}`, pageW - margin, pageH - margin + 2, { align: "right" });
  }
  doc.save(filename);
}

export async function exportDocx(data: AnalyticsResult, blocks: Block[], filename: string) {
  const d = await import("docx");
  const { Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType } = d;

  const text = (t: string, opts: { bold?: boolean; italics?: boolean; size?: number; color?: string } = {}) => new TextRun({ text: t, ...opts });
  const heading = (t: string, level: (typeof HeadingLevel)[keyof typeof HeadingLevel] = HeadingLevel.HEADING_1) =>
    new Paragraph({ heading: level, spacing: { before: 280, after: 120 }, children: [text(t)] });
  const para = (t: string) => new Paragraph({ spacing: { after: 100 }, children: [text(t)] });
  const bullets = (items: string[]) => items.map((t) => new Paragraph({ bullet: { level: 0 }, spacing: { after: 60 }, children: [text(t)] }));

  const cell = (t: string, header = false, right = false) =>
    new TableCell({
      shading: header ? { type: ShadingType.CLEAR, fill: "E0E7FF", color: "auto" } : undefined,
      margins: { top: 60, bottom: 60, left: 90, right: 90 },
      children: [new Paragraph({ alignment: right ? d.AlignmentType.RIGHT : d.AlignmentType.LEFT, children: [text(t, { bold: header, size: 18 })] })],
    });
  const table = (head: string[], rows: string[][], rightFrom = 1) =>
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [
        new TableRow({ tableHeader: true, children: head.map((h, i) => cell(h, true, i >= rightFrom)) }),
        ...rows.map((r) => new TableRow({ children: r.map((c, i) => cell(c, false, i >= rightFrom)) })),
      ],
    });

  const kids: (InstanceType<typeof Paragraph> | InstanceType<typeof Table>)[] = [];
  const logo = await loadLogo();
  if (logo) {
    const w = 220;
    kids.push(
      new Paragraph({
        alignment: d.AlignmentType.CENTER,
        spacing: { after: 160 },
        children: [new ImageRun({ type: "jpg", data: logo.bytes, transformation: { width: w, height: Math.round((w * LOGO_H) / LOGO_W) } })],
      }),
    );
  }
  kids.push(
    new Paragraph({ heading: HeadingLevel.TITLE, children: [text("Analytics Report")] }),
    new Paragraph({ spacing: { after: 200 }, children: [text(subtitle(data), { color: "64748B", size: 20 })] }),
  );

  if (data.insights.headline) kids.push(heading("Summary"), para(data.insights.headline));
  if (data.preparation.length) {
    kids.push(heading("Data preparation"), para("The file was tidied in memory before analysis; the stored dataset is unchanged."), ...bullets(data.preparation));
  }

  kids.push(heading("Key metrics"));
  kids.push(table(["Group", "Metric", "Value", "Note"], data.kpis.map((k) => [k.group, k.label, typeof k.value === "number" ? `${formatValue(k.value)}${k.unit}` : String(k.value), k.note]), 2));

  const sections: [string, string[]][] = [
    ["Observed facts", data.insights.facts],
    ["Statistical relationships", data.insights.relationships],
    ["Predictions", data.insights.predictions],
    ["Recommended actions", data.insights.actions],
  ];
  kids.push(heading("Insights"));
  for (const [title, items] of sections) if (items.length) kids.push(heading(title, HeadingLevel.HEADING_3), ...bullets(items));

  const chartBlocks = blocks.filter((b) => b.id.startsWith("chart-"));
  if (chartBlocks.length) {
    kids.push(new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, children: [text("Charts")] }));
    chartBlocks.forEach((b, n) => {
      const spec = data.charts[Number(b.id.slice(6))];
      const width = 600;
      const height = Math.round((width * b.height) / b.width);
      kids.push(
        new Paragraph({ heading: HeadingLevel.HEADING_3, pageBreakBefore: n > 0 && n % 2 === 0, spacing: { before: 200, after: 60 }, children: [text(spec?.title ?? "Chart")] }),
        new Paragraph({ spacing: { after: 160 }, children: [new ImageRun({ type: "png", data: dataUrlToBytes(b.dataUrl), transformation: { width, height } })] }),
      );
    });
  }

  if (data.stats.length) {
    kids.push(new Paragraph({ pageBreakBefore: true, heading: HeadingLevel.HEADING_1, children: [text("Numeric column statistics")] }));
    kids.push(table(
      ["Column", "Count", "Missing", "Mean", "Median", "Min", "Max"],
      data.stats.map((s) => [s.column, s.count.toLocaleString(), `${s.missing_pct}%`, formatValue(s.mean, "number", true), formatValue(s.median, "number", true), formatValue(s.min, "number", true), formatValue(s.max, "number", true)]),
    ));
  }
  if (data.anomalies.length) {
    kids.push(heading("Outliers and anomalies"));
    kids.push(table(
      ["Column", "Outliers", "% of rows", "Extreme", "Largest values"],
      data.anomalies.map((a) => [a.column, a.outlier_count.toLocaleString(), `${a.outlier_pct}%`, a.extreme_count.toLocaleString(), a.examples.map((v) => formatValue(v, "number", true)).join(", ")]),
    ));
  }
  for (const c of data.categories) {
    kids.push(heading(`${c.column} (${c.unique.toLocaleString()} unique)`, HeadingLevel.HEADING_3));
    kids.push(table(["Value", "Count", "Share"], c.top.map((t) => [t.value, t.count.toLocaleString(), `${t.share_pct}%`])));
  }

  const doc = new Document({
    creator: "AETL - Auto ETL & Analysis",
    title: "Analytics Report",
    sections: [{ properties: { page: { margin: { top: 1000, bottom: 1000, left: 1000, right: 1000 } } }, children: kids }],
  });
  save(await Packer.toBlob(doc), filename);
}
