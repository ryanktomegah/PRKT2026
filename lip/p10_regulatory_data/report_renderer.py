"""
report_renderer.py — Multi-format report rendering.

Sprint 5: JSON, CSV, PDF output from VersionedReport.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict

from lip.p10_regulatory_data.methodology import MethodologyAppendix
from lip.p10_regulatory_data.report_metadata import VersionedReport


class ReportRenderer:
    """Renders VersionedReport into JSON, CSV, or PDF format."""

    def render_json(self, report: VersionedReport) -> str:
        """Structured JSON — machine-readable, schema-consistent."""
        data = self._build_json_dict(report)
        return json.dumps(data, sort_keys=True, indent=2)

    def render_csv(self, report: VersionedReport) -> str:
        """Flat CSV — one row per corridor snapshot, metadata header."""
        output = io.StringIO()

        # Metadata header as comments
        output.write(f"# report_id: {report.report_id}\n")
        output.write(f"# version: {report.version}\n")
        output.write(f"# generated_at: {self._format_timestamp(report.generated_at)}\n")
        output.write(f"# methodology_version: {report.methodology_version}\n")
        output.write(f"# content_hash: {report.content_hash}\n")

        # Data rows
        writer = csv.writer(output)
        headers = [
            "corridor", "period_label", "failure_rate", "total_payments",
            "failed_payments", "bank_count", "trend_direction",
            "trend_magnitude", "contains_stale_data",
        ]
        writer.writerow(headers)

        for s in report.report.corridor_snapshots:
            writer.writerow([
                s.corridor, s.period_label,
                round(s.failure_rate, 6), s.total_payments,
                s.failed_payments, s.bank_count,
                s.trend_direction, round(s.trend_magnitude, 6),
                s.contains_stale_data,
            ])

        # Summary footer
        r = report.report
        writer.writerow([
            "SUMMARY", "", round(r.overall_failure_rate, 6), "",
            "", r.total_corridors_analyzed, r.highest_risk_corridor,
            round(r.concentration_hhi, 6), round(r.systemic_risk_score, 6),
        ])

        # Prepend UTF-8 BOM on its own line so comment lines remain # -prefixed
        return "\ufeff\n" + output.getvalue()

    def render_pdf(self, report: VersionedReport) -> bytes:
        """Formatted PDF — title page, data tables, methodology appendix."""
        try:
            from fpdf import FPDF
        except ImportError:
            raise ImportError(
                "fpdf2 is required for PDF report generation. "
                "Install with: pip install fpdf2"
            ) from None

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_title("Systemic Risk Report")
        pdf.set_subject(report.report_id)

        # Title page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(0, 20, "Systemic Risk Report", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 10, f"Report ID: {report.report_id}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"Version: {report.version}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(
            0, 10,
            f"Generated: {self._format_timestamp(report.generated_at)}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 10,
            f"Period: {report.period_start} to {report.period_end}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(10)

        # Executive summary
        r = report.report
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0, 8, f"Overall Failure Rate: {r.overall_failure_rate:.4f}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 8, f"Highest Risk Corridor: {r.highest_risk_corridor}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 8, f"Systemic Risk Score: {r.systemic_risk_score:.4f}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 8, f"Concentration HHI: {r.concentration_hhi:.4f}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 8, f"Corridors Analyzed: {r.total_corridors_analyzed}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 8, f"Stale Corridors: {r.stale_corridor_count}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(10)

        # Corridor data table
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Corridor Data", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B", 9)
        col_widths = [30, 22, 22, 22, 22, 22, 22, 22]
        table_headers = [
            "Corridor", "Fail Rate", "Total", "Failed",
            "Banks", "Trend", "Magnitude", "Stale",
        ]
        for i, h in enumerate(table_headers):
            pdf.cell(col_widths[i], 8, h, border=1)
        pdf.ln()
        pdf.set_font("Helvetica", "", 9)
        for s in r.corridor_snapshots:
            vals = [
                s.corridor, f"{s.failure_rate:.4f}", str(s.total_payments),
                str(s.failed_payments), str(s.bank_count), s.trend_direction,
                f"{s.trend_magnitude:.4f}", str(s.contains_stale_data),
            ]
            for i, v in enumerate(vals):
                pdf.cell(col_widths[i], 7, v, border=1)
            pdf.ln()
        pdf.ln(10)

        # Methodology appendix
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Methodology Appendix", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for title, body in MethodologyAppendix.get_sections().items():
            heading = title.replace("_", " ").title()
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, body)
            pdf.ln(4)

        # Integrity footer
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(
            0, 6, f"Content Hash: {report.content_hash}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.cell(
            0, 6, f"Methodology Version: {report.methodology_version}",
            new_x="LMARGIN", new_y="NEXT",
        )

        return bytes(pdf.output())

    def _build_json_dict(self, report: VersionedReport) -> Dict[str, Any]:
        """Build the JSON-serializable dictionary."""
        r = report.report
        return {
            "report_id": report.report_id,
            "version": report.version,
            "supersedes": report.supersedes,
            "generated_at": self._format_timestamp(report.generated_at),
            "period_start": report.period_start,
            "period_end": report.period_end,
            "methodology_version": report.methodology_version,
            "content_hash": report.content_hash,
            "overall_failure_rate": round(r.overall_failure_rate, 6),
            "highest_risk_corridor": r.highest_risk_corridor,
            "concentration_hhi": round(r.concentration_hhi, 6),
            "systemic_risk_score": round(r.systemic_risk_score, 6),
            "stale_corridor_count": r.stale_corridor_count,
            "total_corridors_analyzed": r.total_corridors_analyzed,
            "corridor_snapshots": [
                {
                    "corridor": s.corridor,
                    "period_label": s.period_label,
                    "failure_rate": round(s.failure_rate, 6),
                    "total_payments": s.total_payments,
                    "failed_payments": s.failed_payments,
                    "bank_count": s.bank_count,
                    "trend_direction": s.trend_direction,
                    "trend_magnitude": round(s.trend_magnitude, 6),
                    "contains_stale_data": s.contains_stale_data,
                }
                for s in r.corridor_snapshots
            ],
            "methodology": MethodologyAppendix.get_sections(),
        }

    @staticmethod
    def _format_timestamp(ts: float) -> str:
        """Convert Unix timestamp to ISO-8601 string."""
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
