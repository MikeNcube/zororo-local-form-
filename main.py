from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging
import os
import json
import re
import base64
import smtplib
import uvicorn
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4
import requests
import validators
import pdf_builder
import easipol_catalog

app = FastAPI(
    title="Zororo Phumulani v4.1 - Railway Presentation Mode", version="4.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PDF_DIR = "generated_pdfs"
STATIC_DIR = "static"
REGISTRY_FILE = "submitted_policies.json"
CAPTURES_FILE = "easipol_captures.json"

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if not os.path.exists(REGISTRY_FILE):
    with open(REGISTRY_FILE, "w") as f:
        json.dump([], f)

if not os.path.exists(CAPTURES_FILE):
    with open(CAPTURES_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


# ─── EMAIL CONFIG ─────────────────────────────────────────────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "noreply@zororo-phumulani.co.za")
DUMMY_EMAIL = os.environ.get("DUMMY_EMAIL", "applications@zororo-phumulani.co.za")


def send_policy_email(
    to_address: str, pdf_bytes: bytes,
    policy_ref: str, applicant_name: str,
) -> None:
    """Send policy PDF via SMTP. Silent on any failure or missing config."""
    if not SMTP_USER:
        logging.warning("send_policy_email: SMTP_USER not configured — skipping.")
        return
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to_address
        msg["Subject"] = f"Your Zororo Phumulani Policy — Ref: {policy_ref}"
        body = (
            f"Dear {applicant_name},\n\n"
            "Thank you for your application.\n"
            "Your policy summary is attached.\n\n"
            f"Policy Reference: {policy_ref}\n\n"
            "Queries: info@zororo-phumulani.co.za | 011 339 1484\n\n"
            "Zororo Phumulani Investments (Pty) Ltd\n"
            "FSP48558 — Underwritten by KGA Life FSP15980"
        )
        msg.attach(MIMEText(body, "plain"))
        attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        attachment.add_header(
            "Content-Disposition", "attachment",
            filename=f"Zororo_Policy_{policy_ref}.pdf",
        )
        msg.attach(attachment)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_address, msg.as_string())
        logging.info("Policy email sent: %s ref=%s", to_address, policy_ref)
    except Exception as exc:
        logging.warning("send_policy_email failed: %s", exc)


# ─── EASIPOL INTEGRATION CONFIG ───────────────────────────────────────────────
EASIPOL_LIVE = os.environ.get("EASIPOL_LIVE", "false").strip().lower() == "true"
EASIPOL_TIMEOUT = int(os.environ.get("EASIPOL_TIMEOUT", "10"))
EASIPOL_BASE_URL = os.environ.get("EASIPOL_BASE_URL", "http://127.0.0.1:8900")
_EASIPOL_PAYAT_PREFIX: str = os.environ.get("EASIPOL_PAYAT_PREFIX", "115830")
_EASIPOL_COUNTER_FILE: str = os.environ.get("EASIPOL_COUNTER_FILE", ".easipol_mock_counter")


def _get_easipol_references() -> tuple:
    """Return (policy_number, billing_reference). Falls back gracefully if unavailable."""
    if not EASIPOL_LIVE:
        return "DEMO-PREVIEW-MODE", "NO-LIVE-REFERENCE"
    try:
        auth_resp = requests.post(
            f"{EASIPOL_BASE_URL}/auth",
            headers={"Authorization": os.environ["EASIPOL_BASIC_AUTH"]},
            timeout=EASIPOL_TIMEOUT,
        )
        auth_resp.raise_for_status()
        access_token = auth_resp.json()["access-token"]
        pol_resp = requests.post(
            f"{EASIPOL_BASE_URL}/policies",
            headers={"access-token": access_token},
            json={"source_form": "zororo-local-form-"},
            timeout=EASIPOL_TIMEOUT,
        )
        pol_resp.raise_for_status()
        resp_data = pol_resp.json()
        policy_number = str(resp_data["policy_no"])
        billing_reference = str(resp_data["reference_no"])
        if not (billing_reference.isdigit() and len(billing_reference) == 20):
            raise ValueError(
                f"Pay@ billing_reference invalid (got {billing_reference!r}); "
                "must be exactly 20 digits."
            )
        return (policy_number, billing_reference)
    except Exception as exc:
        logging.warning(f"Easipol unavailable: {exc}")
        policy_ref = f"ZP-FALLBACK-{uuid4().hex[:8].upper()}"
        return policy_ref, "PENDING-EASIPOL"


def load_registered_phone_numbers() -> List[str]:
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def append_registered_phone_number(phone_num: str):
    numbers = load_registered_phone_numbers()
    numbers.append(phone_num)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(numbers, f)


def _load_easipol_captures() -> list:
    try:
        with open(CAPTURES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _validate_billing_reference(ref: str) -> None:
    if not re.fullmatch(r"\d{20}", ref):
        raise ValueError(f"Easipol billing_reference failed 20-digit guard: {ref!r}")


def _mock_easipol_references() -> dict:
    """Deterministic counter-based mock. Policy numbers are Easipol-assigned live;
    mock values are shaped but low. 115830 = Pay@ merchant prefix; ZORORO = live policy prefix."""
    try:
        counter = int(open(_EASIPOL_COUNTER_FILE).read().strip()) + 1
    except (FileNotFoundError, ValueError):
        counter = 1
    with open(_EASIPOL_COUNTER_FILE, "w") as fh:
        fh.write(str(counter))
    today = datetime.now().strftime("%Y-%m-%d")
    policy_number = f"ZORORO{counter:06d}"
    billing_reference = f"{_EASIPOL_PAYAT_PREFIX}{counter:014d}"
    _validate_billing_reference(billing_reference)
    logging.info(
        "[EASIPOL MOCK] policy_number=%s billing_reference=%s",
        policy_number, billing_reference,
    )
    return {
        "policy_number":     policy_number,
        "billing_reference": billing_reference,
        "pay_at_number":     billing_reference,
        "easy_pay_number":   f"MOCK-EP-{counter:06d}",
        "inception_date":    today,
        "date_captured":     today,
    }


def _pg_capture(record: dict) -> None:
    """Write one capture row to Postgres. Raises on any failure — caller handles fallback."""
    import psycopg  # deferred: optional dep; ImportError propagates to caller's except
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")
    with psycopg.connect(db_url, connect_timeout=5, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS easipol_captures (
                id                SERIAL PRIMARY KEY,
                captured_at       TIMESTAMPTZ DEFAULT NOW(),
                source_form       TEXT,
                policy_number     TEXT,
                billing_reference TEXT,
                live              BOOLEAN,
                meta              JSONB,
                pay_at_number     TEXT,
                easy_pay_number   TEXT,
                inception_date    TEXT,
                date_captured     TEXT
            )
        """)
        conn.execute(
            """
            INSERT INTO easipol_captures
                (source_form, policy_number, billing_reference, live, meta,
                 pay_at_number, easy_pay_number, inception_date, date_captured)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.get("source_form"),
                record.get("policy_number"),
                record.get("billing_reference"),
                bool(record.get("live", False)),
                record.get("meta"),
                record.get("pay_at_number"),
                record.get("easy_pay_number"),
                record.get("inception_date"),
                record.get("date_captured"),
            ),
        )


def _append_easipol_capture(
    policy_number: str,
    billing_reference: str,
    pay_at_number: str = None,
    easy_pay_number: str = None,
    inception_date: str = None,
    date_captured: str = None,
) -> None:
    """Capture identifiers-only row. Tries Postgres first; falls back to JSON. No PII (POPIA)."""
    from datetime import timezone
    record = {
        "id":              uuid4().hex,
        "source_form":     "zororo-local-form-",
        "policy_number":   policy_number,
        "billing_reference": billing_reference,
        "live":            EASIPOL_LIVE,
        "captured_at":     datetime.now(timezone.utc).isoformat(),
        "pay_at_number":   pay_at_number,
        "easy_pay_number": easy_pay_number,
        "inception_date":  inception_date,
        "date_captured":   date_captured,
    }
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        try:
            _pg_capture({k: record[k] for k in (
                "source_form", "policy_number", "billing_reference", "live",
                "pay_at_number", "easy_pay_number", "inception_date", "date_captured",
            )})
            return
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "Postgres capture failed, falling back to JSON: %s", exc
            )
    # JSON flat-file fallback — always attempted if Postgres absent or failed
    try:
        captures = _load_easipol_captures()
        captures.append(record)
        with open(CAPTURES_FILE, "w", encoding="utf-8") as f:
            json.dump(captures, f)
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("JSON capture fallback failed: %s", exc)


