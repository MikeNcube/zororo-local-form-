"""
3-page branded policy booklet for Zororo-Phumulani.
Uses only ReportLab built-in fonts; no external dependencies beyond ReportLab.
Page 1: Application details + cover selection
Page 2: Declarations, compliance, signature
Page 3: Terms & Conditions summary
"""

import textwrap
import os
from datetime import datetime
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

# ─── LAYOUT ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4          # 595.27 × 841.89 pt
MARGIN = 40.0
CONTENT_W = PAGE_W - 2 * MARGIN

HEADER_H = 52.0
BANNER_H = 18.0
FOOTER_H = 32.0

CONTENT_TOP = PAGE_H - HEADER_H - BANNER_H - 10.0
CONTENT_BOT = FOOTER_H + 14.0

LINE_H = 14.0       # standard body line height
SEC_GAP = 14.0      # gap above section labels
LABEL_W = 110.0     # field-label column width

COL_L_X = MARGIN
COL_L_W = 240.0
COL_R_X = MARGIN + COL_L_W + 20.0
COL_R_W = PAGE_W - MARGIN - COL_R_X

# ─── COLOURS ─────────────────────────────────────────────────────────────────
C_NAVY = HexColor("#1e3a5f")
C_DARK = HexColor("#0d2137")
C_TEAL = HexColor("#0d9488")
C_TEAL_LT = HexColor("#f0fdfa")
C_RED = HexColor("#dc2626")
C_RED_LT = HexColor("#fef2f2")
C_BODY = HexColor("#1a1a2e")
C_META = HexColor("#64748b")
C_WHITE = HexColor("#ffffff")
C_SHADE = HexColor("#f8fafc")
C_DIV = HexColor("#e2e8f0")
C_BORDER = HexColor("#cbd5e1")
C_AMBER = HexColor("#d97706")


# ─── CHROME ──────────────────────────────────────────────────────────────────

def _header(c, page_num: int, policy_ref: str = "") -> None:
    # Navy bar
    c.setFillColor(C_NAVY)
    c.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, fill=True, stroke=False)

    # White chip + ZP logo on the left (graceful skip if file missing)
    text_x = MARGIN
    try:
        zp_logo = os.path.join("static", "zp_logo.png")
        if os.path.exists(zp_logo):
            chip_pad = 8.0
            chip_x = MARGIN
            chip_h = HEADER_H - 2 * chip_pad
            chip_w = 70.0
            chip_y = PAGE_H - HEADER_H + chip_pad
            c.setFillColor(C_WHITE)
            c.roundRect(chip_x, chip_y, chip_w, chip_h, 4,
                        fill=True, stroke=False)
            inner = 4.0
            c.drawImage(
                zp_logo, chip_x + inner, chip_y + inner,
                width=chip_w - 2 * inner, height=chip_h - 2 * inner,
                preserveAspectRatio=True, mask="auto",
            )
            text_x = chip_x + chip_w + 12
    except Exception:
        text_x = MARGIN

    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(text_x, PAGE_H - 24, "ZORORO PHUMULANI")
    c.setFont("Helvetica", 8)
    c.drawString(
        text_x, PAGE_H - 38,
        "Worldwide Funeral Plan  ·  FSP48558  ·  "
        "Underwritten by KGA Life FSP15980",
    )
    if policy_ref:
        c.setFont("Helvetica-Bold", 8)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 24, policy_ref)
    try:
        logo = os.path.join("static", "logo.png")
        if os.path.exists(logo):
            c.drawImage(
                logo, PAGE_W - MARGIN - 55, PAGE_H - HEADER_H + 8,
                width=45, height=34, preserveAspectRatio=True, mask="auto",
            )
    except Exception:
        pass
    # Sub-banner
    by = PAGE_H - HEADER_H - BANNER_H
    c.setFillColor(C_DARK)
    c.rect(0, by, PAGE_W, BANNER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        PAGE_W / 2, by + 5,
        f"Page {page_num}  ·  POPIA PROTECTED  ·  CONFIDENTIAL",
    )


