from fastapi import FastAPI, Form, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import io
import json
import uvicorn

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


@app.post("/submit-global-policy")
async def submit_policy(
    request: Request,
    title: str = Form(...),
    fname: str = Form(...),
    lname: str = Form(...),
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
    bank_name: str = Form(default=""),
    account_name: str = Form(default=""),
    account_num: str = Form(default=""),
    branch_code: str = Form(default=""),
    account_type: str = Form(default="Current"),
    deduction_date: str = Form(default="1"),
    fam_relation: List[str] = Form(default=[]),
    fam_name: List[str] = Form(default=[]),
    fam_dob: List[str] = Form(default=[]),
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
    c.drawString(45, 705, f"Proposer Demographics: {title} {fname} {lname}")
    c.drawString(45, 687, f"Identity Profile Value: {identity_value} ({id_doc_type})")
    c.drawString(45, 669, f"Cover Option Selection: {plan_name}")
    c.drawString(45, 651, f"Calculated Premium Level: {local_total}")

    y = 600
    c.setFont("Helvetica-Bold", 10)
    c.drawString(45, y, "IMMEDIATE DEPENDENTS LIVES ATTACHED:")
    c.setFont("Helvetica", 9)
    has_dependents = False
    for i in range(len(fam_name)):
        if fam_name[i].strip():
            has_dependents = True
            y -= 18
            c.drawString(
                45, y, f"- [{fam_relation[i]}] {fam_name[i]} (DOB: {fam_dob[i]})"
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
    c.drawString(45, 740, "Full Name Allocation: Estate Representative Default")

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
        f"Settlement Selection Channel: {pay_method} (Deduction Date Option: {deduction_date})",
    )
    if pay_method == "Debit Order":
        c.drawString(
            45, 730, f"Banking Profile Account: {bank_name} - (Acc: {account_num})"
        )
    c.drawString(
        45,
        680,
        "• Underwriting Rules: 3 months waiting for immediate family, 6 months for extended lines.",
    )
    c.drawString(
        45,
        660,
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
