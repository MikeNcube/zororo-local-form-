# Zororo-Local-Foam — System Specification

**Status:** Living document · **Owner:** Mike Ncube (AI Engineer & Systems Architect)
**Organisation:** Zororo-Phumulani Funeral Assurance · **FSP:** 48558
**Last updated:** 2026-05-31 · **Spec version:** 1.0

> This is the authoritative contract for what this application is and must do.
> Code does not define this spec — this spec defines the code.
> All sessions reference this document. Update spec before changing code.

---

## 1. System Purpose

A multi-context digital policy onboarding form for Zororo-Phumulani Funeral Assurance (FSP 48558).
It captures prospective policyholder applications across three geographic tiers and generates a
PDF preview booklet. Submitted data is destined for integration with Easipol and Rubilink systems.

Three form contexts served from one codebase via URL routing:
- `/`      — Local South Africa (ZAR, Passport or ID, Pay@ or Debit Order)
- `/sadac` — SADC Regional (cross-border, SADC country selection, ZAR premiums)
- `/wwfp`  — Worldwide Funeral Plan / Diaspora (international, currency conversion display)

Current deployment: Railway (FastAPI + Uvicorn). Stack: Python, FastAPI, ReportLab, flat-file
JSON registry. **No database in MVP** — `submitted_policies.json` guards against duplicate phone
submissions only. Easipol/Rubilink are the systems of record.

---

## 2. Architecture & Stack

### NFR-DEC — CONFIRMED (2026-05-31)

The MVP stack is:
- **Runtime:** Python 3.x + FastAPI + Uvicorn
- **PDF generation:** ReportLab
- **Duplicate guard:** `submitted_policies.json` (flat file, phone number deduplication)
- **Deployment:** Railway (single container, no separate DB service)
- **Templates:** `templates/index.html` (server-rendered via string replacement)
- **Static assets:** `/static/` directory (logo, etc.)

Supabase (Postgres) and Prisma are **NOT part of this project**.
Those belong to `zororo-claims` (Next.js/TypeScript monorepo).
This project remains standalone FastAPI on Railway for the MVP.
Migration to Postgres/Supabase is a post-MVP decision, not a blocker.

---

## 3. Open Decisions — RESOLVED

### BR-DEC-01 — Arrears Tolerance
**Question:** How many missed payments before a policy is considered in arrears / lapsed?
**Resolution:** OUT OF SCOPE for the onboarding form layer.
This is an Easipol/backend policy management concern, not a form concern.
The form collects debit order mandate details and payment method only.
No tolerance — claims blocked immediately on arrears.
**Status:** CLOSED — deferred to Easipol integration layer.
**Status:** CLOSED — deferred to Easipol integration layer.

### BR-DEC-02 — Stillborn Gestation
**Question:** Should the form validate or flag child DOB entries that suggest stillbirth?
**Resolution:** The form captures child DOB and relationship correctly.
Gestation/stillborn validation is a medical underwriting concern, not a form UX concern.
Backend guardrail: if a Child dependent DOB is within 25 weeks of submission date,
flag the submission for manual underwriting review (do not auto-reject).
This flag is added to the PDF output as a REVIEW REQUIRED marker.
Implementation: backend only (`main.py`), no frontend change.
**Status:** CLOSED — backend guardrail, deferred to next backend sprint.

### BR-DEC-03 — Nhaka/Ilifa Scope
**Question:** Does the Nhaka (Shona) / Ilifa (Zulu) cash payout apply to this form?
**Resolution:** OUT OF SCOPE for the digi-app-form policy onboarding layer.
Nhaka/Chema/Ilifa cash payout confirmation is an operational/repatriation concern
handled in `zororo-services-local` (the internal case wizard, not this public form).
This form captures the beneficiary and cover selection; payout execution is downstream.
No field addition required.
**Status:** CLOSED — belongs to zororo-services-local, not this project.

