import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.pipeline import _process_one
from src.enrichment import enrich
from src.excel_exporter import _write_excel
import pandas as pd
from src.schema import FINAL_COLUMNS
from dotenv import load_dotenv

app = FastAPI(title="ALT Mobility - Insurance PDF Ingestion")

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CACHE_DIR = DATA_DIR / "cache"
JSON_OUT = DATA_DIR / "extracted.json"
EXCEL_OUT = DATA_DIR / "extracted.xlsx"
TEMPLATE_PATH = ROOT / "dashboard" / "template.html"
HTML_OUT = ROOT / "dashboard" / "index.html"

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables (OPENAI_API_KEY)
load_dotenv(ROOT / ".env", override=True)

class ExtractionResponse(BaseModel):
    message: str
    action: str
    chassis_number: Optional[str]
    policy_number: Optional[str]

@app.post("/api/upload", response_model=ExtractionResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Save file
    file_path = UPLOADS_DIR / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    try:
        # Process and Extract
        raw_data = _process_one(file_path, CACHE_DIR)
        
        # Enrich
        enriched_data = enrich(raw_data)
        
        # Load existing data
        rows: list[dict] = []
        if JSON_OUT.exists():
            rows = json.loads(JSON_OUT.read_text())
            
        # Deduplication logic
        chassis = enriched_data.get("vehicle_chassis_number")
        policy = enriched_data.get("policy_number")
        source_file = enriched_data.get("source_file")
        
        index_to_update = -1
        # Try to match by chassis number first
        if chassis and chassis != "Not Found":
            for i, row in enumerate(rows):
                if row.get("vehicle_chassis_number") == chassis:
                    index_to_update = i
                    break
                    
        # If no chassis match, try filename
        if index_to_update == -1 and source_file:
            for i, row in enumerate(rows):
                if row.get("source_file") == source_file:
                    index_to_update = i
                    break
        
        action = "appended"
        if index_to_update != -1:
            rows[index_to_update] = enriched_data
            action = "updated"
        else:
            rows.append(enriched_data)
            
        # Save JSON
        JSON_OUT.write_text(json.dumps(rows, default=str, indent=2))
        
        # Save Excel
        ordered_cols = ["source_file", *FINAL_COLUMNS]
        df = pd.DataFrame(rows)
        for col in ordered_cols:
            if col not in df.columns:
                df[col] = None
        df = df[ordered_cols]
        _write_excel(df, EXCEL_OUT)
        
        from scripts.build_dashboard import build
        # Regenerate Dashboard
        build(JSON_OUT, TEMPLATE_PATH, HTML_OUT)
        
        return ExtractionResponse(
            message="Successfully processed PDF",
            action=action,
            chassis_number=chassis,
            policy_number=policy
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

# Mount the dashboard at the root
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
