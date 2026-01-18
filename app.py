import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re
from datetime import datetime
from io import BytesIO

# ---------------- CONFIG ----------------

st.set_page_config(page_title="GST Litigation Tracker", page_icon="📂", layout="wide")
st.title("📂 GST Litigation Tracker – Prototype")

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ---------------- HELPER FUNCTIONS ----------------

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()


def extract_with_ai(batch_texts):
    prompt = f"""
    Extract GST notice details and return ONLY valid JSON array.

    Required keys:
    Entity Name, GSTIN, Notice Type, Description, Ref ID,
    Date Of Issuance, Due Date, Financial Year,
    Total Demand Amount, DIN No, Officer Name,
    Designation, Area Division, Source

    If value not found, keep blank.

    Documents:
    {json.dumps(batch_texts)}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []

    return json.loads(match.group(0))


def calculate_status(due_date):
    try:
        due = datetime.strptime(due_date, "%d-%m-%Y")
        return "Overdue" if due < datetime.today() else "Pending"
    except:
        return "Pending"

# ---------------- SIDEBAR ----------------

st.sidebar.header("📤 Upload Notices")

uploaded_files = st.sidebar.file_uploader(
    "Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

# ---------------- MAIN LOGIC ----------------

if uploaded_files:
    st.info("⏳ Processing notices...")

    batch_texts = []

    for uploaded in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded.read())
            path = tmp.name

        text = extract_text_from_pdf(path)
        batch_texts.append({"Source": uploaded.name, "Text": text})
        os.remove(path)

    results = extract_with_ai(batch_texts)

    df = pd.DataFrame(results)

    if not df.empty:
        # Add Status column
        df["Status"] = df["Due Date"].apply(calculate_status)

        # ---------------- DASHBOARD ----------------

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("📄 Total Notices", len(df))
        col2.metric("🕒 Pending", (df["Status"] == "Pending").sum())
        col3.metric("⛔ Overdue", (df["Status"] == "Overdue").sum())
        col4.metric("✅ Reviewed", (df["Status"] == "Reviewed").sum())

        # ---------------- FILTERS ----------------

        st.subheader("🔍 Filters")

        f1, f2, f3 = st.columns(3)

        notice_filter = f1.multiselect(
            "Notice Type",
            options=df["Notice Type"].dropna().unique()
        )

        fy_filter = f2.multiselect(
            "Financial Year",
            options=df["Financial Year"].dropna().unique()
        )

        status_filter = f3.multiselect(
            "Status",
            options=df["Status"].unique()
        )

        if notice_filter:
            df = df[df["Notice Type"].isin(notice_filter)]
        if fy_filter:
            df = df[df["Financial Year"].isin(fy_filter)]
        if status_filter:
            df = df[df["Status"].isin(status_filter)]

        # ---------------- TABLE ----------------

        st.subheader("📑 Litigation Register")
        st.dataframe(df, use_container_width=True)

        # ---------------- EXCEL DOWNLOAD ----------------

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="GST Notices")

        output.seek(0)

        st.download_button(
            "📥 Download Excel",
            data=output,
            file_name="GST_Litigation_Tracker.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.warning("No data extracted from notices.")


