import re
from datetime import date, datetime
from typing import Dict, List, Optional


def validate_required_fields(**kwargs: str) -> List[str]:
    """Return list of required field names that are empty or whitespace-only."""
    required = [
        'fname', 'lname', 'phone', 'email', 'address', 'dob',
        'gender', 'marital_status', 'ben_fname', 'ben_lname',
        'ben_rel', 'ben_phone',
    ]
    return [f for f in required if not kwargs.get(f, '').strip()]


def canonicalize_sa_phone(phone: str) -> str:
    """
    Fold an SA phone number to a single canonical form ('0XXXXXXXXX').
    Strips spaces/dashes and rewrites leading '+27'/'27' to '0'.
    Used so the duplicate guard cannot be bypassed by reformatting the
    same number (C6 — phone deduplication).
    """
    clean = phone.strip().replace(' ', '').replace('-', '')
    if clean.startswith('+27'):
        clean = '0' + clean[3:]
    elif clean.startswith('27') and len(clean) == 11:
        clean = '0' + clean[2:]
    return clean


def validate_phone(phone: str) -> Optional[str]:
    """Return error string if phone is not a valid SA number, else None."""
    clean = phone.strip().replace(' ', '').replace('-', '')
    if (re.match(r'^0\d{9}$', clean)
            or re.match(r'^\+27\d{9}$', clean)
            or re.match(r'^27\d{9}$', clean)):
        return None
    return (
        f"Phone number '{phone}' is not a valid South African number. "
        "Use 10 digits starting with 0, or +27 format."
    )


def _luhn_valid(id_number: str) -> bool:
    """Return True if id_number passes the Luhn checksum."""
    digits = [int(c) for c in id_number]
    total = 0
    for i, d in enumerate(reversed(digits[:-1])):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10 == digits[-1]


def validate_sa_id(
    id_number: str,
    dob: str,
    gender: str,
) -> Optional[str]:
    """
    Validate SA ID: 13-digit format, Luhn checksum, DOB match, gender match.
    Returns error string on failure, None on success.
    """
    id_clean = id_number.strip()

    if len(id_clean) != 13 or not id_clean.isdigit():
        return "SA ID number must be exactly 13 digits."

    if not _luhn_valid(id_clean):
        return "SA ID number failed checksum validation. Please check the number."

    yy = int(id_clean[0:2])
    mm = int(id_clean[2:4])
    dd = int(id_clean[4:6])

    current_year_2digit = date.today().year % 100
    year = 2000 + yy if yy <= current_year_2digit else 1900 + yy

    try:
        id_dob = date(year, mm, dd)
    except ValueError:
        return f"SA ID number contains an invalid date of birth: {id_clean[0:6]}."

    try:
        submitted_dob = datetime.strptime(dob.strip(), '%Y-%m-%d').date()
    except ValueError:
        return f"Date of birth '{dob}' must be in YYYY-MM-DD format."

    if id_dob != submitted_dob:
        return (
            f"Date of birth in SA ID ({id_dob.strftime('%Y-%m-%d')}) "
            f"does not match submitted date of birth ({submitted_dob})."
        )

    gender_seq = int(id_clean[6:10])
    id_gender = 'male' if gender_seq >= 5000 else 'female'
    submitted_gender = gender.strip().lower()

    if submitted_gender not in ('male', 'female'):
        return (
            f"Gender value '{gender}' is not recognised. "
            "Expected 'Male' or 'Female'."
        )

    if id_gender != submitted_gender:
        return (
            f"Gender in SA ID ({id_gender.title()}) "
            f"does not match submitted gender ({gender.strip().title()})."
        )

    return None


def validate_context_fields(
    form_context: str,
    sadac_country_selection: str,
    country_of_origin: str,
    country_of_residence: str,
) -> Optional[str]:
    """
    Enforce context-specific required fields using the explicit form context.
    form_context must be 'local', 'sadc', or 'wwfp'.
    Returns error string on failure, None on success.
    """
    ctx = form_context.strip().lower()
    if ctx == "sadc":
        if not sadac_country_selection.strip():
            return "SADC context: sadac_country_selection is required."
        if not country_of_origin.strip():
            return (
                "SADC context: country_of_origin is required when "
                "sadac_country_selection is provided."
            )
    elif ctx == "wwfp":
        if not country_of_residence.strip():
            return (
                "Worldwide Funeral Plan context: country_of_residence is required."
            )
    return None


def check_stillborn_flag(
    fam_relation: List[str],
    fam_dob: List[str],
) -> bool:
    """
    Return True if any child dependent's DOB is within 25 weeks of today.
    Signals a potential stillborn/early-birth case for manual underwriting
    review (BR-DEC-02).
    """
    today = date.today()
    for i, relation in enumerate(fam_relation):
        if 'child' not in relation.strip().lower():
            continue
        if i >= len(fam_dob) or not fam_dob[i].strip():
            continue
        try:
            child_dob = datetime.strptime(fam_dob[i].strip(), '%Y-%m-%d').date()
        except ValueError:
            continue
        weeks_ago = (today - child_dob).days / 7
        if 0 <= weeks_ago < 25:
            return True
    return False


def collect_validation_errors(
    form_context: str,
    id_doc_type: str,
    identity_value: str,
    dob: str,
    gender: str,
    phone: str,
    sadac_country_selection: str,
    country_of_origin: str,
    country_of_residence: str,
    field_kwargs: Dict[str, str],
) -> List[str]:
    """
    Run all validation checks and return a list of error messages.
    Empty list means all checks passed.
    """
    errors: List[str] = []

    missing = validate_required_fields(**field_kwargs)
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}.")

    phone_err = validate_phone(phone)
    if phone_err:
        errors.append(phone_err)

    if id_doc_type.strip() == "ID Number":
        id_err = validate_sa_id(identity_value, dob, gender)
        if id_err:
            errors.append(id_err)

    ctx_err = validate_context_fields(
        form_context, sadac_country_selection,
        country_of_origin, country_of_residence,
    )
    if ctx_err:
        errors.append(ctx_err)

    return errors