# ─── EASIPOL v2 — CONFIRMED LIVE CONTRACT (2026-06-07) ───────────────────────
# Originals above (_get_easipol_references, _append_easipol_capture) are kept
# intact. _v2 implements the confirmed live contract. Call site switches to _v2.

def _build_create_policy_body(form_data: dict) -> dict:
    """Build the Easipol CreatePolicy request body from form submission data.

    Shape mirrors the manager's live form (application.zororophumulani.co.za),
    confirmed by bundle inspection 2026-06-11. Does NOT transmit — caller gates.

    # TODO: confirm whether agent_id is the agent's Easipol username or a
    # separate numeric code issued by RubiBlue.
    # TODO: confirm FormID/FormName required in CreatePolicy vs. only in hosted form.
    # TODO: verify SubGroupID 370 (Pay@/cash) vs 371 (Debit) field placement.
    """
    plan_name = form_data.get("plan_name", "")
    pay_method = form_data.get("pay_method", "")
    product_id = easipol_catalog.get_product_id(plan_name) or 0
    subgroup_id = easipol_catalog.get_subgroup_id(pay_method)

    main_member: dict = {
        "FranchiseID":  easipol_catalog.FRANCHISE_ID,
        "SubGroupID":   subgroup_id,
        "FormID":       easipol_catalog.FORM_ID,
        "FormName":     easipol_catalog.FORM_NAME,
        "ProductID":    product_id,
        "First_Name":   form_data.get("fname", "").strip(),
        "Surname":      form_data.get("lname", "").strip(),
        "IDNumber":     form_data.get("identity_value", "").strip(),
        "DateOfBirth":  form_data.get("dob", "").strip(),
        "Gender":       form_data.get("gender", "").strip(),
        "Cell_Number":  form_data.get("phone", "").strip(),
        "Home_Tel":     "",
        "Work_Tel":     "",
        "Payment_Method": pay_method.strip(),
    }
    agent_id = form_data.get("agent_id", "").strip().upper()
    if agent_id:
        main_member["agent_id"] = agent_id

    dep_rows = []
    for i, dep in enumerate(form_data.get("dependents", []), start=1):
        dep_rows.append({
            "RowID":       i,
            "RelationID":  dep.get("relation", ""),
            "FirstName":   dep.get("fname", ""),
            "Surname":     dep.get("lname", ""),
            "IDNumber":    dep.get("id_number", ""),
            "Passport":    "",
            "ProductID":   product_id,
            "Amount":      0,
            "DateOfBirth": dep.get("dob", ""),
            "Premium":     0,
        })

    banking: dict = {
        "BankingDetailsAccountHolder": form_data.get("account_holder", "").strip(),
        "BankingDetailsAccountNumber": form_data.get("account_number", "").strip(),
        "BankingDetailsDebitDay":      form_data.get("debit_day", "1").strip(),
    }
    bank_name = form_data.get("bank_name", "").strip()
    if bank_name:
        banking["BankingDetailsBank"] = bank_name

    return {
        "MainMember":          main_member,
        "PaymentMethod":       None,
        "MainMemberAge":       0,
        "Dependents":          dep_rows,
        "BankingDetails":      banking,
        "Documents":           [],
        "Beneficiary":         None,
        "MainMemberSignature": "",
        "PolicyMemberBenefits": [],
    }


