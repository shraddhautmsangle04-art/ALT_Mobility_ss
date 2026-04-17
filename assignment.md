# Assignment

Extract the data and create a structured dashboard in tabular format. The dashboard should capture the following details:

- **Vehicle Chassis Number**
- **Insurance Details (Own Damage)** – including coverage specifics such as:
  - Fire coverage (Yes/No)
  - Chassis damage coverage and applicable causes
- **Insurance Company Name** (with which the vehicle is registered)

## Additional Requirements

- Create an automated tracker/trigger to identify policies that are nearing expiry (based on defined timelines)
- Ensure the dashboard is clean, accurate, and easy to analyse

## Columns to Extract

| Column | Description |
|---|---|
| `vehicle_chassis_number` | Extract the unique identifier for the vehicle (Chassis No). |
| `insurance_company_name` | Extract the name of the insurance company. |
| `policy_number` | Extract the insurance policy number. |
| `od_start_date` | Extract the Own Damage (OD) policy start date. |
| `od_end_date` | Extract the Own Damage (OD) policy expiry date (used for tracking). |
| `fire_covered` | Identify whether fire coverage is included (Yes/No). |
| `damage_coverage` | Extract and summarize covered risks (e.g., accident, flood, theft). |
| `premium_amount` | Extract the total premium amount for the policy. |
| `days_left` | Calculate remaining days until expiry (OD End Date – Today). |
| `status` | Classify policy as Active / Expiring Soon / Expired based on expiry date. |
| `policy_duration` | Calculate policy duration in years (1, 2, or 3 years). |
| `policy_type` | Classify as Annual (1 year) or Multi-Year (2+ years). |

## Timeline

- **Deadline:** Sunday, 19 April 2026
- **Discussion:** Monday at 12:30 PM to review the submitted assignment