### BR-DEC-04 — Lapse Threshold
**Question:** After how many missed payments is a policy lapsed, and does the form need to communicate this?
**Resolution:** Month-to-month, lapse on first missed payment.
The Terms & Conditions text on Step 3 already states that missed payments may lead to lapse.
No additional form field required.
Enforcement lives in Easipol. The T&C disclosure is sufficient for FSCA compliance at the form layer.
**Status:** CLOSED — enforced downstream in Easipol; T&C disclosure already present.

---

## 4. Form Contexts & Routing

| Route   | Label                         | ID Accepted         | Premium Currency | Special Fields                        |
|---------|-------------------------------|---------------------|------------------|---------------------------------------|
| `/`     | Local South Africa            | Passport or ID   | ZAR              | None                                  |
| `/sadac`| SADC Regional                 | Passport            | ZAR              | SADC Country, Country of Origin       |
| `/wwfp` | Worldwide Funeral Plan        | Passport            | ZAR + conversion | Country of Residence, exchange rate   |

---

## 5. Cover / Premium Matrix

### Local (ZAR)
Family: R2k/R89 · R5k/R129 · R10k/R169 · R15k/R209 · R18k/R229 · R25k/R279 · R30k/R299
Single: R2k/R79 · R5k/R119 · R10k/R159 · R15k/R199 · R18k/R209 · R25k/R259 · R30k/R289

### SADC (ZAR)
Family: R10k/R169 · R15k/R209 · R18k/R229 · R25k/R279 · R30k/R299
Single: R10k/R159 · R15k/R199 · R18k/R209 · R25k/R259 · R30k/R289

### WWFP (ZAR, displayed with local currency conversion)
Family: Premium R45k/R540 · Prestige R75k/R720 · Executive R90k/R1080
Single: Premium R45k/R450 · Prestige R75k/R630 · Executive R90k/R990

Extended family add-on: R2k(R60) · R3k(R80) · R4k(R110) · R5k(R220)

---

## 6. Waiting Periods (per T&C)

- Immediate family (spouse, children): 3 calendar months — natural causes
- Extended family: 6 calendar months — natural causes
- Accidental death: no waiting period (all tiers)

---

## 7. Form Steps

Step 1 — Proposer Details: title, names, ID type/number, DOB, gender, marital status,
          country of residence (WWFP only), SADC country fields (SADC only),
          phone, address, email.

Step 2 — Dependents & Cover: product type, plan type (family/single), cover selection,
          immediate family (max 1 spouse / max 6 children, conditional on marital status),
          extended family (parents/grandparents/aunts/uncles, per-member cover selection),
          beneficiary (name, surname, relationship, contact).

Step 3 — Premium & Payment: payment method (Pay@ or Debit Order), debit mandate fields
          (conditional), communication opt-ins, T&C/needs analysis waiver/intermediary
          appointment checkboxes, premium display (ZAR + converted currency for WWFP).

Step 4 — Documents & Signature: ID document scan, TFS scan booklet, digital signature
          (legal name confirmation).

Success — PDF preview booklet download (DEMO-PREVIEW-MODE, not a live policy).

---

## 8. Compliance Rules (non-negotiable)

C1 — FSP disclosure: FSP 48558 must appear in header and footer on all form contexts.
C2 — Preview watermark: all generated PDFs must carry DEMO PREVIEW / NOT A LIVE CONTRACT notice.
C3 — Needs Analysis Waiver: required checkbox before submission (FSCA requirement).
C4 — Intermediary Appointment: required checkbox before submission.
C5 — T&C acceptance: required checkbox with link to /terms-and-conditions.
C6 — Duplicate guard: phone number deduplication via submitted_policies.json.
C7 — POPIA notice: data collection consent implied by T&C acceptance; no separate PII
     logging in URLs, error messages, or server logs.
C8 — Waiting period disclosure: must appear in scrollable terms block on Step 3.

---

## 9. Out of Scope (MVP)

