"""
Production-grade 3-page policy booklet generator for Zororo-Phumulani.
Uses only ReportLab built-in fonts; no external dependencies beyond ReportLab.
"""

import os
import textwrap
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595.27 × 841.89 pt
MARGIN = 45.0
CONTENT_W = PAGE_W - 2 * MARGIN

HEADER_H = 50.0
BANNER_H = 19.0
FOOTER_H = 28.0

CONTENT_TOP = PAGE_H - HEADER_H - BANNER_H - 8.0
CONTENT_BOT = FOOTER_H + 15.0

ROW_H = 14.0
LABEL_W = 92.0

# Two-column dimensions for page 1
COL_L_X = MARGIN
COL_L_W = 235.0
COL_R_X = MARGIN + COL_L_W + 25.0
COL_R_W = PAGE_W - MARGIN - COL_R_X

# Table row heights
T_HDR_H = 18.0
T_ROW_H = 16.0

# ─── COLOURS ─────────────────────────────────────────────────────────────────
C_NAVY = HexColor("#1e3a5f")
C_DARK = HexColor("#0d2137")
C_TEAL = HexColor("#0d9488")
C_TEAL_LT = HexColor("#f0fdfa")
C_RED = HexColor("#dc2626")
C_RED_LT = HexColor("#fef2f2")
C_RED_BDR = HexColor("#fca5a5")
C_BODY = HexColor("#1a1a2e")
C_META = HexColor("#6b7a99")
C_WHITE = HexColor("#ffffff")
C_ROW_ALT = HexColor("#f0fdfa")
C_DIV = HexColor("#e2e8f0")
C_BORDER = HexColor("#cbd5e1")


# ─── PAGE CHROME ─────────────────────────────────────────────────────────────

