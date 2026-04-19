from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import run  # noqa: E402
from src.schema import FINAL_COLUMNS  # noqa: E402


def _write_excel(df: pd.DataFrame, xlsx_path: Path) -> None:
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.formatting.rule import CellIsRule

    df = df.copy()
    df["premium_amount"] = pd.to_numeric(df["premium_amount"], errors="coerce")
    df["od_end_date_dt"] = pd.to_datetime(df["od_end_date"], errors="coerce")

    # --- Aggregations ---
    by_status = (
        df.groupby("status", dropna=False)
        .agg(policies=("source_file", "count"), total_premium=("premium_amount", "sum"))
        .reset_index().sort_values("policies", ascending=False)
    )
    by_company = (
        df.groupby("insurance_company_name", dropna=False)
        .agg(
            policies=("source_file", "count"),
            total_premium=("premium_amount", "sum"),
            avg_premium=("premium_amount", "mean"),
        )
        .reset_index().sort_values("policies", ascending=False)
    )
    by_type = (
        df.groupby(["policy_type", "policy_duration"], dropna=False)
        .agg(policies=("source_file", "count"), total_premium=("premium_amount", "sum"))
        .reset_index().sort_values("policies", ascending=False)
    )
    by_month = (
        df.assign(expiry_month=df["od_end_date_dt"].dt.strftime("%Y-%m"))
        .groupby("expiry_month", dropna=False)
        .agg(policies=("source_file", "count"))
        .reset_index().sort_values("expiry_month")
    )
    alerts = (
        df[df["days_left"].apply(lambda v: isinstance(v, (int, float)) and v <= 30)]
        .sort_values("days_left")
        .drop(columns=["od_end_date_dt"])
    )

    total = len(df)
    count = {s: int(by_status.loc[by_status["status"] == s, "policies"].sum())
             for s in ["Active", "Expiring Soon", "Expired"]}
    total_premium = float(df["premium_amount"].sum())

    df_out = df.drop(columns=["od_end_date_dt"])

    # --- Styles ---
    NAVY      = "1E3A5F"
    WHITE     = "FFFFFF"
    GREEN     = "16A34A"
    AMBER     = "D97706"
    RED       = "DC2626"
    LIGHT_GREY= "F8FAFC"
    LIGHT_GREEN = "DCFCE7"
    LIGHT_AMBER = "FEF3C7"
    LIGHT_RED   = "FEE2E2"
    ACCENT    = "3B82F6"

    def fill(hex_color):
        return PatternFill("solid", fgColor=hex_color)

    def thin_border():
        s = Side(style="thin", color="CBD5E1")
        return Border(left=s, right=s, top=s, bottom=s)

    def style_header(ws, fill_color=NAVY, font_color=WHITE):
        for cell in ws[1]:
            cell.fill = fill(fill_color)
            cell.font = Font(bold=True, color=font_color)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border()

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        # Write data sheets first so chart references work
        df_out.to_excel(writer, index=False, sheet_name="All Policies")
        alerts.to_excel(writer, index=False, sheet_name="Expiry Alerts (<=30d)")
        by_status.to_excel(writer, index=False, sheet_name="By Status")
        by_company.to_excel(writer, index=False, sheet_name="By Insurer")
        by_type.to_excel(writer, index=False, sheet_name="By Policy Type")
        by_month.to_excel(writer, index=False, sheet_name="By Expiry Month")

        wb = writer.book

        # ── All Policies: live formulas + conditional formatting ──────────
        ws_all = writer.sheets["All Policies"]
        col_map = {ws_all.cell(1, c).value: get_column_letter(c)
                   for c in range(1, ws_all.max_column + 1)}
        od_end = col_map.get("od_end_date", "F")
        days_c = col_map.get("days_left", "J")
        stat_c = col_map.get("status", "K")

        style_header(ws_all)
        ws_all.freeze_panes = "A2"
        ws_all.auto_filter.ref = ws_all.dimensions
        ws_all.sheet_view.showGridLines = False

        last_row = ws_all.max_row
        for row in range(2, last_row + 1):
            ws_all[f"{days_c}{row}"].value = (
                f'=IF({od_end}{row}="","",IFERROR(INT({od_end}{row}-TODAY()),""))'
            )
            ws_all[f"{stat_c}{row}"].value = (
                f'=IF({days_c}{row}="","",IF({days_c}{row}<0,"Expired",'
                f'IF({days_c}{row}<=30,"Expiring Soon","Active")))'
            )
            # Zebra rows
            if row % 2 == 0:
                for col in range(1, ws_all.max_column + 1):
                    ws_all.cell(row, col).fill = fill(LIGHT_GREY)

        # Conditional formatting on status column
        stat_range = f"{stat_c}2:{stat_c}{last_row}"
        ws_all.conditional_formatting.add(stat_range,
            CellIsRule("equal", ['"Active"'],         fill=fill(LIGHT_GREEN), font=Font(color=GREEN, bold=True)))
        ws_all.conditional_formatting.add(stat_range,
            CellIsRule("equal", ['"Expiring Soon"'],  fill=fill(LIGHT_AMBER), font=Font(color=AMBER, bold=True)))
        ws_all.conditional_formatting.add(stat_range,
            CellIsRule("equal", ['"Expired"'],        fill=fill(LIGHT_RED),   font=Font(color=RED,   bold=True)))

        # ── Style other data sheets ───────────────────────────────────────
        for name in ["Expiry Alerts (<=30d)", "By Status", "By Insurer",
                     "By Policy Type", "By Expiry Month"]:
            ws = writer.sheets[name]
            style_header(ws)
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

        # ── Dashboard sheet (first sheet, opens by default) ───────────────
        ws_dash = wb.create_sheet("Dashboard", 0)
        ws_dash.sheet_view.showGridLines = False
        ws_dash.sheet_view.showRowColHeaders = False
        ws_dash.column_dimensions["A"].width = 3
        for col in "BCDEFGHIJ":
            ws_dash.column_dimensions[col].width = 18

        # Title
        ws_dash.merge_cells("B2:I2")
        title = ws_dash["B2"]
        title.value = "ALT MOBILITY — INSURANCE POLICY DASHBOARD"
        title.font = Font(name="Calibri", size=18, bold=True, color=NAVY)
        title.alignment = Alignment(horizontal="center", vertical="center")
        ws_dash.row_dimensions[2].height = 36

        # Subtitle
        ws_dash.merge_cells("B3:I3")
        sub = ws_dash["B3"]
        sub.value = "Own Damage Policy Tracker  |  315 Policies  |  Dates auto-refresh on open"
        sub.font = Font(name="Calibri", size=10, color="64748B", italic=True)
        sub.alignment = Alignment(horizontal="center")
        ws_dash.row_dimensions[3].height = 18

        # KPI boxes  — row 5 (label) + row 6 (value)
        kpis = [
            ("B", "TOTAL POLICIES",  str(total),           NAVY,  WHITE),
            ("D", "ACTIVE",          str(count.get("Active", 0)),          GREEN, WHITE),
            ("F", "EXPIRING SOON",   str(count.get("Expiring Soon", 0)),   AMBER, WHITE),
            ("H", "EXPIRED",         str(count.get("Expired", 0)),         RED,   WHITE),
        ]
        for col, label, value, bg, fg in kpis:
            ws_dash.merge_cells(f"{col}5:{col}5")
            ws_dash.merge_cells(f"{col}6:{col}6")
            lbl_cell = ws_dash[f"{col}5"]
            val_cell = ws_dash[f"{col}6"]
            lbl_cell.value = label
            lbl_cell.fill  = fill(bg)
            lbl_cell.font  = Font(bold=True, color=fg, size=9)
            lbl_cell.alignment = Alignment(horizontal="center", vertical="center")
            lbl_cell.border = thin_border()
            val_cell.value = value
            val_cell.fill  = fill(bg)
            val_cell.font  = Font(bold=True, color=fg, size=22)
            val_cell.alignment = Alignment(horizontal="center", vertical="center")
            val_cell.border = thin_border()
            ws_dash.row_dimensions[5].height = 20
            ws_dash.row_dimensions[6].height = 40

        # Premium KPI
        ws_dash.merge_cells("B7:C7")
        ws_dash.merge_cells("D7:I7")
        prem_lbl = ws_dash["B7"]
        prem_val = ws_dash["D7"]
        prem_lbl.value = "TOTAL PREMIUM (INR)"
        prem_lbl.font  = Font(bold=True, color=NAVY, size=9)
        prem_lbl.fill  = fill("E2E8F0")
        prem_lbl.alignment = Alignment(horizontal="right", vertical="center")
        prem_val.value = f"₹{total_premium:,.2f}"
        prem_val.font  = Font(bold=True, color=NAVY, size=12)
        prem_val.fill  = fill("E2E8F0")
        prem_val.alignment = Alignment(horizontal="left", vertical="center")
        ws_dash.row_dimensions[7].height = 24

        # ── Chart 1: Policies by Status (Pie) ──
        ws_st = writer.sheets["By Status"]
        n_status = ws_st.max_row - 1
        pie = PieChart()
        pie.title = "Policies by Status"
        pie.style = 10
        labels_ref = Reference(ws_st, min_col=1, min_row=2, max_row=1 + n_status)
        data_ref   = Reference(ws_st, min_col=2, min_row=1, max_row=1 + n_status)
        pie.add_data(data_ref, titles_from_data=True)
        pie.set_categories(labels_ref)
        pie.width = 14; pie.height = 12
        ws_dash.add_chart(pie, "B9")

        # ── Chart 2: Top Insurers (Bar) ──
        ws_ins = writer.sheets["By Insurer"]
        n_ins = min(ws_ins.max_row - 1, 8)
        bar = BarChart()
        bar.type = "bar"
        bar.title = "Policies by Insurer (Top 8)"
        bar.style = 10
        bar.y_axis.title = "Insurer"
        bar.x_axis.title = "Policies"
        bar.legend = None
        b_labels = Reference(ws_ins, min_col=1, min_row=2, max_row=1 + n_ins)
        b_data   = Reference(ws_ins, min_col=2, min_row=1, max_row=1 + n_ins)
        bar.add_data(b_data, titles_from_data=True)
        bar.set_categories(b_labels)
        bar.width = 22; bar.height = 12
        ws_dash.add_chart(bar, "D9")

        # ── Chart 3: Expiry Timeline (Column) ──
        ws_mo = writer.sheets["By Expiry Month"]
        n_mo = ws_mo.max_row - 1
        col_chart = BarChart()
        col_chart.type = "col"
        col_chart.title = "Policies Expiring by Month"
        col_chart.style = 10
        col_chart.y_axis.title = "Policies"
        col_chart.x_axis.title = "Month"
        col_chart.legend = None
        m_labels = Reference(ws_mo, min_col=1, min_row=2, max_row=1 + n_mo)
        m_data   = Reference(ws_mo, min_col=2, min_row=1, max_row=1 + n_mo)
        col_chart.add_data(m_data, titles_from_data=True)
        col_chart.set_categories(m_labels)
        col_chart.width = 36; col_chart.height = 12
        ws_dash.add_chart(col_chart, "B22")


def main() -> int:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="Extract structured data from insurance PDFs.")
    parser.add_argument("--input-dir", default=str(ROOT / "300 Insurance Copy"))
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N PDFs.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = data_dir / "cache"

    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    import os
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set. Copy .env.example to .env and set your key.", file=sys.stderr)
        return 1

    result = run(input_dir, cache_dir, workers=args.workers, limit=args.limit)

    ordered_cols = ["source_file", *FINAL_COLUMNS]
    df = pd.DataFrame(result.rows)
    for col in ordered_cols:
        if col not in df.columns:
            df[col] = None
    df = df[ordered_cols]

    json_path = data_dir / "extracted.json"
    xlsx_path = data_dir / "extracted.xlsx"

    json_path.write_text(json.dumps(result.rows, default=str, indent=2))
    _write_excel(df, xlsx_path)

    print(f"Extracted {len(result.rows)} policies -> {json_path}")
    print(f"Excel export -> {xlsx_path}")
    if result.failures:
        print(f"\n{len(result.failures)} failures:")
        for name, err in result.failures[:20]:
            print(f"  - {name}: {err}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
