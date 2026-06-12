"""Branded PDF report generation for the chat ("generate me a report …").

`build_report_pdf(spec)` renders a Digby-branded A4 PDF — cover header with
the logo, a title block, then ordered sections (headings, rich paragraphs,
tables, notes) and a running footer. Returns the on-disk path + a stable id
the API serves at /api/os/report/{id}.

The agent's `generate_report` tool passes a structured spec; nothing here
invents data — it only lays out what the agent supplies.
"""
from __future__ import annotations

import html
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

IST = ZoneInfo("Asia/Kolkata")
_ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
_LOGO = _ASSET_DIR / "logo.png"
REPORTS_DIR = Path(tempfile.gettempdir()) / "digby_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# rid -> human download filename (the served file on disk is <rid>.pdf)
REPORT_NAMES: dict[str, str] = {}

# brand palette
_INK = colors.HexColor("#1f2937")
_MUTE = colors.HexColor("#6b7280")
_TEAL = colors.HexColor("#1f8a70")
_RED = colors.HexColor("#c0492f")
_LINE = colors.HexColor("#e5e7eb")
_HEADBG = colors.HexColor("#1f3a5f")
_ZEBRA = colors.HexColor("#f6f7f9")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("dTitle", parent=ss["Title"], fontName="Helvetica-Bold",
                                fontSize=22, leading=26, textColor=_INK, spaceAfter=2),
        "subtitle": ParagraphStyle("dSub", parent=ss["Normal"], fontName="Helvetica",
                                   fontSize=11, leading=15, textColor=_MUTE, spaceAfter=2),
        "meta": ParagraphStyle("dMeta", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=8.5, leading=12, textColor=_MUTE),
        "h2": ParagraphStyle("dH2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=13.5, leading=17, textColor=_TEAL,
                             spaceBefore=14, spaceAfter=5),
        "body": ParagraphStyle("dBody", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=10, leading=15, textColor=_INK, spaceAfter=7,
                               alignment=TA_LEFT),
        "bullet": ParagraphStyle("dBullet", parent=ss["Normal"], fontName="Helvetica",
                                 fontSize=10, leading=15, textColor=_INK),
        "note": ParagraphStyle("dNote", parent=ss["Normal"], fontName="Helvetica-Oblique",
                               fontSize=8.5, leading=12, textColor=_MUTE, spaceBefore=2,
                               spaceAfter=8),
        "th": ParagraphStyle("dTh", parent=ss["Normal"], fontName="Helvetica-Bold",
                             fontSize=8.5, leading=11, textColor=colors.white),
        "td": ParagraphStyle("dTd", parent=ss["Normal"], fontName="Helvetica",
                             fontSize=9, leading=12, textColor=_INK),
    }


def _inline(text: str) -> str:
    """Escape HTML then re-apply **bold** / *italic* as reportlab markup."""
    t = html.escape(str(text or ""))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", t)
    return t


def _body_flowables(body: str, st: dict) -> list:
    """Split a markdown-ish body into paragraphs + bullet lists."""
    out: list = []
    if not body:
        return out
    for block in re.split(r"\n\s*\n", str(body).strip()):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if lines and all(re.match(r"^\s*[-•]\s+", ln) for ln in lines):
            items = [ListItem(Paragraph(_inline(re.sub(r"^\s*[-•]\s+", "", ln)), st["bullet"]),
                              leftIndent=6) for ln in lines]
            out.append(ListFlowable(items, bulletType="bullet", bulletColor=_TEAL,
                                    bulletFontSize=7, start="•", leftIndent=12, spaceAfter=7))
        else:
            out.append(Paragraph(_inline(" ".join(lines)), st["body"]))
    return out


def _cell(v) -> str:
    """Coerce a cell/header to display text — tolerates the model passing
    a dict like {'header': 'FY', 'align': 'right'} or {'value': 3.45}."""
    if v is None:
        return ""
    if isinstance(v, dict):
        for k in ("header", "label", "name", "text", "title", "value"):
            if k in v and not isinstance(v[k], (dict, list)):
                return str(v[k])
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(_cell(x) for x in v)
    return str(v)


def _table_flowable(tbl: dict, st: dict) -> Table | None:
    cols = tbl.get("columns") or []
    rows = tbl.get("rows") or []
    if not cols or not rows:
        return None
    header = [Paragraph(_inline(_cell(c)), st["th"]) for c in cols]
    data = [header]
    for r in rows:
        cells = list(r) + [""] * (len(cols) - len(r))
        data.append([Paragraph(_inline(_cell(c)), st["td"])
                     for c in cells[:len(cols)]])
    t = Table(data, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEADBG),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), _ZEBRA))
    t.setStyle(TableStyle(style))
    return t


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "report").lower()).strip("-")
    return (s or "report")[:60]


def build_report_pdf(spec: dict) -> tuple[Path, str, str]:
    """Render the spec to a branded PDF. Returns (path, filename, report_id)."""
    st = _styles()
    title = spec.get("title") or "OIL India — Report"
    subtitle = spec.get("subtitle") or ""
    sections = spec.get("sections") or []
    now = datetime.now(IST)

    rid = uuid.uuid4().hex[:16]
    filename = f"{_slug(title)}.pdf"
    path = REPORTS_DIR / f"{rid}.pdf"

    def _header_footer(canvas, doc):
        canvas.saveState()
        w, h = A4
        # header band
        if _LOGO.exists():
            try:
                canvas.drawImage(str(_LOGO), 18 * mm, h - 27 * mm, width=14 * mm,
                                 height=14 * mm, mask="auto", preserveAspectRatio=True)
            except Exception:  # noqa: BLE001
                pass
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(_INK)
        canvas.drawString(35 * mm, h - 18 * mm, "Digby · Oil India Intelligence")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(_MUTE)
        canvas.drawString(35 * mm, h - 22 * mm, "Advisory intelligence layer · advisory only")
        canvas.setStrokeColor(_LINE)
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, h - 29 * mm, w - 18 * mm, h - 29 * mm)
        # footer
        canvas.setStrokeColor(_LINE)
        canvas.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MUTE)
        canvas.drawString(18 * mm, 10 * mm,
                          f"Generated by Digby · {now.strftime('%d %b %Y, %H:%M IST')} · "
                          f"advisory only — figures from OIL's own sources")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=34 * mm, bottomMargin=20 * mm,
        title=title, author="Digby · Oil India",
    )

    flow: list = [Paragraph(_inline(title), st["title"])]
    if subtitle:
        flow.append(Paragraph(_inline(subtitle), st["subtitle"]))
    flow.append(Paragraph(now.strftime("%d %B %Y"), st["meta"]))
    flow.append(Spacer(1, 6 * mm))

    for sec in sections:
        if not isinstance(sec, dict):
            continue
        if sec.get("heading"):
            flow.append(Paragraph(_inline(sec["heading"]), st["h2"]))
        flow.extend(_body_flowables(sec.get("body", ""), st))
        if sec.get("table"):
            t = _table_flowable(sec["table"], st)
            if t is not None:
                flow.append(Spacer(1, 1 * mm))
                flow.append(t)
        if sec.get("note"):
            flow.append(Paragraph("Source / note: " + _inline(sec["note"]), st["note"]))

    doc.build(flow, onFirstPage=_header_footer, onLaterPages=_header_footer)
    logger.info(f"[report] built {filename} ({path.stat().st_size} bytes)")
    return path, filename, rid
