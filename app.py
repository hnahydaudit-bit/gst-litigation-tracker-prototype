import streamlit as st
import pandas as pd
import fitz
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
st.caption("Centralised GST Notice Intake, Tracking & Monitoring")

STATUS_OPTIONS = ["Pending", "Under Review", "Replied", "Closed"]

# ---------------- SESSION ----------------
if "notices" not in st.session_state:
    st.session_state.notices = []

# ---------------- FUNCTIONS ----------------
def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            text += page.get_text("text")
    return text.strip()

def extract_with_ai(batch_texts):
    prompt = f"""
    Extract GST notice details and return ONLY valid JSON array.

    Required fields:
    Entity Name, GSTIN, Notice Type, Financial Year, Ref ID,
    Date Of Issuance, Due Date, Total Demand Amount,
    Officer Name, Designation, Area Division,
    Tax Amount, Interest, Penalty, Source

    If missing, leave blank.

    Documents:
    {json.dumps(batch_texts)}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    raw = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []

    return json.loads(match.group(0))

def add_default_status(data):
    for d in data:
        d["Status"] = "Pending"
    return data

# ---------------- SECTION 1: UPLOAD ----------------
st.header("📤 Notice Intake")

uploaded_files = st.file_uploader(
    "Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Processing notices..."):
        batch_texts = []

        for uploaded in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            text = extract_text_from_pdf(tmp_path)
            batch_texts.append({"Source": uploaded.name, "Text": text})
            os.remove(tmp_path)

        extracted = extract_with_ai(batch_texts)
        extracted = add_default_status(extracted)
        st.session_state.notices.extend(extracted)

    st.success("Notices added to register successfully")

# ---------------- SECTION 2: REGISTER ----------------
st.header("📋 Notice Register")

if st.session_state.notices:
    df = pd.DataFrame(st.session_state.notices)

    st.dataframe(df, use_container_width=True)

    # -------- STATUS EDIT (SMART UX) --------
    st.subheader("✏️ Edit Notice Status")

    notice_labels = [
        f"{i+1}. {row.get('Source','')} | {row.get('GSTIN','')}"
        for i, row in df.iterrows()
    ]

    selected_index = st.selectbox(
        "Select Notice",
        range(len(notice_labels)),
        format_func=lambda x: notice_labels[x]
    )

    new_status = st.selectbox(
        "Update Status",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(df.loc[selected_index, "Status"])
    )

    if st.button("Save Status"):
        st.session_state.notices[selected_index]["Status"] = new_status
        st.success("Status updated successfully")

    # -------- EXCEL DOWNLOAD --------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="GST Notices")
    output.seek(0)

    st.download_button(
        "📥 Download Excel Summary",
        data=output,
        file_name="GST_Litigation_Register.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ---------------- DASHBOARD ----------------
    st.header("📊 Dashboard")

    status_counts = df["Status"].value_counts()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Notices", len(df))
    col2.metric("Pending", status_counts.get("Pending", 0))
    col3.metric("Under Review", status_counts.get("Under Review", 0))
    col4.metric("Closed", status_counts.get("Closed", 0))

    chart_col, table_col = st.columns([1.2, 1])

    # -------- PIE CHART --------
    with chart_col:
        fig, ax = plt.subplots(figsize=(4.5, 4.5))

        blue_gradients = ["#1a73e8", "#4dabf7", "#90caf9", "#e3f2fd"]

        ax.pie(
            status_counts.values,
            labels=status_counts.index,
            autopct="%1.0f%%",
            startangle=90,
            colors=blue_gradients[:len(status_counts)],
            textprops={"fontsize": 9}
        )
        ax.set_title("Notices by Status", fontsize=11)
        ax.axis("equal")
        st.pyplot(fig)

    # -------- SUMMARY TABLE --------
    with table_col:
        summary_df = status_counts.reset_index()
        summary_df.columns = ["Status", "Count"]
        st.subheader("Status Summary")
        st.table(summary_df)

else:
    st.info("No notices processed yet.")





