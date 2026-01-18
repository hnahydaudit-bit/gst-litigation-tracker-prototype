import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re
from io import BytesIO
import matplotlib.pyplot as plt

# ---------------- CONFIG ----------------
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(
    page_title="GST Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

st.title("📂 GST Litigation Tracker")
st.caption("Centralised Notice Intake, Tracking & Monitoring System")

# ---------------- SESSION STORAGE ----------------
if "notices" not in st.session_state:
    st.session_state.notices = []

STATUS_OPTIONS = ["Pending", "Under Review", "Replied", "Closed"]

# ---------------- FUNCTIONS ----------------
def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_with_ai(batch_texts):
    prompt = f"""
    You are an AI that extracts GST litigation notice details.

    Return a JSON array. Each object must contain:
    Entity Name, GSTIN, Type of Notice / Order, Description,
    Ref ID, Date Of Issuance, Due Date, Case ID,
    Notice Type, Financial Year, Total Demand Amount,
    DIN No, Officer Name, Designation, Area Division,
    Tax Amount, Interest, Penalty, Source

    If a field is missing, leave it blank.
    Return ONLY valid JSON. No explanation.

    Documents:
    {json.dumps(batch_texts)}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw_text = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        return []

    return json.loads(match.group(0))

def add_default_status(records):
    for r in records:
        r["Status"] = "Pending"
    return records

# ---------------- SECTION 1: NOTICE INTAKE ----------------
st.header("📤 Notice Intake")

uploaded_files = st.file_uploader(
    "Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Reading notices and extracting details..."):
        batch_texts = []

        for uploaded in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            text = extract_text_from_pdf(tmp_path)
            batch_texts.append({
                "Source": uploaded.name,
                "Text": text
            })

            os.remove(tmp_path)

        extracted_data = extract_with_ai(batch_texts)
        extracted_data = add_default_status(extracted_data)
        st.session_state.notices.extend(extracted_data)

    st.success("Notices successfully added to the register")

# ---------------- SECTION 2: NOTICE REGISTER ----------------
st.header("📋 Notice Register")

if st.session_state.notices:
    df = pd.DataFrame(st.session_state.notices)

    st.subheader("Update Status")
    for i in range(len(df)):
        updated_status = st.selectbox(
            label=f"{df.loc[i, 'Source']} | {df.loc[i, 'GSTIN']}",
            options=STATUS_OPTIONS,
            index=STATUS_OPTIONS.index(df.loc[i, "Status"]),
            key=f"status_{i}"
        )
        st.session_state.notices[i]["Status"] = updated_status

    df = pd.DataFrame(st.session_state.notices)

    st.subheader("All Notices")
    st.dataframe(df, use_container_width=True)

    # -------- Excel Download --------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="GST Notices")
    output.seek(0)

    st.download_button(
        label="📥 Download Excel Summary",
        data=output,
        file_name="GST_Litigation_Register.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ---------------- DASHBOARD ----------------
    st.header("📊 Dashboard Overview")

    status_counts = df["Status"].value_counts()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Notices", len(df))
    col2.metric("Pending", status_counts.get("Pending", 0))
    col3.metric("Under Review", status_counts.get("Under Review", 0))
    col4.metric("Closed", status_counts.get("Closed", 0))

    st.subheader("Status Distribution")

    _, chart_col = st.columns([2, 1])

    with chart_col:
        fig, ax = plt.subplots(figsize=(4, 4))
        ax.pie(
            status_counts.values,
            labels=status_counts.index,
            autopct="%1.0f%%",
            startangle=90,
            textprops={"fontsize": 9}
        )
        ax.set_title("Notices by Status", fontsize=11)
        ax.axis("equal")
        st.pyplot(fig, use_container_width=False)

else:
    st.info("No notices have been processed yet.")




