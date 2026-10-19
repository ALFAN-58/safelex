import streamlit as st
from pypdf import PdfReader
import re
import sqlite3
import hashlib
import os
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
# 1. DATABASE CONNECTION POOLING & STORAGE
# ==============================================================================
DB_FILE = "safelex_local_vault.db"

@st.cache_resource
def get_db():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_local_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            doc_name TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            category TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            page_count INTEGER NOT NULL,
            file_format TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)
    conn.commit()

init_local_db()

def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split(":")
        salt = bytes.fromhex(salt_hex)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return digest.hex() == digest_hex
    except Exception:
        return False

def register_user(username, password):
    username = username.strip().lower()
    if not username or len(password) < 8:
        return False, "Username required and password must be at least 8 characters."
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ?", (username,))
    if c.fetchone():
        return False, "Username already exists. Please sign in."
    c.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    return True, "Account securely created!"

def authenticate_user(username, password):
    username = username.strip().lower()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if row and verify_password(password, row[0]):
        return True
    return False

def auto_assign_category(doc_name, text):
    lower_text = (doc_name + " " + text[:1500]).lower()
    if any(k in lower_text for k in ["lease", "rent", "tenant", "landlord", "apartment"]):
        return "Apartment"
    elif any(k in lower_text for k in ["employment", "employer", "salary", "job", "non-compete"]):
        return "Job"
    elif any(k in lower_text for k in ["phone", "internet", "broadband", "mobile", "verizon"]):
        return "Phone and Internet"
    elif any(k in lower_text for k in ["loan", "credit", "mortgage", "lender", "borrower"]):
        return "Loans"
    elif any(k in lower_text for k in ["subscription", "membership", "netflix", "gym", "renewal"]):
        return "Subscriptions"
    return "Other"

