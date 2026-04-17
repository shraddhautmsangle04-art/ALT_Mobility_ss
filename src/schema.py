from typing import Optional
from pydantic import BaseModel, Field


class ExtractedPolicy(BaseModel):
    """Fields pulled directly out of the PDF by the LLM."""

    vehicle_chassis_number: Optional[str] = Field(
        description=(
            "Vehicle chassis / frame / VIN number — usually 17 alphanumeric characters. "
            "Labelled 'Chassis No', 'Chassis Number', 'Chassis / Frame No', 'VIN', or "
            "'Chassis/VIN'. Do NOT return the engine number or registration number."
        )
    )
    insurance_company_name: Optional[str] = Field(
        description=(
            "Name of the insurance company issuing the policy (e.g. ICICI Lombard General Insurance, "
            "HDFC ERGO General Insurance, Bajaj Allianz, Tata AIG, Reliance General, "
            "The New India Assurance, Future Generali, Go Digit, SBI General). "
            "Usually in the header / logo area or on the Certificate of Insurance."
        )
    )
    policy_number: Optional[str] = Field(
        description=(
            "Policy number or Certificate of Insurance number. Labelled 'Policy No.', "
            "'Policy Number', 'Certificate No.'. Do NOT return the proposal number, "
            "receipt number, or client code."
        )
    )
    od_start_date: Optional[str] = Field(
        description=(
            "Own Damage (Section I / OD) policy start date in ISO YYYY-MM-DD. "
            "Typically under 'Period of Insurance — From' for Own Damage. "
            "If only a combined OD+TP date is given, use that. Ignore the proposal / issue date."
        )
    )
    od_end_date: Optional[str] = Field(
        description=(
            "Own Damage (Section I / OD) expiry date in ISO YYYY-MM-DD. "
            "Typically under 'Period of Insurance — To' for Own Damage. Used for renewal tracking."
        )
    )
    fire_covered: Optional[str] = Field(
        description=(
            "Return 'Yes' if fire / explosion / self-ignition / lightning is a covered peril "
            "under Own Damage (it nearly always is on a Package/Comprehensive policy). "
            "Return 'No' only if the document is a Third-Party-only / Act-only policy, "
            "or fire is explicitly listed as excluded."
        )
    )
    damage_coverage: Optional[str] = Field(
        description=(
            "Short comma-separated list of perils covered under Own Damage. Choose from: "
            "accident, fire, explosion, self-ignition, lightning, theft, burglary, "
            "flood/inundation, cyclone/storm, earthquake, landslide, riot/strike, "
            "terrorism, malicious act, transit (rail/road/air/water). "
            "If the policy is Third-Party-only, return 'third-party only'."
        )
    )
    premium_amount: Optional[float] = Field(
        description=(
            "Final total premium payable including GST, in INR, as a plain number "
            "(strip ₹ and commas). Labelled 'Total Premium', 'Grand Total', "
            "'Final Premium', or 'Amount Payable'. Do NOT return Net OD Premium alone "
            "if a final-total row exists."
        )
    )


FINAL_COLUMNS = [
    "vehicle_chassis_number",
    "insurance_company_name",
    "policy_number",
    "od_start_date",
    "od_end_date",
    "fire_covered",
    "damage_coverage",
    "premium_amount",
    "days_left",
    "status",
    "policy_duration",
    "policy_type",
]

CORE_FIELDS = [
    "vehicle_chassis_number",
    "insurance_company_name",
    "policy_number",
    "od_end_date",
]
