import fitz  # PyMuPDF
from openai import OpenAI
from pydantic import BaseModel, Field, create_model
from pydantic import BaseModel, Field, create_model
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text from a given PDF file using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return text

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts all text from a given PDF byte stream using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e:
        print(f"Error reading PDF stream: {e}")
    return text

def parse_insurance_data_with_ai(text: str, custom_fields: dict) -> Optional[dict]:
    """Uses OpenAI structured output to extract fields from raw text."""
    if not text.strip() or not custom_fields:
        return None
        
    try:
        # Construct the Pydantic BaseModel dynamically
        model_fields = {
            name: (Optional[str], Field(description=desc))
            for name, desc in custom_fields.items()
        }
        DynamicInsuranceData = create_model('DynamicInsuranceData', **model_fields)

        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at extracting structured data from insurance policies. Find the specific fields from the provided document text. If a field is not present, leave it null."
                },
                {
                    "role": "user",
                    "content": f"Extract the requested data from this policy document text:\n\n{text}"
                }
            ],
            response_format=DynamicInsuranceData,
            temperature=0.0
        )
        return completion.choices[0].message.parsed.model_dump()
    except Exception as e:
        print(f"OpenAI extraction error: {e}")
        return None

class PivotTableDefinition(BaseModel):
    sheet_name: str = Field(description="A short, concise name for the Excel sheet (max 30 chars).")
    index: List[str] = Field(description="The column(s) to group by (the rows of the pivot table). Must be exactly matching one of the extracted columns.")
    values: List[str] = Field(description="The numeric column(s) to aggregate. Must be exactly matching one of the extracted columns.")
    aggfunc: str = Field(description="The pandas aggregation function to apply (e.g., 'sum', 'mean', 'count', 'max', 'min').")

class DashboardRequirements(BaseModel):
    pivot_tables: Optional[List[PivotTableDefinition]] = Field(description="List of pivot tables requested. ONLY populate this if the user asks for aggregations (sum, count, etc) or grouping data.", default_factory=list)

def generate_dashboard_config(prompt: str, available_columns: List[str]) -> Optional[List[dict]]:
    """Analyzes user instructions to generate secure pivot table structures."""
    if not prompt.strip():
        return None
        
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a sophisticated data analyst AI. The user will provide a text instruction asking for a dashboard or pivot table. You are restricted to using these exact columns: {', '.join(available_columns)}. Return a structured configuration for pandas pivot_table. ONLY build pivot tables if the user explicitly wants grouping, sums, counts, or structured metric tracking. If they just ask to 'extract data into a tabular dashboard', return an empty list."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format=DashboardRequirements,
            temperature=0.0
        )
        return completion.choices[0].message.parsed.model_dump().get("pivot_tables", [])
    except Exception as e:
        print(f"Pivot generation error: {e}")
        return None

class DeducedColumn(BaseModel):
    name: str = Field(description="The snake_case name of the column (e.g. fire_coverage, chassis_number).")
    description: str = Field(description="A short instruction for the extractor to find this value.")

class TaskDecomposition(BaseModel):
    deduced_columns: List[DeducedColumn] = Field(description="The columns required based on the user's assignment.")
    needs_expiry_tracker: bool = Field(description="True if the user asked for an expiry tracker or timeline trigger.")
    dashboard_instructions: Optional[str] = Field(description="Any instructions specific to generating Pivot tables or Dashboards.")

def decompose_master_task(prompt: str) -> Optional[dict]:
    """Analyzes a master task prompt to deduce required columns and features."""
    if not prompt.strip():
        return None
        
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a master Task Orchestrator. The user will provide a descriptive assignment. You must parse it and return the necessary data columns needed to fulfill the request, detect if an expiry tracker policy was requested, and isolate any specific pivot table or aggregated dashboard commands."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format=TaskDecomposition,
            temperature=0.0
        )
        return completion.choices[0].message.parsed.model_dump()
    except Exception as e:
        print(f"Task decomposition error: {e}")
        return None