- Live Easipol/Rubilink API integration (all submissions are DEMO-PREVIEW-MODE)
- Real payment processing or debit order submission to bank
- Nhaka/Ilifa/Chema payout execution (handled in zororo-services-local)
- Arrears enforcement (handled in Easipol)
- Supabase / Postgres / Prisma (belongs to zororo-claims)
- Admin dashboard or submission history UI
- WhatsApp/SMS notifications post-submission

---

## 10. Approval Gate — README Sign-Off

The following decisions are signed off and this spec is approved for implementation:

- [x] NFR-DEC: Stack confirmed — FastAPI + Railway + flat-file JSON (no Supabase/Prisma in scope)
- [x] BR-DEC-01: Arrears tolerance — deferred to Easipol, out of scope for form
- [x] BR-DEC-02: Stillborn gestation — backend guardrail only, deferred to next sprint
- [x] BR-DEC-03: Nhaka/Ilifa scope — out of scope, belongs to zororo-services-local
- [x] BR-DEC-04: Lapse threshold — 3 missed DOs, enforced in Easipol, T&C disclosure sufficient

**Signed off:** Mike Ncube · 2026-05-31 · Ready to run.

---

## 11. Change Log

| Version | Date       | Change                                                                  |
|---------|------------|-------------------------------------------------------------------------|
| 1.0     | 2026-05-31 | Initial spec. All BR-DEC and NFR-DEC decisions resolved.                |
| 1.1     | 2026-06-07 | Live integration proven — see §13.                                      |
| 1.2     | 2026-06-11 | Easipol CreatePolicy body complete, parked — see §14.                   |

---

## 13. Live Integration — PROVEN

2026-06-07: First successful live Easipol read confirmed. Auth=Basic (two-GUID). GetPolicy by
cellNumber returned HTTP 200 with real data. Confirmed live field shapes: MainMember at top level;
Policy_Number (underscore); PayAtNumber 20 digits; EasyPayNumber 12 digits; Inception_Date &
Date_Captured present. Contract fully confirmed — no guesses remain.



---

## 14. Easipol CreatePolicy — COMPLETE, PARKED (2026-06-11)

**Status:** Body assembly complete and inspectable. Transmission permanently blocked
until all three gates below are cleared. Set `EASIPOL_LIVE=true` only after all gates.

