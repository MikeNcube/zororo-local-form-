import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import main
import pdf_builder
from datetime import date, timedelta

from validators import (
    canonicalize_sa_phone,
    check_stillborn_flag,
    collect_validation_errors,
    validate_context_fields,
    validate_passport,
    validate_phone,
    validate_required_fields,
    validate_sa_id,
    validate_zim_national_id,
)

# Known valid SA ID: DOB 1980-01-01, gender sequence 5009 (Male)
VALID_ID = "8001015009087"

ALL_FIELDS = dict(
    fname="John",
    lname="Doe",
    phone="0812345678",
    email="john@test.co.za",
    address="1 Main Street, Johannesburg",
    dob="1980-01-01",
    gender="Male",
    marital_status="Single",
    ben_fname="Jane",
    ben_lname="Doe",
    ben_rel="Spouse",
    ben_phone="0831234567",
)


# ── SA ID VALIDATION ─────────────────────────────────────────────────────────

def test_sa_id_valid():
    assert validate_sa_id(VALID_ID, "1980-01-01", "Male") is None


def test_sa_id_valid_case_insensitive_gender():
    assert validate_sa_id(VALID_ID, "1980-01-01", "male") is None
    assert validate_sa_id(VALID_ID, "1980-01-01", "MALE") is None


def test_sa_id_wrong_length():
    assert validate_sa_id("123456789012", "1980-01-01", "Male") is not None


def test_sa_id_non_digits():
    assert validate_sa_id("800101500908A", "1980-01-01", "Male") is not None


def test_sa_id_invalid_checksum():
    # Flip last digit from 7 to 1
    assert validate_sa_id("8001015009081", "1980-01-01", "Male") is not None


def test_sa_id_dob_mismatch():
    err = validate_sa_id(VALID_ID, "1981-06-15", "Male")
    assert err is not None
    assert "date of birth" in err.lower()


def test_sa_id_gender_mismatch():
    err = validate_sa_id(VALID_ID, "1980-01-01", "Female")
    assert err is not None
    assert "gender" in err.lower()


def test_sa_id_unrecognised_gender():
    err = validate_sa_id(VALID_ID, "1980-01-01", "Other")
    assert err is not None
    assert "not recognised" in err.lower()


def test_sa_id_invalid_dob_format():
    err = validate_sa_id(VALID_ID, "01/01/1980", "Male")
    assert err is not None
    assert "YYYY-MM-DD" in err


# ── PHONE VALIDATION ─────────────────────────────────────────────────────────

def test_phone_valid_10_digit():
    assert validate_phone("0812345678") is None


def test_phone_valid_plus27():
    assert validate_phone("+27812345678") is None


def test_phone_valid_27_prefix():
    assert validate_phone("27812345678") is None


def test_phone_valid_with_spaces():
    assert validate_phone("081 234 5678") is None


def test_phone_too_short():
    assert validate_phone("081234567") is not None


def test_phone_wrong_prefix():
    assert validate_phone("1812345678") is not None


def test_phone_too_long():
    assert validate_phone("08123456789") is not None


# ── REQUIRED FIELD COMPLETENESS ──────────────────────────────────────────────

def test_required_fields_all_present():
    assert validate_required_fields(**ALL_FIELDS) == []


def test_required_fields_missing_one():
    fields = {**ALL_FIELDS, "fname": ""}
    missing = validate_required_fields(**fields)
    assert "fname" in missing
    assert len(missing) == 1


def test_required_fields_missing_multiple():
    fields = {**ALL_FIELDS, "fname": "", "email": "  ", "ben_phone": ""}
    missing = validate_required_fields(**fields)
    assert set(missing) == {"fname", "email", "ben_phone"}


def test_required_fields_whitespace_counts_as_empty():
    fields = {**ALL_FIELDS, "address": "   "}
    missing = validate_required_fields(**fields)
    assert "address" in missing


# ── CONTEXT-AWARE FIELD ENFORCEMENT ─────────────────────────────────────────