def _footer(c) -> None:
    c.setFillColor(C_DARK)
    c.rect(0, 0, PAGE_W, FOOTER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica", 6.5)
    c.drawString(
        MARGIN, 20,
        "Zororo Phumulani Investments (Pty) Ltd  ·  FSP48558  ·  "
        "Office 102, 1st Floor Nzunza House, 28 Melle St, Braamfontein, "
        "Johannesburg  ·  +27 81 419 4980",
    )
    c.drawString(
        MARGIN, 10,
        "This document is POPIA-protected personal information. "
        "Handle and store with appropriate confidentiality controls.",
    )


# ─── PRIMITIVES ──────────────────────────────────────────────────────────────

def _sec(c, x: float, y: float, text: str) -> float:
    """Draw section label. Returns y after label + underline."""
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_TEAL)
    c.drawString(x, y, text)
    lw = c.stringWidth(text, "Helvetica-Bold", 9)
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(0.6)
    c.line(x, y - 2, x + lw, y - 2)
    return y - 13


def _field(c, x: float, y: float, label: str, value: str,
           col_w: float = 0.0) -> float:
    """Single label: value row. Returns next y."""
    if col_w == 0.0:
        col_w = CONTENT_W
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C_META)
    c.drawString(x, y, label + ":")
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    max_w = col_w - LABEL_W - 4
    if c.stringWidth(str(value or ""), "Helvetica", 9) > max_w:
        ratio = max_w / max(1, c.stringWidth(str(value or ""), "Helvetica", 9))
        cut = max(3, int(len(str(value or "")) * ratio) - 3)
        value = str(value or "")[:cut] + "..."
    c.drawString(x + LABEL_W, y, str(value) if value else "—")
    return y - LINE_H


def _field_wrap(c, x: float, y: float, label: str, value: str,
                col_w: float = 0.0, max_lines: int = 2) -> float:
    """Wrapping label: value. Returns next y."""
    if col_w == 0.0:
        col_w = CONTENT_W
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C_META)
    c.drawString(x, y, label + ":")
    avg_cw = c.stringWidth("n", "Helvetica", 9)
    chars = max(10, int((col_w - LABEL_W - 4) / avg_cw))
    lines = textwrap.wrap(str(value) if value else "—", chars)[:max_lines]
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    for i, ln in enumerate(lines):
        c.drawString(x + LABEL_W, y - i * 11, ln)
    return y - LINE_H * max(1, len(lines)) - 2


def plan_display_name(plan_key: str) -> str:
    """Convert internal plan key (e.g. 'LOCAL_F_R10000|169') to a clean label."""
    if not plan_key:
        return "—"
    key = plan_key.split("|")[0].strip()
    parts = key.split("_")
    ctx_map = {
        "LOCAL": "Local", "SADC": "SADC", "SADAC": "SADC",
        "WWFP": "Worldwide", "WWF": "Worldwide",
    }
    type_map = {"F": "Family", "S": "Single"}
    try:
        ctx = ctx_map.get(parts[0].upper())
        ptype = type_map.get(parts[1].upper()) if len(parts) > 1 else None
        cover = parts[2] if len(parts) > 2 else ""
        if (ctx and ptype and cover.upper().startswith("R")
                and cover[1:].isdigit()):
            amount = int(cover[1:])
            return f"{ctx} {ptype} — R{amount:,} Cover"
    except (IndexError, ValueError):
        pass
    return key


def _field_email(c, x: float, y: float, label: str, value: str,
                 col_w: float = 0.0) -> float:
    """Email row that never truncates: shrink to fit, else wrap. Returns next y."""
    if col_w == 0.0:
        col_w = CONTENT_W
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C_META)
    c.drawString(x, y, label + ":")
    val = str(value) if value else "—"
    c.setFillColor(C_BODY)
    max_w = col_w - LABEL_W - 4
    for size in (9.0, 8.0, 7.0, 6.5):
        if c.stringWidth(val, "Helvetica", size) <= max_w:
            c.setFont("Helvetica", size)
            c.drawString(x + LABEL_W, y, val)
            return y - LINE_H
    # Still too wide at smallest size — wrap across lines at 7pt
    c.setFont("Helvetica", 7)
    avg = c.stringWidth("n", "Helvetica", 7)
    chars = max(8, int(max_w / avg))
    lines = textwrap.wrap(val, chars)[:3]
    for i, ln in enumerate(lines):
        c.drawString(x + LABEL_W, y - i * 9, ln)
    return y - LINE_H - 9 * (len(lines) - 1) - 2


