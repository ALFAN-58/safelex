import streamlit as st
from pypdf import PdfReader
import re
import hashlib
import json
from datetime import datetime
from ics import Calendar, Event
import plotly.express as px
import plotly.graph_objects as go
from dateutil import parser as date_parser
from google import genai

# Optional local DOCX support
try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

st.set_page_config(
    page_title="SafeLex | Legal Intelligence Workspace",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 1. DESIGN SYSTEM & EXECUTIVE STYLING (CSS)
# ==============================================================================
st.markdown("""
<style>
    .stApp {
        background-color: #F7F9FC;
        color: #142A4D;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .block-container {
        max-width: 1320px !important;
        padding-top: 1.5rem !important;
        padding-bottom: 4rem !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    p, li, .stMarkdown { font-size: 15px !important; line-height: 1.6 !important; color: #142A4D; }
    h1 { font-size: 28px !important; font-weight: 800 !important; color: #142A4D !important; }
    h2 { font-size: 20px !important; font-weight: 700 !important; color: #142A4D !important; margin-top: 0.4rem !important; }

    .top-navbar {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;
        padding: 14px 20px; display: flex; align-items: center; justify-content: space-between;
        box-shadow: 0 1px 3px rgba(20, 42, 77, 0.04); margin-bottom: 12px;
    }
    .brand-wrap { display: flex; align-items: center; gap: 14px; }
    .brand-logo-svg {
        background: linear-gradient(135deg, #142A4D 0%, #315D96 100%);
        width: 42px; height: 42px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
    }
    .brand-title { font-size: 22px; font-weight: 800; color: #142A4D; margin: 0; }
    .brand-tagline { font-size: 12.5px; color: #64748B; margin: 0; }
    
    .nav-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .privacy-pill {
        background-color: #E6F4EA; color: #25836B; border: 1px solid #A7F3D0;
        padding: 4px 12px; border-radius: 9999px; font-size: 12.5px; font-weight: 600;
    }

    .amber-notice {
        background-color: #FFF4D6; border: 1px solid #FDE68A; color: #78350F;
        padding: 10px 16px; border-radius: 8px; font-size: 13px; font-weight: 500;
        margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important; padding: 18px 22px !important;
        box-shadow: 0 1px 4px rgba(20, 42, 77, 0.02) !important; margin-bottom: 14px !important;
    }

    .fmt-chip {
        background-color: #F0F5FF; color: #315D96; border: 1px solid #BFDBFE;
        border-radius: 4px; padding: 2px 6px; font-size: 11.5px; font-weight: 700; margin-right: 4px;
    }

    /* Executive Finding Card */
    .finding-card {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 18px 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(20, 42, 77, 0.03);
    }
    .badge-high { background-color: #FEE2E2; color: #991B1B; padding: 3px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 700; }
    .badge-medium { background-color: #FEF3C7; color: #92400E; padding: 3px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 700; }
    .badge-low { background-color: #E0E7FF; color: #3730A3; padding: 3px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 700; }
    .party-chip { background-color: #F1F5F9; color: #475569; padding: 3px 8px; border-radius: 4px; font-size: 11.5px; font-weight: 600; }
    
    .redline-box {
        background-color: #F8FAFC; border-left: 3px solid #315D96; border-radius: 4px;
        padding: 10px 14px; margin-top: 10px;
    }

    button[kind="secondary"] {
        background-color: #FFFFFF !important; color: #315D96 !important; border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important; font-size: 13.5px !important; font-weight: 500 !important;
        padding: 8px 12px !important;
    }
    button[kind="secondary"]:hover { background-color: #F0F5FF !important; border-color: #315D96 !important; color: #142A4D !important; }

    button[kind="primary"] {
        background-color: #315D96 !important; color: #FFFFFF !important; border: none !important;
        border-radius: 8px !important; font-size: 14px !important; font-weight: 600 !important; padding: 10px 20px !important;
    }
    button[kind="primary"]:hover { background-color: #142A4D !important; color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# SAMPLE CONTRACT PRESETS (Instant 1-Click Demo)
# ==============================================================================
SAMPLE_CONTRACTS = {
    "None": "",
    "Vendor SaaS Agreement (Unbalanced Auto-Renewal & Indemnity)": """--- [Page 1] ---
MASTER SERVICES AND CLOUD LICENSE AGREEMENT
This Agreement is entered into on January 15, 2026, by and between CloudVendor Inc. ("Vendor") and Client Corp ("Customer").
1. TERM AND AUTOMATIC RENEWAL. The initial term of this Agreement shall be twelve (12) months. Upon expiration of the initial term, this Agreement shall automatically renew for successive terms of 24 months unless Customer provides written notice of termination at least 90 days prior to the expiration of the current term. 
2. UNILATERAL MODIFICATIONS. Vendor reserves the right, in its sole discretion and at any time, to modify the fees, subscription pricing, service features, and terms upon 10 days notice published on Vendor's website.
--- [Page 2] ---
3. FEES AND PAYMENT TERMS. Customer shall pay the annual subscription fee of $48,000 USD within 15 days of invoice. All late payments shall incur a penalty fee of 5% per month or the highest rate permitted by law.
4. INDEMNIFICATION. Customer agrees to defend, indemnify, and hold harmless Vendor, its officers, directors, employees, and agents from and against any and all claims, damages, liabilities, losses, costs, and expenses (including attorney fees) arising from Customer's use of the service.
5. ARBITRATION AND JURY WAIVER. Any controversy or dispute arising out of this contract shall be settled exclusively by confidential binding arbitration in Delaware. Customer hereby irrevocably waives any right to a trial by jury or class action representation.
--- [Page 3] ---
6. TERMINATION FOR CONVENIENCE. Vendor may terminate this Agreement without cause at any time by giving Customer 7 days written notice. In the event Customer terminates before term expiration, Customer shall pay an early termination fee equal to 100% of the remaining contract value as liquidated damages.
7. GOVERNING LAW. This Agreement shall be governed by the laws of the State of Delaware without regard to conflict of law principles.""",

    "Freelance Consulting Agreement (IP Assignment & Net-60)": """--- [Page 1] ---
INDEPENDENT CONSULTING AGREEMENT
This Agreement is made as of March 1, 2026, by and between MediaCorp ("Client") and Consultant ("Contractor").
1. SERVICES AND COMPENSATION. Client shall pay Contractor the sum of $8,500 USD upon completion of Deliverables. Payment terms are Net-60 business days following Client's written approval of invoice.
2. OWNERSHIP AND IP ASSIGNMENT. Contractor hereby irrevocably assigns and transfers to Client all right, title, and interest worldwide in and to all work product, inventions, designs, and materials created during the term.
--- [Page 2] ---
3. NON-COMPETE RESTRICTION. For a period of 24 months following termination of this Agreement, Contractor shall not provide any consulting services, directly or indirectly, to any entity operating in the digital media space worldwide.
4. TERMINATION. Client may terminate this agreement at any time without cause upon 24 hours notice. Contractor may only terminate upon 60 days advance written notice."""
}

# ==============================================================================
# PARSER & DETERMINISTIC RISK ENGINES
# ==============================================================================
def extract_text_from_file(file_bytes, filename):
    extracted = ""
    filename_lower = filename.lower()
    ext = filename_lower.split(".")[-1].upper() if "." in filename else "FILE"

    if filename_lower.endswith(".pdf"):
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        for page_idx, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted += f"\n--- [Page {page_idx + 1}] ---\n" + page_text
        return extracted, page_count, "PDF"

    elif filename_lower.endswith(".docx"):
        if not HAS_DOCX:
            return "ERROR_MISSING_DOCX", 0, "DOCX"
        import io
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        
        chunk_words = []
        page_num = 1
        for para in paragraphs:
            chunk_words.append(para)
            if len(" ".join(chunk_words).split()) >= 350:
                extracted += f"\n--- [Page {page_num}] ---\n" + "\n".join(chunk_words) + "\n"
                chunk_words = []
                page_num += 1
        if chunk_words:
            extracted += f"\n--- [Page {page_num}] ---\n" + "\n".join(chunk_words) + "\n"
            page_num += 1
        total_pages = max(1, page_num - 1)
        return extracted, total_pages, "DOCX"

    elif filename_lower.endswith((".txt", ".md")):
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        lines = [line for line in raw_text.splitlines() if line.strip()]
        chunk_lines = []
        page_num = 1
        for line in lines:
            chunk_lines.append(line)
            if len(" ".join(chunk_lines).split()) >= 350:
                extracted += f"\n--- [Page {page_num}] ---\n" + "\n".join(chunk_lines) + "\n"
                chunk_lines = []
                page_num += 1
        if chunk_lines:
            extracted += f"\n--- [Page {page_num}] ---\n" + "\n".join(chunk_lines) + "\n"
            page_num += 1
        total_pages = max(1, page_num - 1)
        return extracted, total_pages, ext

    return "", 0, ext

RISK_RULES = [
    {"id": "auto_renewal", "label": "Automatic renewal", "severity": 3,
     "pattern": r"\b(auto(?:matic(?:ally)?)?[\s-]*renew\w*|renews?\s+automatically)\b",
     "why": "The contract continues unless you cancel within a narrow notice window."},
    {"id": "unilateral_change", "label": "One-sided changes", "severity": 3,
     "pattern": r"\b(unilateral\w*|sole discretion|at any time.{0,40}modify|may modify)\b",
     "why": "The counterparty can change terms or pricing without your prior written agreement."},
    {"id": "arbitration", "label": "Arbitration / jury waiver", "severity": 2,
     "pattern": r"\b(arbitration|waive\w* .{0,20}jury|class action waiver)\b",
     "why": "You may surrender your constitutional right to sue in court or join class actions."},
    {"id": "indemnity", "label": "Unilateral indemnification", "severity": 3,
     "pattern": r"\bindemnif\w*\b",
     "why": "You may be forced to pay all of the other party's legal fees and third-party damages."},
    {"id": "penalty", "label": "Liquidated damages or penalties", "severity": 2,
     "pattern": r"\b(late fee|penalt\w*|liquidated damages|early termination fee|forfeit\w*)\b",
     "why": "Imposes extra financial liabilities if you exit early or miss an operational deadline."},
    {"id": "termination", "label": "Termination without cause", "severity": 2,
     "pattern": r"\bterminat\w* .{0,30}without cause\b",
     "why": "The other side can cancel with little warning while holding you to obligations."},
]

NEGATION = re.compile(r"\b(no|not|never|without any|shall not|neither)\b", re.I)

def split_pages(text):
    parts = re.split(r"--- \[Page (\d+)\] ---", text)
    if len(parts) < 3:
        return [(1, text)]
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]

def find_risks(text):
    hits = []
    for page_no, body in split_pages(text):
        for sentence in re.split(r"(?<=[.;])\s+", body):
            sentence = sentence.strip()
            for rule in RISK_RULES:
                if re.search(rule["pattern"], sentence, re.I):
                    if rule["id"] == "penalty" and NEGATION.search(sentence):
                        continue
                    hits.append({**rule, "page": page_no, "quote": sentence[:300]})
    return hits

def risk_score(hits):
    total = sum(h["severity"] for h in hits)
    return min(100, round(total / 20 * 100))

def extract_financials_and_timelines(text):
    money_matches = []
    timeline_matches = []
    pages = split_pages(text)
    
    money_regex = re.compile(r'(?:USD|INR|Rs\.?|\$|₹)\s?\d+(?:,\d+)*(?:\.\d+)?(?:\s?(?:million|billion|lakh|crore|B|M|per month|annually))?', re.IGNORECASE)
    timeline_regex = re.compile(r'\b(?:\d+\s+(?:days|months|years|business days)|within\s+\d+\s+days|by\s+[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})\b', re.IGNORECASE)
    
    for page_no, body in pages:
        for m in money_regex.finditer(body):
            money_matches.append({"text": m.group(0), "page": page_no})
        for t in timeline_regex.finditer(body):
            timeline_matches.append({"text": t.group(0), "page": page_no})
            
    return money_matches, timeline_matches

# ==============================================================================
# UPGRADED GEMINI AI ENGINE (Structured Legal Analysis)
# ==============================================================================
def get_gemini_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def gemini_json(prompt, model="gemini-3.8-flash"):
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.05
            }
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Gemini API Error: {e}")
        return {}

def verify_quote(quote, page_text):
    if not quote or not page_text:
        return False
    norm = lambda s: re.sub(r"[^\w\s]", "", s).lower().strip()
    norm_q = norm(quote)
    norm_body = norm(page_text)
    return norm_q in norm_body or norm_q[:50] in norm_body

def page_text_for(page_no, pages):
    for p_num, body in pages:
        if p_num == page_no:
            return body
    return ""

def top_pages(question, pages, k=4):
    q_words = set(re.findall(r"\w{4,}", question.lower()))
    ranked = sorted(
        pages,
        key=lambda p: len(q_words & set(re.findall(r"\w{4,}", p[1].lower()))),
        reverse=True,
    )
    return ranked[:k]

def stream_gemini_chat(prompt_text, lang="English", model_tag="gemini-3.8-flash"):
    full_prompt = prompt_text
    if lang != "English":
        full_prompt += f"\n\nIMPORTANT: Translate your entire legal response into {lang}."

    try:
        client = get_gemini_client()
        response = client.models.generate_content_stream(
            model=model_tag,
            contents=full_prompt,
            config={"temperature": 0.1}
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f"⚠️ **Gemini API Error:** {e}. Please check your GEMINI_API_KEY in Streamlit Secrets."

# ==============================================================================
# SIDEBAR CONTROLS & DEMO CONTRACTS
# ==============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Engine Settings")
    model_tag = st.selectbox("Gemini Model", options=["gemini-3.8-flash", "gemini-1.5-pro"], index=0)
    target_language = st.selectbox("Language", options=["English", "Hindi (हिंदी)", "Spanish (Español)"], index=0)
    
    st.markdown("---")
    st.markdown("### 🧪 Instant 1-Click Demo")
    st.caption("Don't have a contract handy? Choose a preset to evaluate SafeLex instantly.")
    demo_choice = st.selectbox("Select Sample Agreement", options=list(SAMPLE_CONTRACTS.keys()), index=0)

# ==============================================================================
# TOP NAVBAR
# ==============================================================================
st.markdown("""
<div class="top-navbar">
    <div class="brand-wrap">
        <div class="brand-logo-svg">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L4 5.5V11.5C4 16.8 7.4 21.6 12 23C16.6 21.6 20 16.8 20 11.5V5.5L12 2Z" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="rgba(255,255,255,0.08)"/>
                <path d="M12 7V16M8.5 10.5H15.5M8.5 10.5L7 13.5H10L8.5 10.5ZM15.5 10.5L14 13.5H17L15.5 10.5ZM9.5 16H14.5" stroke="#FFF4D6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div>
            <p class="brand-title">SafeLex AQ Legal Intelligence</p>
            <p class="brand-tagline">Automated Contract Triage & Executive Redline Workspace</p>
        </div>
    </div>
    <div class="nav-badges">
        <span class="privacy-pill">🛡️ Zero-Retention Document Sandbox</span>
    </div>
</div>

<div class="amber-notice">
    <span>⚠️ <b>Regulatory Notice:</b> SafeLex provides automated plain-language legal triage and drafting assistance, not formal legal representation.</span>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# DOCUMENT INGESTION
# ==============================================================================
st.markdown("## 📄 Document Ingestion & Triage")
st.markdown("Upload any agreement (PDF, DOCX, TXT) or pick a sample agreement from the sidebar to inspect risk exposure and negotiation points.")

uploaded_file = st.file_uploader("Upload Legal Document", type=["pdf", "docx", "txt", "md"], label_visibility="collapsed")

doc_text = ""
doc_name = ""
doc_pages_count = 0
doc_fmt = "DEMO"

if uploaded_file:
    file_bytes = uploaded_file.getvalue()
    doc_text, doc_pages_count, doc_fmt = extract_text_from_file(file_bytes, uploaded_file.name)
    doc_name = uploaded_file.name
elif demo_choice != "None":
    doc_text = SAMPLE_CONTRACTS[demo_choice]
    doc_name = demo_choice
    doc_pages_count = len(split_pages(doc_text))
    doc_fmt = "SAMPLE"

if doc_text:
    st.markdown(f"**Loaded Agreement:** `{doc_name}` &nbsp;•&nbsp; <span class='fmt-chip'>{doc_fmt}</span> &nbsp;•&nbsp; **{doc_pages_count} pages detected**", unsafe_allow_html=True)
    
    st.write("")
    run_triage = st.button("🚀 Run Full Automated Triage", type="primary")

    if run_triage or st.session_state.get("triage_ran", False):
        st.session_state["triage_ran"] = True
        
        pages = split_pages(doc_text)
        risk_hits = find_risks(doc_text)
        score = risk_score(risk_hits)
        money_list, timeline_list = extract_financials_and_timelines(doc_text)

        st.markdown("---")
        st.markdown(f"## 📊 Triage Executive Dashboard: {doc_name}")

        # Urgent Banner
        high_sev_hits = [h for h in risk_hits if h["severity"] == 3]
        top_verdicts = high_sev_hits[:3] if high_sev_hits else risk_hits[:3]
        if top_verdicts:
            verdict_items = "".join([f"<p style='margin: 4px 0;'>• <b>{v['label']}</b> (Page {v['page']}) — {v['why']}</p>" for v in top_verdicts])
            st.markdown(f"""
            <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; color: #991B1B;">
                <b style="font-size: 15px;">🛑 Immediate Red Flags (Review Before Signing):</b>
                {verdict_items}
            </div>
            """, unsafe_allow_html=True)

        sev_counts = {
            "High": len([h for h in risk_hits if h["severity"] == 3]),
            "Medium": len([h for h in risk_hits if h["severity"] == 2]),
            "Low": len([h for h in risk_hits if h["severity"] == 1])
        }
        
        col_chart1, col_chart2 = st.columns([1, 1], vertical_alignment="center")
        with col_chart1:
            fig_risk = px.bar(
                x=["High Severity", "Medium Severity", "Low Severity"],
                y=[sev_counts["High"], sev_counts["Medium"], sev_counts["Low"]],
                color=["High Severity", "Medium Severity", "Low Severity"],
                color_discrete_sequence=["#B91C1C", "#D97706", "#25836B"]
            )
            fig_risk.update_layout(
                title_text=f"<b>Predatory Risk Exposure: {score}%</b>",
                showlegend=False,
                margin=dict(t=40, b=10, l=10, r=10),
                height=260,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis_title="",
                yaxis_title="Flagged Clauses",
                yaxis=dict(range=[0, max(5, max(sev_counts.values()) + 2)], dtick=1)
            )
            st.plotly_chart(fig_risk, use_container_width=True)

        with col_chart2:
            max_elem = max(len(risk_hits), len(money_list), len(timeline_list))
            fig_metrics = px.bar(
                x=["Predatory Risks", "Financial Terms", "Deadlines & Dates"],
                y=[len(risk_hits), len(money_list), len(timeline_list)],
                color=["Predatory Risks", "Financial Terms", "Deadlines & Dates"],
                color_discrete_sequence=["#315D96", "#25836B", "#D97706"]
            )
            fig_metrics.update_layout(
                title_text="<b>Contract Elements Extraction</b>",
                showlegend=False,
                margin=dict(t=40, b=10, l=10, r=10),
                height=260,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis_title="",
                yaxis_title="Count",
                yaxis=dict(range=[0, max(5, max_elem + 2)], dtick=1)
            )
            st.plotly_chart(fig_metrics, use_container_width=True)

        # Tabs Layout
        tab_summary, tab_risk_comp, tab_finance_comp, tab_timeline_comp, tab_qa, tab_letter = st.tabs([
            "📊 Executive Triage & Redlines",
            "⚠️ Risk Compartment",
            "💳 Financial Terms",
            "📅 Key Deadlines & Calendar",
            "💬 Document Q&A",
            "✉️ Dispute / Notice Generator"
        ])

        # TAB 1: UPGRADED EXECUTIVE SUMMARY & REDLINES
        with tab_summary:
            st.markdown("### Executive Legal Analysis & Redline Action Plan")
            st.caption("AI-powered legal analysis providing plain-language translations, party bias assessment, and exact counter-proposals.")

            if st.button("Generate Executive Analysis", type="primary", key="btn_modular_sum"):
                with st.spinner("Analyzing contract structure and drafting redlines with Gemini..."):
                    prompt = f"""You are a senior corporate legal counsel triaging an agreement for a client.
Analyze the provided contract text with strict fidelity.
Return valid JSON matching this exact structure:
{{
  "document_type": "e.g., Master Services Agreement, Commercial Lease, Non-Disclosure Agreement",
  "overall_verdict": "2 to 3 sentences summarizing overall fairness, commercial balance, and primary pitfalls for the client.",
  "key_findings": [
    {{
      "category": "One of: Termination & Renewal, Financial & Fees, Indemnification & Liability, Operational Obligation, Restrictive Covenant",
      "clause_title": "Clear short title of the provision",
      "plain_english": "Plain-language explanation of what this provision means in everyday business terms without legal jargon.",
      "party_favored": "Favors Counterparty / Balanced / Favors You",
      "risk_level": "High / Medium / Low",
      "quote": "Exact verbatim sentence or phrase from the document text",
      "page": 1,
      "counter_proposal": "Specific, actionable counter-clause or redline wording to suggest in negotiations."
    }}
  ]
}}
Do not invent quotes or page numbers.
TEXT:
{doc_text[:80000]}"""
                    res = gemini_json(prompt, model_tag)
                    st.session_state["modular_cache"] = res

            cached_res = st.session_state.get("modular_cache", {})
            
            if cached_res:
                doc_type = cached_res.get("document_type", "Standard Agreement")
                verdict = cached_res.get("overall_verdict", "Analysis complete.")
                
                st.markdown(f"""
                <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                        <span style="font-size: 13px; font-weight: 700; color: #64748B; text-transform: uppercase;">Identified Document Classification</span>
                        <span style="background-color: #F0F5FF; color: #315D96; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 13px;">{doc_type}</span>
                    </div>
                    <p style="font-size: 16px; font-weight: 600; color: #142A4D; margin: 0 0 6px 0;">Executive Verdict:</p>
                    <p style="font-size: 14.5px; color: #334155; margin: 0;">{verdict}</p>
                </div>
                """, unsafe_allow_html=True)
                
                findings = cached_res.get("key_findings", [])
                st.markdown("#### Key Provisions, Plain-Language Meaning & Redlines")
                
                for item in findings:
                    p_num = item.get("page", 1)
                    quote = item.get("quote", "")
                    p_body = page_text_for(p_num, pages)
                    is_verified = verify_quote(quote, p_body)
                    badge_verified = "🛡️ Verified Source" if is_verified else "⚠️ Unverified Quote"
                    
                    risk = item.get("risk_level", "Medium")
                    badge_class = "badge-high" if risk == "High" else ("badge-medium" if risk == "Medium" else "badge-low")
                    
                    st.markdown(f"""
                    <div class="finding-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <div>
                                <span class="{badge_class}">{risk.upper()} RISK</span>
                                &nbsp;<b style="font-size: 16px; color: #142A4D;">{item.get('clause_title')}</b>
                                <span style="color: #64748B; font-size: 12.5px;">({item.get('category')})</span>
                            </div>
                            <span class="party-chip">{item.get('party_favored')}</span>
                        </div>
                        <p style="margin: 0 0 8px 0; font-size: 14.5px;"><b>Plain Meaning:</b> {item.get('plain_english')}</p>
                        <p style="margin: 0 0 6px 0; color: #64748B; font-size: 13.5px;">
                            <b>Document Excerpt:</b> &ldquo;{quote}&rdquo; &nbsp;•&nbsp; <i>Page {p_num} ({badge_verified})</i>
                        </p>
                        <div class="redline-box">
                            <b style="color: #315D96; font-size: 13px;">💡 Recommended Redline / Negotiation Counter-Proposal:</b>
                            <p style="margin: 4px 0 0 0; font-size: 13.5px; color: #1E293B;">{item.get('counter_proposal')}</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Click **'Generate Executive Analysis'** above to run the legal counsel engine.")

        # TAB 2: DETERMINISTIC RISK COMPARTMENT
        with tab_risk_comp:
            with st.container(border=True):
                st.markdown(f"### ⚠️ Flagged Risk Compartment (Exposure Score: {score}%)")
                st.write("Deterministic pattern matching highlights aggressive or one-sided contract mechanisms.")
                if risk_hits:
                    for idx, h in enumerate(risk_hits):
                        with st.expander(f"🔴 [{h['label']}] Severity {h['severity']}/3 — Page {h['page']}"):
                            st.markdown(f"**Exact Clause Quote:**")
                            st.markdown(f"> \"{h['quote']}\"")
                            st.markdown(f"**Commercial Impact:** {h['why']}")
                            st.markdown(f"**Source Grounding:** 🛡️ Extracted from Page {h['page']}")
                else:
                    st.success("No heavy predatory risk markers detected by deterministic rules.")

        # TAB 3: FINANCIAL OVERVIEW
        with tab_finance_comp:
            with st.container(border=True):
                st.markdown("### 💳 Financial Sums & Pricing Compartment")
                st.caption("Extracted explicit payment sums, fee schedules, and deposits.")
                if money_list:
                    for m in money_list:
                        st.markdown(f"- 💵 **{m['text']}** (Page {m['page']})")
                else:
                    st.info("No explicit monetary sums detected.")

        # TAB 4: TIMELINES & CALENDAR EXPORT
        with tab_timeline_comp:
            with st.container(border=True):
                st.markdown("### 📅 Critical Timelines & Calendar Sync")
                st.caption("Extracted contractual notice periods, renewal windows, and deadlines.")
                
                if timeline_list:
                    for t in timeline_list:
                        st.markdown(f"- ⏱️ **{t['text']}** (Page {t['page']})")
                else:
                    st.info("No explicit time durations detected automatically.")

                st.markdown("---")
                cal = Calendar()
                event = Event()
                event.name = f"Notice / Renewal Deadline: {doc_name}"
                event.begin = datetime.now()
                event.description = f"Critical legal deadline tracked by SafeLex AQ for {doc_name}."
                cal.events.add(event)
                st.download_button(
                    "📅 Download Calendar Reminder (.ics)",
                    str(cal),
                    file_name="safelex_deadline.ics",
                    mime="text/calendar",
                    use_container_width=True
                )

        # TAB 5: DOCUMENT-GROUNDED Q&A CHAT
        with tab_qa:
            with st.container(border=True):
                st.markdown("### 💬 Document-Grounded Q&A")
                st.caption("Ask specific questions about this agreement. Answers are strictly grounded in contract text.")
                user_q = st.text_input("Ask a question about this document...", key="doc_chat_in")
                if st.button("Send ↗", type="primary", key="doc_chat_btn"):
                    if user_q.strip():
                        with st.spinner("Retrieving relevant pages and consulting Gemini..."):
                            relevant_pages = top_pages(user_q, pages, k=3)
                            context_blob = "\n".join([f"--- [Page {p[0]}] ---\n{p[1]}" for p in relevant_pages])
                            
                            prompt = f"""You are a specialized legal document triage assistant for SafeLex AQ. 
Your ONLY job is to answer questions based strictly on the provided contract text.
If the user's question is off-topic, random, nonsense, or unrelated to legal matters/this document, reply: "I can only answer questions related to this legal document. Please ask a question about the contract text."

Question: {user_q}

Contract Text:
{context_blob}"""
                            st.write_stream(stream_gemini_chat(prompt, target_language, model_tag))

        # TAB 6: FORMAL ACTION LETTER GENERATOR
        with tab_letter:
            with st.container(border=True):
                st.markdown("### ✉️ Formal Dispute or Cancellation Notice Generator")
                st.caption("Auto-draft a legally grounded letter referencing exact contract terms.")
                
                c_name = st.text_input("Your Name / Organization", value="Client Representative")
                c_date = st.text_input("Notice Date", value=datetime.now().strftime("%Y-%m-%d"))
                c_ref = st.text_input("Contract / Reference Number", value="REF-2026-001")
                c_amt = st.text_input("Disputed Amount (if any)", value="$0.00")
                letter_type = st.selectbox("Letter Purpose", ["Contract Termination & Non-Renewal Notice", "Dispute of Unauthorized Fees", "Refund Request"])
                
                if st.button("Draft Formal Notice", type="primary"):
                    with st.spinner("Drafting formal letter from verified clauses using Gemini..."):
                        letter_prompt = f"Draft a formal {letter_type} letter from {c_name}, dated {c_date}, referencing account {c_ref} and amount {c_amt}. Cite relevant clauses and page numbers from this agreement:\n\n{doc_text[:20000]}"
                        st.write_stream(stream_gemini_chat(letter_prompt, target_language, model_tag))
