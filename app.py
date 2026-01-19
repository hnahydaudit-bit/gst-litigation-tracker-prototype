import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re
import io
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="GST Litigation Tracker", layout="wide")
st.title("📂 GST Litigation Tracker")

# Secure API Key handling
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Please set GEMINI_API_KEY in your Streamlit secrets.")

STATUS_OPTIONS = ["Pending", "Under Review", "Replied", "Closed"]

# ================= SESSION STORAGE =================
if "notice_register" not in st.session_state:
    st.session_state.notice_register = pd.DataFrame()

# ================= HELPERS =================
def extract_text_from_pdf(path):
    text = ""
    try:
        with fitz.open(path) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
    return text.strip()

def to_excel(df):
    """Converts dataframe to an excel binary stream"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

def extract_with_ai_batch(batch_texts):
    prompt = f"""
You are a GST litigation expert.
Extract data STRICTLY from text. Return ONLY a valid JSON array.
If a field is not found, use null.

Fields:
- Entity Name, GSTIN, Type of Notice / Order, Description, Ref ID, 
- Date Of Issuance, Due Date, Case ID, Notice Type, Financial Year, 
- Total Demand Amount, DIN No, Officer Name, Designation, Area Division, 
- Tax Amount, Interest, Penalty, Source

DOCUMENTS:
{json.dumps(batch_texts, indent=2)}
"""
    # Using gemini-1.5-flash (the current stable flash model)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it only contains the JSON array
        clean_json = re.search(r"\[.*\]", response.text, re.DOTALL)
        if clean_json:
            return json.loads(clean_json.group(0))
    except Exception as e:
        st.error(f"AI Extraction Error: {e}")
    return []

# ================= UPLOAD SECTION =================
st.subheader("📤 Upload GST Notices")

uploaded_files = st.file_uploader(
    "Upload Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    if st.button("Process Documents"):
        with st.spinner("Extracting notice details..."):
            batch_texts = []

            for file in uploaded_files:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(file.getvalue())
                    path = tmp.name

                text = extract_text_from_pdf(path)
                os.remove(path)

                if text:
                    batch_texts.append({
                        "Source": file.name,
                        "text": text[:8000]  # Chunking to fit context limits
                    })

            if batch_texts:
                extracted = extract_with_ai_batch(batch_texts)

                if extracted:
                    df_new = pd.DataFrame(extracted)
                    df_new["Status"] = "Pending"
                    df_new["Last Updated"] = datetime.now().strftime("%d-%m-%Y %H:%M")

                    st.session_state.notice_register = pd.concat(
                        [st.session_state.notice_register, df_new],
                        ignore_index=True
                    )

                    st.success(f"Successfully processed {len(df_new)} notices!")
                    
                    st.subheader("📄 Current Upload Summary")
                    st.dataframe(df_new, use_container_width=True)

                    excel_data = to_excel(df_new)
                    st.download_button(
                        label="📥 Download Excel (This Upload)",
                        data=excel_data,
                        file_name=f"Notice_Summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

# ================= DASHBOARD =================
if not st.session_state.notice_register.empty:
    st.divider()
    st.subheader("📊 Notice Status Overview")

    df_reg = st.session_state.notice_register
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric("Total Notices", len(df_reg))
        status_counts = df_reg["Status"].value_counts()
        st.write(status_counts)

    with col2:
        # Simple Pie Chart using Streamlit Native if Matplotlib is complex
        if not status_counts.empty:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4, 4))
            status_counts.plot(kind='pie', autopct='%1.0f%%', ax=ax, startangle=90)
            ax.set_ylabel('')
            st.pyplot(fig)

# ================= STATUS UPDATE =================
st.divider()
st.subheader("📝 Update Notice Status")

if not st.session_state.notice_register.empty:
    df = st.session_state.notice_register

    selected_index = st.selectbox(
        "Select Notice to update",
        options=df.index,
        format_func=lambda x: f"{df.loc[x, 'Ref ID']} | {df.loc[x, 'Source']}"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        new_status = st.selectbox(
            "Update Status",
            STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(df.loc[selected_index, "Status"])
        )
    
    if st.button("Confirm Update"):
        st.session_state.notice_register.at[selected_index, "Status"] = new_status
        st.session_state.notice_register.at[selected_index, "Last Updated"] = \
            datetime.now().strftime("%d-%m-%Y %H:%M")
        st.success("Status updated!")
        st.rerun()

# ================= NOTICE HISTORY =================
st.divider()
with st.expander("📚 View Full Notice Register"):
    if not st.session_state.notice_register.empty:
        st.dataframe(st.session_state.notice_register, use_container_width=True)

        full_excel = to_excel(st.session_state.notice_register)
        st.download_button(
            "📥 Download Full Register (Excel)",
            data=full_excel,
            file_name="GST_Litigation_Register_Full.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No notices uploaded yet.")