def _tbl_hdr(c, x: float, y: float,
             cols: List[str], widths: List[float]) -> float:
    tw = sum(widths)
    c.setFillColor(C_NAVY)
    c.rect(x, y - 16, tw, 18, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica-Bold", 8)
    cx = x
    for col, w in zip(cols, widths):
        c.drawString(cx + 4, y - 1, col.upper())
        cx += w
    # Extra gap below header band so first data row never overlaps (Bug 4)
    return y - 24


def _tbl_row(c, x: float, y: float, cells: List[str],
             widths: List[float], shade: bool = False) -> float:
    tw = sum(widths)
    if shade:
        c.setFillColor(C_SHADE)
        c.rect(x, y - 14, tw, 16, fill=True, stroke=False)
    c.setStrokeColor(C_DIV)
    c.setLineWidth(0.3)
    c.line(x, y - 14, x + tw, y - 14)
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    cx = x
    for cell, w in zip(cells, widths):
        val = str(cell) if cell else "—"
        if c.stringWidth(val, "Helvetica", 9) > w - 8:
            ratio = (w - 8) / max(1, c.stringWidth(val, "Helvetica", 9))
            cut = max(3, int(len(val) * ratio) - 3)
            val = val[:cut] + "..."
        c.drawString(cx + 4, y - 1, val)
        cx += w
    return y - 14


def _tick(c, x: float, y: float) -> None:
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(1.4)
    c.setLineCap(1)
    p = c.beginPath()
    p.moveTo(x, y + 3)
    p.lineTo(x + 3, y)
    p.lineTo(x + 7, y + 5)
    c.drawPath(p, stroke=True, fill=False)
    c.setLineCap(0)
    c.setLineWidth(0.5)
    c.setStrokeColor(C_BODY)


def _icon_row(c, x: float, y: float, checked: bool, label: str) -> None:
    if checked:
        _tick(c, x, y)
    else:
        c.setFillColor(C_META)
        c.setFont("Helvetica", 9)
        c.drawString(x, y, "—")
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    c.drawString(x + 13, y, label)


# ─── PAGE 1 ───────────────────────────────────────────────────────────────────

def _page1(c, d: Dict[str, Any], stillborn: bool, policy_ref: str) -> None:
    _header(c, 1, policy_ref)
    _footer(c)
    y = CONTENT_TOP

    # Title block
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(C_NAVY)
    c.drawCentredString(PAGE_W / 2, y, "POLICY APPLICATION FORM")
    y -= 14
    c.setFont("Helvetica", 9)
    c.setFillColor(C_META)
    c.drawCentredString(
        PAGE_W / 2, y,
        "Worldwide Funeral Plan – Digital Application",
    )
    y -= 11
    now = datetime.now()
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        PAGE_W / 2, y,
        f"Policy Ref: {policy_ref}   |   "
        f"Submitted: {now.strftime('%d %b %Y  %H:%M')} SAST   |   "
        "T&C Version: WWF-TC-v2025.1",
    )
    y -= 14

    # Stillborn flag
    if stillborn:
        fh = 20.0
        c.setFillColor(C_RED_LT)
        c.setStrokeColor(C_RED)
        c.setLineWidth(0.8)
        c.rect(MARGIN, y - fh, CONTENT_W, fh, fill=True, stroke=True)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(C_RED)
        c.drawString(
            MARGIN + 6, y - fh + 6,
            "REVIEW REQUIRED: Child DOB within 25 weeks of submission "
            "(BR-DEC-02). Manual underwriting review.",
        )
        y -= fh + 6

    # ── LEFT COLUMN: MAIN MEMBER DETAILS ──────────────────────────────────────
    y -= 4
    yl = _sec(c, COL_L_X, y, "Main Member Details")

    full_name = (
        f"{d.get('title','')} {d.get('fname','')} {d.get('lname','')}".strip()
    )
    dob_val = d.get('dob', '')
    dob_disp = dob_val
    if dob_val:
        try:
            birth = datetime.strptime(dob_val, "%Y-%m-%d")
            age = (datetime.now() - birth).days // 365
            dob_disp = f"{dob_val}  (age {age})"
        except Exception:
            pass

    yl = _field(c, COL_L_X, yl, "Full Name",    full_name,              COL_L_W)
    yl = _field(c, COL_L_X, yl, "Date of Birth", dob_disp,              COL_L_W)
    yl = _field(c, COL_L_X, yl, "Gender",         d.get('gender', ''),  COL_L_W)
    yl = _field(c, COL_L_X, yl, "Marital Status", d.get('marital_status', ''), COL_L_W)
    yl = _field(c, COL_L_X, yl, "ID Type",        d.get('id_doc_type', ''), COL_L_W)
    yl = _field(c, COL_L_X, yl, "ID / Passport",  d.get('identity_value', ''), COL_L_W)
    yl = _field(c, COL_L_X, yl, "Phone",           d.get('phone', ''),   COL_L_W)
    yl = _field_email(c, COL_L_X, yl, "Email",     d.get('email', ''),   COL_L_W)
    if d.get('street_address', '').strip():
        yl = _field(c, COL_L_X, yl, "Street Address",
                    d.get('street_address', ''), COL_L_W)
        if d.get('area_suburb', '').strip():
            yl = _field(c, COL_L_X, yl, "Area/Suburb",
                        d.get('area_suburb', ''), COL_L_W)
        if d.get('postal_code', '').strip():
            yl = _field(c, COL_L_X, yl, "Postal Code",
                        d.get('postal_code', ''), COL_L_W)
    else:
        yl = _field_wrap(c, COL_L_X, yl, "Address",
                         d.get('address', ''), COL_L_W, 2)

    ctx = d.get('form_context', 'local')
    if d.get('sadac_country_selection', '').strip():
        yl = _field(c, COL_L_X, yl, "SADC Country",
                    d.get('sadac_country_selection', ''), COL_L_W)
        yl = _field(c, COL_L_X, yl, "Country Origin",
                    d.get('country_of_origin', ''), COL_L_W)
    if ctx == 'wwfp':
        yl = _field(c, COL_L_X, yl, "Country Residence",
                    d.get('country_of_residence', ''), COL_L_W)
    if d.get('nationality', '').strip():
        yl = _field(c, COL_L_X, yl, "Nationality",
                    d.get('nationality', ''), COL_L_W)
    if d.get('whatsapp', '').strip():
        yl = _field(c, COL_L_X, yl, "WhatsApp",
                    d.get('whatsapp', ''), COL_L_W)
    if d.get('alt_phone', '').strip():
        yl = _field(c, COL_L_X, yl, "Alt Contact",
                    d.get('alt_phone', ''), COL_L_W)

    # ── RIGHT COLUMN: COVER SELECTION ─────────────────────────────────────────
    yr = y
    yr = _sec(c, COL_R_X, yr, "Cover Selection")

    ctx_labels = {
        'local': 'Local South Africa',
        'sadc': 'SADC Regional',
        'wwfp': 'Worldwide Diaspora',
    }
    yr = _field(c, COL_R_X, yr, "Context",
                ctx_labels.get(ctx, 'Local South Africa'), COL_R_W)
    yr = _field(c, COL_R_X, yr, "Plan",
                plan_display_name(d.get('plan_name', '')), COL_R_W)
    yr = _field(c, COL_R_X, yr, "Monthly Premium",
                d.get('local_total', ''), COL_R_W)
    yr = _field(c, COL_R_X, yr, "Payment Method",
                d.get('pay_method', ''), COL_R_W)
    yr = _field(c, COL_R_X, yr, "Policy Reference",
                policy_ref, COL_R_W)

    # Divider
    col_floor = min(yl, yr) - 6
    c.setStrokeColor(C_DIV)
    c.setLineWidth(0.4)
    c.line(COL_R_X - 10, y + 4, COL_R_X - 10, col_floor)

    # ── COVER DEFINITIONS BOX ─────────────────────────────────────────────────
    bx_y = col_floor - 14
    bx_h = 52.0
    c.setFillColor(C_TEAL_LT)
    c.setStrokeColor(C_TEAL)
    c.setLineWidth(0.6)
    c.rect(MARGIN, bx_y - bx_h, CONTENT_W, bx_h, fill=True, stroke=True)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C_TEAL)
    c.drawString(MARGIN + 7, bx_y - 12, "COVER DEFINITIONS")
    c.setFont("Helvetica", 9)
    c.setFillColor(C_BODY)
    c.drawString(MARGIN + 7, bx_y - 24,
                 "Immediate Family (Main Member, Spouse, Children): "
                 "3-month waiting period for natural causes.")
    c.drawString(MARGIN + 7, bx_y - 36,
                 "Extended Family (Parents, in-laws, other relatives): "
                 "6-month waiting period for natural causes.")
    c.drawString(MARGIN + 7, bx_y - 48,
                 "Accidental death: no waiting period. "
                 "Extended family max age 90.")

    # ── DEPENDENTS TABLE ──────────────────────────────────────────────────────
    tab_y = bx_y - bx_h - 16
    tab_y = _sec(c, MARGIN, tab_y, "Immediate Dependents")

    fn = d.get('fam_fname', [])
    ln = d.get('fam_lname', [])
    rel = d.get('fam_relation', [])
    dobs = d.get('fam_dob', [])
    entries = [
        (rel[i], f"{fn[i]} {ln[i]}".strip(), dobs[i])
        for i in range(len(fn)) if fn[i].strip() or ln[i].strip()
    ]

    cols = ["Relationship", "Full Name", "Date of Birth"]
    widths = [115.0, 245.0, 155.0]
    tab_y = _tbl_hdr(c, MARGIN, tab_y, cols, widths)

    max_rows = max(1, int((tab_y - CONTENT_BOT) / 14) - 1)
    shown = entries[:max_rows]
    for idx, (r, nm, dv) in enumerate(shown):
        tab_y = _tbl_row(c, MARGIN, tab_y, [r, nm, dv],
                         widths, shade=(idx % 2 == 1))
    overflow = len(entries) - len(shown)
    if overflow > 0:
        _tbl_row(c, MARGIN, tab_y,
                 [f"... and {overflow} more dependent(s)", "", ""],
                 widths, shade=(len(shown) % 2 == 1))
    if not entries:
        _tbl_row(c, MARGIN, tab_y, ["None declared", "", ""],
                 widths, shade=False)


