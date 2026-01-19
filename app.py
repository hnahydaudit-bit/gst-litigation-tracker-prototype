import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="GST Litigation Tracker", layout="wide")
st.title("📂 GST Litigation Tracker")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

STATUS_OPTIONS = ["Pending", "Under Review", "Replied", "Closed"]

# ================= SESSION STORAGE =================
if "notice_register" not in st.session_state:
    st.session_state.notice_register = pd.DataFrame()

# ================= HELPERS =================
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()


def extract_with_ai_batch(batch_texts):
    prompt = f"""
You are a GST litigation expert.

Extract data STRICTLY from text.
DO NOT GUESS OR FILL DUMMY VALUES.
If not found, use null.

Return ONLY valid JSON array.

Fields:
- Entity Name
- GSTIN
- Type of Notice / Order
- Description
- Ref ID
- Date Of Issuance
- Due Date
- Case ID
- Notice Type
- Financial Year
- Total Demand Amount
- DIN No
- Officer Name
- Designation
- Area Division
- Tax Amount
- Interest
- Penalty
- Source

DOCUMENTS:
{json.dumps(batch_texts, indent=2)}
"""

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)

    match = re.search(r"\[.*\]", response.text, re.DOTALL)
    if not match:
        return []

    return json.loads(match.group(0))


# ================= UPLOAD SECTION =================
st.subheader("📤 Upload GST Notices")

uploaded_files = st.file_uploader(
    "Upload Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Extracting notice details..."):
        batch_texts = []

        for file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                path = tmp.name

            text = extract_text_from_pdf(path)
            os.remove(path)

            if text:
                batch_texts.append({
                    "Source": file.name,
                    "text": text[:8000]  # safe limit
                })

        extracted = extract_with_ai_batch(batch_texts)

        if extracted:
            df_new = pd.DataFrame(extracted)
            df_new["Status"] = "Pending"
            df_new["Last Updated"] = datetime.now().strftime("%d-%m-%Y %H:%M")

            st.session_state.notice_register = pd.concat(
                [st.session_state.notice_register, df_new],
                ignore_index=True
            )

            st.success("Notices processed successfully")

            st.subheader("📄 Current Upload Summary")
            st.dataframe(df_new, use_container_width=True)

            st.download_button(
                "📥 Download Excel (This Upload)",
                df_new.to_excel(index=False),
                file_name="GST_Notice_Summary.xlsx"
            )

# ================= DASHBOARD =================
if not st.session_state.notice_register.empty:
    st.divider()
    st.subheader("📊 Notice Status Overview")

    status_counts = (
        st.session_state.notice_register["Status"]
        .value_counts()
        .reset_index()
    )
    status_counts.columns = ["Status", "Count"]

    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric("Total Notices", len(st.session_state.notice_register))

    with col2:
        st.pyplot(
            status_counts.set_index("Status").plot(
                kind="pie",
                y="Count",
                legend=False,
                autopct="%1.0f%%",
                figsize=(4, 4)
            ).get_figure()
        )

# ================= STATUS UPDATE =================
st.divider()
st.subheader("📝 Update Notice Status")

if not st.session_state.notice_register.empty:
    df = st.session_state.notice_register

    selected_index = st.selectbox(
        "Select Notice (Ref ID / Source)",
        options=df.index,
        format_func=lambda x: f"{df.loc[x, 'Ref ID']} | {df.loc[x, 'Source']}"
    )

    new_status = st.selectbox(
        "Update Status",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(df.loc[selected_index, "Status"])
    )

    if st.button("Update Status"):
        st.session_state.notice_register.loc[selected_index, "Status"] = new_status
        st.session_state.notice_register.loc[selected_index, "Last Updated"] = \
            datetime.now().strftime("%d-%m-%Y %H:%M")

        st.success("Status updated successfully")

# ================= NOTICE HISTORY =================
st.divider()
with st.expander("📚 View Full Notice Register"):
    if not st.session_state.notice_register.empty:
        st.dataframe(
            st.session_state.notice_register,
            use_container_width=True
        )

        st.download_button(
            "📥 Download Full Register",
            st.session_state.notice_register.to_excel(index=False),
            file_name="GST_Litigation_Register.xlsx"
        )