def test_context_local_sa_no_errors():
    assert validate_context_fields("local", "", "", "") is None


def test_context_sadc_both_fields_present():
    assert validate_context_fields("sadc", "Botswana", "Zimbabwe", "") is None


def test_context_sadc_missing_country_of_origin():
    err = validate_context_fields("sadc", "Botswana", "", "")
    assert err is not None
    assert "country_of_origin" in err.lower()


def test_context_wwfp_with_residence():
    assert validate_context_fields("wwfp", "", "", "United Kingdom") is None


def test_context_wwfp_missing_residence():
    err = validate_context_fields("wwfp", "", "", "")
    assert err is not None
    assert "country_of_residence" in err.lower()


def test_context_local_ignores_sadc_fields_even_when_populated():
    # local form_context: SADC fields present but not required — no error
    err = validate_context_fields("local", "Botswana", "", "")
    assert err is None


# ── STILLBORN FLAG ───────────────────────────────────────────────────────────

def test_stillborn_child_within_25_weeks():
    dob = (date.today() - timedelta(weeks=10)).strftime("%Y-%m-%d")
    assert check_stillborn_flag(["Child"], [dob]) is True


def test_stillborn_child_exactly_at_25_weeks_not_flagged():
    dob = (date.today() - timedelta(weeks=25)).strftime("%Y-%m-%d")
    assert check_stillborn_flag(["Child"], [dob]) is False


def test_stillborn_child_beyond_25_weeks_not_flagged():
    dob = (date.today() - timedelta(weeks=30)).strftime("%Y-%m-%d")
    assert check_stillborn_flag(["Child"], [dob]) is False


def test_stillborn_spouse_not_flagged():
    dob = (date.today() - timedelta(weeks=5)).strftime("%Y-%m-%d")
    assert check_stillborn_flag(["Spouse"], [dob]) is False


def test_stillborn_mixed_family_flags_on_child():
    adult_dob = (date.today() - timedelta(weeks=2600)).strftime("%Y-%m-%d")
    child_dob = (date.today() - timedelta(weeks=8)).strftime("%Y-%m-%d")
    assert check_stillborn_flag(["Spouse", "Child"], [adult_dob, child_dob]) is True


def test_stillborn_no_family():
    assert check_stillborn_flag([], []) is False


def test_stillborn_invalid_dob_skipped():
    assert check_stillborn_flag(["Child"], ["not-a-date"]) is False


# ── COLLECT_VALIDATION_ERRORS INTEGRATION ────────────────────────────────────

def _base_kwargs():
    return dict(
        form_context="local",
        id_doc_type="Passport",
        identity_value="A12345678",
        dob="1980-01-01",
        gender="Male",
        phone="0812345678",
        sadac_country_selection="",
        country_of_origin="",
        country_of_residence="",
        field_kwargs=ALL_FIELDS,
    )


def test_collect_no_errors_for_valid_passport_submission():
    assert collect_validation_errors(**_base_kwargs()) == []


def test_collect_id_number_triggers_sa_id_validation():
    kwargs = _base_kwargs()
    kwargs["id_doc_type"] = "ID Number"
    kwargs["identity_value"] = "8001015009087"
    kwargs["dob"] = "1980-01-01"
    kwargs["gender"] = "Male"
    base_fields = {**ALL_FIELDS, "dob": "1980-01-01", "gender": "Male"}
    kwargs["field_kwargs"] = base_fields
    assert collect_validation_errors(**kwargs) == []


def test_collect_reports_all_errors_at_once():
    kwargs = _base_kwargs()
    kwargs["phone"] = "invalid"
    kwargs["field_kwargs"] = {**ALL_FIELDS, "phone": "invalid", "fname": ""}
    errs = collect_validation_errors(**kwargs)
    combined = " ".join(errs)
    assert "fname" in combined
    assert "valid South African" in combined


