from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import io
import json
import uvicorn
import smtplib
import ssl
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

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


# ─── EMAIL LOGIC ────────────────────────────────────────────────────────
def send_email_ssl(to_addr: str, subject: str, html_body: str,
                   pdf_bytes: Optional[bytes], pdf_filename: str) -> bool:
    smtp_host = os.environ.get("SMTP_HOST", "mail.zororo-phumulani.co.za")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_user = os.environ.get("SMTP_USER", "nomthandazo.wwfp@zororo-phumulani.co.za")
    smtp_pass = os.environ.get("SMTP_PASS", "SPA7MW6AOYG4AVLQ")

    if not smtp_user or not smtp_pass:
        return False

    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid.uuid4()}@zororo-phumulani.co.za>"

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if pdf_bytes:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
        msg.attach(part)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [to_addr], msg.as_string())
        return True
    except Exception:
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


def read_and_render_template(title_label, context_flag):
    file_path = "templates/index.html"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            html_content = html_content.replace("{{FORM_CONTEXT_TITLE}}", title_label)
            html_content = html_content.replace("{{CONTEXT_FLAG}}", context_flag)
            return html_content
    return "<h1>System Error: templates/index.html missing!</h1>"


@app.get("/", response_class=HTMLResponse)
async def serve_local_form():
    return read_and_render_template(
        "LOCAL REGIONAL FORM SECTION (FSP48558)", "South Africa"
    )


@app.get("/sadac", response_class=HTMLResponse)
async def serve_sadac_form():
    return read_and_render_template(
        "SADC REGIONAL FORM SECTION (FSP48558)", "SADC Region"
    )


