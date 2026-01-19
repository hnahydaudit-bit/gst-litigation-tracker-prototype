import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import google.generativeai as genai
import tempfile
import os
import json
import re
from io import BytesIO
import plotly.express as px
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="GST Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ---------------- SESSION STATE ----------------
if "notices" not in st.session_state:
    st.session_state.notices = []

if "latest_upload" not in st.session_state:
    st.session_state.latest_upload = pd.DataFrame()

# ---------------- HELPERS ----------------
def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

def extract_with_ai(batch_texts):
    prompt = f"""
    Extract GST litigation notice details.

    Return ONLY a JSON array with keys:
    Entity Name, GSTIN, Type of Notice / Order (System Update),
    Description, Ref ID, Date Of Issuance, Due Date, Case ID,
    Notice Type (ASMT-10 or ADT - 01 / SCN or Appeal),
    Financial Year, Total Demand Amount as per Notice,
    DIN No, Officer Name, Designation, Area Division,
    Tax Amount, Interest, Penalty, Source

    If not found, leave blank.

    Documents:
    {json.dumps(batch_texts, indent=2)}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(match.group(0)) if match else []

def add_defaults(data):
    for d in data:
        d["Status"] = "Pending"
        d["Last Updated"] = datetime.now().strftime("%d-%m-%Y")
    return data

# ---------------- UI ----------------
st.title("📂 GST Litigation Tracker")

st.markdown(
    "Automated GST notice extraction, tracking & status monitoring",
    unsafe_allow_html=True
)

# ---------------- UPLOAD SECTION ----------------
st.subheader("📤 Upload GST Notices")

uploaded_files = st.file_uploader(
    "Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    with st.spinner("Processing notices..."):
        batch_texts = []

        for file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file.read())
                path = tmp.name

            text = extract_text_from_pdf(path)
            batch_texts.append({"Source": file.name, "Text": text})
            os.remove(path)

        extracted = add_defaults(extract_with_ai(batch_texts))
        latest_df = pd.DataFrame(extracted)

        st.session_state.latest_upload = latest_df
        st.session_state.notices.extend(extracted)

    st.success("Notices processed successfully")

    # -------- CURRENT UPLOAD OUTPUT --------
    st.subheader("📄 Current Upload Summary")
    st.dataframe(latest_df, use_container_width=True)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        latest_df.to_excel(writer, index=False, sheet_name="Summary")
    buffer.seek(0)

    st.download_button(
        "📥 Download Excel (This Upload)",
        data=buffer,
        file_name="GST_Notice_Summary_Current_Upload.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- DASHBOARD ----------------
if st.session_state.notices:
    df = pd.DataFrame(st.session_state.notices)

    st.divider()
    st.subheader("📊 Litigation Dashboard")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        st.metric("Total Notices", len(df))

    with col2:
        st.metric(
            "Pending",
            int((df["Status"] == "Pending").sum())
        )

    with col3:
        pie = df["Status"].value_counts().reset_index()
        pie.columns = ["Status", "Count"]

        fig = px.pie(
            pie,
            values="Count",
            names="Status",
            hole=0.55,
            color_discrete_sequence=px.colors.sequential.Blues
        )

        fig.update_layout(
            height=280,
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=True
        )

        st.plotly_chart(fig, use_container_width=True)

# ---------------- NOTICE HISTORY ----------------
st.divider()

if st.button("📂 View / Update Notice Register"):
    st.subheader("📁 Notice Register")

    df = pd.DataFrame(st.session_state.notices)

    # --- SMART FILTER ---
    filter_status = st.selectbox(
        "Filter by Status",
        ["All", "Pending", "In Progress", "Replied", "Closed"]
    )

    view_df = df if filter_status == "All" else df[df["Status"] == filter_status]

    st.dataframe(view_df, use_container_width=True)

    # --- STATUS UPDATE (FAST & CLEAN) ---
    st.subheader("✏️ Update Notice Status")

    selected_ref = st.selectbox(
        "Select Ref ID",
        view_df["Ref ID"].dropna().unique()
    )

    new_status = st.selectbox(
        "New Status",
        ["Pending", "In Progress", "Replied", "Closed"]
    )

    if st.button("Update Status"):
        for n in st.session_state.notices:
            if n.get("Ref ID") == selected_ref:
                n["Status"] = new_status
                n["Last Updated"] = datetime.now().strftime("%d-%m-%Y")
        st.success("Status updated successfully")
        st.rerun()

# ---------------- FOOTER ----------------
st.caption(
    "Prototype | API-ready | Confidential processing recommended via Enterprise AI"
)