def _header(c, subtitle: str) -> None:
    c.setFillColor(C_NAVY)
    c.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGIN, PAGE_H - 22, "ZORORO PHUMULANI")
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN, PAGE_H - 37, subtitle)
    try:
        logo_path = os.path.join("static", "logo.png")
        if os.path.exists(logo_path):
            c.drawImage(logo_path, PAGE_W - MARGIN - 55,
                        PAGE_H - HEADER_H + 8, width=45, height=32,
                        preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    banner_y = PAGE_H - HEADER_H - BANNER_H
    c.setFillColor(C_RED)
    c.rect(0, banner_y, PAGE_W, BANNER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        PAGE_W / 2, banner_y + 6,
        "DEMO PREVIEW ONLY  \xb7  NOT A LIVE CONTRACT  \xb7  FSP 48558",
    )


def _footer(c, page_num: int) -> None:
    c.setFillColor(C_DARK)
    c.rect(0, 0, PAGE_W, FOOTER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica", 7)
    c.drawString(
        MARGIN, 10,
        "Zororo Phumulani Investments (Pty) Ltd  \xb7  "
        "FSP 48558  \xb7  Underwritten by KGA Life FSP15980",
    )
    c.setFont("Helvetica-Bold", 7)
    c.drawRightString(PAGE_W - MARGIN, 10, f"Page {page_num}")


# ─── TYPOGRAPHY ──────────────────────────────────────────────────────────────

def _sec_label(c, x: float, y: float, text: str) -> None:
    c.setFillColor(C_TEAL)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x, y, text.upper())
    lw = c.stringWidth(text.upper(), "Helvetica-Bold", 8)
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(0.5)
    c.line(x, y - 2, x + lw, y - 2)


def _fit(c, text: str, font: str, size: float, max_w: float) -> str:
    """Truncate text to fit within max_w points."""
    if not text:
        return "—"
    if c.stringWidth(text, font, size) <= max_w:
        return text
    total_w = c.stringWidth(text, font, size)
    ratio = max_w / total_w
    cut = max(3, int(len(text) * ratio) - 3)
    candidate = text[:cut] + "..."
    while cut > 0 and c.stringWidth(candidate, font, size) > max_w:
        cut -= 1
        candidate = text[:cut] + "..."
    return candidate


def _field(c, x: float, y: float, label: str, value: str,
           col_w: float = 235.0) -> float:
    """Single-line label: value row. Returns next y."""
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(C_META)
    c.drawString(x, y, label + ":")
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    val = _fit(c, str(value) if value else "", "Helvetica", 9,
               col_w - LABEL_W - 2)
    c.drawString(x + LABEL_W, y, val)
    return y - ROW_H


def _field_wrap(c, x: float, y: float, label: str, value: str,
                col_w: float = 235.0, max_lines: int = 2) -> float:
    """Wrapped label: value row (address, email). Returns next y."""
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(C_META)
    c.drawString(x, y, label + ":")
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    avg_w = c.stringWidth("n", "Helvetica", 9)
    chars = max(12, int((col_w - LABEL_W - 2) / avg_w))
    lines = textwrap.wrap(str(value) if value else "—", chars)[:max_lines]
    if not lines:
        lines = ["—"]
    for i, line in enumerate(lines):
        c.drawString(x + LABEL_W, y - i * 11, line)
    return y - ROW_H * max(1, len(lines)) - 2


# ─── TABLE ───────────────────────────────────────────────────────────────────

def _tbl_header(c, x: float, y: float,
                cols: List[str], widths: List[float]) -> float:
    total_w = sum(widths)
    c.setFillColor(C_NAVY)
    c.rect(x, y - T_HDR_H + 4, total_w, T_HDR_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 8)
    cx = x
    for col, w in zip(cols, widths):
        c.drawString(cx + 4, y - 1, col.upper())
        cx += w
    return y - T_HDR_H


def _tbl_row(c, x: float, y: float, cells: List[str],
             widths: List[float], shade: bool = False) -> float:
    total_w = sum(widths)
    if shade:
        c.setFillColor(C_ROW_ALT)
        c.rect(x, y - T_ROW_H + 4, total_w, T_ROW_H, fill=True, stroke=False)
    c.setStrokeColor(C_DIV)
    c.setLineWidth(0.3)
    c.line(x, y - T_ROW_H + 4, x + total_w, y - T_ROW_H + 4)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(C_BODY)
    cx = x
    for cell, w in zip(cells, widths):
        s = _fit(c, str(cell) if cell else "—",
                 "Helvetica", 8.5, w - 8)
        c.drawString(cx + 4, y - 1, s)
        cx += w
    return y - T_ROW_H


# ─── TICK / CROSS ────────────────────────────────────────────────────────────

def _tick(c, x: float, y: float, sz: float = 7.0) -> None:
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(1.5)
    c.setLineCap(1)
    p = c.beginPath()
    p.moveTo(x, y + sz * 0.45)
    p.lineTo(x + sz * 0.38, y + sz * 0.08)
    p.lineTo(x + sz, y + sz * 0.75)
    c.drawPath(p, stroke=True, fill=False)
    c.setLineCap(0)
    c.setLineWidth(0.5)
    c.setStrokeColor(C_BODY)


def _cross(c, x: float, y: float, sz: float = 7.0) -> None:
    c.setStrokeColor(C_RED)
    c.setLineWidth(1.5)
    c.setLineCap(1)
    p = c.beginPath()
    p.moveTo(x + 1, y + 1)
    p.lineTo(x + sz - 1, y + sz - 1)
    p.moveTo(x + sz - 1, y + 1)
    p.lineTo(x + 1, y + sz - 1)
    c.drawPath(p, stroke=True, fill=False)
    c.setLineCap(0)
    c.setLineWidth(0.5)
    c.setStrokeColor(C_BODY)


def _icon_row(c, x: float, y: float, checked: bool, label: str) -> None:
    if checked:
        _tick(c, x, y)
    else:
        _cross(c, x, y)
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    c.drawString(x + 14, y + 1, label)


# ─── PAGE 1: POLICY SUMMARY COVER ────────────────────────────────────────────

def _page1(c, d: Dict[str, Any], stillborn: bool) -> None:
    _header(c, "Policy Application Summary")
    _footer(c, 1)

    y = CONTENT_TOP

    # ── LEFT: PROPOSER DETAILS ────────────────────────────────────────────────
    _sec_label(c, COL_L_X, y, "Proposer Details")
    yl = y - 16

    full_name = f"{d['title']} {d['fname']} {d['lname']}".strip()
    yl = _field(c, COL_L_X, yl, "Full Name", full_name, COL_L_W)
    yl = _field(c, COL_L_X, yl, "ID Type", d['id_doc_type'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "ID Number", d['identity_value'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "Date of Birth", d['dob'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "Gender", d['gender'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "Marital Status", d['marital_status'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "Phone", d['phone'], COL_L_W)
    yl = _field(c, COL_L_X, yl, "Email", d['email'], COL_L_W)
    yl = _field_wrap(c, COL_L_X, yl, "Address", d['address'], COL_L_W, 2)

    sadc = bool(d.get('sadac_country_selection', '').strip())
    wwfp = d.get('product_type', '').strip().lower() == 'wwfp'
    if sadc:
        yl = _field(c, COL_L_X, yl, "SADC Country",
                    d['sadac_country_selection'], COL_L_W)
        yl = _field(c, COL_L_X, yl, "Country Origin",
                    d['country_of_origin'], COL_L_W)
    if wwfp:
        yl = _field(c, COL_L_X, yl, "Country Residence",
                    d['country_of_residence'], COL_L_W)

    # ── RIGHT: COVER SELECTION ────────────────────────────────────────────────
    _sec_label(c, COL_R_X, y, "Cover Selection")
    yr = y - 16

    _ctx_labels = {
        'local': 'Local South Africa',
        'sadc': 'SADC Regional',
        'wwfp': 'Worldwide Diaspora',
    }
    ctx_display = _ctx_labels.get(
        d.get('form_context', 'local'), 'Local South Africa'
    )
    prod = d['product_type'].replace('_', ' ').title()
    yr = _field(c, COL_R_X, yr, "Form Context", ctx_display, COL_R_W)
    yr = _field(c, COL_R_X, yr, "Product Type", prod, COL_R_W)
    yr = _field(c, COL_R_X, yr, "Plan", d['plan_name'], COL_R_W)
    yr = _field(c, COL_R_X, yr, "Monthly Premium", d['local_total'], COL_R_W)
    yr = _field(c, COL_R_X, yr, "Policy Ref",
                d.get('policy_number', 'DEMO-PREVIEW-MODE'), COL_R_W)

    # Waiting period box
    yr -= 10
    box_h = 60.0
    c.setFillColor(C_TEAL_LT)
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(0.6)
    c.rect(COL_R_X, yr - box_h, COL_R_W, box_h, fill=True, stroke=True)
    c.setFillColor(C_TEAL)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(COL_R_X + 6, yr - 11, "WAITING PERIODS (PER T&C)")
    c.setFont("Helvetica", 8)
    c.setFillColor(C_BODY)
    c.drawString(COL_R_X + 6, yr - 24, "Immediate family (natural causes): 3 months")
    c.drawString(COL_R_X + 6, yr - 36, "Extended family (natural causes):  6 months")
    c.drawString(COL_R_X + 6, yr - 48, "Accidental death:                  No waiting period")
    yr -= box_h + 8

    # Thin vertical divider between columns
    col_floor = min(yl, yr) - 8
    c.setStrokeColor(C_DIV)
    c.setLineWidth(0.4)
    c.line(COL_R_X - 13, y + 4, COL_R_X - 13, col_floor)

    # ── IMMEDIATE DEPENDENTS TABLE ────────────────────────────────────────────
    dep_y = min(yl, yr) - 18

    if stillborn:
        rh = 24.0
        c.setFillColor(C_RED_LT)
        c.setStrokeColor(C_RED)
        c.setLineWidth(0.8)
        c.rect(MARGIN, dep_y - rh, CONTENT_W, rh, fill=True, stroke=True)
        c.setFillColor(C_RED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(
            MARGIN + 6, dep_y - rh + 8,
            "!! REVIEW REQUIRED — Child DOB within 25 weeks of submission"
            " (BR-DEC-02). Manual underwriting review required.",
        )
        dep_y -= rh + 6

    _sec_label(c, MARGIN, dep_y, "Immediate Dependents")
    dep_y -= 14

    t_cols = ["Relationship", "Full Name", "Date of Birth"]
    t_widths = [120.0, 245.0, 140.0]
    dep_y = _tbl_header(c, MARGIN, dep_y, t_cols, t_widths)

    fn = d.get('fam_fname', [])
    ln = d.get('fam_lname', [])
    rel = d.get('fam_relation', [])
    dob = d.get('fam_dob', [])

    entries = [
        (rel[i], f"{fn[i]} {ln[i]}".strip(), dob[i])
        for i in range(len(fn))
        if fn[i].strip() or ln[i].strip()
    ]

    max_rows = max(1, int((dep_y - CONTENT_BOT) / T_ROW_H) - 1)
    shown = entries[:max_rows]
    overflow = len(entries) - len(shown)

    for idx, (r, nm, d_val) in enumerate(shown):
        dep_y = _tbl_row(c, MARGIN, dep_y, [r, nm, d_val],
                         t_widths, shade=(idx % 2 == 1))

    if overflow > 0:
        dep_y = _tbl_row(
            c, MARGIN, dep_y,
            [f"... and {overflow} more dependent(s)", "", ""],
            t_widths, shade=(len(shown) % 2 == 1),
        )

    if not entries:
        _tbl_row(c, MARGIN, dep_y, ["None declared", "", ""],
                 t_widths, shade=False)


# ─── PAGE 2: BENEFICIARY & EXTENDED FAMILY ───────────────────────────────────

def _page2(c, d: Dict[str, Any]) -> None:
    _header(c, "Beneficiary, Extended Family & Payment")
    _footer(c, 2)

    y = CONTENT_TOP

    # ── BENEFICIARY BOX ───────────────────────────────────────────────────────
    bfull = f"{d['ben_fname']} {d['ben_lname']}".strip()
    bx_h = 68.0
    c.setFillColor(C_TEAL_LT)
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(0.8)
    c.rect(MARGIN, y - bx_h, CONTENT_W, bx_h, fill=True, stroke=True)
    _sec_label(c, MARGIN + 6, y - 10, "Beneficiary Details")
    by = y - 26
    by = _field(c, MARGIN + 6, by, "Full Name", bfull, CONTENT_W - 12)
    by = _field(c, MARGIN + 6, by, "Relationship", d['ben_rel'], CONTENT_W - 12)
    _field(c, MARGIN + 6, by, "Contact", d['ben_phone'], CONTENT_W - 12)
    y -= bx_h + 18

    # ── EXTENDED FAMILY TABLE ─────────────────────────────────────────────────
    _sec_label(c, MARGIN, y, "Extended Family Cover Members")
    y -= 14

    ext_cols = ["Relationship", "Full Name", "Date of Birth", "Cover Amount"]
    ext_w = [115.0, 175.0, 110.0, 105.0]
    y = _tbl_header(c, MARGIN, y, ext_cols, ext_w)

    efn = d.get('ext_fam_fname', [])
    eln = d.get('ext_fam_lname', [])
    erel = d.get('ext_fam_relation', [])
    edob = d.get('ext_fam_dob', [])
    ecov = d.get('ext_fam_cover', [])

    ext_entries = [
        (erel[i], f"{efn[i]} {eln[i]}".strip(), edob[i],
         f"R{ecov[i]}" if ecov[i] else "—")
        for i in range(len(efn))
        if efn[i].strip() or eln[i].strip()
    ]

    if ext_entries:
        for idx, row in enumerate(ext_entries):
            if y < CONTENT_BOT + 40:
                break
            y = _tbl_row(c, MARGIN, y, list(row), ext_w,
                         shade=(idx % 2 == 1))
    else:
        y = _tbl_row(c, MARGIN, y, ["None declared", "", "", ""],
                     ext_w, shade=False)

    # ── PAYMENT DETAILS ───────────────────────────────────────────────────────
    y -= 20
    _sec_label(c, MARGIN, y, "Payment Details")
    y -= 14

    pay = d.get('pay_method', '')
    y = _field(c, MARGIN, y, "Payment Method", pay, CONTENT_W)

    if pay == "Debit Order":
        y = _field(c, MARGIN, y, "Bank", d.get('bank_name', ''), CONTENT_W)
        y = _field(c, MARGIN, y, "Account Holder",
                   d.get('account_name', ''), CONTENT_W)

        raw_acc = d.get('account_num', '')
        masked = "****" + (raw_acc[-4:] if len(raw_acc) >= 4
                           else raw_acc.zfill(4))
        y = _field(c, MARGIN, y, "Account Number", masked, CONTENT_W)
        y = _field(c, MARGIN, y, "Account Type",
                   d.get('account_type', ''), CONTENT_W)
        y = _field(c, MARGIN, y, "Branch Code",
                   d.get('branch_code', ''), CONTENT_W)
        y = _field(c, MARGIN, y, "Commencement",
                   d.get('commencement_date', ''), CONTENT_W)
        _field(c, MARGIN, y, "Deduction Date",
               f"{d.get('deduction_date', '1')} of the month", CONTENT_W)


# ─── PAGE 3: DECLARATIONS & SIGNATURE ────────────────────────────────────────

def _page3(c, d: Dict[str, Any]) -> None:
    _header(c, "Declarations & Electronic Signature")
    _footer(c, 3)

    y = CONTENT_TOP

    # ── COMMUNICATION OPT-INS (2×2 grid) ─────────────────────────────────────
    _sec_label(c, MARGIN, y, "Communication Opt-Ins")
    y -= 18

    opt_items = [
        ("Telephone", d.get('optin_phone', False)),
        ("SMS / Text", d.get('optin_sms', False)),
        ("Email",      d.get('optin_email', False)),
        ("WhatsApp",   d.get('optin_whatsapp', False)),
    ]
    half_w = CONTENT_W / 2
    for i, (label, checked) in enumerate(opt_items):
        xi = MARGIN + (i % 2) * half_w
        yi = y - (i // 2) * 18
        _icon_row(c, xi, yi, checked, label)
    y -= 2 * 18 + 12

    # ── LEGAL DECLARATIONS ────────────────────────────────────────────────────
    _sec_label(c, MARGIN, y, "Legal Declarations")
    y -= 16

    decl_items = [
        ("Terms & Conditions Accepted",
         d.get('terms_acceptance', False)),
        ("Needs Analysis Waiver Acknowledged",
         d.get('needs_analysis_waiver', False)),
        ("Mandated Intermediary Appointed",
         d.get('intermediary_appointment', False)),
    ]
    for label, checked in decl_items:
        _icon_row(c, MARGIN, y, checked, label)
        y -= 18

    # ── ELECTRONIC SIGNATURE DECLARATION ─────────────────────────────────────
    y -= 20
    _sec_label(c, MARGIN, y, "Electronic Signature Declaration")
    y -= 20

    # Signature line (above the name)
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.8)
    c.line(MARGIN, y, MARGIN + 270, y)

    # Signed name in Times-Italic below the line
    y -= 4
    c.setFont("Times-Italic", 16)
    c.setFillColor(C_NAVY)
    sig = d.get('legal_name_confirm', '')
    c.drawString(MARGIN + 4, y - 16, sig)

    # Submission date
    sub_date = datetime.now().strftime("%d %B %Y")
    c.setFont("Helvetica", 8)
    c.setFillColor(C_META)
    c.drawString(MARGIN + 4, y - 34, f"Digitally confirmed  \xb7  {sub_date}")

    # ── DISCLAIMER BOX ────────────────────────────────────────────────────────
    disc_bot = CONTENT_BOT
    disc_h = 58.0
    c.setFillColor(C_RED_LT)
    c.setStrokeColor(C_RED_BDR)
    c.setLineWidth(0.8)
    c.rect(MARGIN, disc_bot, CONTENT_W, disc_h, fill=True, stroke=True)
    c.setFillColor(C_RED)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(MARGIN + 7, disc_bot + disc_h - 12,
                 "PRESENTATION LAYER PREVIEW — DEMO-PREVIEW-MODE")
    disc_body = (
        "This document is not backed by a live Easipol policy registry, "
        "carries no transaction ID, and is not an active issued contract. "
        "No policy has been issued. All fields are for demonstration purposes only."
    )
    c.setFont("Helvetica", 7.5)
    c.setFillColor(C_BODY)
    lines = textwrap.wrap(disc_body, 90)
    for i, line in enumerate(lines[:3]):
        c.drawString(MARGIN + 7, disc_bot + disc_h - 27 - i * 11, line)


# ─── PUBLIC ENTRY POINT ──────────────────────────────────────────────────────

def build_policy_pdf(pdf_path: str, d: Dict[str, Any],
                     stillborn_review: bool = False,
                     compress: bool = True) -> None:
    """
    Build and write the 3-page branded policy booklet to pdf_path.
    d must contain all form fields from submit_policy.
    compress=False disables stream compression (useful for text-search in tests).
    """
    page_compression = 1 if compress else 0
    c = rl_canvas.Canvas(pdf_path, pagesize=A4,
                         pageCompression=page_compression)
    _page1(c, d, stillborn_review)
    c.showPage()
    _page2(c, d)
    c.showPage()
    _page3(c, d)
    c.save()
