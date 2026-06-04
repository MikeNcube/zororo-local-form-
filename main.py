from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging
import os
import json
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
import validators
import pdf_builder

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

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if not os.path.exists(REGISTRY_FILE):
    with open(REGISTRY_FILE, "w") as f:
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


def _get_easipol_references() -> tuple:
    """Return (policy_number, billing_reference). Falls back gracefully if unavailable."""
    if not EASIPOL_LIVE:
        return "DEMO-PREVIEW-MODE", "NO-LIVE-REFERENCE"
    try:
        # TODO: replace with real Easipol HTTP call using EASIPOL_TIMEOUT
        raise RuntimeError("Easipol credentials not yet configured.")
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
):
    # POPIA consent gate — must be explicitly "true" (POPIA Act 4 of 2013)
    if popia_consent.strip().lower() != "true":
        raise HTTPException(
            status_code=422,
            detail="POPIA consent is required to submit your application.",
        )

    clean_phone = validators.canonicalize_sa_phone(phone)
    if clean_phone in load_registered_phone_numbers():
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

    policy_number, payat_number = _get_easipol_references()

    pdf_filename = "Zororo_Presentation_Preview_Booklet.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    pdf_data = {
        "title": title, "fname": fname, "lname": lname,
        "id_doc_type": id_doc_type, "identity_value": identity_value,
        "dob": dob, "gender": gender, "marital_status": marital_status,
        "phone": phone, "email": effective_email, "address": address,
        "no_client_email": no_client_email,
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
        "X-Easipol-Billing-Reference": str(payat_number),
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