def _get_easipol_references_v2(form_data: dict = None) -> dict:
    """v2 — confirmed live contract. Returns dict with 6 Easipol fields.

    PARKED STATE (2026-06-11): body assembly complete; transmission blocked.
    Three gates must clear before EASIPOL_LIVE=true is set:
      (1) Manager go-ahead to bring a second form online.
      (2) Confirm Basic Auth credentials have CreatePolicy WRITE access.
      (3) Rotate / reissue the exposed Basic Auth credential.

    Live READ contract (confirmed 2026-06-07):
      auth:  POST /auth -> session headers: access-token / expiry / uid / token-type
      read:  GET  /api/PolicyV2/GetPolicy
             wrapper: {HttpResponseCode, ResponseMessage, ResponseObject}
             policy_number:   ResponseObject.MainMember.Policy_Number (or PolicyNumber)
             pay_at_number:   ResponseObject.MainMember.PayAtNumber (20 digits, prefix 115830)
             easy_pay_number: ResponseObject.MainMember.EasyPayNumber (~12 digits)
             inception_date:  ResponseObject.MainMember.Inception_Date
             date_captured:   ResponseObject.MainMember.Date_Captured
    """
    if form_data:
        try:
            body = _build_create_policy_body(form_data)
            logging.debug("[EASIPOL PARKED] CreatePolicy body: %s", json.dumps(body))
        except Exception as exc:
            logging.warning("[EASIPOL PARKED] Body build error: %s", exc)

    if not EASIPOL_LIVE:
        return {
            "policy_number":     "DEMO-PREVIEW-MODE",
            "billing_reference": "NO-LIVE-REFERENCE",
            "pay_at_number":     None,
            "easy_pay_number":   None,
            "inception_date":    None,
            "date_captured":     None,
        }

    raise NotImplementedError(
        "PARKED — CreatePolicy transmission blocked. Three gates must clear: "
        "(1) manager go-ahead, (2) write-access confirmed, (3) credential rotation."
    )