def save_document_to_vault(username, doc_name, file_hash, category, text, pages, fmt):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM documents WHERE username = ? AND file_hash = ?", (username, file_hash))
    if not c.fetchone():
        c.execute(
            "INSERT INTO documents (username, doc_name, file_hash, category, extracted_text, page_count, file_format, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (username, doc_name, file_hash, category, text, pages, fmt, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

def get_user_documents(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, doc_name, category, page_count, file_format, uploaded_at FROM documents WHERE username = ? ORDER BY id DESC", (username,))
    rows = c.fetchall()
    return [{"id": r[0], "doc_name": r[1], "category": r[2], "pages": r[3], "format": r[4], "date": r[5]} for r in rows]

def get_document_by_id(doc_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT extracted_text, page_count, category, file_format, doc_name FROM documents WHERE id = ?", (doc_id,))
    return c.fetchone()

# ==============================================================================
# 2. DESIGN SYSTEM (CSS)
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

    p, li, .stMarkdown { font-size: 15.5px !important; line-height: 1.6 !important; color: #142A4D; }
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
    .user-pill {
        background-color: #142A4D; color: #FFFFFF; padding: 4px 12px;
        border-radius: 9999px; font-size: 12.5px; font-weight: 600;
    }

    .amber-notice {
        background-color: #FFF4D6; border: 1px solid #FDE68A; color: #78350F;
        padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 500;
        margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF !important; border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important; padding: 16px 20px !important;
        box-shadow: 0 1px 4px rgba(20, 42, 77, 0.02) !important; margin-bottom: 12px !important;
    }

    .fmt-chip {
        background-color: #F0F5FF; color: #315D96; border: 1px solid #BFDBFE;
        border-radius: 4px; padding: 2px 6px; font-size: 11.5px; font-weight: 700; margin-right: 4px;
    }

    .summary-compartment {
        background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px;
        padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(20, 42, 77, 0.02);
    }

    button[kind="secondary"] {
        background-color: #FFFFFF !important; color: #315D96 !important; border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important; font-size: 13.5px !important; font-weight: 500 !important;
        padding: 8px 12px !important; text-align: left !important; justify-content: flex-start !important;
    }
    button[kind="secondary"]:hover { background-color: #F0F5FF !important; border-color: #315D96 !important; color: #142A4D !important; }

    button[kind="primary"] {
        background-color: #315D96 !important; color: #FFFFFF !important; border: none !important;
        border-radius: 8px !important; font-size: 14px !important; font-weight: 600 !important; padding: 8px 16px !important;
    }
    button[kind="primary"]:hover { background-color: #142A4D !important; color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================
if "logged_in_user" not in st.session_state:
    st.session_state["logged_in_user"] = None
if "selected_doc_id" not in st.session_state:
    st.session_state["selected_doc_id"] = None
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Dashboard"

# ==============================================================================
# AUTHENTICATION GATEWAY
# ==============================================================================
if not st.session_state["logged_in_user"]:
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
                <p class="brand-title">SafeLex v2.6</p>
                <p class="brand-tagline">Multi-File Uploader & Case Comparison Vault.</p>
            </div>
        </div>
        <div class="nav-badges">
            <span class="privacy-pill">🛡️ Secure Local SQLite • Cloud Gemini API</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    _, auth_col, _ = st.columns([1.2, 2, 1.2])
    with auth_col:
        with st.container(border=True):
            st.markdown("## 🔐 Sign in to SafeLex")
            st.caption("Access multi-file uploading, side-by-side comparison, and local vault.")

            tab_login, tab_signup = st.tabs(["🔑 Log In", "✨ Create Account"])

            with tab_login:
                login_user = st.text_input("Username", key="login_u", placeholder="e.g., aditya")
                login_pass = st.text_input("Password", type="password", key="login_p", placeholder="••••••••")
                if st.button("Unlock Workspace ↗", type="primary", use_container_width=True):
                    if authenticate_user(login_user, login_pass):
                        st.session_state["logged_in_user"] = login_user.strip().lower()
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

            with tab_signup:
                new_user = st.text_input("Choose a Username", key="reg_u", placeholder="e.g., aditya")
                new_pass = st.text_input("Choose a Password (Min 8 chars)", type="password", key="reg_p", placeholder="••••••••")
                if st.button("Create Vault Account", type="primary", use_container_width=True):
                    if len(new_pass) < 8:
                        st.warning("Password must be at least 8 characters long.")
                    else:
                        ok, msg = register_user(new_user, new_pass)
                        if ok:
                            st.session_state["logged_in_user"] = new_user.strip().lower()
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
    st.stop()

current_user = st.session_state["logged_in_user"]

# ==============================================================================
# 3. CACHED PARSER & ENGINES
# ==============================================================================
@st.cache_data(show_spinner=False)
def cached_extract_text(file_bytes, filename, file_hash):
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

def is_legal_document(text):
    legal_keywords = [
        "agreement", "contract", "parties", "tenant", "landlord", "lease", 
        "employer", "employee", "shall", "liable", "indemnity", "termination", 
        "jurisdiction", "confidential", "clause", "terms and conditions", "obligations", "governing law"
    ]
    text_lower = text.lower()
    matches = sum(1 for kw in legal_keywords if kw in text_lower)
    return matches >= 2

RISK_RULES = [
    {"id": "auto_renewal", "label": "Automatic renewal", "severity": 3,
     "pattern": r"\b(auto(?:matic(?:ally)?)?[\s-]*renew\w*|renews?\s+automatically)\b",
     "why": "The contract continues unless you cancel within a notice window."},
    {"id": "unilateral_change", "label": "One-sided changes", "severity": 3,
     "pattern": r"\b(unilateral\w*|sole discretion|at any time.{0,40}modify|may modify)\b",
     "why": "The company can change terms without your agreement."},
    {"id": "arbitration", "label": "Arbitration / jury waiver", "severity": 2,
     "pattern": r"\b(arbitration|waive\w* .{0,20}jury|class action waiver)\b",
     "why": "You may give up the right to sue in court."},
    {"id": "indemnity", "label": "Indemnification", "severity": 3,
     "pattern": r"\bindemnif\w*\b",
     "why": "You may have to cover the other party's losses or legal costs."},
    {"id": "penalty", "label": "Fees or penalties", "severity": 2,
     "pattern": r"\b(late fee|penalt\w*|liquidated damages|early termination fee|forfeit\w*)\b",
     "why": "You may pay extra money if you miss a deadline or leave early."},
    {"id": "termination", "label": "Termination without cause", "severity": 2,
     "pattern": r"\bterminat\w* .{0,30}without cause\b",
     "why": "The other side can end the agreement with little warning."},
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
# 4. GEMINI API JSON & STREAMING ENGINES
# ==============================================================================
def get_gemini_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

def gemini_json(prompt, model="gemini-2.5-flash"):
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0
            }
        )
        return json.loads(response.text)
    except Exception:
        return {}

def verify_quote(quote, page_text):
    norm = lambda s: re.sub(r"\s+", " ", s).lower()
    return norm(quote) in norm(page_text)

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

def stream_gemini_chat(prompt_text, lang="English", model_tag="gemini-2.5-flash"):
    full_prompt = prompt_text
    if lang != "English":
        full_prompt += f"\n\nIMPORTANT: Translate your entire response into {lang}."

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
# SIDEBAR NAVIGATION
# ==============================================================================
with st.sidebar:
    st.markdown(f"<div class='user-pill'>👤 Vault: {current_user}</div>", unsafe_allow_html=True)
    if st.button("🚪 Sign Out", key="logout_btn", type="secondary", use_container_width=True):
        st.session_state["logged_in_user"] = None
        st.session_state["selected_doc_id"] = None
        st.rerun()

    st.markdown("---")
    st.markdown("### 🗂️ Situation Folders")
    
    user_docs = get_user_documents(current_user)
    folders = ["Apartment", "Job", "Phone and Internet", "Loans", "Subscriptions", "Other"]
    
    if st.button("📊 Dashboard Home", key="nav_dash", type="secondary", use_container_width=True):
        st.session_state["selected_doc_id"] = None
        st.session_state["active_tab"] = "Dashboard"
        st.rerun()

    if st.button("⚖️ Compare Cases", key="nav_compare", type="secondary", use_container_width=True):
        st.session_state["selected_doc_id"] = None
        st.session_state["active_tab"] = "Compare"
        st.rerun()

    st.write("")
    for folder in folders:
        folder_docs = [d for d in user_docs if d["category"] == folder]
        with st.expander(f"📁 {folder} ({len(folder_docs)})", expanded=False):
            if not folder_docs:
                st.caption("No documents in this folder.")
            else:
                for doc in folder_docs:
                    if st.button(f"📄 {doc['doc_name'][:24]}...", key=f"doc_sel_{doc['id']}", type="secondary", use_container_width=True):
                        st.session_state["selected_doc_id"] = doc["id"]
                        st.session_state["active_tab"] = "DocumentWorkspace"
                        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Engine Settings")
    model_tag = st.selectbox("Gemini Model", options=["gemini-2.5-flash", "gemini-2.5-pro"], index=0)
    target_language = st.selectbox("Language", options=["English", "Hindi (हिंदी)", "Spanish (Español)"], index=0)

# ==============================================================================
# TOP NAVBAR
# ==============================================================================
total_docs_count = len(user_docs)

st.markdown(f"""
<div class="top-navbar">
    <div class="brand-wrap">
        <div class="brand-logo-svg">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L4 5.5V11.5C4 16.8 7.4 21.6 12 23C16.6 21.6 20 16.8 20 11.5V5.5L12 2Z" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" fill="rgba(255,255,255,0.08)"/>
                <path d="M12 7V16M8.5 10.5H15.5M8.5 10.5L7 13.5H10L8.5 10.5ZM15.5 10.5L14 13.5H17L15.5 10.5ZM9.5 16H14.5" stroke="#FFF4D6" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </div>
        <div>
            <p class="brand-title">SafeLex v2.6 Workspace</p>
            <p class="brand-tagline">Multi-File Uploader & Comparison • {total_docs_count} docs stored</p>
        </div>
    </div>
    <div class="nav-badges">
        <span class="user-pill">👤 {current_user}</span>
        <span class="privacy-pill">🛡️ Powered by Gemini API</span>
    </div>
</div>

<div class="amber-notice">
    <span>⚠️ <b>Disclaimer:</b> Plain-language summary, not legal advice. Consult a qualified lawyer for decisions involving rights or money.</span>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# 5. VIEW ROUTERS (DASHBOARD, WORKSPACE, COMPARE)
# ==============================================================================

@st.fragment
def render_dashboard():
    st.markdown("## 📊 Dashboard Home")
    st.caption("Upload multiple documents simultaneously. Hold `Ctrl` or `Cmd` while selecting files to upload more than one at a time, or upload them sequentially.")

    col_up1, col_up2 = st.columns([3, 2], vertical_alignment="center")
    with col_up1:
        st.markdown("### 📥 Multi-File Uploader")
        st.markdown("<span style='font-size:13px; color:#64748B;'>Select and upload multiple PDF, DOCX, TXT, or MD files. Click 'Save Files to Vault' to process them.</span>", unsafe_allow_html=True)
    with col_up2:
        uploaded_files = st.file_uploader("Upload files", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        st.write(f"📁 **{len(uploaded_files)} file(s) selected in queue.**")
        if st.button("🚀 Save Files to Vault", type="primary"):
            processed = st.session_state.setdefault("processed_hashes", set())
            new_saved = 0
            for f in uploaded_files:
                file_bytes = f.getvalue()
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                if file_hash in processed:
                    continue
                processed.add(file_hash)
                text, pages, fmt = cached_extract_text(file_bytes, f.name, file_hash)
                if not text or text == "ERROR_MISSING_DOCX":
                    st.warning(f"Could not read {f.name}.")
                elif not is_legal_document(text):
                    st.warning(f"{f.name} doesn't look like a legal document, so it wasn't saved.")
                else:
                    category = auto_assign_category(f.name, text)
                    save_document_to_vault(current_user, f.name, file_hash, category, text, pages, fmt)
                    new_saved += 1
            if new_saved:
                st.toast(f"Successfully saved {new_saved} document(s) to vault!")
                st.rerun()

    st.write("")
    if not user_docs:
        st.info("No documents uploaded yet. Drop files above to begin.")
    else:
        st.markdown("### 📄 Recent Documents in Vault")
        for doc in user_docs[:6]:
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                st.markdown(f"**{doc['doc_name']}**")
            with c2:
                st.markdown(f"📁 {doc['category']}")
            with c3:
                st.markdown(f"📅 {doc['date']}")
            with c4:
                if st.button("Open", key=f"dash_open_{doc['id']}", type="primary"):
                    st.session_state["selected_doc_id"] = doc["id"]
                    st.session_state["active_tab"] = "DocumentWorkspace"
                    st.rerun()

@st.fragment
def render_compare_view():
    st.markdown("## ⚖️ Side-by-Side Case Comparison")
    st.caption("Select two different documents from your vault to compare risk scores, financial terms, and obligations side by side.")

    if len(user_docs) < 2:
        st.warning("Please upload at least two legal documents to use the comparison feature.")
        return

    doc_options = {f"{d['doc_name']} ({d['category']})": d['id'] for d in user_docs}
    col_sel1, col_sel2 = st.columns(2)
    
    with col_sel1:
        doc_a_label = st.selectbox("Select Case A", options=list(doc_options.keys()), index=0)
    with col_sel2:
        default_idx = 1 if len(doc_options) > 1 else 0
        doc_b_label = st.selectbox("Select Case B", options=list(doc_options.keys()), index=default_idx)

    doc_a_id = doc_options[doc_a_label]
    doc_b_id = doc_options[doc_b_label]

    data_a = get_document_by_id(doc_a_id)
    data_b = get_document_by_id(doc_b_id)

    if not data_a or not data_b:
        st.error("Error loading selected documents.")
        return

    text_a, pages_count_a, cat_a, fmt_a, name_a = data_a[0], data_a[1], data_a[2], data_a[3], data_a[4]
    text_b, pages_count_b, cat_b, fmt_b, name_b = data_b[0], data_b[1], data_b[2], data_b[3], data_b[4]

    risks_a = find_risks(text_a)
    score_a = risk_score(risks_a)
    money_a, timelines_a = extract_financials_and_timelines(text_a)

    risks_b = find_risks(text_b)
    score_b = risk_score(risks_b)
    money_b, timelines_b = extract_financials_and_timelines(text_b)

    st.markdown("---")
    
    cmp_col1, cmp_col2 = st.columns(2)

    with cmp_col1:
        with st.container(border=True):
            st.markdown(f"### 📄 {name_a}")
            st.markdown(f"<span class='fmt-chip'>{fmt_a}</span> Folder: **{cat_a}** &nbsp;•&nbsp; {pages_count_a} pages", unsafe_allow_html=True)
            st.markdown(f"#### 🛑 Risk Exposure Score: {score_a}%")
            st.write(f"**Detected Risk Flags:** {len(risks_a)}")
            for r in risks_a[:3]:
                st.markdown(f"- 🔴 {r['label']} (Page {r['page']})")
            
            st.markdown(f"**Financial References:** {len(money_a)}")
            for m in money_a[:3]:
                st.markdown(f"- 💵 {m['text']}")

    with cmp_col2:
        with st.container(border=True):
            st.markdown(f"### 📄 {name_b}")
            st.markdown(f"<span class='fmt-chip'>{fmt_b}</span> Folder: **{cat_b}** &nbsp;•&nbsp; {pages_count_b} pages", unsafe_allow_html=True)
            st.markdown(f"#### 🛑 Risk Exposure Score: {score_b}%")
            st.write(f"**Detected Risk Flags:** {len(risks_b)}")
            for r in risks_b[:3]:
                st.markdown(f"- 🔴 {r['label']} (Page {r['page']})")
            
            st.markdown(f"**Financial References:** {len(money_b)}")
            for m in money_b[:3]:
                st.markdown(f"- 💵 {m['text']}")

    st.markdown("### 🤖 AI Comparative Verdict")
    if st.button("Run AI Comparative Analysis", type="primary"):
        with st.spinner("Analyzing differences between both cases with Gemini..."):
            compare_prompt = f"""Compare these two legal documents/cases. Highlight key differences in risk, financial terms, and obligations:\n\nCASE A ({name_a}):\n{text_a[:6000]}\n\nCASE B ({name_b}):\n{text_b[:6000]}"""
            st.write_stream(stream_gemini_chat(compare_prompt, target_language, model_tag))

@st.fragment
def render_document_workspace():
    doc_id = st.session_state["selected_doc_id"]
    data = get_document_by_id(doc_id)
    if not data:
        st.error("Document not found.")
        return

    extracted_text, page_count, category, fmt, doc_name = data[0], data[1], data[2], data[3], data[4]
    pages = split_pages(extracted_text)
    
    risk_hits = find_risks(extracted_text)
    score = risk_score(risk_hits)
    money_list, timeline_list = extract_financials_and_timelines(extracted_text)

    if st.button("← Back to Dashboard", type="secondary"):
        st.session_state["selected_doc_id"] = None
        st.session_state["active_tab"] = "Dashboard"
        st.rerun()

    st.markdown(f"## 📄 {doc_name}")
    st.markdown(f"<span class='fmt-chip'>{fmt}</span> Folder: **{category}** &nbsp;•&nbsp; {page_count} pages", unsafe_allow_html=True)

    high_sev_hits = [h for h in risk_hits if h["severity"] == 3]
    top_verdicts = high_sev_hits[:3] if high_sev_hits else risk_hits[:3]
    if top_verdicts:
        verdict_items = "".join([f"<p style='margin: 4px 0;'>• {v['label']} (Page {v['page']})</p>" for v in top_verdicts])
        st.markdown(f"""
        <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; color: #991B1B;">
            <b>🛑 Before you sign:</b>
            {verdict_items}
        </div>
        """, unsafe_allow_html=True)

    sev_counts = {"High": len([h for h in risk_hits if h["severity"] == 3]),
                  "Medium": len([h for h in risk_hits if h["severity"] == 2]),
                  "Low": len([h for h in risk_hits if h["severity"] == 1])}
    
    col_chart1, col_chart2 = st.columns([1, 1], vertical_alignment="center")
    with col_chart1:
        fig_risk = px.bar(
            x=["High Severity", "Medium Severity", "Low Severity"],
            y=[sev_counts["High"], sev_counts["Medium"], sev_counts["Low"]],
            color=["High Severity", "Medium Severity", "Low Severity"],
            color_discrete_sequence=["#B91C1C", "#D97706", "#25836B"]
        )
        fig_risk.update_layout(
            title_text=f"<b>Risk Exposure Score: {score}% (Severity Breakdown)</b>",
            showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10),
            height=260,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title="",
            yaxis_title="Count"
        )
        st.plotly_chart(fig_risk, use_container_width=True)

    with col_chart2:
        fig_metrics = px.bar(
            x=["Risk Flags", "Financial Sums", "Deadlines"],
            y=[len(risk_hits), len(money_list), len(timeline_list)],
            color=["Risk Flags", "Financial Sums", "Deadlines"],
            color_discrete_sequence=["#315D96", "#25836B", "#D97706"]
        )
        fig_metrics.update_layout(
            title_text="<b>Document Elements Breakdown</b>",
            showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10),
            height=260,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title="",
            yaxis_title="Count"
        )
        st.plotly_chart(fig_metrics, use_container_width=True)

    tab_summary, tab_risk_comp, tab_finance_comp, tab_timeline_comp, tab_qa, tab_letter = st.tabs([
        "📊 Executive Summary",
        "⚠️ Risk Compartment",
        "💳 Financial Overview",
        "📅 Key Timelines",
        "💬 Chat & Q&A",
        "✉️ Action Letter"
    ])

    with tab_summary:
        st.markdown("### Modular Document Breakdown")
        st.caption("Each category is extracted into a standalone compartmentalized card with exact verified citations.")

        if st.button("Generate Modular Analysis", type="primary", key="btn_modular_sum"):
            with st.spinner("Extracting modular blocks with Gemini..."):
                prompt = f"""You are analyzing a contract for a non-lawyer.
Use ONLY the text below. Return JSON with this exact shape containing distinct items for each compartment. Do not use numbers:
{{
  "executive_summary": [
    {{"content": "...", "page": 1, "quote": "exact words from text"}}
  ],
  "money": [
    {{"content": "...", "page": 1, "quote": "exact words from text"}}
  ],
  "obligations": [
    {{"content": "...", "page": 1, "quote": "exact words from text"}}
  ],
  "penalties": [
    {{"content": "...", "page": 1, "quote": "exact words from text"}}
  ]
}}
Do not invent quotes or pages. If a category has nothing, provide an empty list.
TEXT:
{extracted_text[:12000]}"""
                res = gemini_json(prompt, model_tag)
                st.session_state["modular_cache"] = res

        cached_res = st.session_state.get("modular_cache", {})
        
        st.markdown("#### Executive Summary Compartment")
        exec_items = cached_res.get("executive_summary", [])
        if exec_items:
            for item in exec_items:
                p_num = item.get("page", 1)
                p_body = page_text_for(p_num, pages)
                quote = item.get("quote", "")
                is_verified = verify_quote(quote, p_body)
                badge = "🛡️ **[Verified Quote]**" if is_verified else "⚠️ **[Unverified Quote]**"
                
                st.markdown(f"""
                <div class="summary-compartment">
                    <p style="margin-bottom: 6px;"><b>Overview:</b> {item.get('content', '')}</p>
                    <p style="color: #64748B; font-size: 14px; margin-bottom: 4px;"><b>Source Text:</b> &ldquo;{quote}&rdquo;</p>
                    <p style="font-size: 12.5px; color: #315D96; margin: 0;">Page {p_num} &nbsp;•&nbsp; {badge}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Click 'Generate Modular Analysis' above to load this compartment.")

        st.markdown("#### Financial Sums & Pricing Compartment")
        money_items = cached_res.get("money", [])
        if money_items:
            for item in money_items:
                p_num = item.get("page", 1)
                p_body = page_text_for(p_num, pages)
                quote = item.get("quote", "")
                is_verified = verify_quote(quote, p_body)
                badge = "🛡️ **[Verified Quote]**" if is_verified else "⚠️ **[Unverified Quote]**"
                
                st.markdown(f"""
                <div class="summary-compartment">
                    <p style="margin-bottom: 6px;"><b>Payment Term:</b> {item.get('content', '')}</p>
                    <p style="color: #64748B; font-size: 14px; margin-bottom: 4px;"><b>Source Text:</b> &ldquo;{quote}&rdquo;</p>
                    <p style="font-size: 12.5px; color: #315D96; margin: 0;">Page {p_num} &nbsp;•&nbsp; {badge}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No specific modular financial blocks generated yet.")

        st.markdown("#### Core Obligations Compartment")
        ob_items = cached_res.get("obligations", [])
        if ob_items:
            for item in ob_items:
                p_num = item.get("page", 1)
                p_body = page_text_for(p_num, pages)
                quote = item.get("quote", "")
                is_verified = verify_quote(quote, p_body)
                badge = "🛡️ **[Verified Quote]**" if is_verified else "⚠️ **[Unverified Quote]**"
                
                st.markdown(f"""
                <div class="summary-compartment">
                    <p style="margin-bottom: 6px;"><b>Duty / Obligation:</b> {item.get('content', '')}</p>
                    <p style="color: #64748B; font-size: 14px; margin-bottom: 4px;"><b>Source Text:</b> &ldquo;{quote}&rdquo;</p>
                    <p style="font-size: 12.5px; color: #315D96; margin: 0;">Page {p_num} &nbsp;•&nbsp; {badge}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No specific modular obligation blocks generated yet.")

        st.markdown("#### Penalties & Fees Compartment")
        pen_items = cached_res.get("penalties", [])
        if pen_items:
            for item in pen_items:
                p_num = item.get("page", 1)
                p_body = page_text_for(p_num, pages)
                quote = item.get("quote", "")
                is_verified = verify_quote(quote, p_body)
                badge = "🛡️ **[Verified Quote]**" if is_verified else "⚠️ **[Unverified Quote]**"
                
                st.markdown(f"""
                <div class="summary-compartment">
                    <p style="margin-bottom: 6px;"><b>Penalty / Risk:</b> {item.get('content', '')}</p>
                    <p style="color: #64748B; font-size: 14px; margin-bottom: 4px;"><b>Source Text:</b> &ldquo;{quote}&rdquo;</p>
                    <p style="font-size: 12.5px; color: #315D96; margin: 0;">Page {p_num} &nbsp;•&nbsp; {badge}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No specific modular penalty blocks generated yet.")

    with tab_risk_comp:
        with st.container(border=True):
            st.markdown(f"### ⚠️ Dedicated Risk Compartment (Score: {score}%)")
            st.write("Click any flagged clause below to examine exact context, severity, and why it matters.")
            if risk_hits:
                for idx, h in enumerate(risk_hits):
                    with st.expander(f"🔴 [{h['label']}] Severity Level {h['severity']} — Page {h['page']}"):
                        st.markdown(f"**Exact Clause Quote:**")
                        st.markdown(f"> \"{h['quote']}\"")
                        st.markdown(f"**Why it matters:** {h['why']}")
                        st.markdown(f"**Confidence Label:** 🛡️ Quoted directly from document (Page {h['page']})")
            else:
                st.success("No heavy predatory risk markers detected by deterministic rules.")

    with tab_finance_comp:
        with st.container(border=True):
            st.markdown("### 💳 Financial Overview Compartment")
            st.caption("Extracted explicit monetary values, deposits, and fee references.")
            if money_list:
                for m in money_list:
                    st.markdown(f"- 💵 **{m['text']}** (Page {m['page']})")
            else:
                st.info("No explicit monetary sums detected.")

    with tab_timeline_comp:
        with st.container(border=True):
            st.markdown("### 📅 Key Timelines Compartment")
            st.caption("Extracted notice periods, duration limits, and critical dates.")
            
            calendar_events_found = []
            if timeline_list:
                for t in timeline_list:
                    st.markdown(f"- ⏱️ **{t['text']}** (Page {t['page']})")
                    try:
                        parsed_dt = date_parser.parse(t['text'], fuzzy=True)
                        calendar_events_found.append((t['text'], parsed_dt))
                    except Exception:
                        pass
            else:
                st.info("No explicit time durations or dates parsed automatically.")

            st.markdown("---")
            cal = Calendar()
            event = Event()
            event.name = f"Contract Deadline: {doc_name}"
            event.begin = datetime.now()
            event.description = "Automated SafeLex legal timeline reminder."
            cal.events.add(event)
            st.download_button("Download calendar.ics", str(cal), "safelex_timeline.ics", "text/calendar", use_container_width=True)

    with tab_qa:
        with st.container(border=True):
            st.markdown("### Follow-up Chat with Page Retrieval")
            user_q = st.text_input("Ask a question about this document...", key="doc_chat_in")
            if st.button("Send ↗", type="primary", key="doc_chat_btn"):
                if user_q.strip():
                    with st.spinner("Retrieving relevant pages and generating grounded answer with Gemini..."):
                        relevant_pages = top_pages(user_q, pages, k=3)
                        context_blob = "\n".join([f"--- [Page {p[0]}] ---\n{p[1]}" for p in relevant_pages])
                        prompt = f"Answer this question strictly using the contract text with [Page X] citations. If not found, say 'Not found in this document':\n\nQuestion: {user_q}\n\nContract:\n{context_blob}"
                        st.write_stream(stream_gemini_chat(prompt, target_language, model_tag))

    with tab_letter:
        with st.container(border=True):
            st.markdown("### Dispute or Cancellation Letter Form Generator")
            st.caption("Fill in your details to draft a verified formal notice.")
            
            c_name = st.text_input("Your Name / Company", value=current_user)
            c_date = st.text_input("Contract Date", value=datetime.now().strftime("%Y-%m-%d"))
            c_ref = st.text_input("Account / Contract Reference Number", value="REF-10928")
            c_amt = st.text_input("Disputed Amount (if applicable)", value="$0.00")
            letter_type = st.selectbox("Letter Purpose", ["Cancellation Notice", "Dispute Charge", "Refund Request"])
            
            if st.button("Draft Verified Letter", type="primary"):
                with st.spinner("Drafting formal letter from verified clauses using Gemini..."):
                    letter_prompt = f"Draft a formal {letter_type} letter from {c_name}, dated {c_date}, referencing account {c_ref} and amount {c_amt}. Cite relevant contract terms and page numbers from this document:\n\n{extracted_text[:8000]}"
                    st.write_stream(stream_gemini_chat(letter_prompt, target_language, model_tag))

# Router logic
if st.session_state["active_tab"] == "Dashboard":
    render_dashboard()
elif st.session_state["active_tab"] == "Compare":
    render_compare_view()
elif st.session_state["active_tab"] == "DocumentWorkspace":
    render_document_workspace()
