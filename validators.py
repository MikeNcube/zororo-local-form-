import re
from datetime import date, datetime
from typing import Dict, List, Optional

# Zimbabwe National ID district-to-province mapping (district code → province)
ZW_PROVINCE_CODES = {
    "01": "Harare Metropolitan", "02": "Harare Metropolitan",
    "03": "Harare Metropolitan", "04": "Harare Metropolitan",
    "05": "Harare Metropolitan", "06": "Harare Metropolitan",
    "07": "Harare Metropolitan", "08": "Harare Metropolitan",
    "09": "Harare Metropolitan", "10": "Mashonaland East",
    "11": "Mashonaland East",    "12": "Mashonaland Central",
    "13": "Mashonaland Central", "14": "Mashonaland West",
    "15": "Mashonaland West",    "16": "Matabeleland North",
    "17": "Matabeleland North",  "18": "Matabeleland South",
    "19": "Matabeleland South",  "20": "Midlands",
    "21": "Midlands",            "22": "Masvingo",
    "23": "Masvingo",            "24": "Manicaland",
    "25": "Manicaland",          "26": "Bulawayo Metropolitan",
    "27": "Bulawayo Metropolitan", "28": "Bulawayo Metropolitan",
    "29": "Matabeleland South",  "30": "Matabeleland South",
    "31": "Matabeleland North",  "32": "Midlands",
    "33": "Midlands",            "34": "Masvingo",
    "35": "Manicaland",          "36": "Manicaland",
    "37": "Mashonaland East",    "38": "Mashonaland Central",
    "39": "Mashonaland West",    "40": "Matabeleland North",
    "41": "Matabeleland South",  "42": "Midlands",
    "43": "Masvingo",            "44": "Manicaland",
    "45": "Mashonaland East",    "46": "Mashonaland Central",
    "47": "Mashonaland West",    "48": "Matabeleland North",
    "49": "Matabeleland South",  "50": "Midlands",
    "51": "Masvingo",            "52": "Manicaland",
    "53": "Mashonaland East",    "54": "Mashonaland Central",
    "55": "Mashonaland West",    "56": "Matabeleland North",
    "57": "Matabeleland South",  "58": "Midlands",
    "59": "Masvingo",            "60": "Manicaland",
    "61": "Mashonaland East",    "62": "Mashonaland Central",
    "63": "Matabeleland South",  "64": "Matabeleland South",
    "65": "Bulawayo Metropolitan", "66": "Bulawayo Metropolitan",
    "67": "Matabeleland North",  "68": "Midlands",
}

_ZIM_NID_RE = re.compile(r'^\d{2}-\d{6}[A-Z]\d{2}$')


def validate_zim_national_id(id_str: str) -> bool:
    """Return True if id_str matches Zimbabwe National ID format (DD-XXXXXXADD)."""
    return bool(_ZIM_NID_RE.match(id_str.strip().upper()))


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


def validate_branch_office(branch_office: str) -> Optional[str]:
    """Return error string if branch office is not selected, else None."""
    if not branch_office.strip():
        return "Please select a branch office."
    return None


def validate_street_address(street_address: str) -> Optional[str]:
    """Return error string if street_address is empty, else None."""
    if not street_address.strip():
        return "Street address is required."
    return None


def validate_phone(phone: str, form_context: str = "local") -> Optional[str]:
    """Return error string if phone is not valid for the given context, else None."""
    clean = phone.strip().replace(' ', '').replace('-', '')
    ctx = form_context.strip().lower()

    sa_ok = (
        re.match(r'^0\d{9}$', clean)
        or re.match(r'^\+27\d{9}$', clean)
        or re.match(r'^27\d{9}$', clean)
    )

    if ctx == 'local':
        if sa_ok:
            return None
        return (
            f"Phone number '{phone}' is not a valid South African number. "
            "Use 10 digits starting with 0, or +27 format."
        )

    if ctx == 'sadc':
        if sa_ok:
            return None
        if (re.match(r'^\+263\d{7,9}$', clean)
                or re.match(r'^00263\d{7,9}$', clean)):
            return None
        if re.match(r'^\+[1-9]\d{7,14}$', clean):
            return None
        return (
            f"Phone number '{phone}' is not a valid number. "
            "Use SA format (0XXXXXXXXX), Zimbabwe (+263XXXXXXXXX), "
            "or international E.164 (+[country code][number])."
        )

    if ctx == 'wwfp':
        if re.match(r'^\+[1-9]\d{7,14}$', clean):
            return None
        if sa_ok:
            return None
        return (
            f"Phone number '{phone}' is not valid. "
            "Use international format: +[country code][number], e.g. +447911123456."
        )

    if sa_ok:
        return None
    return (
        f"Phone number '{phone}' is not a valid South African number. "
        "Use 10 digits starting with 0, or +27 format."
    )


def validate_passport(identity_value: str, form_context: str = "local") -> Optional[str]:
    """Validate passport number format based on form context. Returns error string or None."""
    val = identity_value.strip().upper()
    ctx = form_context.strip().lower()

    sa_re = re.compile(r'^[A-Z]{1,2}\d{7,8}$')
    zw_re = re.compile(r'^[A-Z]{2}\d{6}$')
    intl_re = re.compile(r'^[A-Z]{1,2}\d{6,9}$')

    if ctx == 'local':
        if sa_re.match(val) or zw_re.match(val):
            return None
        return "Invalid passport format. SA: A12345678 \xb7 Zimbabwe: GN452257"

    if zw_re.match(val) or intl_re.match(val):
        return None
    return "Invalid passport format. Zimbabwe: GN452257"


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
    skip_beneficiary: bool = False,
) -> List[str]:
    """
    Run all validation checks and return a list of error messages.
    Empty list means all checks passed.
    skip_beneficiary=True omits ben_fname/ben_lname/ben_rel/ben_phone from required check.
    """
    errors: List[str] = []

    if skip_beneficiary:
        core_fields = [
            'fname', 'lname', 'phone', 'email', 'address',
            'dob', 'gender', 'marital_status',
        ]
        missing = [f for f in core_fields if not field_kwargs.get(f, '').strip()]
    else:
        missing = validate_required_fields(**field_kwargs)
    if missing:
        errors.append(f"Missing required fields: {', '.join(missing)}.")

    phone_err = validate_phone(phone, form_context)
    if phone_err:
        errors.append(phone_err)

    if id_doc_type.strip() == "ID Number":
        id_err = validate_sa_id(identity_value, dob, gender)
        if id_err:
            errors.append(id_err)
    elif id_doc_type.strip() == "Passport":
        pass_err = validate_passport(identity_value, form_context)
        if pass_err:
            errors.append(pass_err)

    ctx_err = validate_context_fields(
        form_context, sadac_country_selection,
        country_of_origin, country_of_residence,
    )
    if ctx_err:
        errors.append(ctx_err)

    return errors
