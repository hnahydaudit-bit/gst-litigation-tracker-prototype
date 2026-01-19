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

# ---------------- UPLOAD ----------------
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

            text = extract_text_from_pdf(path)[:12000]  # token safety
            batch_texts.append({"Source": file.name, "Text": text})
            os.remove(path)

        extracted = extract_with_ai(batch_texts)
        new_df = pd.DataFrame(extracted)
        new_df = add_defaults(new_df)

        # --------- MERGE LOGIC (NO DUPLICATES) ---------
        if st.session_state.notices_df.empty:
            st.session_state.notices_df = new_df
        else:
            existing = st.session_state.notices_df

            for _, row in new_df.iterrows():
                ref = row["Ref ID"]

                if ref in existing["Ref ID"].values:
                    idx = existing[existing["Ref ID"] == ref].index
                    for col in new_df.columns:
                        if col not in ["Status", "Last Updated"]:
                            existing.loc[idx, col] = row[col]
                else:
                    existing = pd.concat(
                        [existing, row.to_frame().T],
                        ignore_index=True
                    )

            st.session_state.notices_df = existing

        st.session_state.latest_upload = new_df

    st.success("Notices processed successfully")

    # -------- CURRENT UPLOAD --------
    st.subheader("📄 Current Upload Summary")
    st.dataframe(new_df, use_container_width=True)

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        new_df.to_excel(writer, index=False)
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

        chart = (
            alt.Chart(pie_df)
            .mark_arc()
            .encode(
                theta="Count:Q",
                color=alt.Color("Status:N", scale=alt.Scale(scheme="blues")),
                tooltip=["Status", "Count"]
            )
            .properties(height=220)
        )

        st.altair_chart(chart, use_container_width=True)

# ---------------- NOTICE REGISTER ----------------
st.divider()

if st.button("📂 View / Update Notice Register"):
    df = st.session_state.notices_df

    st.subheader("📁 Notice Register")
    st.dataframe(df, use_container_width=True)

    st.subheader("✏️ Update Status")

    ref_id = st.selectbox("Select Ref ID", df["Ref ID"].dropna().unique())
    new_status = st.selectbox(
        "New Status",
        ["Pending", "In Progress", "Replied", "Closed"]
    )

    if st.button("Update Status"):
        idx = df[df["Ref ID"] == ref_id].index
        st.session_state.notices_df.loc[idx, "Status"] = new_status
        st.session_state.notices_df.loc[idx, "Last Updated"] = datetime.now().strftime("%d-%m-%Y")
        st.success("Status updated successfully")










