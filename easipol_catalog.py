"""
Easipol product catalog — FranchiseID 457.

Sourced 2026-06-11 from manager's live bundle at application.zororophumulani.co.za.
Bypasses GetAllActiveProducts (returns [] for our credentials — that endpoint is not
used by the production form; all ProductIDs are static).
"""
from typing import Optional


FRANCHISE_ID: int = 457
BRANCH_ID: int = 0
UNDERWRITER_ID: int = 74
FORM_ID: int = 21
FORM_NAME: str = "zorphonline"
SUBGROUP_CASH: int = 370    # Pay@ / EasyPay
SUBGROUP_DEBIT: int = 371   # Debit Order

# plan_name field value format: "<KEY>|<premium>", e.g. "LOCAL_F_R10000|169"
PRODUCT_ID_MAP: dict = {
    # Local plans
    "LOCAL_F_R5000":    6412,
    "LOCAL_F_R10000":   6401,
    "LOCAL_F_R15000":   6413,
    "LOCAL_F_R18000":   6414,
    "LOCAL_F_R25000":   6415,
    "LOCAL_F_R30000":   6416,
    "LOCAL_S_R5000":    6418,
    "LOCAL_S_R10000":   6419,
    "LOCAL_S_R15000":   6420,
    "LOCAL_S_R18000":   6421,
    "LOCAL_S_R25000":   6422,
    "LOCAL_S_R30000":   6423,
    # SADC plans
    "SADC_F_R10000":    130046,
    "SADC_F_R15000":    130048,
    "SADC_F_R18000":    130050,
    "SADC_F_R25000":    130052,
    "SADC_F_R30000":    130053,
    "SADC_S_R10000":    130054,
    "SADC_S_R15000":    130055,
    "SADC_S_R18000":    130056,
    "SADC_S_R25000":    130057,
    "SADC_S_R30000":    130058,
    # WWFP / Diaspora plans
    "WWFP_PREMIUM_F":   174156,
    "WWFP_PREMIUM_S":   174162,
    "WWFP_PRESTIGE_F":  174163,
    "WWFP_PRESTIGE_S":  174164,
    "WWFP_EXECUTIVE_F": 174165,
    "WWFP_EXECUTIVE_S": 174166,
    # NOTE: LOCAL_F_R2000 and LOCAL_S_R2000 absent from manager's live bundle.
    # TODO: confirm ProductIDs with RubiBlue before adding.
}


def get_product_id(plan_name: str) -> Optional[int]:
    """Extract ProductID from plan_name like 'LOCAL_F_R10000|169'. None if unmapped."""
    key = plan_name.split("|")[0].strip() if plan_name else ""
    return PRODUCT_ID_MAP.get(key)


def get_subgroup_id(pay_method: str) -> int:
    """Map form pay_method to Easipol SubGroupID. Default: SUBGROUP_DEBIT."""
    pm = (pay_method or "").strip().lower()
    if any(x in pm for x in ("pay@", "payat", "easypay", "cash")):
        return SUBGROUP_CASH
    return SUBGROUP_DEBIT
