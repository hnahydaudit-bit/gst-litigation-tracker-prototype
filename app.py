import streamlit as st
import pandas as pd
import fitz
import google.generativeai as genai
import tempfile
import os
import json
import re
from io import BytesIO
from datetime import datetime
import altair as alt

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="GST Litigation Tracker",
    page_icon="📂",
    layout="wide"
)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ---------------- SESSION STATE ----------------
if "notices_df" not in st.session_state:
    st.session_state.notices_df = pd.DataFrame()

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

    Leave blank if not found.

    Documents:
    {json.dumps(batch_texts, indent=2)}
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content(prompt)
    text = response.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(match.group(0)) if match else []

def add_defaults(df):
    df["Status"] = "Pending"
    df["Last Updated"] = datetime.now().strftime("%d-%m-%Y")
    return df

# ---------------- UI ----------------
st.title("📂 GST Litigation Tracker")
st.caption("Automated GST notice extraction & litigation management")

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

        extracted = extract_with_ai(batch_texts)
        latest_df = pd.DataFrame(extracted)
        latest_df = add_defaults(latest_df)

        st.session_state.latest_upload = latest_df

        if st.session_state.notices_df.empty:
            st.session_state.notices_df = latest_df
        else:
            st.session_state.notices_df = pd.concat(
                [st.session_state.notices_df, latest_df],
                ignore_index=True
            )

    st.success("Notices processed successfully")

    # ---- CURRENT UPLOAD SUMMARY ----
    st.subheader("📄 Current Upload Summary")
    st.dataframe(latest_df, use_container_width=True)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        latest_df.to_excel(writer, index=False)
    buffer.seek(0)

    st.download_button(
        "📥 Download Excel (This Upload)",
        data=buffer,
        file_name="GST_Notice_Summary_Current_Upload.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- DASHBOARD ----------------
if not st.session_state.notices_df.empty:
    df = st.session_state.notices_df

    st.divider()
    st.subheader("📊 Litigation Dashboard")

    c1, c2, c3 = st.columns([1, 1, 2])

    with c1:
        st.metric("Total Notices", len(df))

    with c2:
        st.metric("Pending", int((df["Status"] == "Pending").sum()))

    with c3:
        pie_df = df["Status"].value_counts().reset_index()
        pie_df.columns = ["Status", "Count"]

        pie_chart = (
            alt.Chart(pie_df)
            .mark_arc()
            .encode(
                theta="Count:Q",
                color=alt.Color(
                    "Status:N",
                    scale=alt.Scale(scheme="blues"),
                    legend=alt.Legend(title="Status")
                ),
                tooltip=["Status", "Count"]
            )
            .properties(height=220)
        )

        st.altair_chart(pie_chart, use_container_width=True)

# ---------------- NOTICE REGISTER ----------------
st.divider()

if st.button("📂 View / Update Notice Register"):
    st.subheader("📁 Notice Register")

    df = st.session_state.notices_df

    filter_status = st.selectbox(
        "Filter by Status",
        ["All", "Pending", "In Progress", "Replied", "Closed"]
    )

    view_df = df if filter_status == "All" else df[df["Status"] == filter_status]

    st.dataframe(view_df, use_container_width=True)

    st.subheader("✏️ Update Notice Status")

    ref_list = view_df["Ref ID"].dropna().unique()

    if len(ref_list) > 0:
        selected_ref = st.selectbox("Select Ref ID", ref_list)
        new_status = st.selectbox(
            "New Status",
            ["Pending", "In Progress", "Replied", "Closed"]
        )

        if st.button("Update Status"):
            idx = st.session_state.notices_df[
                st.session_state.notices_df["Ref ID"] == selected_ref
            ].index

            st.session_state.notices_df.loc[idx, "Status"] = new_status
            st.session_state.notices_df.loc[idx, "Last Updated"] = datetime.now().strftime("%d-%m-%Y")

            st.success("Status updated successfully")









