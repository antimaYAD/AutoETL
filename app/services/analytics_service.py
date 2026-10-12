"""Automatic multi-domain analytics (framework doc sections 19-25).

Pipeline: data preparation -> domain + column roles -> schema-aware KPIs ->
statistics -> chart specs -> anomalies -> forecast -> insights/actions.

Everything is deterministic -- no AI/LLM calls and no arbitrary code.
"""
from __future__ import annotations

import math
import re
import warnings

import numpy as np
import pandas as pd

from app.services.prep_service import prepare_frame

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

MAX_CHART_POINTS = 60
TOP_N = 10
FORECAST_PERIODS = 3


def _norm(name) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _to_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _fmt(v) -> str:
    f = _to_float(v)
    if f is None:
        return "n/a"
    a = abs(f)
    if a >= 1e9:
        return f"{f / 1e9:.2f}B"
    if a >= 1e6:
        return f"{f / 1e6:.2f}M"
    if a >= 1e3:
        return f"{f:,.0f}"
    return f"{f:,.2f}"


def _is_text(s: pd.Series) -> bool:
    return not (
        pd.api.types.is_numeric_dtype(s)
        or pd.api.types.is_datetime64_any_dtype(s)
        or pd.api.types.is_bool_dtype(s)
    )


def _clean(o):
    """Make the whole result strictly JSON-safe (no NaN/inf, no numpy types)."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return round(f, 4) if math.isfinite(f) else None
    if isinstance(o, pd.Timestamp):
        return o.strftime("%Y-%m-%d")
    if o is pd.NaT:
        return None
    return o


# ---------------------------------------------------------------------------
# Data preparation: make messy real-world exports analysable
# ---------------------------------------------------------------------------

_DATE_HINT = re.compile(r"date|time|period|month|day|dob|created|updated|timestamp")
_DATE_TEXT = re.compile(
    r"^\s*(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}[-/ ][A-Za-z]{3,9}[-/ ,]+\d{2,4}|[A-Za-z]{3,9}[ -]\d{1,2},?[ -]\d{2,4})"
)
_ID_SUFFIXES = ("_id", "_no", "_number", "_code", "_key", "_uuid", "_pin", "_zip")
_ID_WORDS = {"id", "uuid", "guid", "phone", "mobile", "pincode", "zip", "zipcode"}


def _looks_like_id(name: str) -> bool:
    n = _norm(name)
    return n in _ID_WORDS or n.endswith(_ID_SUFFIXES) or n.startswith("id_")


def _to_numeric_text(series: pd.Series) -> pd.Series | None:
    non_null = series.dropna()
    if non_null.empty:
        return None
    s = non_null.astype(str).str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True).str.replace(r"[,$€£₹%\s]", "", regex=True)
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().mean() >= 0.95:
        return num.reindex(series.index)
    return None


def _excel_serial_to_date(series: pd.Series) -> pd.Series | None:
    vals = _num(series).dropna()
    if vals.empty:
        return None
    if vals.between(20000, 80000).mean() > 0.95 and (vals % 1 == 0).mean() > 0.9:
        return pd.to_datetime(_num(series), unit="D", origin="1899-12-30", errors="coerce")
    return None


def _text_to_date(series: pd.Series, hinted: bool) -> pd.Series | None:
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return None
    sample = non_null.head(200)
    if not hinted and sample.map(lambda v: bool(_DATE_TEXT.match(v))).mean() < 0.8:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(series.astype(str).where(series.notna()), errors="coerce", format="mixed")
    return parsed if parsed[series.notna()].notna().mean() >= 0.9 else None


def _find_product_pair(df: pd.DataFrame, col: str, exclude: set[str] | None = None) -> tuple[str, str] | None:
    """Return (A, B) when `col` equals A x B on most rows where all three are present."""
    exclude = (exclude or set()) | {col}
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in exclude and not _looks_like_id(c)][:10]
    sample = df.sample(min(len(df), 800), random_state=0) if len(df) > 800 else df
    target = _num(sample[col])
    for i, a in enumerate(numeric):
        for b in numeric[i + 1:]:
            prod = _num(sample[a]) * _num(sample[b])
            mask = target.notna() & prod.notna()
            if mask.sum() < 10 or (target[mask] == 0).all():
                continue
            if np.isclose(prod[mask], target[mask], rtol=0.01, atol=0.01).mean() > 0.9:
                return a, b
    return None


def _name_derived_columns(df: pd.DataFrame, notes: list[str]) -> pd.DataFrame:
    """Give unlabeled numeric columns a name when they equal A x B of two other columns."""
    unlabeled = [c for c in df.columns if re.fullmatch(r"Column \d+", str(c)) and pd.api.types.is_numeric_dtype(df[c])]
    rename: dict[str, str] = {}
    for col in unlabeled:
        pair = _find_product_pair(df, col, set(unlabeled))
        if not pair:
            continue
        a, b = pair
        qty, price = (a, b) if any(k in _norm(a) for k in ("qty", "quantity", "units")) else (b, a)
        if any(k in _norm(qty) for k in ("qty", "quantity", "units")) and any(k in _norm(price) for k in ("unit", "price", "rate")):
            word = re.sub(r"(?i)\b(unit|price|rate)\b", "", str(price)).strip() or "Value"
            new = f"Total {word.title()} Amount"
        else:
            new = f"{a} × {b}"
        while new in df.columns or new in rename.values():
            new += "*"
        rename[col] = new
        notes.append(f"Unlabeled column '{col}' matches {a} × {b} on most rows; named it '{new}'.")
    return df.rename(columns=rename)


def prepare_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df, notes = prepare_frame(df)
    if df.empty:
        return df, notes

    empty_cols = [c for c in df.columns if df[c].isna().all()]
    if empty_cols:
        df = df.drop(columns=empty_cols)
        notes.append(f"Dropped {len(empty_cols)} completely empty column(s): {', '.join(map(str, empty_cols))}.")

    to_num, to_date = [], []
    for col in list(df.columns):
        s = df[col]
        hinted = bool(_DATE_HINT.search(_norm(col)))
        if pd.api.types.is_datetime64_any_dtype(s):
            continue
        if _is_text(s):
            if not _looks_like_id(col):
                num = _to_numeric_text(s)
                if num is not None:
                    serial = _excel_serial_to_date(num) if hinted else None
                    if serial is not None:
                        df[col] = serial
                        to_date.append(f"{col} (Excel serial dates)")
                    else:
                        df[col] = num
                        to_num.append(col)
                    continue
            parsed = _text_to_date(s, hinted)
            if parsed is not None:
                df[col] = parsed
                to_date.append(str(col))
        elif pd.api.types.is_numeric_dtype(s) and hinted:
            serial = _excel_serial_to_date(s)
            if serial is not None:
                df[col] = serial
                to_date.append(f"{col} (Excel serial dates)")

    if to_num:
        notes.append(f"Converted {len(to_num)} text column(s) to numbers: {', '.join(to_num)}.")
    if to_date:
        notes.append(f"Recognised date column(s): {', '.join(to_date)}.")

    df = _name_derived_columns(df, notes)
    return df, notes


# ---------------------------------------------------------------------------
# Domain detection (section 19)
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "sales": ["order", "sale", "revenue", "quantity", "unit_price", "customer", "product", "discount", "amount", "qty", "invoice"],
    "ecommerce": ["cart", "checkout", "visitor", "session", "conversion", "refund", "return_rate", "sku"],
    "finance": ["account", "expense", "budget", "invoice", "debit", "credit", "transaction", "ledger", "profit"],
    "inventory": ["stock", "inventory", "warehouse", "reorder", "on_hand", "supplier", "bin"],
    "hr": ["employee", "salary", "hire", "attrition", "tenure", "attendance", "payroll", "headcount"],
    "marketing": ["campaign", "impression", "click", "ctr", "spend", "lead", "channel", "ad_"],
    "logistics": ["shipment", "delivery", "carrier", "route", "freight", "dispatch"],
    "supply_chain": ["fulfillment", "lead_time", "backorder", "procurement", "vendor", "po_number"],
    "healthcare": ["patient", "appointment", "visit", "admission", "diagnosis", "ward"],
    "education": ["student", "course", "grade", "enrollment", "assignment", "semester"],
    "real_estate": ["property", "rent", "sqft", "listing", "bedroom", "mortgage", "lease"],
    "energy": ["consumption", "kwh", "meter", "utility", "tariff", "peak_demand"],
    "saas": ["subscription", "mrr", "arr", "plan", "renewal", "seat", "cancellation"],
}


def detect_domain(df: pd.DataFrame) -> dict:
    names = [_norm(c) for c in df.columns]
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = [kw for kw in keywords if any(kw in n for n in names)]
        if hits:
            scores[domain] = len(hits)
            matched[domain] = hits
    if not scores:
        return {"domain": "general", "confidence": 0.0, "matched_terms": []}
    best = max(scores, key=scores.get)
    confidence = max(round(scores[best] / max(len(DOMAIN_KEYWORDS[best]), 1), 2), 0.1)
    return {"domain": best, "confidence": confidence, "matched_terms": matched[best]}


# ---------------------------------------------------------------------------
# Column roles
# ---------------------------------------------------------------------------

_ENTITY_HINT = re.compile(r"name|customer|client|product|item|particular|vendor|supplier|agent|employee|region|state|city|category|segment|channel|department|type|plan")


def _is_sequential_key(series: pd.Series) -> bool:
    if len(series) < 2 or not pd.api.types.is_integer_dtype(series) or series.nunique() != len(series):
        return False
    return bool((series.sort_values().diff().dropna() == 1).all())


def detect_column_roles(df: pd.DataFrame, profile: dict | None = None) -> dict:
    roles: dict[str, list[str]] = {"date": [], "id": [], "measure": [], "dimension": [], "other": []}
    rows = len(df)
    for col in df.columns:
        s = df[col]
        nun = int(s.nunique(dropna=True))
        if pd.api.types.is_datetime64_any_dtype(s):
            roles["date"].append(col)
        elif _looks_like_id(col) or _is_sequential_key(s):
            roles["id"].append(col)
        elif pd.api.types.is_bool_dtype(s):
            roles["dimension"].append(col)
        elif pd.api.types.is_numeric_dtype(s):
            (roles["measure"] if nun > 1 else roles["other"]).append(col)
        elif nun < 2:
            roles["other"].append(col)
        elif rows > 50 and nun > 0.9 * s.notna().sum():
            roles["other"].append(col)
        else:
            roles["dimension"].append(col)
    roles["dimension"].sort(key=lambda c: (0 if _ENTITY_HINT.search(_norm(c)) else 1, int(df[c].nunique())))
    return roles


def _pick(columns, include: list[str], exclude: list[str]) -> str | None:
    best, best_score = None, 0
    for c in columns:
        n = _norm(c)
        if any(e in n for e in exclude):
            continue
        for rank, pat in enumerate(include):
            if pat in n:
                score = len(include) - rank
                if score > best_score:
                    best, best_score = c, score
                break
    return best


REVENUE_INC = ["total_sale", "sales_amount", "sale_amount", "net_sales", "total_revenue", "revenue", "total_amount", "turnover", "amount", "sales", "sale", "total", "value"]
REVENUE_EXC = ["unit", "price", "rate", "cost", "cogs", "expense", "discount", "tax", "qty", "quantity", "margin", "profit", "percent", "pct"]
COST_INC = ["total_cost", "cost_amount", "cogs", "total_expense", "expense", "cost"]
COST_EXC = ["unit", "price", "rate", "per_", "percent", "pct"]
QTY_INC = ["quantity", "qty", "units", "volume"]
QTY_EXC = ["price", "rate", "cost", "amount", "value"]
ORDER_INC = ["order_id", "invoice_number", "invoice_no", "invoice", "order_no", "order_number", "transaction_id", "txn"]
ORDER_EXC = ["date", "time", "status", "type", "name"]
CUSTOMER_INC = ["customer_name", "client_name", "customer", "client", "buyer", "account_name", "user_id"]
CUSTOMER_EXC = ["type", "segment", "category", "date"]


def _schema(df: pd.DataFrame, roles: dict) -> dict:
    measures = roles["measure"]
    all_cols = list(df.columns)
    revenue = _pick(measures, REVENUE_INC, REVENUE_EXC)
    return {
        "revenue": revenue,
        "cost": _pick(measures, COST_INC, COST_EXC),
        "quantity": _pick(measures, QTY_INC, QTY_EXC),
        "order": _pick(all_cols, ORDER_INC, ORDER_EXC),
        "customer": _pick(all_cols, CUSTOMER_INC, CUSTOMER_EXC),
        "primary": revenue or (measures[0] if measures else None),
    }


# ---------------------------------------------------------------------------
# Time series helpers
# ---------------------------------------------------------------------------

def _period_label(ts: pd.Timestamp, rule: str) -> str:
    return ts.strftime("%b %Y") if rule == "ME" else ts.strftime("%d %b %y")


def _build_time_series(df: pd.DataFrame, date_col: str, schema: dict) -> dict | None:
    frame = pd.DataFrame({"d": df[date_col]})
    frame["value"] = _num(df[schema["primary"]]) if schema["primary"] else np.nan
    frame["cost"] = _num(df[schema["cost"]]) if schema["cost"] else np.nan
    frame = frame.dropna(subset=["d"])
    if len(frame) < 2:
        return None
    span = (frame["d"].max() - frame["d"].min()).days
    rule = "ME" if span > 120 else ("W" if span > 30 else "D")
    grouped = frame.set_index("d").resample(rule)
    out = grouped[["value", "cost"]].sum(min_count=1)
    out["records"] = grouped.size()
    partial = None
    if len(out) > 3 and rule != "D":
        gap = 2 if rule == "ME" else 1
        if frame["d"].max().normalize() < out.index[-1].normalize() - pd.Timedelta(days=gap):
            partial = _period_label(out.index[-1], rule)
            out = out.iloc[:-1]
    if len(out) < 2:
        return None
    out["profit"] = out["value"] - out["cost"]
    out["margin"] = np.where(out["value"] != 0, out["profit"] / out["value"] * 100, np.nan)
    out["trend"] = out["value"].rolling(3, min_periods=2).mean() if len(out) >= 5 else np.nan
    return {"frame": out, "rule": rule, "partial": partial, "start": frame["d"].min(), "end": frame["d"].max(), "span_days": span}


# ---------------------------------------------------------------------------
# KPIs (section 20 - only when the required columns exist)
# ---------------------------------------------------------------------------

def compute_kpis(df: pd.DataFrame, roles: dict, domain: dict, schema: dict, ts: dict | None) -> list[dict]:
    kpis: list[dict] = []

    def add(key, label, value, unit="", note="", group="Performance", **extra):
        if value is not None:
            kpis.append({"key": key, "label": label, "value": value, "unit": unit, "note": note, "group": group, **extra})

    rows = len(df)
    dom = domain["domain"]
    rev_col, cost_col = schema["revenue"], schema["cost"]

    revenue = None
    if rev_col:
        rev = _num(df[rev_col])
        revenue = _to_float(rev.sum())
        label = "Total Revenue" if dom in {"sales", "ecommerce", "finance", "saas"} else f"Total {rev_col}"
        add("total_revenue", label, revenue, note=f"sum of {rev_col}")
    if schema["quantity"]:
        add("units_sold", "Units Sold" if dom in {"sales", "ecommerce", "inventory"} else f"Total {schema['quantity']}",
            _to_float(_num(df[schema["quantity"]]).sum()), note=f"sum of {schema['quantity']}")

    orders = int(df[schema["order"]].nunique()) if schema["order"] else None
    if orders:
        add("total_orders", "Total Orders", orders, note=f"distinct {schema['order']}")
        if revenue is not None:
            add("aov", "Average Order Value", _to_float(revenue / orders))
    customers = int(df[schema["customer"]].nunique()) if schema["customer"] else None
    if customers:
        add("customers", "Unique Customers", customers, note=f"distinct {schema['customer']}")
        if revenue is not None:
            add("revenue_per_customer", "Revenue per Customer", _to_float(revenue / customers))

    if rev_col and cost_col:
        both = pd.DataFrame({"r": _num(df[rev_col]), "c": _num(df[cost_col])}).dropna()
        if not both.empty:
            profit = both["r"].sum() - both["c"].sum()
            add("gross_profit", "Gross Profit", _to_float(profit), note=f"{rev_col} - {cost_col}")
            if both["r"].sum():
                add("margin_pct", "Gross Margin", _to_float(profit / both["r"].sum() * 100), "%")
            loss = both[both["r"] < both["c"]]
            if len(loss):
                add("loss_rows", "Loss-making Rows", int(len(loss)), note=f"{_fmt((loss['c'] - loss['r']).sum())} total shortfall")

    if ts is not None:
        f = ts["frame"]
        add("date_range", "Date Range", f"{ts['start']:%d %b %Y} → {ts['end']:%d %b %Y}", note=f"{ts['span_days'] + 1} days")
        if schema["primary"] and f["value"].notna().any() and len(f) >= 2:
            last, prev = f["value"].iloc[-1], f["value"].iloc[-2]
            if prev:
                add("mom_growth", "Latest Period Growth", _to_float((last - prev) / abs(prev) * 100), "%",
                    note=f"{_period_label(f.index[-1], ts['rule'])} vs {_period_label(f.index[-2], ts['rule'])}")
            unit = {"ME": "Month", "W": "Week", "D": "Day"}[ts["rule"]]
            add("avg_period", f"Avg {unit}ly {schema['primary']}" if unit != "Day" else f"Avg Daily {schema['primary']}", _to_float(f["value"].mean()))
            best = f["value"].idxmax()
            add("best_period", f"Best {unit}", _period_label(best, ts["rule"]), note=_fmt(f["value"].max()))

    dim = _concentration_dim(df, schema, roles)
    if dim and schema["primary"]:
        grouped = _num(df[schema["primary"]]).groupby(df[dim]).sum().sort_values(ascending=False)
        total = grouped[grouped > 0].sum()
        if total and len(grouped) >= 20:
            add("top10_share", f"Top 10 {dim} Share", _to_float(grouped.head(10).clip(lower=0).sum() / total * 100), "%",
                note=f"of total {schema['primary']}", dim=dim)

    missing_pct = round(float(df.isna().sum().sum() / max(df.size, 1) * 100), 2)
    add("total_records", "Total Records", rows, group="Data quality")
    add("completeness", "Completeness", round(100 - missing_pct, 2), "%", group="Data quality")
    add("missing_pct", "Missing Values", missing_pct, "%", group="Data quality")
    add("duplicate_pct", "Duplicate Rows", round(float(df.duplicated().mean() * 100), 2) if rows else 0.0, "%", group="Data quality")
    add("unique_cols", "Columns", int(df.shape[1]), group="Data quality")
    return kpis


def _concentration_dim(df: pd.DataFrame, schema: dict, roles: dict) -> str | None:
    if schema["customer"] and schema["customer"] in df.columns and _is_text(df[schema["customer"]]):
        return schema["customer"]
    for d in roles["dimension"]:
        if df[d].nunique() >= 20:
            return d
    return None


# ---------------------------------------------------------------------------
# Statistics tables
# ---------------------------------------------------------------------------

def column_stats(df: pd.DataFrame, roles: dict) -> list[dict]:
    rows = []
    for col in roles["measure"][:12]:
        s = _num(df[col])
        v = s.dropna()
        if v.empty:
            continue
        rows.append({
            "column": col, "count": int(v.count()), "missing_pct": round(float(s.isna().mean() * 100), 2),
            "sum": _to_float(v.sum()), "mean": _to_float(v.mean()), "median": _to_float(v.median()),
            "std": _to_float(v.std()), "min": _to_float(v.min()), "p25": _to_float(v.quantile(0.25)),
            "p75": _to_float(v.quantile(0.75)), "p95": _to_float(v.quantile(0.95)), "max": _to_float(v.max()),
            "skew": _to_float(v.skew()) if len(v) > 2 else None,
        })
    return rows


def category_summaries(df: pd.DataFrame, roles: dict, schema: dict) -> list[dict]:
    out = []
    for dim in roles["dimension"][:6]:
        counts = df[dim].value_counts(dropna=True)
        total = int(counts.sum())
        sums = _num(df[schema["primary"]]).groupby(df[dim]).sum() if schema["primary"] else None
        out.append({
            "column": dim, "unique": int(df[dim].nunique()),
            "top": [
                {"value": str(k), "count": int(v), "share_pct": round(v / total * 100, 2),
                 "measure_total": _to_float(sums.get(k)) if sums is not None else None}
                for k, v in counts.head(8).items()
            ],
        })
    return out


# ---------------------------------------------------------------------------
# Charts (section 21)
# ---------------------------------------------------------------------------

def _spec(kind, title, data, series, x_label="", y_label="", fmt="number", description="", **extra):
    return {"kind": kind, "title": title, "description": description, "x_key": "label", "series": series,
            "data": data, "x_label": x_label, "y_label": y_label, "format": fmt, **extra}


def _clipped_histogram(df: pd.DataFrame, col: str, bins: int = 14) -> dict | None:
    v = _num(df[col]).dropna()
    if len(v) < 5 or v.nunique() < 3:
        return None
    lo, hi = v.quantile(0.01), v.quantile(0.99)
    clipped = v[(v >= lo) & (v <= hi)]
    if clipped.nunique() < 3:
        clipped, lo, hi = v, v.min(), v.max()
    counts, edges = np.histogram(clipped, bins=bins)
    note = f"Showing the 1st-99th percentile ({_fmt(lo)} to {_fmt(hi)}); {len(v) - len(clipped)} extreme value(s) hidden." if len(clipped) < len(v) else ""
    return _spec(
        "histogram", f"Distribution of {col}",
        [{"label": f"{_fmt(edges[i])}", "range": f"{_fmt(edges[i])} – {_fmt(edges[i + 1])}", "value": int(counts[i])} for i in range(len(counts))],
        [{"key": "value", "label": "Records"}], x_label=col, y_label="Number of records", fmt="count", description=note,
    )


def build_charts(df: pd.DataFrame, roles: dict, schema: dict, ts: dict | None, forecast: dict | None) -> list[dict]:
    charts: list[dict] = []
    primary = schema["primary"]

    if ts is not None and primary:
        f, rule = ts["frame"].tail(MAX_CHART_POINTS), ts["rule"]
        unit = {"ME": "month", "W": "week", "D": "day"}[rule]
        desc = f"Latest {unit} ({ts['partial']}) is incomplete and excluded." if ts["partial"] else ""
        rows = [{"label": _period_label(i, rule), "value": _to_float(r["value"]) or 0, "trend": _to_float(r["trend"])} for i, r in f.iterrows()]
        series = [{"key": "value", "label": primary}] + ([{"key": "trend", "label": "3-period average", "dashed": True}] if f["trend"].notna().any() else [])
        charts.append(_spec("line", f"{primary} by {unit}", rows, series, x_label=unit.capitalize(), y_label=primary, description=desc))

        if forecast:
            charts.append(forecast["chart"])

        if schema["cost"]:
            rows = [{"label": _period_label(i, rule), "revenue": _to_float(r["value"]) or 0, "cost": _to_float(r["cost"]) or 0, "profit": _to_float(r["profit"]) or 0} for i, r in f.iterrows()]
            charts.append(_spec("line", f"Revenue vs cost vs profit by {unit}", rows,
                                [{"key": "revenue", "label": "Revenue"}, {"key": "cost", "label": "Cost"}, {"key": "profit", "label": "Profit"}],
                                x_label=unit.capitalize(), y_label="Amount", description=desc))
            rows = [{"label": _period_label(i, rule), "value": _to_float(r["margin"])} for i, r in f.iterrows() if pd.notna(r["margin"])]
            if len(rows) >= 2:
                charts.append(_spec("line", f"Gross margin % by {unit}", rows, [{"key": "value", "label": "Margin %"}],
                                    x_label=unit.capitalize(), y_label="Margin (%)", fmt="percent"))

        charts.append(_spec("bar", f"Transactions per {unit}", [{"label": _period_label(i, rule), "value": int(r["records"])} for i, r in f.iterrows()],
                            [{"key": "value", "label": "Transactions"}], x_label=unit.capitalize(), y_label="Number of records", fmt="count", description=desc))

        if ts["span_days"] >= 14 and len(df) >= 50:
            d = df[roles["date"][0]]
            wk = _num(df[primary]).groupby(d.dt.dayofweek).sum().reindex(range(7)).fillna(0)
            names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            charts.append(_spec("bar", f"{primary} by weekday", [{"label": names[i], "value": _to_float(v) or 0} for i, v in wk.items()],
                                [{"key": "value", "label": primary}], x_label="Day of week", y_label=primary,
                                description="Which days of the week drive the most activity."))

    if primary:
        values = _num(df[primary])
        ranked, pareto_done = 0, False
        for dim in roles["dimension"]:
            if ranked >= 5:
                break
            grouped = values.groupby(df[dim].astype(str)).sum().sort_values(ascending=False)
            if len(grouped) < 2:
                continue
            total = grouped[grouped > 0].sum() or 1
            top = grouped.head(TOP_N)
            charts.append(_spec(
                "hbar", f"Top {len(top)} {dim} by {primary}",
                [{"label": str(k), "value": _to_float(v) or 0, "share": round(float(max(v, 0) / total * 100), 1)} for k, v in top.items()],
                [{"key": "value", "label": primary}], x_label=primary, y_label=dim,
                description=f"{len(grouped)} distinct {dim}; the top {len(top)} hold {max(top.clip(lower=0).sum(), 0) / total * 100:.1f}% of the total.",
            ))
            ranked += 1
            if not pareto_done and len(grouped) >= 10 and (dim == schema["customer"] or not schema["customer"]):
                pareto_done = True
                pos = grouped[grouped > 0].head(15)
                cum = (pos.cumsum() / total * 100).round(1)
                charts.append(_spec(
                    "pareto", f"Pareto: {dim} contribution to {primary}",
                    [{"label": str(k), "value": _to_float(v) or 0, "cumulative": float(cum[k])} for k, v in pos.items()],
                    [{"key": "value", "label": primary}, {"key": "cumulative", "label": "Cumulative %"}],
                    x_label=dim, y_label=primary, description="Bars show each item's total; the line shows the running share of the overall total.",
                ))

        donuts = 0
        for dim in roles["dimension"]:
            if donuts >= 2:
                break
            grouped = values.groupby(df[dim].astype(str)).sum().sort_values(ascending=False)
            grouped = grouped[grouped > 0]
            if not 2 <= len(grouped) <= 14:
                continue
            total = grouped.sum()
            head, rest = grouped.head(6), grouped.iloc[6:].sum()
            data = [{"label": str(k), "value": _to_float(v) or 0, "share": round(float(v / total * 100), 1)} for k, v in head.items()]
            if rest > 0:
                data.append({"label": "Other", "value": _to_float(rest) or 0, "share": round(float(rest / total * 100), 1)})
            charts.append(_spec("donut", f"{primary} share by {dim}", data, [{"key": "value", "label": primary}]))
            donuts += 1

    hist_cols = [c for c in dict.fromkeys([primary, schema["quantity"], *roles["measure"]]) if c][:3]
    for col in hist_cols:
        h = _clipped_histogram(df, col)
        if h:
            charts.append(h)

    x = schema["quantity"] or (roles["measure"][0] if roles["measure"] else None)
    y = primary if primary != x else (roles["measure"][1] if len(roles["measure"]) > 1 else None)
    if x and y and x != y:
        sub = pd.DataFrame({"x": _num(df[x]), "y": _num(df[y])}).dropna()
        if len(sub) >= 5:
            trimmed = sub[(sub["x"] <= sub["x"].quantile(0.99)) & (sub["y"] <= sub["y"].quantile(0.99))]
            sub = trimmed.sample(min(len(trimmed), 500), random_state=0)
            charts.append(_spec("scatter", f"{x} vs {y}", [{"x": _to_float(a), "y": _to_float(b)} for a, b in zip(sub["x"], sub["y"])],
                                [{"key": "y", "label": y}], x_label=x, y_label=y, description="Sample of up to 500 records (top 1% trimmed for readability)."))

    numeric = [c for c in roles["measure"] if _num(df[c]).notna().sum() > 1][:8]
    if len(numeric) >= 2:
        corr = df[numeric].apply(_num).corr()
        charts.append({"kind": "heatmap", "title": "Correlation between numeric columns", "description": "Values near +1 or -1 indicate a strong linear relationship. Correlation is not causation.",
                       "columns": numeric, "matrix": [[_to_float(corr.loc[a, b]) or 0 for b in numeric] for a in numeric]})

    miss = (df.isna().mean() * 100)
    miss = miss[miss > 0].sort_values(ascending=False).head(12)
    if not miss.empty:
        charts.append(_spec("hbar", "Missing values by column", [{"label": str(k), "value": round(float(v), 2)} for k, v in miss.items()],
                            [{"key": "value", "label": "% missing"}], x_label="% of rows missing", y_label="Column", fmt="percent"))
    return charts


# ---------------------------------------------------------------------------
# Anomalies (section 22)
# ---------------------------------------------------------------------------

def detect_anomalies(df: pd.DataFrame, roles: dict) -> list[dict]:
    anomalies = []
    for col in roles["measure"][:10]:
        vals = _num(df[col]).dropna()
        if len(vals) < 10:
            continue
        q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            deviating = vals[vals != q1]
            if 0 < len(deviating) <= max(1, int(len(vals) * 0.05)):
                anomalies.append({"column": col, "outlier_count": int(len(deviating)), "outlier_pct": round(len(deviating) / len(vals) * 100, 2),
                                  "extreme_count": int(len(deviating)), "lower_bound": _to_float(q1), "upper_bound": _to_float(q1),
                                  "max_value": _to_float(vals.max()), "examples": [_to_float(v) for v in deviating.abs().nlargest(3).index.map(lambda i: vals[i])]})
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (vals < lo) | (vals > hi)
        count = int(mask.sum())
        if count:
            extreme = int(((vals < q1 - 3 * iqr) | (vals > q3 + 3 * iqr)).sum())
            anomalies.append({"column": col, "outlier_count": count, "outlier_pct": round(count / len(vals) * 100, 2), "extreme_count": extreme,
                              "lower_bound": _to_float(lo), "upper_bound": _to_float(hi), "max_value": _to_float(vals.max()),
                              "examples": [_to_float(v) for v in vals[mask].abs().sort_values(ascending=False).head(3).index.map(lambda i: vals[i])]})
    return anomalies


# ---------------------------------------------------------------------------
# Forecast (section 22 - deterministic linear trend with an 80% band)
# ---------------------------------------------------------------------------

def build_forecast(ts: dict | None, primary: str | None) -> dict | None:
    if ts is None or not primary:
        return None
    series = ts["frame"]["value"].dropna()
    n = len(series)
    if n < 4:
        return None
    rule = ts["rule"]
    y = series.values.astype(float)
    x = np.arange(n)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    resid_std = float(np.std(y - fitted, ddof=2)) if n > 2 else 0.0
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = float(1 - ((y - fitted) ** 2).sum() / ss_tot) if ss_tot else 0.0
    future_x = np.arange(n, n + FORECAST_PERIODS)
    fut = slope * future_x + intercept
    band = 1.28 * resid_std
    floor = 0.0 if (y >= 0).all() else -np.inf
    lower, upper, fut = np.maximum(fut - band, floor), fut + band, np.maximum(fut, floor)
    idx = pd.date_range(series.index[-1], periods=FORECAST_PERIODS + 1, freq=rule)[1:]
    confidence = "low" if (n < 6 or r2 < 0.3) else ("medium" if r2 < 0.7 else "high")

    hist = [{"label": _period_label(i, rule), "value": _to_float(v)} for i, v in series.items()]
    fc = [{"label": _period_label(i, rule), "value": _to_float(v), "lower": _to_float(lo), "upper": _to_float(up)} for i, v, lo, up in zip(idx, fut, lower, upper)]
    data = [{"label": h["label"], "actual": h["value"]} for h in hist[-MAX_CHART_POINTS:]]
    data[-1]["forecast"] = data[-1]["actual"]
    data += [{"label": f["label"], "forecast": f["value"], "lower": f["lower"], "upper": f["upper"]} for f in fc]
    unit = {"ME": "month", "W": "week", "D": "day"}[rule]
    chart = _spec("forecast", f"{primary}: actual vs forecast (next {FORECAST_PERIODS} {unit}s)", data,
                  [{"key": "actual", "label": "Actual"}, {"key": "forecast", "label": "Forecast", "dashed": True},
                   {"key": "lower", "label": "Lower (80%)", "faint": True}, {"key": "upper", "label": "Upper (80%)", "faint": True}],
                  x_label=unit.capitalize(), y_label=primary,
                  description=f"Linear trend over {n} complete {unit}s (R²={r2:.2f}, confidence: {confidence}).")
    return {"measure": primary, "method": "linear_trend", "periods": n, "r2": round(r2, 3), "confidence": confidence,
            "slope": _to_float(slope), "history": hist, "forecast": fc, "chart": chart}


# ---------------------------------------------------------------------------
# Insights + actions (sections 23-24)
# ---------------------------------------------------------------------------

def generate_insights(df, roles, domain, schema, kpis, anomalies, forecast, ts, prep_notes) -> dict:
    facts, relationships, predictions, actions = [], [], [], []
    km = {k["key"]: k for k in kpis}
    primary = schema["primary"]
    dom = domain["domain"]

    facts.append(f"Detected domain: {dom} ({int(domain['confidence'] * 100)}% confidence; matched {', '.join(domain['matched_terms'][:5])})."
                 if dom != "general" else "No specific business domain detected, so generic analysis was applied.")
    facts.append(f"Analysed {len(df):,} rows and {df.shape[1]} columns after preparation.")
    if ts is not None:
        facts.append(f"Data spans {ts['start']:%d %b %Y} to {ts['end']:%d %b %Y} ({ts['span_days'] + 1} days).")

    if "total_revenue" in km:
        line = f"{schema['revenue']} totals {_fmt(km['total_revenue']['value'])}"
        if "gross_profit" in km:
            line += f" against a total cost of {_fmt(km['total_revenue']['value'] - km['gross_profit']['value'])}, giving a gross profit of {_fmt(km['gross_profit']['value'])}"
            if "margin_pct" in km:
                line += f" ({km['margin_pct']['value']:.1f}% margin)"
        facts.append(line + ".")

    if schema["revenue"] and _num(df[schema["revenue"]]).isna().mean() > 0.01:
        pair = _find_product_pair(df, schema["revenue"])
        if pair:
            a, b = pair
            gap = df[_num(df[schema["revenue"]]).isna()]
            est = (_num(gap[a]) * _num(gap[b])).sum()
            pct = _num(df[schema["revenue"]]).isna().mean() * 100
            facts.append(f"{pct:.1f}% of {schema['revenue']} values are blank, although it equals {a} × {b} on the other rows. "
                         f"Those blank rows imply roughly {_fmt(est)} of additional revenue not included in the totals above.")
            actions.append(f"Fill the blank {schema['revenue']} values using {a} × {b} to get complete revenue figures.")
    if "aov" in km:
        facts.append(f"Average order value is {_fmt(km['aov']['value'])} across {km['total_orders']['value']:,} orders.")

    if primary and pd.api.types.is_numeric_dtype(df[primary]):
        v = _num(df[primary]).dropna()
        if len(v) > 10 and v.median() > 0 and v.mean() > 2 * v.median():
            facts.append(f"{primary} is heavily right-skewed (median {_fmt(v.median())} vs mean {_fmt(v.mean())}): a small number of very large transactions drive the total.")

    if ts is not None and primary:
        f = ts["frame"]["value"].dropna()
        unit = {"ME": "month", "W": "week", "D": "day"}[ts["rule"]]
        if len(f) >= 2:
            best, worst = f.idxmax(), f.idxmin()
            facts.append(f"Best {unit}: {_period_label(best, ts['rule'])} ({_fmt(f.max())}); weakest {unit}: {_period_label(worst, ts['rule'])} ({_fmt(f.min())}).")
        if "mom_growth" in km:
            g = km["mom_growth"]["value"]
            facts.append(f"{primary} {'increased' if g >= 0 else 'decreased'} {abs(g):.1f}% ({km['mom_growth']['note']}).")
        if len(f) >= 6 and f.std() > 0:
            z = (f - f.mean()) / f.std()
            for i in z[z.abs() > 2].index[:3]:
                facts.append(f"{_period_label(i, ts['rule'])} was unusually {'high' if z[i] > 0 else 'low'} ({_fmt(f[i])}, {abs(z[i]):.1f} standard deviations from the average).")
        if ts["partial"]:
            facts.append(f"The latest {unit} ({ts['partial']}) is incomplete, so it was excluded from trends, growth and the forecast.")

    if primary:
        values = _num(df[primary])
        for dim in roles["dimension"][:3]:
            g = values.groupby(df[dim].astype(str)).sum().sort_values(ascending=False)
            pos = g[g > 0]
            if len(pos) >= 2 and pos.sum():
                facts.append(f"'{g.index[0]}' is the largest {dim}, contributing {g.iloc[0] / pos.sum() * 100:.1f}% of total {primary}"
                             + (f"; the top 3 together contribute {pos.head(3).sum() / pos.sum() * 100:.1f}%." if len(pos) > 5 else "."))
                if len(pos) > 5 and pos.head(3).sum() / pos.sum() > 0.6:
                    actions.append(f"{dim} concentration is high (top 3 = {pos.head(3).sum() / pos.sum() * 100:.0f}% of {primary}). Consider reducing dependency on a few {dim} values.")
        if "top10_share" in km:
            facts.append(f"The top 10 {km['top10_share']['dim']} values generate {km['top10_share']['value']:.1f}% of {primary}.")
        if ts is not None and ts["span_days"] >= 14 and len(df) >= 50:
            wk = values.groupby(df[roles["date"][0]].dt.dayofweek).sum()
            if len(wk) >= 3 and wk.sum():
                names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                facts.append(f"{names[int(wk.idxmax())]} is the strongest weekday ({wk.max() / wk.sum() * 100:.1f}% of {primary}); {names[int(wk.idxmin())]} is the weakest.")

    if "loss_rows" in km:
        facts.append(f"{km['loss_rows']['value']:,} row(s) have {schema['revenue']} below {schema['cost']} ({km['loss_rows']['note']}).")
        actions.append(f"Review the {km['loss_rows']['value']:,} loss-making line items for pricing or discount errors.")

    for a in anomalies[:3]:
        facts.append(f"{a['column']}: {a['outlier_count']:,} outlier(s) ({a['outlier_pct']}% of rows), {a['extreme_count']:,} of them extreme; largest value {_fmt(a['max_value'])}.")

    miss = df.isna().mean() * 100
    worst = miss[miss > 5].sort_values(ascending=False).head(3)
    for col, pct in worst.items():
        facts.append(f"Column '{col}' is {pct:.1f}% empty.")
    numeric = [c for c in roles["measure"] if _num(df[c]).notna().sum() > 1][:8]
    if len(numeric) >= 2:
        corr = df[numeric].apply(_num).corr()
        pairs = sorted(((abs(corr.loc[a, b]), a, b, corr.loc[a, b]) for i, a in enumerate(numeric) for b in numeric[i + 1:] if pd.notna(corr.loc[a, b])), reverse=True)
        for _, a, b, r in pairs[:3]:
            if abs(r) >= 0.5:
                relationships.append(f"'{a}' and '{b}' are {'positively' if r > 0 else 'negatively'} correlated (r={r:.2f}). Correlation does not imply causation.")

    if forecast:
        last_hist, last_fc = forecast["history"][-1]["value"], forecast["forecast"][-1]["value"]
        unit = {"ME": "month", "W": "week", "D": "day"}[ts["rule"]]
        delta = (last_fc - last_hist) / abs(last_hist) * 100 if last_hist else 0
        predictions.append(f"Linear trend over {forecast['periods']} {unit}s projects {forecast['measure']} to {'rise' if delta >= 0 else 'fall'} about {abs(delta):.1f}% "
                           f"to {_fmt(last_fc)} within {FORECAST_PERIODS} {unit}s (80% range {_fmt(forecast['forecast'][-1]['lower'])} to {_fmt(forecast['forecast'][-1]['upper'])}).")
        predictions.append(f"Forecast confidence is {forecast['confidence']} (R²={forecast['r2']}); with only {forecast['periods']} periods treat it as directional.")
        if delta < -10:
            actions.append(f"Forecast shows a >10% decline in {forecast['measure']}; review the categories and customers driving it.")
    else:
        predictions.append("No forecast: this needs a date column with at least 4 complete periods of data.")

    if anomalies:
        actions.append(f"Investigate extreme values in '{anomalies[0]['column']}' before relying on averages; the median is a safer summary.")
    if km.get("missing_pct", {}).get("value", 0) > 5:
        actions.append("Missing-value rate exceeds 5%; consider filling or removing sparse columns before downstream use.")
    if km.get("duplicate_pct", {}).get("value", 0) > 1:
        actions.append("Duplicate rows exceed 1%; run the 'Remove duplicates' transformation.")

    headline = " ".join(facts[2:4]) if len(facts) > 3 else facts[0]
    return {"headline": headline, "facts": facts, "relationships": relationships, "predictions": predictions, "actions": actions}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def analyze_dataset(df: pd.DataFrame) -> dict:
    df, prep_notes = prepare_dataframe(df)
    domain = detect_domain(df)

    if df.empty or df.shape[1] == 0:
        return _clean({
            "domain": domain, "column_roles": {"date": [], "id": [], "measure": [], "dimension": [], "other": []},
            "kpis": [], "charts": [], "anomalies": [], "forecast": None, "stats": [], "categories": [],
            "preparation": prep_notes, "date_range": None, "row_count": 0, "column_count": int(df.shape[1]),
            "insights": {"headline": "The dataset has no data rows.", "facts": ["The dataset has no data rows to analyse."], "relationships": [], "predictions": [], "actions": []},
        })

    roles = detect_column_roles(df)
    schema = _schema(df, roles)
    ts = _build_time_series(df, roles["date"][0], schema) if roles["date"] and schema["primary"] else None
    forecast = build_forecast(ts, schema["primary"])
    kpis = compute_kpis(df, roles, domain, schema, ts)
    charts = build_charts(df, roles, schema, ts, forecast)
    anomalies = detect_anomalies(df, roles)
    insights = generate_insights(df, roles, domain, schema, kpis, anomalies, forecast, ts, prep_notes)

    return _clean({
        "domain": domain,
        "column_roles": roles,
        "columns_used": {k: v for k, v in schema.items() if v},
        "kpis": kpis,
        "charts": charts,
        "anomalies": anomalies,
        "forecast": {k: v for k, v in forecast.items() if k != "chart"} if forecast else None,
        "stats": column_stats(df, roles),
        "categories": category_summaries(df, roles, schema),
        "preparation": prep_notes,
        "date_range": {"start": ts["start"], "end": ts["end"]} if ts else None,
        "insights": insights,
        "row_count": int(len(df)),
        "column_count": int(df.shape[1]),
    })