def test_collect_sadc_error_reported():
    kwargs = _base_kwargs()
    kwargs["form_context"] = "sadc"
    kwargs["sadac_country_selection"] = "Namibia"
    kwargs["country_of_origin"] = ""
    errs = collect_validation_errors(**kwargs)
    assert any("country_of_origin" in e.lower() for e in errs)


# ── NEW: EXPLICIT form_context ENFORCEMENT ───────────────────────────────────

def test_collect_local_context_ignores_absent_sadc_fields():
    # form_context='local' — missing SADC fields must not trigger errors
    kwargs = _base_kwargs()
    kwargs["form_context"] = "local"
    kwargs["sadac_country_selection"] = ""
    kwargs["country_of_origin"] = ""
    assert collect_validation_errors(**kwargs) == []


def test_collect_sadc_context_requires_sadac_country_selection():
    # form_context='sadc' — sadac_country_selection missing → error
    kwargs = _base_kwargs()
    kwargs["form_context"] = "sadc"
    kwargs["sadac_country_selection"] = ""
    kwargs["country_of_origin"] = ""
    errs = collect_validation_errors(**kwargs)
    assert any("sadac_country_selection" in e.lower() for e in errs)


def test_collect_wwfp_context_requires_country_of_residence():
    # form_context='wwfp' — country_of_residence missing → error
    kwargs = _base_kwargs()
    kwargs["form_context"] = "wwfp"
    kwargs["country_of_residence"] = ""
    errs = collect_validation_errors(**kwargs)
    assert any("country_of_residence" in e.lower() for e in errs)