# ─── PAGE 2 ───────────────────────────────────────────────────────────────────

def _page2(c, d: Dict[str, Any], policy_ref: str) -> None:
    _header(c, 2, policy_ref)
    _footer(c)
    y = CONTENT_TOP

    # ── BENEFICIARY ───────────────────────────────────────────────────────────
    y = _sec(c, MARGIN, y, "Beneficiary Details")
    bfull = (
        f"{d.get('ben_fname','')} {d.get('ben_lname','')}".strip() or "—"
    )
    y = _field(c, MARGIN, y, "Full Name", bfull, CONTENT_W)
    y = _field(c, MARGIN, y, "Relationship", d.get('ben_rel', ''), CONTENT_W)
    y = _field(c, MARGIN, y, "Contact", d.get('ben_phone', ''), CONTENT_W)
    if d.get('bene_deferred'):
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(C_AMBER)
        c.drawString(MARGIN + LABEL_W, y + LINE_H - 2,
                     "Beneficiary deferred — to nominate within 30 days.")
    y -= SEC_GAP

    # ── NEEDS ANALYSIS ────────────────────────────────────────────────────────
    y = _sec(c, MARGIN, y, "Needs Analysis & Declarations")
    opt_vals = [k.replace("optin_", "").capitalize()
                for k in ("optin_phone", "optin_sms", "optin_email", "optin_whatsapp")
                if d.get(k)]
    notif = ", ".join(opt_vals) if opt_vals else "None selected"
    dep_count = len([f for f in d.get('fam_fname', []) if f.strip()])

    na_left = [
        ("Existing Funeral Cover", "Not declared"),
        ("Replacement Policy", "Not declared"),
        ("Number of Dependants", str(dep_count)),
    ]
    na_right = [
        ("Notification Prefs", notif),
        ("FAIS Advice Record", "ACCEPTED"),
        ("Needs Analysis",     "Waiver accepted"),
    ]
    yl = y
    yr = y
    for lbl, val in na_left:
        yl = _field(c, COL_L_X, yl, lbl, val, COL_L_W)
    for lbl, val in na_right:
        yr = _field(c, COL_R_X, yr, lbl, val, COL_R_W)
    y = min(yl, yr) - SEC_GAP

    # ── AGENT DETAILS ─────────────────────────────────────────────────────────
    y = _sec(c, MARGIN, y, "Agent / Connector Details")
    province = (d.get('sadac_country_selection') or
                d.get('country_of_origin') or "South Africa")
    agent_name = d.get('agent_name', '').strip() or "—"
    agent_phone = d.get('agent_phone', '').strip() or "0814194980"
    branch_office = d.get('branch_office', '').strip() or "—"
    manager_name = d.get('manager_name', '').strip() or "—"
    y = _field(c, MARGIN, y, "Agent / Connector", agent_name, CONTENT_W)
    y = _field(c, MARGIN, y, "Agent Contact", agent_phone, CONTENT_W)
    y = _field(c, MARGIN, y, "Agent Email",
               "simbarashencube007@gmail.com", CONTENT_W)
    y = _field(c, MARGIN, y, "Branch Office", branch_office, CONTENT_W)
    y = _field(c, MARGIN, y, "Manager / Supervisor", manager_name, CONTENT_W)
    y = _field(c, MARGIN, y, "Province / Region", province, CONTENT_W)
    y -= SEC_GAP

    # ── WAITING PERIODS GRID ──────────────────────────────────────────────────
    y = _sec(c, MARGIN, y, "Waiting Periods Summary")
    cell_w = (CONTENT_W - 8) / 2
    cell_h = 36.0
    grid_data = [
        ("Accidental Death",    "Immediate cover on first premium"),
        ("Natural — Imm. Family", "3 calendar months"),
        ("Natural — Ext. Family", "6 calendar months"),
        ("Suicide",             "12 calendar months"),
    ]
    for i, (lbl, val) in enumerate(grid_data):
        gx = MARGIN + (i % 2) * (cell_w + 8)
        gy = y - (i // 2) * (cell_h + 4)
        c.setFillColor(C_TEAL_LT)
        c.setStrokeColor(C_TEAL)
        c.setLineWidth(0.5)
        c.rect(gx, gy - cell_h, cell_w, cell_h, fill=True, stroke=True)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(C_NAVY)
        c.drawString(gx + 6, gy - 13, lbl)
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BODY)
        c.drawString(gx + 6, gy - 26, val)
    y -= 2 * (cell_h + 4) + SEC_GAP

    # ── COMPLIANCE AUDIT ──────────────────────────────────────────────────────
    y = _sec(c, MARGIN, y, "Compliance & Consent Audit Record")
    now = datetime.now()
    y = _field(c, MARGIN, y, "Submission Timestamp",
               now.strftime("%d %B %Y  %H:%M:%S") + " SAST", CONTENT_W)
    y = _field(c, MARGIN, y, "T&C Version",
               "WWF-TC-v2025.1", CONTENT_W)
    y = _field(c, MARGIN, y, "POPIA Consent",
               "YES — given by applicant at submission", CONTENT_W)
    y = _field(c, MARGIN, y, "T&C Accepted",
               "ACCEPTED", CONTENT_W)
    terms_ok = bool(d.get('terms_acceptance'))
    needs_ok = bool(d.get('needs_analysis_waiver'))
    inter_ok = bool(d.get('intermediary_appointment'))
    for lbl, val in [
        ("Terms & Conditions",        "ACCEPTED" if terms_ok else "NOT confirmed"),
        ("Needs Analysis Waiver",     "ACCEPTED" if needs_ok else "NOT confirmed"),
        ("Intermediary Appointment",  "ACCEPTED" if inter_ok else "NOT confirmed"),
    ]:
        y = _field(c, MARGIN, y, lbl, val, CONTENT_W)
    y -= SEC_GAP

    # ── SIGNATURE BLOCK (no element overlap, fixed top-to-bottom order) ────────
    # (a) heading
    y = _sec(c, MARGIN, y, "Electronic Signature — ECT Act No. 25 of 2002")
    # (b) confirmation paragraph
    c.setFont("Helvetica", 9)
    c.setFillColor(C_META)
    c.drawString(
        MARGIN, y,
        "By signing below the applicant confirms acceptance of all Terms & "
        "Conditions, POPIA consent, FAIS advice record, and Needs Analysis.",
    )
    y -= 11
    c.drawString(
        MARGIN, y,
        "This typed legal name constitutes a binding electronic signature "
        "under ECT Act s.13.",
    )
    # (c) blank space before the signature line (>= 18pt)
    y -= 26

    # (d) signature line
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.8)
    c.line(MARGIN, y, MARGIN + 280, y)

    # (e) label BELOW the line
    y -= 11
    c.setFont("Helvetica", 8)
    c.setFillColor(C_META)
    c.drawString(MARGIN, y, "Applicant Signature (Electronic)")

    # (f) typed name in italic, clearly below the label
    y -= 20
    c.setFont("Times-Italic", 15)
    c.setFillColor(C_NAVY)
    c.drawString(MARGIN + 4, y, d.get('legal_name_confirm', ''))

    # (g) date / time / IP line
    y -= 16
    submission_ip = d.get('submission_ip', '') or "Recorded at submission"
    c.setFont("Helvetica", 8.5)
    c.setFillColor(C_META)
    c.drawString(
        MARGIN + 4, y,
        f"Date & Time: {now.strftime('%d %B %Y')}  |  "
        f"{now.strftime('%H:%M')} SAST  |  IP: {submission_ip}",
    )

    # Extended family table (if any + space available)
    efn = d.get('ext_fam_fname', [])
    ext_entries = [
        (d.get('ext_fam_relation', [''] * len(efn))[i],
         f"{efn[i]} {d.get('ext_fam_lname', [''] * len(efn))[i]}".strip(),
         d.get('ext_fam_dob', [''] * len(efn))[i],
         f"R{d.get('ext_fam_cover', [''] * len(efn))[i]}"
         if d.get('ext_fam_cover', [''] * len(efn))[i] else "—")
        for i in range(len(efn)) if efn[i].strip()
    ]
    if ext_entries and y > CONTENT_BOT + 70:
        y -= SEC_GAP
        y = _sec(c, MARGIN, y, "Extended Family Cover Members")
        ew = [110.0, 170.0, 105.0, 130.0]
        y = _tbl_hdr(c, MARGIN, y,
                     ["Relationship", "Full Name", "DOB", "Cover Amount"], ew)
        for idx, row in enumerate(ext_entries):
            if y < CONTENT_BOT + 20:
                break
            y = _tbl_row(c, MARGIN, y, list(row), ew, shade=(idx % 2 == 1))


