import os
import pandas as pd
from datetime import datetime
from analyzer import extract_text_from_pdf, parse_insurance_data_with_ai
from dotenv import load_dotenv

def process_pdfs(input_dir: str, output_excel: str):
    pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    if not pdfs:
        print(f"No PDFs found in the '{input_dir}' directory.")
        return

    results = []
    
    print(f"Found {len(pdfs)} PDFs. Starting processing...")
    
    for i, pdf_file in enumerate(pdfs):
        print(f"Processing ({i+1}/{len(pdfs)}): {pdf_file}")
        pdf_path = os.path.join(input_dir, pdf_file)
        
        # 1. Extract raw text
        raw_text = extract_text_from_pdf(pdf_path)
        
        # 2. Extract structured data using OpenAI
        structured_data = parse_insurance_data_with_ai(raw_text)
        
        if structured_data:
            structured_data['file_name'] = pdf_file
            results.append(structured_data)
        else:
            print(f"  -> Failed to extract data from {pdf_file}")

    if not results:
        print("No data was extracted from any files.")
        return

    # 3. Create DataFrame
    df = pd.DataFrame(results)
    
    # Ensure specific column order
    cols = ['file_name', 'insurance_company', 'policy_number', 'chassis_number', 
            'od_start_date', 'od_end_date', 'premium', 'coverage_details']
    
    for col in cols:
        if col not in df.columns:
            df[col] = None
    
    df = df[cols]

    # 4. Derived calculation: Days until Expiry
    try:
        df['parsed_end_date'] = pd.to_datetime(df['od_end_date'], errors='coerce')
        today = pd.Timestamp.today().normalize()
        df['days_until_expiry'] = (df['parsed_end_date'] - today).dt.days
        df = df.drop(columns=['parsed_end_date'])
    except Exception as e:
        print(f"Notice: Could not calculate 'days_until_expiry' automatically. {e}")
        df['days_until_expiry'] = "Parsing error"

    # 5. Export to Excel
    df.to_excel(output_excel, index=False)
    print(f"\nSuccessfully processed {len(results)} files.")
    print(f"Data exported to {output_excel}")


if __name__ == "__main__":
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY is not set in the environment or .env file.")
        print("Please create a .env file and add your API key: OPENAI_API_KEY=your_key_here")
        exit(1)
    
    INPUT_DIR = "sample_pdfs"
    OUTPUT_FILE = "output_results.xlsx"
    
    os.makedirs(INPUT_DIR, exist_ok=True)
    
    process_pdfs(INPUT_DIR, OUTPUT_FILE)