# ── GROUP 2: ENDPOINT INTEGRATION TESTS ─────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with isolated registry and PDF output directories."""
    reg_file = str(tmp_path / "registry.json")
    pdf_dir = str(tmp_path / "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump([], f)
    monkeypatch.setattr(main, "REGISTRY_FILE", reg_file)
    monkeypatch.setattr(main, "PDF_DIR", pdf_dir)
    with TestClient(main.app) as c:
        yield c


def make_valid_form_data():
    """Return a dict of all required form fields for a valid local submission."""
    return {
        "product_type": "standard",
        "title": "Mr",
        "fname": "Tendai",
        "lname": "Moyo",
        "gender": "Male",
        "country_of_residence": "",
        "id_doc_type": "Passport",
        "identity_value": "A12345678",
        "phone": "0811234567",
        "plan_name": "LOCAL_F_R10000|169",
        "local_total": "R 169.00",
        "pay_method": "PayAt",
        "legal_name_confirm": "Tendai Moyo",
        "email": "tendai@zororo.test",
        "dob": "1985-06-15",
        "address": "12 Main Street, Johannesburg",
        "marital_status": "Single",
        "sadac_country_selection": "",
        "country_of_origin": "",
        "street_address": "12 Main Street",
        "ben_fname": "Rudo",
        "ben_lname": "Moyo",
        "ben_rel": "Spouse",
        "ben_phone": "0829876543",
        "terms_acceptance": "true",
        "needs_analysis_waiver": "true",
        "intermediary_appointment": "true",
        "form_context": "local",
        "popia_consent": "true",
        "branch_office": "Braamfontein (Head Office)",
    }


def test_submit_valid_local(client):
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")


def test_submit_duplicate_phone(client):
    data = make_valid_form_data()
    client.post("/submit-global-policy", data=data)
    resp2 = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp2.status_code == 400
    assert "already been registered" in resp2.json()["detail"]


def test_submit_missing_required_field(client):
    # Whitespace-only passes FastAPI's str type check but fails our strip/empty guard
    data = make_valid_form_data()
    data["fname"] = "   "
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 400


def test_submit_invalid_sa_id(client):
    data = make_valid_form_data()
    data["id_doc_type"] = "ID Number"
    data["identity_value"] = "1234567890123"  # fails Luhn checksum
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 400


def test_submit_invalid_phone(client):
    data = make_valid_form_data()
    data["phone"] = "12345"
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 400


def test_submit_sadc_missing_country(client):
    data = make_valid_form_data()
    data["form_context"] = "sadc"
    data["sadac_country_selection"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 400


def test_submit_wwfp_missing_residence(client):
    data = make_valid_form_data()
    data["form_context"] = "wwfp"
    data["country_of_residence"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 400


def test_submit_response_headers(client):
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-easipol-policy-number") is not None
    assert resp.headers.get("x-easipol-billing-reference") is not None


# ── GROUP 3: VALIDATOR EDGE CASES ────────────────────────────────────────────

# SA ID: 9001045800082 — DOB 1990-01-04, gender seq 5800 (Male), checksum 2
_KNOWN_GOOD_ID = "9001045800082"


def test_sa_id_valid_known_good():
    assert validate_sa_id(_KNOWN_GOOD_ID, "1990-01-04", "Male") is None


def test_sa_id_five_chars_too_short():
    assert validate_sa_id("12345", "1990-01-04", "Male") is not None


def test_sa_id_dob_mismatch_specific_id():
    # Known-good ID encodes DOB 1990-01-04; submit 1995-01-01 → mismatch error
    err = validate_sa_id(_KNOWN_GOOD_ID, "1995-01-01", "Male")
    assert err is not None
    assert "date of birth" in err.lower()


def test_phone_plus27_format_specific():
    assert validate_phone("+27821234567") is None


def test_phone_valid_0format():
    assert validate_phone("0821234567") is None


def test_stillborn_flag_not_set_for_adult():
    # 2010-01-01 is well over 25 weeks ago — flag must not be set
    assert check_stillborn_flag(["Child"], ["2010-01-01"]) is False


def test_submit_dependent_without_id(client):
    """Submit with a child dependent but no child ID field — must return 200."""
    data = make_valid_form_data()
    data["fam_relation[]"] = "Child"
    data["fam_fname[]"] = "Amai"
    data["fam_lname[]"] = "Moyo"
    data["fam_dob[]"] = "2018-03-10"
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200


# ── PHONE CANONICALIZATION (duplicate-guard hardening) ───────────────────────

def test_canonicalize_phone_0_format_unchanged():
    assert canonicalize_sa_phone("0821234567") == "0821234567"


def test_canonicalize_phone_plus27_folds_to_0():
    assert canonicalize_sa_phone("+27821234567") == "0821234567"


def test_canonicalize_phone_27_folds_to_0():
    assert canonicalize_sa_phone("27821234567") == "0821234567"


def test_canonicalize_phone_strips_spaces_and_dashes():
    assert canonicalize_sa_phone("+27 82 123-4567") == "0821234567"


def test_submit_duplicate_phone_cross_format(client):
    """Same number in +27 form must be caught as a duplicate of the 0 form."""
    first = make_valid_form_data()
    first["phone"] = "0821234567"
    assert client.post("/submit-global-policy", data=first).status_code == 200

    second = make_valid_form_data()
    second["phone"] = "+27821234567"
    resp2 = client.post("/submit-global-policy", data=second)
    assert resp2.status_code == 400
    assert "already been registered" in resp2.json()["detail"]


# ── PASSPORT FORMAT VALIDATION ────────────────────────────────────────────────

def test_sa_passport_valid():
    assert validate_passport("A12345678", "local") is None


def test_sa_passport_valid_two_letters():
    assert validate_passport("AB1234567", "local") is None


def test_zw_passport_valid():
    assert validate_passport("GN452257", "sadc") is None


def test_zw_passport_valid_2():
    assert validate_passport("BE471896", "wwfp") is None


def test_passport_invalid_gibberish():
    assert validate_passport("hello", "local") is not None
    assert validate_passport("hello", "sadc") is not None
    assert validate_passport("hello", "wwfp") is not None


def test_passport_invalid_short():
    assert validate_passport("A12", "local") is not None


# ── PHONE VALIDATION — SADC/WWFP CONTEXTS ────────────────────────────────────

def test_zw_phone_valid_sadc():
    assert validate_phone("+263771234567", "sadc") is None


def test_uk_phone_valid_wwfp():
    assert validate_phone("+447911123456", "wwfp") is None


def test_zw_phone_rejected_local():
    assert validate_phone("+263771234567", "local") is not None


def test_intl_phone_valid_wwfp():
    assert validate_phone("+15551234567", "wwfp") is None


def test_invalid_phone_all_contexts():
    assert validate_phone("notaphone", "local") is not None
    assert validate_phone("notaphone", "sadc") is not None
    assert validate_phone("notaphone", "wwfp") is not None


# ── SPRINT 4: EASIPOL HEADER SCAFFOLDING ─────────────────────────────────────

def test_easipol_live_false_returns_demo_headers(client):
    """EASIPOL_LIVE=False (default) must return the demo placeholder strings."""
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-easipol-policy-number") == "DEMO-PREVIEW-MODE"
    assert resp.headers.get("x-easipol-billing-reference") == "NO-LIVE-REFERENCE"


def test_easipol_live_true_returns_fallback(client, monkeypatch):
    """EASIPOL_LIVE=True in PARKED state must return 200 with PENDING policy ref."""
    monkeypatch.setattr(main, "EASIPOL_LIVE", True)
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-easipol-policy-number") == "PENDING"


# ── SPRINT 4: MAX DEPENDENTS ENFORCEMENT ─────────────────────────────────────

def test_max_dependents_exceeded(client):
    """8 immediate family entries must be rejected with 422."""
    data = make_valid_form_data()
    data["fam_relation"] = ["Spouse"] + ["Child"] * 7
    data["fam_fname"] = ["Jane"] + ["Child%d" % i for i in range(7)]
    data["fam_lname"] = ["Moyo"] * 8
    data["fam_dob"] = ["2000-01-01"] * 8
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 422
    assert "dependents" in resp.json()["detail"].lower()


def test_max_dependents_within_limit(client):
    """Exactly 7 immediate family entries must be accepted."""
    data = make_valid_form_data()
    data["fam_relation"] = ["Spouse"] + ["Child"] * 6
    data["fam_fname"] = ["Jane"] + ["Child%d" % i for i in range(6)]
    data["fam_lname"] = ["Moyo"] * 7
    data["fam_dob"] = ["2000-01-01"] + ["2010-01-01"] * 6
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200


# ── SPRINT 4: BANKING BANNER IN HTML ─────────────────────────────────────────

def test_banking_banner_in_html(client):
    """GET / must render the Easipol banking info banner element."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "easipolBankingBanner" in resp.text


# ── SPRINT 5: ZIMBABWE NATIONAL ID VALIDATION ────────────────────────────────

def test_zim_national_id_valid_male():
    """63-123456A78: position 8 digit = '6' (≥5) → Male → valid format."""
    assert validate_zim_national_id("63-123456A78") is True


def test_zim_national_id_valid_female():
    """08-300874Y46: position 8 digit = '4' (<5) → Female → valid format."""
    assert validate_zim_national_id("08-300874Y46") is True


def test_zim_national_id_wrong_format():
    """No hyphen separator → does not match format."""
    assert validate_zim_national_id("63123456A78") is False


def test_zim_national_id_wrong_check_letter_position():
    """Letter after 5 digits instead of 6 → wrong position → invalid."""
    assert validate_zim_national_id("63-12345A678") is False


# ── SPRINT 5: BENEFICIARY DEFERRAL ───────────────────────────────────────────

def test_submit_no_beneficiary_bene_deferred(client):
    """Submission with all beneficiary fields empty returns 200 and X-Bene-Deferred: true."""
    data = make_valid_form_data()
    data["ben_fname"] = ""
    data["ben_lname"] = ""
    data["ben_rel"] = ""
    data["ben_phone"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200
    assert resp.headers.get("x-bene-deferred") == "true"


def test_submit_with_beneficiary_bene_not_deferred(client):
    """Submission with beneficiary fully filled returns 200 and X-Bene-Deferred: false."""
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-bene-deferred") == "false"


# ── SPRINT 6: POPIA CONSENT ENFORCEMENT ──────────────────────────────────────

def test_popia_consent_missing_returns_422(client):
    """Omitting popia_consent must return 422."""
    data = make_valid_form_data()
    data["popia_consent"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 422
    assert "popia" in resp.json()["detail"].lower()


def test_popia_consent_false_returns_422(client):
    """popia_consent='false' must return 422."""
    data = make_valid_form_data()
    data["popia_consent"] = "false"
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 422
    assert "popia" in resp.json()["detail"].lower()


def test_popia_consent_true_returns_200(client):
    """popia_consent='true' must return 200."""
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200


# ── SPRINT 6: EASIPOL RESILIENCE ─────────────────────────────────────────────

def test_easipol_live_true_fallback_never_501(client, monkeypatch):
    """EASIPOL_LIVE=True in PARKED state must never return 501 — always 200 with PENDING billing."""
    monkeypatch.setattr(main, "EASIPOL_LIVE", True)
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-easipol-billing-reference") == "PENDING"


def test_easipol_live_false_always_demo_ref(client):
    """EASIPOL_LIVE=False must always return DEMO-PREVIEW-MODE regardless of other config."""
    resp = client.post("/submit-global-policy", data=make_valid_form_data())
    assert resp.status_code == 200
    assert resp.headers.get("x-easipol-policy-number") == "DEMO-PREVIEW-MODE"


# ── SPRINT 7C: PDF CONTENT + EMAIL + MODAL ───────────────────────────────────

def _make_pdf_data() -> dict:
    """Minimal pdf_data dict for direct pdf_builder tests."""
    return {
        "title": "Mr", "fname": "Tendai", "lname": "Moyo",
        "id_doc_type": "Passport", "identity_value": "A12345678",
        "dob": "1985-06-15", "gender": "Male", "marital_status": "Single",
        "phone": "0811234567", "email": "tendai@test.co.za",
        "address": "12 Main St, JHB", "plan_name": "LOCAL_F|169",
        "local_total": "R 169.00", "product_type": "standard",
        "form_context": "local", "policy_number": "DEMO-PREVIEW-MODE",
        "sadac_country_selection": "", "country_of_origin": "",
        "country_of_residence": "", "pay_method": "PayAt",
        "fam_fname": [], "fam_lname": [], "fam_relation": [], "fam_dob": [],
        "ext_fam_fname": [], "ext_fam_lname": [], "ext_fam_relation": [],
        "ext_fam_dob": [], "ext_fam_cover": [],
        "ben_fname": "", "ben_lname": "", "ben_rel": "", "ben_phone": "",
        "bene_deferred": True, "no_client_email": True,
        "bank_name": "", "account_name": "", "account_num": "",
        "branch_code": "", "account_type": "", "acc_holder_phone": "",
        "commencement_date": "", "deduction_date": "",
        "optin_phone": False, "optin_sms": False, "optin_email": False,
        "optin_whatsapp": False, "terms_acceptance": True,
        "needs_analysis_waiver": True, "intermediary_appointment": True,
        "legal_name_confirm": "Tendai Moyo",
    }


def _pdf_text(d: dict) -> str:
    p = os.path.join(tempfile.mkdtemp(), "test.pdf")
    pdf_builder.build_policy_pdf(p, d, compress=False)
    return open(p, "rb").read().decode("latin-1", errors="ignore")


def test_pdf_contains_claim_documents():
    """PDF page 3 must contain 'Claim Documents' section."""
    assert "Claim Documents" in _pdf_text(_make_pdf_data())


def test_pdf_contains_customer_care_email():
    """PDF page 3 footer must contain customer-care email."""
    assert "customer-care@zororo" in _pdf_text(_make_pdf_data())


def test_submit_no_email_returns_200(client):
    """Submission with empty email must return 200 (uses DUMMY_EMAIL)."""
    data = make_valid_form_data()
    data["email"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200


def test_send_policy_email_no_smtp_user_no_raise(monkeypatch):
    """send_policy_email must return silently when SMTP_USER is empty."""
    monkeypatch.setattr(main, "SMTP_USER", "")
    main.send_policy_email(
        "test@test.com", b"fake_pdf_bytes", "TEST-REF-123", "Test User"
    )


def test_pre_execute_modal_in_html(client):
    """GET / must render the pre-execute confirmation modal element."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "preExecuteModal" in resp.text


# ── SPRINT 8: CLIENT IP AUDIT + SADAC DUPLICATE ALLOW ────────────────────────

def test_submit_captures_forwarded_ip(client, monkeypatch):
    """X-Forwarded-For first entry must flow into pdf_data['submission_ip']."""
    captured = {}
    orig = main.pdf_builder.build_policy_pdf

    def spy(path, data, *a, **k):
        captured["ip"] = data.get("submission_ip")
        return orig(path, data, *a, **k)

    monkeypatch.setattr(main.pdf_builder, "build_policy_pdf", spy)
    resp = client.post(
        "/submit-global-policy",
        data=make_valid_form_data(),
        headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
    )
    assert resp.status_code == 200
    assert captured["ip"] == "203.0.113.7"


def test_missing_branch_office_returns_422(client):
    """Empty branch_office must return 422 with the branch prompt."""
    data = make_valid_form_data()
    data["branch_office"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 422
    assert "branch office" in resp.json()["detail"].lower()


def test_submit_branch_and_manager_flow_to_pdf(client, monkeypatch):
    """branch_office + manager_name must reach pdf_data on a 200 submission."""
    captured = {}
    orig = main.pdf_builder.build_policy_pdf

    def spy(path, data, *a, **k):
        captured.update(data)
        return orig(path, data, *a, **k)

    monkeypatch.setattr(main.pdf_builder, "build_policy_pdf", spy)
    data = make_valid_form_data()
    data["branch_office"] = "Polokwane"
    data["manager_name"] = "Grace Dube"
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200
    assert captured["branch_office"] == "Polokwane"
    assert captured["manager_name"] == "Grace Dube"


def test_sadac_allows_repeated_phone(client):
    """SADAC context must accept the same phone number on multiple policies."""
    data = make_valid_form_data()
    data["form_context"] = "sadc"
    data["sadac_country_selection"] = "Zimbabwe"
    data["country_of_origin"] = "Zimbabwe"
    data["id_doc_type"] = "Passport"
    data["identity_value"] = "AB123456"
    first = client.post("/submit-global-policy", data=data)
    assert first.status_code == 200
    second = client.post("/submit-global-policy", data=dict(data))
    assert second.status_code == 200


# ── SPRINT 10: DEPENDENT DATA FLOW ───────────────────────────────────────────

def test_pdf_shows_spouse_dependent():
    """Spouse in fam arrays must appear in PDF Immediate Dependents table."""
    d = _make_pdf_data()
    d["fam_relation"] = ["Spouse"]
    d["fam_fname"] = ["Grace"]
    d["fam_lname"] = ["Moyo"]
    d["fam_dob"] = ["1987-03-15"]
    text = _pdf_text(d)
    assert "Spouse" in text
    assert "Grace" in text


def test_pdf_shows_child_dependent():
    """Child in fam arrays must appear in PDF Immediate Dependents table."""
    d = _make_pdf_data()
    d["fam_relation"] = ["Child"]
    d["fam_fname"] = ["Blessing"]
    d["fam_lname"] = ["Moyo"]
    d["fam_dob"] = ["2015-06-10"]
    text = _pdf_text(d)
    assert "Child" in text
    assert "Blessing" in text


def test_pdf_shows_extended_family():
    """Parent in ext_fam arrays must appear in PDF Extended Family table."""
    d = _make_pdf_data()
    d["ext_fam_relation"] = ["Parent"]
    d["ext_fam_fname"] = ["Abel"]
    d["ext_fam_lname"] = ["Ncube"]
    d["ext_fam_dob"] = ["1955-01-01"]
    d["ext_fam_cover"] = ["60"]
    text = _pdf_text(d)
    assert "Abel" in text


def test_pdf_none_declared_when_no_dependents():
    """PDF must show 'None declared' when immediate family arrays are empty."""
    text = _pdf_text(_make_pdf_data())
    assert "None declared" in text


# ── SPRINT 9: PLAN DISPLAY NAME + ADDRESS BLOCK ──────────────────────────────

def test_plan_display_name_wwfp_executive():
    """plan_display_name for WWFP_EXECUTIVE_F must return a clean label."""
    result = pdf_builder.plan_display_name("WWFP_EXECUTIVE_F")
    assert "WWFP_" not in result
    assert "_" not in result
    assert result


# ── SPRINT 8 PART 5A: ADDRESS BLOCK + NATIONALITY ────────────────────────────

def test_missing_street_address_returns_422(client):
    """Empty street_address must return 422 with 'Street address is required.'"""
    data = make_valid_form_data()
    data["street_address"] = ""
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 422
    assert "street address" in resp.json()["detail"].lower()


def test_submit_full_address_block_captured(client, monkeypatch):
    """Full address block fields must reach pdf_data on a 200 submission."""
    captured = {}
    orig = main.pdf_builder.build_policy_pdf

    def spy(path, data, *a, **k):
        captured.update(data)
        return orig(path, data, *a, **k)

    monkeypatch.setattr(main.pdf_builder, "build_policy_pdf", spy)
    data = make_valid_form_data()
    data["street_address"] = "45 Hope Street"
    data["area_suburb"] = "Hillbrow"
    data["postal_code"] = "2001"
    data["nationality"] = "Zimbabwe"
    data["alt_phone"] = "0791234567"
    data["whatsapp"] = "0811234567"
    resp = client.post("/submit-global-policy", data=data)
    assert resp.status_code == 200
    assert captured["street_address"] == "45 Hope Street"
    assert captured["area_suburb"] == "Hillbrow"
    assert captured["postal_code"] == "2001"
    assert captured["nationality"] == "Zimbabwe"
    assert captured["alt_phone"] == "0791234567"
    assert captured["whatsapp"] == "0811234567"


# ── SPRINT 12: EASIPOL CAPTURE PERSISTENCE ───────────────────────────────────

def test_easipol_capture_appends_one_record(tmp_path, monkeypatch):
    """PARKED state: live submit must append exactly one capture record (with PENDING refs)."""
    captures_file = str(tmp_path / "easipol_captures.json")
    reg_file = str(tmp_path / "registry.json")
    pdf_dir = str(tmp_path / "pdfs")
    os.makedirs(pdf_dir, exist_ok=True)
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump([], f)

    monkeypatch.setattr(main, "REGISTRY_FILE", reg_file)
    monkeypatch.setattr(main, "PDF_DIR", pdf_dir)
    monkeypatch.setattr(main, "CAPTURES_FILE", captures_file)
    monkeypatch.setattr(main, "EASIPOL_LIVE", True)

    with TestClient(main.app) as c:
        resp = c.post("/submit-global-policy", data=make_valid_form_data())

    assert resp.status_code == 200
    with open(captures_file, "r", encoding="utf-8") as f:
        records = json.load(f)
    assert len(records) == 1
    # PARKED: NotImplementedError caught non-blocking; refs are PENDING until gates clear
    assert records[0]["policy_number"] == "PENDING"
    assert records[0]["billing_reference"] == "PENDING"
    assert records[0]["source_form"] == "zororo-local-form-"
    assert records[0]["live"] is True
