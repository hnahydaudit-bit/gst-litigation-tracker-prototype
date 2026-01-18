import streamlit as st
import pandas as pd
import fitz
import tempfile
import os
import json
import re
import google.generativeai as genai

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

st.set_page_config(page_title="GST Litigation Tracker", page_icon="📂")
st.title("📂 GST Litigation Tracker – Prototype")

uploaded_files = st.file_uploader(
    "Upload GST Notice PDFs",
    type=["pdf"],
    accept_multiple_files=True
)

def extract_text_from_pdf(path):
    text = ""
    with fitz.open(path) as doc:
        for p in doc:
            text += p.get_text()
    return text

def extract_with_ai(docs):
    prompt = f"""
    Extract GST notice details and return JSON array with:
    Entity Name, GSTIN, Notice Type, Ref ID, Due Date,
    Financial Year, Total Demand Amount, Source
    Documents: {json.dumps(docs)}
    Return ONLY JSON.
    """

    model = genai.GenerativeModel("models/gemini-2.5-flash")
    resp = model.generate_content(prompt)
    data = resp.candidates[0].content.parts[0].text

    match = re.search(r"\[.*\]", data, re.DOTALL)
    return json.loads(match.group(0)) if match else []

if uploaded_files:
    docs = []

    for f in uploaded_files:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(f.read())
            path = tmp.name

        text = extract_text_from_pdf(path)
        docs.append({"source": f.name, "text": text})
        os.remove(path)

    results = extract_with_ai(docs)
    df = pd.DataFrame(results)

    st.success("Notices processed successfully!")
    st.dataframe(df)

    st.download_button(
        "Download Excel",
        df.to_excel(index=False),
        file_name="Litigation_Tracker.xlsx"
    )
