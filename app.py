import streamlit as st
import pandas as pd
import io
import os
from dotenv import load_dotenv

# Import analyzer functions
from analyzer import parse_insurance_data_with_ai, extract_text_from_pdf_bytes, generate_dashboard_config, decompose_master_task

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Insurance Policy Parser", page_icon="📄", layout="wide")

st.title("📄 AI Insurance Policy Parser")

if not os.getenv("OPENAI_API_KEY"):
    st.error("⚠️ OPENAI_API_KEY is not set. Please add it to your `.env` file.")
    st.stop()

# --- INITIALIZE STATE ---
if "column_config" not in st.session_state:
    st.session_state.column_config = [
        {"Column Name": "vehicle_chassis_number", "Description / Instruction": "Extract the unique identifier for the vehicle."},
        {"Column Name": "insurance_company_name", "Description / Instruction": "Extract the name of the insurance company."}
    ]

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("⚙️ Column Configuration")
st.sidebar.markdown("Review and edit the fields to extract.")

edited_config = st.sidebar.data_editor(
    pd.DataFrame(st.session_state.column_config), 
    num_rows="dynamic", 
    use_container_width=True,
    hide_index=True
)

st.sidebar.info("💡 Any columns you define above are protected. The AI will not delete them.")

# --- MASTER AI TASK ASSISTANT ---
st.subheader("🤖 AI Task Assistant")
master_task = st.text_area(
    "Paste your entire assignment here. The AI will automatically deduce missing columns, set up trackers, and generate dashboards during extraction.",
    placeholder="e.g. Extract Vehicle Chassis Number, Fire coverage (Yes/No)... Create an automated tracker to identify policies nearing expiry.",
    height=120
)

# --- FILE UPLOADER & EXTRACTION ---
uploaded_files = st.file_uploader("Upload Policy PDFs", type=['pdf'], accept_multiple_files=True)

if uploaded_files:
    if st.button("Extract Data"):
        
        # 1. Grab Manually Edited Columns
        custom_fields = {}
        for _, row in edited_config.iterrows():
            col_name = str(row["Column Name"]).strip()
            if pd.notna(row["Column Name"]) and col_name: 
                desc = str(row["Description / Instruction"]).strip() if pd.notna(row["Description / Instruction"]) else "Extract this field"
                custom_fields[col_name] = desc
                
        # 2. Autonomous Task Evaluation (No extra clicks needed)
        needs_tracker = False
        dashboard_instructions = ""
        
        if master_task.strip():
            with st.spinner("🤖 Evaluating Task Instructions..."):
                decomposition = decompose_master_task(master_task)
                if decomposition:
                    needs_tracker = decomposition.get("needs_expiry_tracker", False)
                    dashboard_instructions = decomposition.get("dashboard_instructions", "")
                    
                    # Merge deduced columns WITHOUT overwriting what user manually typed
                    for col in decomposition.get("deduced_columns", []):
                        ai_col_name = col["name"].strip()
                        if ai_col_name and ai_col_name not in custom_fields:
                            custom_fields[ai_col_name] = col["description"]
                            
        if not custom_fields:
            st.error("Please define at least one column (either manually in the sidebar or via the Task Assistant) before extracting.")
            st.stop()
            
        # 3. Extraction Loop
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            status_text.text(f"Processing ({i+1}/{len(uploaded_files)}): {file.name}...")
            
            file_bytes = file.read()
            raw_text = extract_text_from_pdf_bytes(file_bytes)
            
            structured_data = parse_insurance_data_with_ai(raw_text, custom_fields)
            
            if structured_data:
                structured_data['file_name'] = file.name
                results.append(structured_data)
            else:
                st.warning(f"Failed to extract data from {file.name}")
                
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        status_text.text("Extraction complete!")
        
        if results:
            df = pd.DataFrame(results)
            
            cols = ['file_name'] + list(custom_fields.keys())
            for col in cols:
                if col not in df.columns:
                    df[col] = None
            df = df[cols]
            
            # --- EXPIRY TRACKER PIPELINE ---
            expiry_col = None
            for col in df.columns:
                if 'expiry' in col.lower() or 'end_date' in col.lower():
                    expiry_col = col
                    break
            
            if expiry_col:
                try:
                    df['parsed_end_date'] = pd.to_datetime(df[expiry_col], errors='coerce')
                    today = pd.Timestamp.today().normalize()
                    df['days_until_expiry'] = (df['parsed_end_date'] - today).dt.days
                    df = df.drop(columns=['parsed_end_date'])
                except Exception:
                    pass

            if needs_tracker and 'days_until_expiry' in df.columns:
                st.error("⚠️ Automated Expiry Alerts Tracker (<= 30 Days)")
                alerts_df = df[df['days_until_expiry'] <= 30]
                if not alerts_df.empty:
                    st.dataframe(alerts_df)
                else:
                    st.success("✅ No policies are expiring within the next 30 days!")
            
            st.subheader("Extracted Table")
            st.dataframe(df)

            # --- ADVANCED DASHBOARD PIPELINE ---
            pivot_tables_data = [] 
            
            if dashboard_instructions:
                st.subheader("📊 Dynamic Appended Dashboards")
                with st.spinner("Generating Dashboard metrics from your prompt..."):
                    pivot_configs = generate_dashboard_config(dashboard_instructions, df.columns.tolist())
                    
                if pivot_configs:
                    for config in pivot_configs:
                        sheet_name = config.get("sheet_name", "Pivot Table")
                        index_cols = [c for c in config.get("index", []) if c in df.columns]
                        val_cols = [c for c in config.get("values", []) if c in df.columns]
                        agg = config.get("aggfunc", "sum")
                        
                        if index_cols and val_cols:
                            try:
                                for vc in val_cols:
                                    df[vc] = pd.to_numeric(df[vc], errors='coerce')
                                
                                pivot_df = pd.pivot_table(df, index=index_cols, values=val_cols, aggfunc=agg)
                                pivot_tables_data.append((sheet_name, pivot_df))
                                
                                st.markdown(f"**{sheet_name}** *(Pivot by: `{index_cols[0]}`, Value: `{val_cols[0]}`, Aggregation: `{agg.upper()}`)*")
                                st.dataframe(pivot_df)
                                
                                if len(index_cols) == 1 and len(val_cols) == 1:
                                    st.bar_chart(pivot_df)
                                    
                            except Exception as e:
                                st.error(f"Could not generate pivot table '{sheet_name}': {e}")
                else:
                    st.info("The AI determined your prompt requested a standard tabular extraction without specific aggregation charts (e.g. you didn't ask to 'sum' or 'group' anything). Your main Extracted Table above is ready!")
            
            # --- EXCEL EXPORT ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Parsed Data')
                
                for sheet_name, pivot_df in pivot_tables_data:
                    clean_sheet = str(sheet_name)[:31].replace(':', '').replace('/', '').replace('\\', '').replace('?', '').replace('*', '').replace('[', '').replace(']', '')
                    if not clean_sheet: clean_sheet = "Pivot"
                    pivot_df.to_excel(writer, sheet_name=clean_sheet)

            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 Download Full Data as Excel",
                data=processed_data,
                file_name="parsed_insurance_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.warning("No data could be extracted.")
