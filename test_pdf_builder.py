"""
Smoke tests for pdf_builder.build_policy_pdf.
Each test writes to pytest's tmp_path and verifies raw PDF bytes or file state.
"""

import os
from datetime import date, timedelta

from pdf_builder import build_policy_pdf


def _minimal_pdf_data():
    """Return a minimal but complete pdf_data dict accepted by build_policy_pdf."""
    return {
        "title": "Mr",
        "fname": "Test",
        "lname": "User",
        "id_doc_type": "Passport",
        "identity_value": "A87654321",
        "dob": "1985-06-15",
        "gender": "Male",
        "marital_status": "Single",
        "phone": "0811112222",
        "email": "test@zororo.test",
        "address": "1 Test Street, Johannesburg",
        "sadac_country_selection": "",
        "country_of_origin": "",
        "country_of_residence": "",
        "product_type": "standard",
        "plan_name": "LOCAL_F_R10000|169",
        "local_total": "R 169.00",
        "form_context": "local",
        "policy_number": "DEMO-PREVIEW-MODE",
        "fam_fname": [],
        "fam_lname": [],
        "fam_relation": [],
        "fam_dob": [],
        "ben_fname": "Jane",
        "ben_lname": "User",
        "ben_rel": "Spouse",
        "ben_phone": "0829876543",
        "ext_fam_fname": [],
        "ext_fam_lname": [],
        "ext_fam_relation": [],
        "ext_fam_dob": [],
        "ext_fam_cover": [],
        "pay_method": "PayAt",
        "bank_name": "",
        "account_name": "",
        "account_num": "",
        "branch_code": "",
        "account_type": "Current",
        "acc_holder_phone": "",
        "commencement_date": "",
        "deduction_date": "1",
        "optin_phone": False,
        "optin_sms": False,
        "optin_email": False,
        "optin_whatsapp": False,
        "terms_acceptance": True,
        "needs_analysis_waiver": True,
        "intermediary_appointment": True,
        "legal_name_confirm": "Test User",
    }


def test_pdf_builds_without_error(tmp_path):
    """PDF file is created and has non-zero size."""
    pdf_path = str(tmp_path / "out.pdf")
    build_policy_pdf(pdf_path, _minimal_pdf_data())
    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 0


def test_pdf_stillborn_flag_included(tmp_path):
    """REVIEW REQUIRED text appears in raw bytes when stillborn_review=True."""
    d = _minimal_pdf_data()
    child_dob = (date.today() - timedelta(weeks=10)).strftime("%Y-%m-%d")
    d["fam_fname"] = ["Baby"]
    d["fam_lname"] = ["User"]
    d["fam_relation"] = ["Child"]
    d["fam_dob"] = [child_dob]
    pdf_path = str(tmp_path / "out_stillborn.pdf")
    build_policy_pdf(pdf_path, d, stillborn_review=True, compress=False)
    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert b"REVIEW REQUIRED" in raw


def test_pdf_no_stillborn_flag(tmp_path):
    """REVIEW REQUIRED text absent when stillborn_review=False."""
    pdf_path = str(tmp_path / "out_no_stillborn.pdf")
    build_policy_pdf(pdf_path, _minimal_pdf_data(),
                     stillborn_review=False, compress=False)
    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert b"REVIEW REQUIRED" not in raw


def test_pdf_masked_account_number(tmp_path):
    """Last 4 digits of account appear; full unmasked number never written."""
    d = _minimal_pdf_data()
    d["pay_method"] = "Debit Order"
    d["account_num"] = "1234567890"
    d["account_name"] = "Test Holder"
    d["bank_name"] = "Capitec"
    d["branch_code"] = "470010"
    pdf_path = str(tmp_path / "out_masked.pdf")
    build_policy_pdf(pdf_path, d, compress=False)
    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert b"7890" in raw               # last 4 digits in masked "****7890"
    assert b"1234567890" not in raw     # full raw account never written to PDF


def test_pdf_no_dependents(tmp_path):
    """'None declared' row appears when fam_fname list is empty."""
    d = _minimal_pdf_data()
    # fam_fname is already [] in minimal data
    pdf_path = str(tmp_path / "out_nodep.pdf")
    build_policy_pdf(pdf_path, d, compress=False)
    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert b"None declared" in raw


def test_pdf_sadc_context(tmp_path):
    """'SADC' text appears in raw bytes for SADC form context."""
    d = _minimal_pdf_data()
    d["form_context"] = "sadc"
    d["sadac_country_selection"] = "Botswana"
    d["country_of_origin"] = "Zimbabwe"
    pdf_path = str(tmp_path / "out_sadc.pdf")
    build_policy_pdf(pdf_path, d, compress=False)
    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert b"SADC" in raw