# ─── PAGE 3: TERMS & CONDITIONS ───────────────────────────────────────────────

def _page3(c, d: Dict[str, Any], policy_ref: str) -> None:
    # Extended footer for page 3
    c.setFillColor(C_DARK)
    c.rect(0, 0, PAGE_W, FOOTER_H, fill=True, stroke=False)
    c.setFillColor(C_WHITE)
    c.setFont("Helvetica", 6)
    lines_f = [
        "FSP: Zororo Phumulani Investments (Pty) Ltd  ·  FSP48558  ·  "
        "28 Melle St, Braamfontein  ·  +27 81 419 4980  ·  "
        "info@zororo-phumulani.co.za",
        "Underwriter: KGA Life (Pty) Ltd  ·  FSP15980  ·  Stellenbosch  "
        "·  +27 21 944 6300   |   "
        "Claims: claims2@zororo-phumulani.co.za  ·  "
        "customer-care@zororo-phumulani.co.za",
        "FAIS Ombud: 0860-324766  ·  info@faisombud.co.za  ·  "
        "www.faisombud.co.za",
    ]
    for i, ln in enumerate(lines_f):
        c.drawString(MARGIN, FOOTER_H - 8 - i * 8, ln)

    _header(c, 3, policy_ref)
    y = CONTENT_TOP

    # Title
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(C_NAVY)
    c.drawCentredString(PAGE_W / 2, y, "Policy Terms & Conditions Summary")
    y -= 16

    # Helpers
    def sec(text):
        nonlocal y
        y -= 4
        y = _sec(c, MARGIN, y, text)

    def item(text, bullet=True):
        nonlocal y
        chars = int(CONTENT_W / 5.0)
        prefix = "• " if bullet else ""
        lines = textwrap.wrap(prefix + text, chars)
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BODY)
        for i, ln in enumerate(lines):
            c.drawString(MARGIN + (12 if i > 0 else 0), y, ln)
            y -= 12
        y -= 1

    def numbered(num, text):
        nonlocal y
        chars = int((CONTENT_W - 20) / 5.0)
        lines = textwrap.wrap(text, chars)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(C_NAVY)
        c.drawString(MARGIN, y, f"{num}.")
        c.setFont("Helvetica", 9)
        c.setFillColor(C_BODY)
        for i, ln in enumerate(lines):
            c.drawString(MARGIN + 18, y, ln)
            y -= 12
        y -= 1

    # ── GENERAL ──────────────────────────────────────────────────────────────
    sec("General")
    numbered(1, "Premiums due monthly in advance by the 1st of each month.")
    numbered(2, "Main member age 18–65 to join. Maximum entry age 65 (next birthday).")
    wwfp = (d.get('form_context', 'local') == 'wwfp')
    if wwfp:
        numbered(3, "WWF policy for Zimbabwean nationals in any part of the world.")
    else:
        numbered(3, "Policy for members residing in South Africa and the SADC region.")
    numbered(4, "Insured lives limited to those declared on the application form.")
    numbered(5, ("Extended family cover: residents of SA or Zimbabwe only. "
                 "Max age 90. Cash amount claimable if deceased is outside SA/ZIM."))
    numbered(6, "Cohabiting couples qualify for family benefits if declared on form.")
    numbered(7, ("Max 6 unmarried children under 21. Extended to 26 if full-time student. "
                 "Physically/mentally disabled dependants covered (no grant, dependent on parents)."))

    # ── WAITING PERIODS ───────────────────────────────────────────────────────
    sec("Waiting Periods")
    numbered(1, "Cover commences on the 1st day of the month only.")
    numbered(2, "Accidental death: immediate cover from first premium.")
    numbered(3, "Natural causes — immediate family: 3 calendar months.")
    numbered(4, "Natural causes — extended family: 6 calendar months.")
    numbered(5, "Suicide: 12 calendar months.")
    numbered(6, "Newborns enjoy immediate cover if added within 6 months of birth.")

    # ── EXCLUSIONS ────────────────────────────────────────────────────────────
    sec("Exclusions")
    item("Nuclear, biological or chemical weapons or radioactive contamination.")
    item("Sabotage of facilities releasing radioactive or biochemical agents.")
    item("Involvement of insured lives in unlawful activity.")
    item("Wilful self-injury or influence of alcohol/narcotics/drugs "
         "(unless prescribed by registered doctor).")

    # ── PREMIUMS & CLAIMS ─────────────────────────────────────────────────────
    sec("Premiums & Claims")
    numbered(1, "Month-to-month basis. No surrender value. Premiums payable lifelong.")
    numbered(2, "Claims must be submitted within 6 months of the date of death.")
    numbered(3, "Policy lapses after 3 months of non-payment.")
    numbered(4, "60-day grace period for arrears before policy is cancelled.")
    numbered(5, "Foster children excluded unless proof of legal adoption supplied.")

    # ── CHILDREN BENEFIT SCALE ────────────────────────────────────────────────
    sec("Children Benefit Scale")
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_BODY)
    c.drawString(MARGIN, y,
                 "14+ years: 100%   |   6–13 years: 50%   |   "
                 "0–5 years: 25%   |   Stillborn (28+ weeks): 25%")
    y -= 14

    # ── CLAIM DOCUMENTS REQUIRED ─────────────────────────────────────────────
    sec("Claim Documents Required")
    numbered(1, "Main member ID/Passport (certified copy).")
    numbered(2, "Deceased ID/Passport or Registrar General affidavit.")
    numbered(3, "Certified death certificate or signed burial order.")
    numbered(4, "SAPS accident report if cause of death is unnatural.")
    numbered(5, "Doctor’s letter confirming pregnancy months (for stillbirth).")
    numbered(6, "Notice of death if the person passed away in South Africa.")
    numbered(7, "Mother’s certified ID/Passport in case of a minor or stillbirth.")

    # ── TERMINATION ───────────────────────────────────────────────────────────
    sec("Termination")
    item("1 month written notice of cancellation by either party.")
    item("Policy lapses on non-payment or withdrawal from the scheme.")
    item("Cover ceases immediately on policyholder withdrawal.")


# ─── PUBLIC ENTRY POINT ──────────────────────────────────────────────────────

def build_policy_pdf(pdf_path: str, d: Dict[str, Any],
                     stillborn_review: bool = False,
                     compress: bool = True) -> None:
    """
    Build and write the 3-page branded policy booklet to pdf_path.
    d must contain all form fields from submit_policy.
    compress=False disables stream compression (useful for text-search in tests).
    """
    policy_ref = d.get('policy_number', 'DEMO-PREVIEW-MODE')
    page_compression = 1 if compress else 0
    c = rl_canvas.Canvas(pdf_path, pagesize=A4,
                         pageCompression=page_compression)
    _page1(c, d, stillborn_review, policy_ref)
    c.showPage()
    _page2(c, d, policy_ref)
    c.showPage()
    _page3(c, d, policy_ref)
    c.save()