@app.get("/wwfp", response_class=HTMLResponse)
async def serve_wwfp_form():
    return read_and_render_template(
        "WWFP DIASPORA FORM SECTION (FSP48558)", "International"
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
    email: str = Form(...),
    dob: str = Form(...),
    address: str = Form(...),
    marital_status: str = Form(...),
    sadac_country_selection: str = Form(default=""),
    country_of_origin: str = Form(default=""),
    ben_fname: str = Form(...),
    ben_lname: str = Form(...),
    ben_rel: str = Form(...),
    ben_phone: str = Form(...),
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
):
    clean_phone = phone.strip().replace(" ", "")
    if clean_phone in load_registered_phone_numbers():
        raise HTTPException(
            status_code=400,
            detail="Guardrail Failure: A policy has already been registered with this mobile phone number.",
        )

    append_registered_phone_number(clean_phone)

    # STICK TO THE EMAIL PLAN: EXPLICIT DEMO/PREVIEW PLACEHOLDERS
    policy_number = "DEMO-PREVIEW-MODE"
    payat_number = "NO-LIVE-REFERENCE"

    pdf_filename = "Zororo_Presentation_Preview_Booklet.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    # PARTITION STEP: STRICT 3-PAGE REPORTLAB PDF DRAWING BLOCK
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor

    c = canvas.Canvas(pdf_path, pagesize=A4)

    # PAGE 1: CORE METRICS WITH NOTICEABLE WATERMARKS
    c.setFillColor(HexColor("#1e3a5f"))
    c.rect(0, 815, 595, 30, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(45, 825, "ZORORO PHUMULANI PRESENTATION LAYER PREVIEW BOOKLET")

    # Big Red Warning Banner matching your email statement
    c.setFillColor(HexColor("#dc2626"))
    c.rect(45, 785, 505, 20, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(
        55,
        791,
        "NOTICE: DEMO PREVIEW ONLY · NOT A LIVE SYSTEM CONTRACT · NO POLICY ISSUED",
    )

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, 755, f"STATUS: {policy_number}")
    c.drawString(45, 737, f"BILLING LINKAGE: {payat_number}")
    c.setFont("Helvetica", 10)
    c.drawString(45, 705, f"Proposer Demographics: {title} {fname} {lname} (Gender: {gender}, Marital Status: {marital_status})")
    c.drawString(45, 687, f"Identity Profile Value: {identity_value} ({id_doc_type})")
    current_y = 669
    c.drawString(45, current_y, f"Country of Residence: {country_of_residence if country_of_residence else 'N/A'}")
    current_y -= 18 # Space for next line

    # Conditionally display SADC specific country fields
    if sadac_country_selection and country_of_origin:
        c.drawString(45, current_y, f"SADC Country Selection: {sadac_country_selection}")
        current_y -= 18
        c.drawString(45, current_y, f"Country of Origin: {country_of_origin}")
        current_y -= 18
        c.drawString(45, current_y, f"Product Type: {product_type.replace('_', ' ').title()}")
        current_y -= 18
        c.drawString(45, current_y, f"Cover Option Selection: {plan_name}")
        current_y -= 18
        c.drawString(45, current_y, f"Calculated Premium Level: {local_total}")
        current_y -= 18 # Ensure space for next section
    else:
        c.drawString(45, current_y, f"Product Type: {product_type.replace('_', ' ').title()}")
        current_y -= 18
        c.drawString(45, current_y, f"Cover Option Selection: {plan_name}")
        current_y -= 18
        c.drawString(45, current_y, f"Calculated Premium Level: {local_total}")
        current_y -= 18 # Ensure space for next section

    # Calculate starting y for IMMEDIATE DEPENDENTS based on current_y
    y = current_y - 30 # Add a buffer space
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, y, "IMMEDIATE DEPENDENTS LIVES ATTACHED:")
    c.setFont("Helvetica", 9)
    has_dependents = False
    for i in range(len(fam_fname)):
        if fam_fname[i].strip() or fam_lname[i].strip(): # Check if either name part is present
            has_dependents = True
            y -= 18
            c.drawString(
                45, y, f"- [{fam_relation[i]}] {fam_fname[i]} {fam_lname[i]} (DOB: {fam_dob[i]})"
            )
    if not has_dependents:
        y -= 18
        c.drawString(45, y, "None declared.")

    # PAGE 2: EXTENDED FAMILY SUMMARY
    c.showPage()
    c.setFillColor(HexColor("#1e3a5f"))
    c.rect(0, 815, 595, 30, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(45, 825, "EXTENDED FAMILY COVER MEMBERS & BENEFICIARIES (PAGE 2)")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, 770, "NOMINATED ESTATE LEGAL CLAIM BENEFICIARY RELATIONSHIP:")
    c.setFont("Helvetica", 10)
    c.drawString(45, 740, f"Full Name: {ben_fname} {ben_lname}")
    c.drawString(45, 725, f"Relationship: {ben_rel}")
    c.drawString(45, 710, f"Contact Mobile: {ben_phone}")
    
    y_ext_fam = 680
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, y_ext_fam, "EXTENDED FAMILY COVER MEMBERS:")
    c.setFont("Helvetica", 9)
    has_ext_fam = False
    for i in range(len(ext_fam_fname)):
        if ext_fam_fname[i].strip() or ext_fam_lname[i].strip():
            has_ext_fam = True
            y_ext_fam -= 18
            c.drawString(
                45, y_ext_fam, f"- [{ext_fam_relation[i]}] {ext_fam_fname[i]} {ext_fam_lname[i]} (DOB: {ext_fam_dob[i]}) - Cover: R{ext_fam_cover[i]}"
            )
    if not has_ext_fam:
        y_ext_fam -= 18
        c.drawString(45, y_ext_fam, "None declared.")

    # PAGE 3: MANDATES & DISCLAIMER SIGN-OFF
    c.showPage()
    c.setFillColor(HexColor("#1e3a5f"))
    c.rect(0, 815, 595, 30, fill=True, stroke=False)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(45, 825, "STATUTORY MANDATE & POPIA DATA DECLARATION (PAGE 3)")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(45, 780, "DEBIT ORDER ELECTRONIC AUTHORIZATION FRAMEWORK MANDATE")
    c.setFont("Helvetica", 8)
    c.drawString(
        45,
        760,
        "I the undersigned, authorize Zororo Phumulani to debit my bank account monthly.",
    )
    c.drawString(
        45,
        745,
        f"Settlement Selection Channel: {pay_method} (Deduction Date: {deduction_date})",
    )
    if pay_method == "Debit Order":
        c.drawString(45, 730, f"Banking Profile Account: {account_name} - (Acc: {account_num}) (Type: {account_type})")
        c.drawString(45, 715, f"Account Holder Phone: {acc_holder_phone}")
        c.drawString(45, 700, f"Commencement Date: {commencement_date}")

    y_optin = 660
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, y_optin, "COMMUNICATION OPT-INS:")
    c.setFont("Helvetica", 9)
    y_optin -= 15
    c.drawString(45, y_optin, f"- Telephone: {'Yes' if optin_phone else 'No'}")
    y_optin -= 15
    c.drawString(45, y_optin, f"- SMS: {'Yes' if optin_sms else 'No'}")
    y_optin -= 15
    c.drawString(45, y_optin, f"- Email: {'Yes' if optin_email else 'No'}")
    y_optin -= 15
    c.drawString(45, y_optin, f"- WhatsApp: {'Yes' if optin_whatsapp else 'No'}")

    y_legal = y_optin - 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, y_legal, "LEGAL DECLARATIONS:")
    c.setFont("Helvetica", 9)
    y_legal -= 15
    c.drawString(45, y_legal, f"- Terms & Conditions Accepted: {'Yes' if terms_acceptance else 'No'}")
    y_legal -= 15
    c.drawString(45, y_legal, f"- Needs Analysis Waiver Acknowledged: {'Yes' if needs_analysis_waiver else 'No'}")
    y_legal -= 15
    c.drawString(45, y_legal, f"- Mandated Intermediary Appointed: {'Yes' if intermediary_appointment else 'No'}")
    y_legal -= 15
    c.drawString(
        45,
        y_legal,
        "• Legal Full Name Affirmation declaration confirmed: Signed by "
        + legal_name_confirm,
    )

    # Bottom Disclaimer matching email text
    c.setFillColor(HexColor("#fef2f2"))
    c.rect(45, 45, 505, 40, fill=True, stroke=False)
    c.setFillColor(HexColor("#991b1b"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(55, 70, "PRESENTATION LAYER PREVIEW WARNING")
    c.setFont("Helvetica", 7.5)
    c.drawString(
        55,
        56,
        "This document was compiled locally inside standalone presentation components. It is not backed by a live",
    )
    c.drawString(
        55,
        46,
        "Easipol core database policy registry profile, carries no real transaction ID, and is not an active issued contract.",
    )

    c.save()

    # Trigger Phase 2 Email Flow
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    client_body = get_client_email_template(f"{fname} {lname}", policy_number, plan_name, local_total)
    send_email_ssl(email, "Your Zororo Phumulani Policy Application", client_body, pdf_bytes, pdf_filename)

    exposed_headers = {
        "X-Easipol-Policy-Number": str(policy_number),
        "X-Easipol-Billing-Reference": str(payat_number),
        "Access-Control-Expose-Headers": "X-Easipol-Policy-Number, X-Easipol-Billing-Reference",
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
