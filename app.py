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

if "show_register" not in st.session_state:
    st.session_state.show_register = False

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

    Fields:
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
    return json.loads(match.group(0)) if match else []

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
                path = tmp.name

            batch_texts.append({
                "Source": uploaded.name,
                "Text": extract_text_from_pdf(path)
            })
            os.remove(path)

        extracted = add_default_status(extract_with_ai(batch_texts))
        st.session_state.notices.extend(extracted)

    st.success("Notices added successfully")

# ---------------- MAIN DASHBOARD ----------------
if st.session_state.notices:
    df = pd.DataFrame(st.session_state.notices)
    status_counts = df["Status"].value_counts()

    st.header("📊 Dashboard")

    # -------- KPIs --------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Notices", len(df))
    k2.metric("Pending", status_counts.get("Pending", 0))
    k3.metric("Under Review", status_counts.get("Under Review", 0))
    k4.metric("Closed", status_counts.get("Closed", 0))

    dash_col, side_col = st.columns([1.2, 1])

    # -------- PIE CHART (SMALL & CLEAN) --------
    with dash_col:
        fig, ax = plt.subplots(figsize=(3.4, 3.4))
        colors = ["#1a73e8", "#4285f4", "#8ab4f8", "#e8f0fe"]

        ax.pie(
            status_counts.values,
            labels=status_counts.index,
            autopct="%1.0f%%",
            startangle=90,
            colors=colors[:len(status_counts)],
            textprops={"fontsize": 8}
        )
        ax.set_title("Notice Status Distribution", fontsize=10)
        ax.axis("equal")
        plt.tight_layout()
        st.pyplot(fig)

    # -------- STATUS EDIT (FAST) --------
    with side_col:
        st.subheader("✏️ Update Notice Status")

        labels = [
            f"{i+1}. {row.get('Source','')} | {row.get('GSTIN','')}"
            for i, row in df.iterrows()
        ]

        with st.form("status_form", clear_on_submit=False):
            idx = st.selectbox(
                "Select Notice",
                range(len(labels)),
                format_func=lambda x: labels[x]
            )

            new_status = st.selectbox(
                "New Status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(df.loc[idx, "Status"])
            )

            submit = st.form_submit_button("Update Status")

            if submit:
                st.session_state.notices[idx]["Status"] = new_status
                st.success("Status updated instantly")

    # -------- NOTICE HISTORY BUTTON --------
    st.divider()

    if st.button("📂 View Notice History"):
        st.session_state.show_register = not st.session_state.show_register

    if st.session_state.show_register:
        with st.expander("Notice Register", expanded=True):
            st.dataframe(df, use_container_width=True)

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

else:
    st.info("Upload GST notices to start tracking.")