**What was built:**
- `easipol_catalog.py` — static ProductID map for FranchiseID 457 (26 plans confirmed
  from manager's live bundle; LOCAL R2000 plans absent from bundle, TODO confirm).
- `_build_create_policy_body()` in `main.py` — assembles the full Easipol CreatePolicy
  JSON body server-side from form submission data, matching the manager's live form shape.
- `_get_easipol_references_v2()` — builds + logs the body at DEBUG level on every
  submission (EASIPOL_LIVE=false), returns DEMO-PREVIEW-MODE placeholders. When
  EASIPOL_LIVE=true, raises NotImplementedError (caught non-blocking → returns PENDING).
- `agent_id` optional field added to the form and MainMember payload.

**Architecture confirmed (investigation 2026-06-11):**
The manager's form submits to a Next.js admin backend (`zororo-phumulani-applications-admin-
production.up.railway.app/api/submit`) which calls Easipol CreatePolicy server-side.
Our form mirrors this: FastAPI backend calls Easipol server-side once EASIPOL_LIVE=true.
No Easipol credentials or IDs appear in any client bundle.

**Three gates — must ALL clear before EASIPOL_LIVE=true:**

1. **Manager go-ahead** — confirm a second form calling CreatePolicy is acceptable
   (Easipol may enforce one form per franchise or require registration).
2. **Write-access confirmed** — proven that our Basic Auth credentials have CreatePolicy
   WRITE access. Only GetPolicy READ has been confirmed (2026-06-07).
3. **Credential rotation** — the Basic Auth credential currently in use was stored
   in EASIPOL_BASIC_AUTH env var; rotate / reissue before any live write call.

**Open questions for RubiBlue:**
- Do current credentials support CreatePolicy, or is a separate write-entitlement needed?
- Must CreatePolicy include `FormID: 21` / `FormName: "zorphonline"`, or are these the
  hosted-form config identifiers only?
- Is `agent_id` the agent's Easipol login username or a separate numeric agent code?
- What ProductIDs cover the LOCAL R2000 FAMILY and LOCAL R2000 SINGLE plans?

---

## 12. BR-DEC Decision Sheet — RESOLVED from published T&C (zororophumulani.co.za)

Source: https://zororophumulani.co.za/terms-and-conditions.php (fetched 2026-05-31)
All four values resolved directly from the live published Terms and Conditions.
No further business owner sign-off required for form implementation — these are already public policy wording.
KGA Life confirmation still recommended before any backend enforcement changes.

| ID        | Rule                | Published T&C value                                      | DECISION     | Source                  |
|-----------|---------------------|----------------------------------------------------------|--------------|-------------------------|
| BR-DEC-01 | Arrears tolerance   | "No claims honoured if premiums in arrears or short paid"| No tolerance — claims blocked immediately on arrears | T&C: Payment of Premiums §7 |
| BR-DEC-02 | Stillborn gestation | "Stillborn defined as death after 25 weeks of pregnancy" | **25 weeks** | T&C: Notes (bottom)     |
| BR-DEC-03 | Nhaka/Ilifa scope   | Listed as benefit on Local plans page; not on SADC/WWFP  | **Local only** | Plans page + homepage   |
| BR-DEC-04 | Lapse threshold     | "Policy will lapse if obligations are not met" (no grace period stated) | Month-to-month, lapse on first missed payment | T&C: Termination §2 + Payment §3 |

**BUILD GATE: OPEN — values sourced from authoritative published T&C.**
Note: The form T&C text on Step 3 must be updated to match these values exactly.

Source: Cross-functional audit of Local / SADC / Worldwide forms (2026-05-31)
Proposed values supplied by Claude (AI recommendation only — not authoritative).
Authority: Business owner + KGA Life underwriter sign-off required on each row.
Moonstone (compliance) to review BR-DEC-01 and BR-DEC-04 interaction before lock.

### Interaction note (read before signing)
BR-DEC-01 and BR-DEC-04 must be internally consistent.
Recommended pairing: 60-day arrears tolerance + 3-month lapse window.
Do NOT mix 45-day arrears with 3-month lapse — these contradict at claim stage.

| ID        | Rule                 | Local    | SADC        | Worldwide | PROPOSED       | Reasoning                                                                 | DECISION | Approved by | Date |
|-----------|----------------------|----------|-------------|-----------|----------------|---------------------------------------------------------------------------|----------|-------------|------|
| BR-DEC-01 | Arrears tolerance    | 45 days  | not stated  | 60 days   | **60 days**    | Customer-favourable; reduces disputed rejections; pairs with 3-month lapse; confirm KGA Life allows it | | | |
| BR-DEC-02 | Stillborn gestation  | 25 weeks | 26 weeks    | 28 weeks  | **26 weeks**   | Matches Worldwide T&C; consistent with SA viability threshold; 25w and 28w look like drafting drift; underwriter must sign this one | | | |
| BR-DEC-03 | Nhaka/Ilifa scope    | Local    | SADC+Local  | All lanes | **Local+SADC** | Appears explicitly only in Local/SADC forms; safe default is to scope there unless business extends to Worldwide; product/cost decision not compliance | | | |
| BR-DEC-04 | Lapse threshold      | 2 months | not stated  | 3 months  | **3 months**   | More forgiving to families; reduces involuntary lapses; pairs with 60-day arrears tolerance | | | |

### Sign-off instructions
1. Review PROPOSED column and reasoning with KGA Life and Moonstone.
2. Enter the ratified value in the DECISION column (may differ from PROPOSED).
3. Enter approver name and date for each row.
4. Once all four DECISION cells are filled and signed, update SPEC.md Section 3.
5. Remove the GATE comment in 08-gemini-cli-handover.md to unblock the build.

**BUILD GATE: Gemini CLI prompt is blocked until all four DECISION cells are filled and signed.**


