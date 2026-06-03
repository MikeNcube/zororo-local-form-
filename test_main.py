import json
import os

import pytest
from fastapi.testclient import TestClient

import main
from datetime import date, timedelta

from validators import (
    canonicalize_sa_phone,
    check_stillborn_flag,
    collect_validation_errors,
    validate_context_fields,
    validate_phone,
    validate_required_fields,
    validate_sa_id,
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
        "ben_fname": "Rudo",
        "ben_lname": "Moyo",
        "ben_rel": "Spouse",
        "ben_phone": "0829876543",
        "terms_acceptance": "true",
        "needs_analysis_waiver": "true",
        "intermediary_appointment": "true",
        "form_context": "local",
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