# ─── EMAIL LOGIC (HTTP API — SendGrid / Resend) ─────────────────────────
def _pdf_attachment_payload(pdf_bytes: Optional[bytes], pdf_filename: str):
    """Build provider-neutral base64 PDF attachment dict, or None if no PDF."""
    if not pdf_bytes:
        return None
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    return {"filename": pdf_filename, "content": encoded}


def _build_sendgrid_payload(from_email, to_addr, subject, html_body, attachment):
    """Assemble SendGrid v3 mail/send JSON body."""
    payload = {
        "personalizations": [{"to": [{"email": to_addr}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_body}],
    }
    if attachment:
        payload["attachments"] = [{
            "content": attachment["content"],
            "filename": attachment["filename"],
            "type": "application/pdf",
            "disposition": "attachment",
        }]
    return payload


def _build_resend_payload(from_email, to_addr, subject, html_body, attachment):
    """Assemble Resend emails API JSON body."""
    payload = {
        "from": from_email,
        "to": [to_addr],
        "subject": subject,
        "html": html_body,
    }
    if attachment:
        payload["attachments"] = [attachment]
    return payload


def _post_email_json(url: str, api_key: str, payload: dict, timeout: int = 15) -> bool:
    """POST JSON to a transactional email provider; return True on 2xx."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return 200 <= response.status < 300


def _dispatch_via_provider(provider, api_key, from_email, to_addr,
                           subject, html_body, attachment) -> bool:
    """Route outbound mail to SendGrid or Resend based on EMAIL_PROVIDER."""
    if provider == "sendgrid":
        url = "https://api.sendgrid.com/v3/mail/send"
        payload = _build_sendgrid_payload(
            from_email, to_addr, subject, html_body, attachment
        )
    else:
        url = "https://api.resend.com/emails"
        payload = _build_resend_payload(
            from_email, to_addr, subject, html_body, attachment
        )
    return _post_email_json(url, api_key, payload)


def send_email_worker(to_addr: str, subject: str, html_body: str,
                      pdf_bytes: Optional[bytes], pdf_filename: str) -> bool:
    """
    Send one transactional email via HTTPS API (SendGrid or Resend).
    Runs under FastAPI BackgroundTasks — failures never block the HTTP response.
    """
    api_key = os.environ.get("EMAIL_API_KEY", "")
    from_email = os.environ.get(
        "DEFAULT_FROM_EMAIL", "applications@zororo-phumulani.co.za"
    )
    provider = os.environ.get("EMAIL_PROVIDER", "resend").strip().lower()

    if not api_key:
        print("[ERROR] PROVIDER DISPATCH ERROR: EMAIL_API_KEY is not configured")
        return False

    if provider not in ("sendgrid", "resend"):
        print(
            f"[ERROR] PROVIDER DISPATCH ERROR: "
            f"unsupported EMAIL_PROVIDER '{provider}' (use sendgrid or resend)"
        )
        return False

    attachment = _pdf_attachment_payload(pdf_bytes, pdf_filename)

    try:
        ok = _dispatch_via_provider(
            provider, api_key, from_email, to_addr, subject, html_body, attachment
        )
        if ok:
            print(f"[EMAIL] Policy PDF notification dispatched via {provider}")
        return ok
    except urllib.error.HTTPError as exc:
        exc.read()
        print(
            f"[EMAIL ERROR] Provider returned HTTP {exc.code} from {provider}"
        )
        return False
    except Exception as exc:
        print(f"[ERROR] PROVIDER DISPATCH ERROR: {exc}")
        return False


def get_client_email_template(name, policy_number, plan, premium):
    today = datetime.now().strftime("%d %B %Y")
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;">
<div style="max-width:600px;margin:32px auto;border-radius:10px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.10);">
  <div style="background:linear-gradient(135deg,#1e3a5f,#0d2137);padding:28px 32px;">
    <h1 style="color:#fff;font-size:22px;margin:0 0 6px;">Zororo Phumulani</h1>
    <p style="color:rgba(255,255,255,0.65);margin:0;font-size:13px;">Application Received — Digital Gateway</p>
  </div>
  <div style="background:#fff;padding:28px 32px;">
    <p style="font-size:15px;color:#1a1a2e;">Dear <b>{name}</b>,</p>
    <p style="color:#4a5568;font-size:14px;line-height:1.7;">
      Your policy application has been successfully received.
      Attached is your completed application form for your records.</p>
    <div style="background:#f5f7fb;border-left:4px solid #0d9488;border-radius:6px;padding:18px 20px;margin:20px 0;">
      <p style="margin:0 0 4px;font-size:11px;color:#6b7a99;font-weight:bold;text-transform:uppercase;">Policy Tracker Reference</p>
      <p style="margin:0;font-size:24px;font-weight:bold;color:#1e3a5f;">{policy_number}</p>
      <p style="margin:8px 0 0;font-size:13px;color:#6b7a99;">{plan} &nbsp;·&nbsp; {premium} &nbsp;·&nbsp; {today}</p>
    </div>
    <p style="font-size:13px;color:#4a5568;">For immediate assistance call <b>+27 81 419 4980</b></p>
  </div>
  <div style="background:#0d2137;padding:14px 32px;text-align:center;">
    <p style="color:rgba(255,255,255,0.4);font-size:10px;margin:0;">
      Zororo Phumulani Investments (Pty) Ltd · FSP48558 · Underwritten by KGA Life FSP15980</p>
  </div>
</div>
</body></html>"""


def read_and_render_template(title_label, context_flag, form_context="local"):
    file_path = "templates/index.html"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            html_content = html_content.replace("{{FORM_CONTEXT_TITLE}}", title_label)
            html_content = html_content.replace("{{CONTEXT_FLAG}}", context_flag)
            hidden = (
                f'<input type="hidden" name="form_context" value="{form_context}">'
            )
            html_content = html_content.replace("{{FORM_CONTEXT}}", hidden)
            return html_content
    return "<h1>System Error: templates/index.html missing!</h1>"


@app.get("/", response_class=HTMLResponse)
async def serve_local_form():
    return read_and_render_template(
        "LOCAL REGIONAL FORM SECTION (FSP48558)", "South Africa", "local"
    )


@app.get("/sadac", response_class=HTMLResponse)
async def serve_sadac_form():
    return read_and_render_template(
        "SADC REGIONAL FORM SECTION (FSP48558)", "SADC Region", "sadc"
    )


@app.get("/wwfp", response_class=HTMLResponse)
async def serve_wwfp_form():
    return read_and_render_template(
        "WWFP DIASPORA FORM SECTION (FSP48558)", "International", "wwfp"
    )


@app.get("/terms-and-conditions", response_class=HTMLResponse)
async def serve_terms_and_conditions():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Terms & Conditions</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    </head>
    <body class="bg-gray-50 p-8 font-sans">
        <div class="max-w-4xl mx-auto bg-white rounded-lg shadow-lg p-8">
            <h1 class="text-3xl font-bold text-gray-900 mb-6">Zororo Phumulani Terms & Conditions</h1>
            <h2 class="text-xl font-semibold text-gray-800 mb-4">1. Introduction</h2>
            <p class="mb-4 text-gray-700">Welcome to Zororo Phumulani. These Terms and Conditions govern your use of our digital application form and the services provided through it. By accessing or using our services, you agree to be bound by these Terms.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">2. Eligibility</h2>
            <p class="mb-4 text-gray-700">You must be at least 18 years old and a legal resident of the country where the policy is issued to use our services. By proceeding, you confirm that you meet these eligibility requirements.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">3. Application Process</h2>
            <p class="mb-4 text-gray-700">The digital application form requires accurate and complete information. Any false or misleading information may result in the denial or termination of your policy. All data submitted is subject to our Privacy Policy.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">4. Policy Acceptance</h2>
            <p class="mb-4 text-gray-700">Submission of this form does not guarantee policy acceptance. All applications are subject to underwriting approval by Zororo Phumulani, which may include a waiting period. You will be notified of your application status via your provided contact details.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">5. Premiums and Payments</h2>
            <p class="mb-4 text-gray-700">Policy premiums are calculated based on your selected cover options and personal details. Payments must be made via approved methods (e.g., debit order, Pay@). Failure to make timely payments may lead to policy lapse.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">6. Communication</h2>
            <p class="mb-4 text-gray-700">By providing your contact details, you consent to receive communications from Zororo Phumulani regarding your application, policy, and related services, based on your opt-in preferences.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">7. Legal Declarations</h2>
            <p class="mb-4 text-gray-700">You acknowledge and agree to all legal declarations made during the application process, including the Terms & Conditions Acceptance, Needs Analysis Waiver, and Mandated Intermediary Appointment.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">8. Privacy Policy</h2>
            <p class="mb-4 text-gray-700">Your privacy is important to us. Our Privacy Policy details how we collect, use, and protect your personal information. By using our services, you agree to our <a href="#" class="text-blue-600 hover:underline">Privacy Policy</a>.</p>

            <h2 class="text-xl font-semibold text-gray-800 mb-4">9. Amendments</h2>
            <p class="mb-4 text-gray-700">Zororo Phumulani reserves the right to amend these Terms and Conditions at any time. Updates will be posted on our website. Continued use of our services constitutes acceptance of the revised Terms.</p>

            <p class="text-sm text-gray-600 mt-8">Last Updated: May 27, 2026</p>
        </div>
    </body>
    </html>
    """


@app.post("/submit-global-policy")
async def submit_policy(
    request: Request,
    background_tasks: BackgroundTasks,
    product_type: str = Form(...),
    title: str = Form(...),
    fname: str = Form(...),
    lname: str = Form(...),
    gender: str = Form(...),
    country_of_residence: str = Form(default=""),
    id_doc_type: str = Form(...),
    identity_value: str = Form(...),
    phone: str = Form(...),
    plan_name: str = Form(...),
    local_total: str = Form(...),
    pay_method: str = Form(...),
    legal_name_confirm: str = Form(...),
    email: str = Form(default=""),
    dob: str = Form(...),
    address: str = Form(...),
    marital_status: str = Form(...),
    sadac_country_selection: str = Form(default=""),
    country_of_origin: str = Form(default=""),
    ben_fname: str = Form(default=""),
    ben_lname: str = Form(default=""),
    ben_rel: str = Form(default=""),
    ben_phone: str = Form(default=""),
    bank_name: str = Form(default=""),
    account_name: str = Form(default=""),
    account_num: str = Form(default=""),
    branch_code: str = Form(default=""),
    account_type: str = Form(default="Current"),
    acc_holder_phone: str = Form(default=""),
    commencement_date: str = Form(default=""),
    deduction_date: str = Form(default="1"),
    fam_relation: List[str] = Form(default=[]),
    fam_fname: List[str] = Form(default=[]),
    fam_lname: List[str] = Form(default=[]),
    fam_dob: List[str] = Form(default=[]),
    ext_fam_relation: List[str] = Form(default=[]),
    ext_fam_fname: List[str] = Form(default=[]),
    ext_fam_lname: List[str] = Form(default=[]),
    ext_fam_dob: List[str] = Form(default=[]),
    ext_fam_cover: List[str] = Form(default=[]),
    optin_phone: bool = Form(False),
    optin_sms: bool = Form(False),
    optin_email: bool = Form(False),
    optin_whatsapp: bool = Form(False),
    terms_acceptance: bool = Form(...),
    needs_analysis_waiver: bool = Form(...),
    intermediary_appointment: bool = Form(...),
    passport_doc: UploadFile = File(default=None),
    tsf_doc: UploadFile = File(default=None),
    form_context: str = Form(default="local"),
    popia_consent: str = Form(default=""),
    agent_name: str = Form(default=""),
    agent_phone: str = Form(default=""),
    agent_id: str = Form(default=""),
    branch_office: str = Form(default=""),
    manager_name: str = Form(default=""),
    street_address: str = Form(default=""),
    area_suburb: str = Form(default=""),
    postal_code: str = Form(default=""),
    alt_phone: str = Form(default=""),
    whatsapp: str = Form(default=""),
    nationality: str = Form(default=""),
):
    # POPIA consent gate — must be explicitly "true" (POPIA Act 4 of 2013)
    if popia_consent.strip().lower() != "true":
        raise HTTPException(
            status_code=422,
            detail="POPIA consent is required to submit your application.",
        )

    # Branch office is required (FSCA intermediary attribution)
    branch_err = validators.validate_branch_office(branch_office)
    if branch_err:
        raise HTTPException(status_code=422, detail=branch_err)

    # Street address is required
    street_err = validators.validate_street_address(street_address)
    if street_err:
        raise HTTPException(status_code=422, detail=street_err)

    # Client IP for audit trail (Railway proxy: x-forwarded-for holds real IP)
    fwd = request.headers.get("x-forwarded-for", "")
    client_ip = fwd.split(",")[0].strip() if fwd else (
        request.client.host if request.client else "Unknown")

    # Duplicate phone guard — skipped for SADAC (same number may repeat)
    clean_phone = validators.canonicalize_sa_phone(phone)
    if form_context != "sadc" and clean_phone in load_registered_phone_numbers():
        raise HTTPException(
            status_code=400,
            detail="Guardrail Failure: A policy has already been registered with this mobile phone number.",
        )

    # Immediate family count guard (SPEC §7: max 1 spouse + 6 children = 7)
    dep_count = sum(1 for f in fam_fname if f.strip())
    if dep_count > 7:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Maximum 7 immediate dependents permitted "
                f"(1 spouse + up to 6 children). {dep_count} submitted."
            ),
        )

    # Email — optional; fall back to DUMMY_EMAIL if not provided
    no_client_email = not email.strip()
    effective_email = email.strip() if email.strip() else DUMMY_EMAIL

    # Beneficiary deferral flag — all four fields empty means defer
    bene_deferred = not any([
        ben_fname.strip(), ben_lname.strip(),
        ben_rel.strip(), ben_phone.strip(),
    ])

    # ── VALIDATION LAYER — runs before any writes or PDF generation ─────────
    field_kwargs = dict(
        fname=fname, lname=lname, phone=phone, email=effective_email,
        address=address, dob=dob, gender=gender,
        marital_status=marital_status, ben_fname=ben_fname,
        ben_lname=ben_lname, ben_rel=ben_rel, ben_phone=ben_phone,
    )
    errors = validators.collect_validation_errors(
        form_context=form_context,
        id_doc_type=id_doc_type,
        identity_value=identity_value,
        dob=dob,
        gender=gender,
        phone=phone,
        sadac_country_selection=sadac_country_selection,
        country_of_origin=country_of_origin,
        country_of_residence=country_of_residence,
        field_kwargs=field_kwargs,
        skip_beneficiary=bene_deferred,
    )
    if errors:
        raise HTTPException(status_code=400, detail=" | ".join(errors))

    stillborn_review = validators.check_stillborn_flag(fam_relation, fam_dob)
    # ── END VALIDATION ────────────────────────────────────────────────────────

    append_registered_phone_number(clean_phone)

    # ── EASIPOL FETCH (before PDF so live values thread into the document) ────
    easipol_data: dict = {}
    easipol_policy_number = "PENDING"
    easipol_billing_reference = "PENDING"
    try:
        _ep_deps = []
        for i, fn in enumerate(fam_fname):
            if fn.strip():
                _ep_deps.append({
                    "relation":   fam_relation[i] if i < len(fam_relation) else "",
                    "fname":      fn.strip(),
                    "lname":      fam_lname[i] if i < len(fam_lname) else "",
                    "dob":        fam_dob[i] if i < len(fam_dob) else "",
                    "id_number":  "",
                })
        for i, fn in enumerate(ext_fam_fname):
            if fn.strip():
                _ep_deps.append({
                    "relation":   ext_fam_relation[i] if i < len(ext_fam_relation) else "",
                    "fname":      fn.strip(),
                    "lname":      ext_fam_lname[i] if i < len(ext_fam_lname) else "",
                    "dob":        ext_fam_dob[i] if i < len(ext_fam_dob) else "",
                    "id_number":  "",
                })
        easipol_data = _get_easipol_references_v2(form_data={
            "fname":          fname,
            "lname":          lname,
            "identity_value": identity_value,
            "dob":            dob,
            "gender":         gender,
            "phone":          phone,
            "plan_name":      plan_name,
            "pay_method":     pay_method,
            "agent_id":       agent_id,
            "dependents":     _ep_deps,
            "account_holder": account_name,
            "account_number": account_num,
            "debit_day":      deduction_date,
            "bank_name":      bank_name,
        })
        easipol_policy_number = easipol_data.get("policy_number", "PENDING")
        easipol_billing_reference = easipol_data.get("billing_reference", "PENDING")
    except Exception as exc:
        logging.error("Easipol fetch (non-blocking): %s", exc)
    # ── END EASIPOL FETCH ─────────────────────────────────────────────────────
    policy_number = easipol_policy_number

    # ── EASIPOL CAPTURE ───────────────────────────────────────────────────────
    try:
        _append_easipol_capture(
            policy_number=easipol_policy_number,
            billing_reference=easipol_billing_reference,
            pay_at_number=easipol_data.get("pay_at_number"),
            easy_pay_number=easipol_data.get("easy_pay_number"),
            inception_date=easipol_data.get("inception_date"),
            date_captured=easipol_data.get("date_captured"),
        )
    except Exception as exc:
        logging.error("Easipol capture (non-blocking): %s", exc)
    # ── END EASIPOL CAPTURE ───────────────────────────────────────────────────

    pdf_filename = "Zororo_Presentation_Preview_Booklet.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    pdf_data = {
        "title": title, "fname": fname, "lname": lname,
        "id_doc_type": id_doc_type, "identity_value": identity_value,
        "dob": dob, "gender": gender, "marital_status": marital_status,
        "phone": phone, "email": effective_email, "address": address,
        "no_client_email": no_client_email,
        "submission_ip": client_ip,
        "agent_name": agent_name, "agent_phone": agent_phone,
        "branch_office": branch_office, "manager_name": manager_name,
        "sadac_country_selection": sadac_country_selection,
        "country_of_origin": country_of_origin,
        "country_of_residence": country_of_residence,
        "product_type": product_type, "plan_name": plan_name,
        "local_total": local_total,
        "form_context": form_context,
        "policy_number": policy_number,
        "fam_relation": fam_relation, "fam_fname": fam_fname,
        "fam_lname": fam_lname, "fam_dob": fam_dob,
        "ben_fname": ben_fname, "ben_lname": ben_lname,
        "ben_rel": ben_rel, "ben_phone": ben_phone,
        "ext_fam_relation": ext_fam_relation, "ext_fam_fname": ext_fam_fname,
        "ext_fam_lname": ext_fam_lname, "ext_fam_dob": ext_fam_dob,
        "ext_fam_cover": ext_fam_cover,
        "pay_method": pay_method, "bank_name": bank_name,
        "account_name": account_name, "account_num": account_num,
        "branch_code": branch_code, "account_type": account_type,
        "acc_holder_phone": acc_holder_phone,
        "commencement_date": commencement_date, "deduction_date": deduction_date,
        "optin_phone": optin_phone, "optin_sms": optin_sms,
        "optin_email": optin_email, "optin_whatsapp": optin_whatsapp,
        "terms_acceptance": terms_acceptance,
        "needs_analysis_waiver": needs_analysis_waiver,
        "intermediary_appointment": intermediary_appointment,
        "legal_name_confirm": legal_name_confirm,
        "bene_deferred": bene_deferred,
        "street_address": street_address,
        "area_suburb": area_suburb,
        "postal_code": postal_code,
        "alt_phone": alt_phone,
        "whatsapp": whatsapp,
        "nationality": nationality,
        "easipol_pay_at_number":    easipol_data.get("pay_at_number",    "Pending (live)") if EASIPOL_LIVE else "Pending (live)",
        "easipol_easy_pay_number":  easipol_data.get("easy_pay_number",  "Pending (live)") if EASIPOL_LIVE else "Pending (live)",
        "easipol_inception_date":   easipol_data.get("inception_date",   "Pending (live)") if EASIPOL_LIVE else "Pending (live)",
        "easipol_date_captured":    easipol_data.get("date_captured",    "Pending (live)") if EASIPOL_LIVE else "Pending (live)",
    }
    pdf_builder.build_policy_pdf(pdf_path, pdf_data, stillborn_review)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    # SMTP policy email (silent on failure)
    try:
        send_policy_email(
            effective_email, pdf_bytes,
            policy_number, f"{fname} {lname}".strip(),
        )
    except Exception as _e:
        logging.warning("send_policy_email wrapper failed: %s", _e)

    # HTTP API fallback email (background task)
    client_body = get_client_email_template(
        f"{fname} {lname}", policy_number, plan_name, local_total,
    )
    background_tasks.add_task(
        send_email_worker,
        effective_email,
        "Your Zororo Phumulani Policy Application",
        client_body,
        pdf_bytes,
        pdf_filename,
    )

    exposed_headers = {
        "X-Easipol-Policy-Number": str(policy_number),
        "X-Easipol-Billing-Reference": str(easipol_billing_reference),
        "X-Bene-Deferred": str(bene_deferred).lower(),
        "Access-Control-Expose-Headers": (
            "X-Easipol-Policy-Number, X-Easipol-Billing-Reference, X-Bene-Deferred"
        ),
    }
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_filename,
        headers=exposed_headers,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
