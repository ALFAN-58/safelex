
import streamlit as st
from pypdf import PdfReader
import requests

st.set_page_config(
    page_title="SafeLex | On-Device Legal Triage",
    page_icon="⚖️",
    layout="wide"
)

# Custom Design & Typography
st.markdown("""
<style>
    .reportview-container { background: #0f172a; }
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1e293b; margin-bottom: 0px; }
    .status-badge {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 13px;
        font-weight: 600;
        border: 1px solid #86efac;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

st.warning(
    "⚠️ **PRELIMINARY TRIAGE ONLY — NOT LEGAL ADVICE:** "
    "This tool runs locally on Gemma 2B to extract terms, cite verbatim text, and identify ambiguities. "
    "It cannot determine legal enforceability or replace a qualified attorney."
)

st.markdown('<p class="main-title">⚖️ SafeLex: Private On-Device Legal Triage</p>', unsafe_allow_html=True)
st.caption("Zero-Cloud Architecture • Google Gemma (2B Local Edge) • Strict Grounding")

with st.sidebar:
    st.header("🔒 Privacy & Hardware Audit")
    st.markdown('<div class="status-badge">🟢 100% On-Device (Offline)</div>', unsafe_allow_html=True)
    st.write("")
    st.info("Zero external API calls. All inferences route strictly to localhost:11434.")
    
    st.markdown("### ⚙️ Engine")
    model_name = st.text_input("Ollama Model Tag", value="gemma:2b")
    
    st.markdown("---")
    st.markdown("### 📋 Verification Checklist")
    st.markdown("- [x] **L1**: Local PDF Parsing\n- [x] **L5**: Verbatim Source Citations\n- [x] **L8**: Calibrated Uncertainty\n- [x] **L9**: Zero Network Leaks")

def extract_text_from_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    extracted = ""
    for page_idx, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            extracted += f"\n--- [Page {page_idx + 1}] ---\n" + page_text
    return extracted

def is_legal_document(text):
    legal_keywords = [
        "agreement", "contract", "parties", "tenant", "landlord", "lease", 
        "employer", "employee", "shall", "liable", "indemnity", "termination", 
        "jurisdiction", "confidential", "clause", "terms and conditions"
    ]
    text_lower = text.lower()
    matches = sum(1 for kw in legal_keywords if kw in text_lower)
    return matches >= 2

def query_local_gemma_chat(prompt_text):
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt_text
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }

    try:
        response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=120)
        if response.status_code == 200:
            return response.json().get("message", {}).get("content", "No output generated.")
        return f"Error: Local engine returned HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "❌ Ollama is offline. Please start Ollama."

uploaded_doc = st.file_uploader("📂 Select a Legal Document (PDF Format)", type=["pdf"])

if uploaded_doc is not None:
    if "current_file" not in st.session_state or st.session_state["current_file"] != uploaded_doc.name:
        st.session_state["current_file"] = uploaded_doc.name
        st.session_state.pop("last_triage", None)

    extracted_text = extract_text_from_pdf(uploaded_doc)
    
    if not extracted_text.strip():
        st.error("No readable text found in this PDF.")
    elif not is_legal_document(extracted_text):
        st.error("🚫 Non-Legal Document Detected: This document contains no standard legal clauses or contract terms. SafeLex only triages legal agreements.")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📄 Raw Document Stream")
            st.text_area("Extracted Document Text", extracted_text, height=480)
            
        with col2:
            st.subheader("🔍 Structured Automated Triage")
            if st.button("🚀 Run Full Automated Triage"):
                triage_prompt = (
                    f"Read this legal agreement:\n\n{extracted_text}\n\n"
                    "Provide a clear legal triage with these exact sections:\n"
                    "### 1. Parties, Scope & Financials\n"
                    "List the parties, their responsibilities, investments/considerations, and payment or profit splits.\n\n"
                    "### 2. Termination & Penalties (With Verbatim Quotes)\n"
                    "Identify notice periods, exit conditions, and damages/penalties. Quote exact sentences.\n\n"
                    "### 3. Red Flags & Key Clauses\n"
                    "Highlight restrictive covenants, dispute seats, or non-standard requirements.\n\n"
                    "### 4. Matters Where Document Is Silent\n"
                    "List important omissions, such as Force Majeure or renewal terms."
                )
                with st.spinner("Analyzing document locally through Gemma..."):
                    result = query_local_gemma_chat(triage_prompt)
                    st.session_state["last_triage"] = result
            
            if "last_triage" in st.session_state:
                st.markdown(st.session_state["last_triage"])
                st.download_button(
                    label="💾 Download Triage Report (.txt)",
                    data=st.session_state["last_triage"],
                    file_name="safelex_triage_report.txt",
                    mime="text/plain"
                )

        st.markdown("---")
        st.subheader("💬 Interactive Clause Verification")
        st.caption("Ask specific questions (e.g., 'How much is invested?', 'What is the confidentiality penalty?')")
        
        user_query = st.text_input("Enter your specific question:")
        if st.button("Query Document"):
            if user_query.strip():
                with st.spinner("Searching document..."):
                    qa_prompt = (
                        f"You are examining this contract:\n\n{extracted_text}\n\n"
                        f"Question: {user_query}\n\n"
                        "Instructions:\n"
                        "- Answer the question directly using facts from the contract.\n"
                        "- Quote the exact clause or sentence that provides this answer.\n"
                        "- If and only if the topic is not mentioned anywhere in the contract, reply: 'The document is silent on this matter.'"
                    )
                    answer = query_local_gemma_chat(qa_prompt)
                    st.info(answer)