import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import time
import smtplib
import os
import json
import sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- DATABASE AND CONFIG PATHS ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'leadgen.db')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def init_database():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Scheduled emails table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            company_name TEXT,
            website TEXT,
            niche TEXT,
            scheduled_time TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    ''')
    
    # Email log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            company_name TEXT,
            website TEXT,
            contact_email TEXT,
            niche TEXT,
            subject TEXT,
            body TEXT,
            status TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


def load_config():
    """Load Gmail credentials from config.json file."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except:
        return {"gmail_address": "", "gmail_app_password": "", "sender_name": ""}


def save_config(config):
    """Save Gmail credentials to config.json file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)


# Initialize database on app start
init_database()

# --- SESSION STATE ---
if 'email_log' not in st.session_state:
    st.session_state.email_log = []

if 'approval_state' not in st.session_state:
    st.session_state.approval_state = {}


# --- GMAIL SENDING FUNCTION ---
def send_email_gmail(recipient_email, subject, body):
    """Send email via Gmail SMTP using config.json credentials."""
    config = load_config()
    gmail_address = config.get('gmail_address') or os.environ.get('GMAIL_ADDRESS')
    gmail_password = config.get('gmail_app_password') or os.environ.get('GMAIL_APP_PASSWORD')
    
    if not gmail_address or not gmail_password:
        return False, "Gmail credentials not configured. Set them in Settings (sidebar) or in config.json"
    
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_address
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_address, gmail_password)
            server.send_message(msg)
        
        return True, "Email sent successfully!"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check your App Password."
    except Exception as e:
        return False, f"Failed to send: {str(e)}"


def log_email(company_name, website, contact_email, niche, subject, body, sent_status, notes=""):
    """Add entry to email tracking log in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO email_log (timestamp, company_name, website, contact_email, niche, subject, body, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        company_name, website, contact_email, niche, subject, 
        body.replace('\n', ' '), sent_status, notes
    ))
    conn.commit()
    conn.close()


def schedule_email_db(recipient_email, subject, body, scheduled_datetime, company_name, website, niche):
    """Schedule an email in the database for the background scheduler to process."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO scheduled_emails (recipient, subject, body, company_name, website, niche, scheduled_time, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
    ''', (
        recipient_email, subject, body, company_name, website, niche,
        scheduled_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()
    return scheduled_datetime


def get_scheduled_emails():
    """Get all scheduled emails from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, recipient, subject, scheduled_time, status FROM scheduled_emails ORDER BY scheduled_time DESC LIMIT 50')
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_email_log():
    """Get email log from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, company_name, website, contact_email, niche, subject, status, notes FROM email_log ORDER BY timestamp DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()
    return rows

# --- CONFIGURATION ---
st.set_page_config(
    page_title="LeadGen Pro",
    layout="wide",
    page_icon="◆",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    
    /* Base Styles - Premium Dark Theme */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        color: #E8ECF4;
    }
    
    /* Main Background - Rich dark with subtle gradient */
    .stApp {
        background: linear-gradient(180deg, #0D0D12 0%, #13131A 100%);
    }
    
    /* SIDEBAR TOGGLE - Fixed visible button */
    [data-testid="collapsedControl"] {
        display: block !important;
        visibility: visible !important;
        position: fixed !important;
        top: 14px !important;
        left: 14px !important;
        z-index: 999999 !important;
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
        border-radius: 10px !important;
        padding: 8px !important;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4) !important;
    }
    
    [data-testid="collapsedControl"] svg {
        color: white !important;
        width: 20px !important;
        height: 20px !important;
    }
    
    [data-testid="collapsedControl"]:hover {
        transform: scale(1.05) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6) !important;
    }
    
    /* Hide default header buttons that might overlap */
    button[kind="header"] {
        visibility: visible !important;
    }
    
    /* Premium Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111118 0%, #0D0D12 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    
    section[data-testid="stSidebar"] > div {
        background: transparent;
    }

    
    /* Premium Cards */
    .card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
    }
    
    /* Issue Items - Subtle amber accent */
    .issue-item {
        background: rgba(251, 191, 36, 0.08);
        border: 1px solid rgba(251, 191, 36, 0.15);
        border-left: 3px solid #F59E0B;
        padding: 16px 20px;
        margin: 12px 0;
        border-radius: 12px;
        font-size: 14px;
        color: #FCD34D;
        transition: all 0.25s ease;
    }
    
    .issue-item:hover {
        background: rgba(251, 191, 36, 0.12);
        transform: translateX(6px);
    }
    
    /* Email Output - Premium container */
    .email-output {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 28px;
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        line-height: 1.85;
        white-space: pre-wrap;
        color: #D1D5DB;
    }
    
    /* Input Fields - Premium glass style */
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.04) !important;
        background-color: rgba(20, 20, 30, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        color: #FFFFFF !important;
        border-radius: 12px !important;
        transition: all 0.25s ease;
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* Force text color in inputs */
    input, textarea, select {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }
    
    .stTextInput input {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }
    
    .stTextArea textarea {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        background-color: rgba(20, 20, 30, 0.8) !important;
    }
    
    .stTextInput > div > div > input:focus, 
    .stTextArea > div > div > textarea:focus {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15) !important;
    }
    
    .stTextInput > div > div > input::placeholder,
    .stTextArea > div > div > textarea::placeholder {
        color: #6B7280 !important;
        -webkit-text-fill-color: #6B7280 !important;
    }
    
    /* Selectbox styling */
    .stSelectbox > div > div > div {
        background: rgba(20, 20, 30, 0.8) !important;
        border-radius: 12px !important;
        color: #FFFFFF !important;
    }
    
    .stSelectbox [data-baseweb="select"] span {
        color: #FFFFFF !important;
    }
    
    /* Primary Button - Premium gradient */
    .stButton > button {
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: 600;
        font-family: 'DM Sans', sans-serif;
        padding: 0.6rem 1.4rem;
        transition: all 0.25s ease;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.25);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(99, 102, 241, 0.35);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* Download Button - Ghost style */
    .stDownloadButton > button {
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #E8ECF4;
        border-radius: 12px;
        font-weight: 500;
        font-family: 'DM Sans', sans-serif;
        transition: all 0.25s ease;
    }
    
    .stDownloadButton > button:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.25);
    }
    
    /* Section Headers */
    h1 {
        color: #FFFFFF;
        font-weight: 700;
        font-family: 'DM Sans', sans-serif;
    }
    
    h2, h3 {
        color: #E8ECF4;
        font-weight: 600;
        font-family: 'DM Sans', sans-serif;
    }
    
    /* Dividers */
    hr {
        border: none;
        height: 1px;
        background: rgba(255, 255, 255, 0.06);
        margin: 1.5rem 0;
    }
    
    /* Progress bar */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #6366F1, #8B5CF6);
        border-radius: 10px;
    }
    
    /* Info/Success messages */
    .stAlert {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #6366F1 transparent transparent transparent;
    }
    
    /* Code blocks */
    .stCode, code {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        color: #E8ECF4 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* File uploader */
    .stFileUploader > div {
        background: rgba(255, 255, 255, 0.02);
        border: 2px dashed rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        transition: all 0.25s ease;
    }
    
    .stFileUploader > div:hover {
        border-color: #6366F1;
        background: rgba(99, 102, 241, 0.05);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 10px;
        color: #9CA3AF;
        font-weight: 500;
        font-family: 'DM Sans', sans-serif;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(99, 102, 241, 0.15);
        color: #E8ECF4;
    }
    
    /* DataFrame styling */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }
    
    /* Markdown text */
    .stMarkdown p {
        color: #9CA3AF;
    }
    
    /* Labels */
    .stTextInput label, .stTextArea label, .stSelectbox label {
        color: #9CA3AF !important;
        font-weight: 500;
        font-size: 13px;
        font-family: 'DM Sans', sans-serif !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header {
        visibility: hidden;
    }
    
    /* Premium Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.2);
    }
    </style>
""", unsafe_allow_html=True)


# --- WEBSITE SCRAPING ---
def scrape_website_text(url):
    """Scrape text content from a website."""
    if not url:
        return "", ""
    
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Get homepage
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        homepage_text = soup.get_text(separator=' ', strip=True)
        homepage_text = re.sub(r'\s+', ' ', homepage_text)[:3000]  # Limit text
        
        # Try to find and scrape services page
        services_text = ""
        services_links = soup.find_all('a', href=True)
        for link in services_links:
            href = link['href'].lower()
            text = link.get_text().lower()
            if 'service' in href or 'service' in text or 'what-we-do' in href:
                services_url = href
                if not services_url.startswith('http'):
                    parsed = urlparse(url)
                    services_url = f"{parsed.scheme}://{parsed.netloc}{services_url}"
                try:
                    resp = requests.get(services_url, headers=headers, timeout=8)
                    srv_soup = BeautifulSoup(resp.text, 'html.parser')
                    for element in srv_soup(['script', 'style', 'nav', 'footer']):
                        element.decompose()
                    services_text = srv_soup.get_text(separator=' ', strip=True)
                    services_text = re.sub(r'\s+', ' ', services_text)[:2000]
                    break
                except:
                    pass
        
        return homepage_text, services_text
        
    except Exception as e:
        return f"Error scraping: {str(e)}", ""


# --- WEBSITE ANALYSIS ---
def analyze_website(company_name, website_url, niche, homepage_text, services_text):
    """Analyze website text and extract conversion issues."""
    
    issues = []
    combined_text = (homepage_text + " " + services_text).lower()
    
    # Check for value proposition
    value_words = ['help', 'solve', 'achieve', 'result', 'outcome', 'benefit', 'save', 'grow', 'increase']
    has_value_prop = any(word in combined_text for word in value_words)
    if not has_value_prop:
        issues.append("Homepage describes services but does not communicate clear outcomes or benefits for clients.")
    
    # Check for CTA
    cta_words = ['contact', 'call', 'schedule', 'book', 'get started', 'free quote', 'request', 'consultation']
    has_cta = any(word in combined_text for word in cta_words)
    if not has_cta:
        issues.append("No clear call-to-action guiding visitors to take the next step.")
    
    # Check for trust signals
    trust_words = ['years', 'experience', 'certified', 'guarantee', 'testimonial', 'review', 'client', 'trusted', 'award']
    has_trust = any(word in combined_text for word in trust_words)
    if not has_trust:
        issues.append("Missing trust signals like testimonials, certifications, or experience indicators.")
    
    # Check for differentiation
    diff_words = ['unique', 'only', 'different', 'unlike', 'specialized', 'exclusive', 'proprietary']
    has_diff = any(word in combined_text for word in diff_words)
    if not has_diff and services_text:
        issues.append("Services section lists offerings without explaining what sets the business apart.")
    
    # Check for clarity
    if len(homepage_text) < 200:
        issues.append("Homepage content is too sparse to communicate value effectively.")
    elif len(homepage_text) > 2500:
        issues.append("Homepage is text-heavy without clear hierarchy, making it hard to scan quickly.")
    
    # Check for contact info visibility
    contact_words = ['email', 'phone', '@', 'call us']
    has_contact = any(word in combined_text for word in contact_words)
    if not has_contact:
        issues.append("Contact information is not prominently visible in the main content.")
    
    # Check for services clarity
    if not services_text and 'service' not in combined_text:
        issues.append("No dedicated services section explaining what the business offers.")
    
    # Limit to 4 issues max
    return issues[:4]


# --- EMAIL GENERATION ---

# Issue data with unique impacts (no duplicated decision logic)
ISSUE_DATA = {
    "value_prop": {
        "statement": "The homepage explains what you do but not what clients get out of it",
        "impact": "which makes it easy to scroll past"
    },
    "cta": {
        "statement": "There is no obvious next step for someone ready to reach out",
        "impact": "and that friction costs inquiries"
    },
    "trust": {
        "statement": "There are no testimonials or proof of past work",
        "impact": "so new leads have little reason to trust the business"
    },
    "differentiation": {
        "statement": "Services are listed but nothing explains what makes you different",
        "impact": "which weakens your position against competitors"
    },
    "sparse": {
        "statement": "The homepage does not say enough to build confidence",
        "impact": "so people leave before understanding the value"
    },
    "dense": {
        "statement": "There is a lot of text but no clear structure",
        "impact": "which buries the key points"
    },
    "contact": {
        "statement": "Contact info is hard to find",
        "impact": "adding friction for anyone ready to reach out"
    },
    "services": {
        "statement": "There is no clear section explaining what you offer",
        "impact": "leaving scope unclear"
    }
}

# Pre-written combined issues (smooth, no repetition)
COMBINED_ISSUES = {
    ("value_prop", "cta"): "The homepage explains what you do but not the outcomes. There is also no clear next step. That combination makes it easy for leads to leave without acting.",
    ("value_prop", "trust"): "The homepage focuses on services but not results, and there is no proof of past work. Both of those make it harder for someone new to reach out.",
    ("cta", "trust"): "There is no obvious way to take the next step, and no testimonials to back up the claims. That tends to cost inquiries.",
    ("trust", "differentiation"): "The site lacks proof of past work, and nothing explains what sets you apart. That makes the decision harder for anyone evaluating options.",
    ("sparse", "cta"): "The homepage is thin on content and there is no clear call to action. People are leaving before they even consider reaching out.",
    ("dense", "cta"): "There is a lot of text without structure, and no obvious next step. The key points get buried.",
}

def map_issue_to_key(issue):
    """Map detected issue to a key."""
    issue_lower = issue.lower()
    if "outcome" in issue_lower or "benefit" in issue_lower or "value" in issue_lower:
        return "value_prop"
    elif "call-to-action" in issue_lower or "cta" in issue_lower or "next step" in issue_lower:
        return "cta"
    elif "trust" in issue_lower or "testimonial" in issue_lower or "credential" in issue_lower:
        return "trust"
    elif "differentiation" in issue_lower or "sets" in issue_lower or "apart" in issue_lower:
        return "differentiation"
    elif "sparse" in issue_lower or "too brief" in issue_lower or "too short" in issue_lower:
        return "sparse"
    elif "text-heavy" in issue_lower or "hierarchy" in issue_lower or "dense" in issue_lower:
        return "dense"
    elif "contact" in issue_lower:
        return "contact"
    elif "services section" in issue_lower or "dedicated" in issue_lower:
        return "services"
    return None

def generate_email(company_name, niche, issues):
    """Generate cold email. Max 2 issues, 120-150 words, no AI signals."""
    
    # Purposeful openings (no "jumped out", "a few things", no easing in)
    openings = [
        f"Looked at {company_name}'s site. There are a couple of things worth addressing.",
        f"Went through {company_name}'s website. Two things could use attention.",
        f"Checked out {company_name}'s site. Couple of quick notes.",
        f"Looked at {company_name}'s website earlier. Worth flagging two things."
    ]
    opening = openings[hash(company_name) % len(openings)]
    
    # Confident CTAs (short, specific, no permission asking)
    ctas = [
        "I can outline what I would fix first.",
        "Happy to send a short list of priorities.",
        "I can share a quick breakdown of changes.",
        "I have specific ideas if useful."
    ]
    cta = ctas[hash(company_name + niche) % len(ctas)]
    
    # Subject lines
    subjects = [
        f"Quick thought on {company_name}",
        f"Re: {company_name}",
        f"Your website",
        f"{company_name}"
    ]
    subject = subjects[hash(company_name) % len(subjects)]
    
    # Practical context (one unique angle per email, no duplication)
    contexts = [
        f"In {niche}, first impressions close deals.",
        f"Most {niche} leads decide fast. Clarity wins.",
        f"{niche.capitalize()} clients reach out to whoever looks credible.",
        f"Speed and trust matter in {niche}."
    ]
    context = contexts[hash(company_name + niche) % len(contexts)]
    
    # No issues case
    if not issues:
        email_body = f"""Hi,

{opening}

The foundation is there, but the messaging could work harder to convert interest into inquiries.

{context}

{cta}

Best"""
        return subject, email_body
    
    # Map issues (max 2, no duplicates)
    mapped_keys = []
    used_keys = set()
    for issue in issues[:4]:
        key = map_issue_to_key(issue)
        if key and key not in used_keys:
            mapped_keys.append(key)
            used_keys.add(key)
        if len(mapped_keys) == 2:
            break
    
    # Fallback
    if not mapped_keys:
        issue_text = f"{issues[0].rstrip('.')}. That could be affecting how leads perceive the business."
    elif len(mapped_keys) == 2:
        # Check for pre-combined version (smoother flow)
        pair = (mapped_keys[0], mapped_keys[1])
        pair_rev = (mapped_keys[1], mapped_keys[0])
        if pair in COMBINED_ISSUES:
            issue_text = COMBINED_ISSUES[pair]
        elif pair_rev in COMBINED_ISSUES:
            issue_text = COMBINED_ISSUES[pair_rev]
        else:
            # Build separate but connected
            i1 = ISSUE_DATA[mapped_keys[0]]
            i2 = ISSUE_DATA[mapped_keys[1]]
            issue_text = f"{i1['statement']}, {i1['impact']}. Also, {i2['statement'].lower()}, {i2['impact']}."
    else:
        i1 = ISSUE_DATA[mapped_keys[0]]
        issue_text = f"{i1['statement']}, {i1['impact']}."
    
    email_body = f"""Hi,

{opening}

{issue_text}

{context}

{cta}

Best"""
    
    return subject, email_body


# --- UI LAYOUT ---
with st.sidebar:
    st.markdown("""
    <div style='padding: 24px 0;'>
        <div style='display: flex; align-items: center; gap: 12px;'>
            <div style='width: 36px; height: 36px; background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center;'>
                <span style='font-size: 18px;'>◆</span>
            </div>
            <div>
                <span style='font-size: 18px; font-weight: 700; color: #FFFFFF; font-family: DM Sans, sans-serif;'>LeadGen Pro</span>
                <p style='font-size: 11px; color: #6B7280; margin: 2px 0 0 0; font-family: DM Sans, sans-serif;'>Website Audit & Outreach</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # --- GMAIL SETTINGS ---
    with st.expander("⚙️ Gmail Settings", expanded=False):
        config = load_config()
        
        st.markdown("*Credentials saved to config.json - works on any device*")
        
        gmail_email = st.text_input("Gmail Address", value=config.get('gmail_address', ''), key="settings_email")
        gmail_pass = st.text_input("App Password", value=config.get('gmail_app_password', ''), type="password", key="settings_pass")
        sender_name = st.text_input("Sender Name (optional)", value=config.get('sender_name', ''), key="settings_name")
        
        if st.button("💾 Save Settings", use_container_width=True):
            save_config({
                "gmail_address": gmail_email,
                "gmail_app_password": gmail_pass,
                "sender_name": sender_name
            })
            st.success("✅ Settings saved!")
        
        st.markdown("""
        <div style='font-size: 11px; color: #9CA3AF; margin-top: 10px;'>
            <a href='https://myaccount.google.com/apppasswords' target='_blank' style='color: #6366F1;'>Get App Password →</a>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("""
    <div style='padding: 16px; background: rgba(99, 102, 241, 0.08); border-radius: 14px; border: 1px solid rgba(99, 102, 241, 0.15); margin-bottom: 20px;'>
        <p style='font-size: 13px; font-weight: 600; color: #E8ECF4; margin-bottom: 14px; font-family: DM Sans, sans-serif;'>How It Works</p>
        <div style='font-size: 12px; color: #9CA3AF; line-height: 2; font-family: DM Sans, sans-serif;'>
            <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 4px;'>
                <span style='color: #6366F1; font-weight: 600;'>1</span>
                <span>Enter business details</span>
            </div>
            <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 4px;'>
                <span style='color: #6366F1; font-weight: 600;'>2</span>
                <span>Scrape or paste content</span>
            </div>
            <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 4px;'>
                <span style='color: #6366F1; font-weight: 600;'>3</span>
                <span>Get conversion audit</span>
            </div>
            <div style='display: flex; align-items: center; gap: 10px;'>
                <span style='color: #6366F1; font-weight: 600;'>4</span>
                <span>Generate cold email</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style='padding: 12px;'>
        <p style='font-size: 10px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-family: DM Sans, sans-serif;'>Focus Areas</p>
        <div style='font-size: 12px; color: #9CA3AF; line-height: 1.9; font-family: DM Sans, sans-serif;'>
            <div style='margin-bottom: 4px;'>• Messaging clarity</div>
            <div style='margin-bottom: 4px;'>• Value proposition</div>
            <div style='margin-bottom: 4px;'>• Call-to-action</div>
            <div style='margin-bottom: 4px;'>• Trust signals</div>
            <div>• Content structure</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Main Area
st.markdown("""
<div style='padding: 30px 0 40px 0;'>
    <p style='font-size: 12px; color: #6366F1; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; font-family: DM Sans, sans-serif;'>Website Analysis</p>
    <h1 style='font-size: 36px; font-weight: 700; color: #FFFFFF; margin-bottom: 12px; font-family: DM Sans, sans-serif; line-height: 1.2;'>Audit websites. Generate outreach.</h1>
    <p style='color: #9CA3AF; font-size: 15px; font-family: DM Sans, sans-serif;'>Enter business details to identify conversion issues and create personalized cold emails.</p>
</div>
""", unsafe_allow_html=True)

# Input Section
st.markdown("### Business Information")
col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input("Company Name", placeholder="Acme Plumbing Services")
    website_url = st.text_input("Website URL", placeholder="acmeplumbing.com")

with col2:
    niche_options = [
        "Consulting",
        "Plumbing",
        "HVAC",
        "Electrical",
        "Legal Services",
        "Accounting",
        "Real Estate",
        "Dental",
        "Medical",
        "Chiropractic",
        "Physical Therapy",
        "Home Renovation",
        "Landscaping",
        "Roofing",
        "Cleaning Services",
        "Insurance",
        "Financial Planning",
        "Marketing Agency",
        "IT Services",
        "Photography",
        "Catering",
        "Fitness",
        "Salon/Spa",
        "Auto Repair",
        "Other"
    ]
    niche = st.selectbox("Niche/Industry", options=niche_options, index=0)
    scrape_btn = st.button("🔍 Auto-Scrape Website", use_container_width=True)

# Text inputs
st.markdown("### Website Content")
st.markdown("*Paste the text content or click Auto-Scrape above*")

# Handle auto-scrape
if scrape_btn and website_url:
    with st.spinner("Scraping website..."):
        homepage_text, services_text = scrape_website_text(website_url)
        st.session_state['homepage_text'] = homepage_text
        st.session_state['services_text'] = services_text

# Get stored values or empty
default_homepage = st.session_state.get('homepage_text', '')
default_services = st.session_state.get('services_text', '')

col3, col4 = st.columns(2)
with col3:
    homepage_text = st.text_area("Homepage Text", value=default_homepage, height=200, placeholder="Paste the main text from the homepage...")
with col4:
    services_text = st.text_area("Services Page Text (optional)", value=default_services, height=200, placeholder="Paste text from services page if available...")

# Generate button
st.markdown("---")
generate_btn = st.button("⚡ Analyze & Generate Email", type="primary", use_container_width=True)

# Process and store in session state
if generate_btn:
    if not company_name:
        st.error("Please enter a company name.")
    elif not homepage_text:
        st.error("Please provide homepage text (paste manually or use auto-scrape).")
    else:
        with st.spinner("Analyzing website..."):
            time.sleep(0.5)  # Brief pause for UX
            
            # Step 1 & 2: Analyze and extract issues
            issues = analyze_website(company_name, website_url, niche, homepage_text, services_text)
            
            # Step 4: Generate email
            subject, email_body = generate_email(company_name, niche, issues)
        
        # Store results in session state for persistence
        st.session_state['generated_result'] = {
            'company_name': company_name,
            'website_url': website_url,
            'niche': niche,
            'issues': issues,
            'subject': subject,
            'email_body': email_body
        }

# Display results if they exist in session state
if 'generated_result' in st.session_state and st.session_state['generated_result']:
    result = st.session_state['generated_result']
    
    st.markdown("---")
    
    # Issues Found
    st.markdown("### 🔍 Issues Identified")
    if result['issues']:
        for i, issue in enumerate(result['issues'], 1):
            st.markdown(f'<div class="issue-item">#{i}: {issue}</div>', unsafe_allow_html=True)
    else:
        st.info("No major conversion issues detected from the provided text.")
    
    st.markdown("---")
    
    # Email Output
    st.markdown("### 📧 Generated Email")
    
    # Editable subject line with default
    edited_subject = st.text_input("Subject Line", value=result['subject'], key="single_subject")
    
    # v1.1: Editable email body
    edited_body = st.text_area("Email Body", value=result['email_body'], height=250, key="single_body")
    
    st.markdown("---")
    
    # v1.1: Recipient email and approval
    st.markdown("### 📤 Send Email")
    col_email, col_approve = st.columns([2, 1])
    
    with col_email:
        recipient_email = st.text_input("Recipient Email", placeholder="contact@company.com", key="single_recipient")
    
    with col_approve:
        st.markdown("<br>", unsafe_allow_html=True)
        approved = st.checkbox("✅ Approve this email for sending", key="single_approve")
    
    # Action buttons
    col_dl, col_send, col_log, col_clear = st.columns([1, 1, 1, 1])
    
    with col_dl:
        st.download_button(
            "📥 Download Email",
            f"Subject: {edited_subject}\n\n{edited_body}",
            file_name=f"{result['company_name'].replace(' ', '_')}_email.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col_send:
        send_clicked = st.button("📧 Send via Gmail", use_container_width=True, disabled=not approved)
        if send_clicked:
            if not approved:
                st.error("⚠️ Please approve the email before sending.")
            elif not recipient_email:
                st.error("⚠️ Please enter recipient email address.")
            else:
                success, message = send_email_gmail(recipient_email, edited_subject, edited_body)
                if success:
                    st.success(f"✅ {message}")
                    log_email(result['company_name'], result['website_url'], recipient_email, result['niche'], edited_subject, edited_body, "Yes")
                else:
                    st.error(f"❌ {message}")
                    log_email(result['company_name'], result['website_url'], recipient_email, result['niche'], edited_subject, edited_body, "Failed", message)
    
    with col_log:
        if st.button("📋 Save to Log Only", use_container_width=True):
            log_email(result['company_name'], result['website_url'], recipient_email or "N/A", result['niche'], edited_subject, edited_body, "No - Logged Only")
            st.success("✅ Email saved to tracking log!")
    
    with col_clear:
        if st.button("🗑️ Clear Result", use_container_width=True):
            st.session_state['generated_result'] = None
            st.rerun()
    
    # --- SCHEDULING SECTION ---
    st.markdown("---")
    st.markdown("### ⏰ Schedule Email")
    st.markdown("*Schedule for any date/time. Run `scheduler.py` separately to send scheduled emails.*")
    
    col_date, col_time = st.columns(2)
    
    with col_date:
        schedule_date = st.date_input("Date", value=datetime.now().date() + timedelta(days=1), key="schedule_date")
    
    with col_time:
        schedule_time = st.time_input("Time", value=datetime.now().replace(hour=9, minute=0).time(), key="schedule_time")
    
    schedule_clicked = st.button("📅 Schedule Email", use_container_width=True, disabled=not approved)
    if schedule_clicked:
        if not approved:
            st.error("⚠️ Please approve the email before scheduling.")
        elif not recipient_email:
            st.error("⚠️ Please enter recipient email address.")
        else:
            scheduled_datetime = datetime.combine(schedule_date, schedule_time)
            if scheduled_datetime <= datetime.now():
                st.error("⚠️ Please select a future date/time.")
            else:
                schedule_email_db(
                    recipient_email, edited_subject, edited_body, scheduled_datetime,
                    result['company_name'], result['website_url'], result['niche']
                )
                st.success(f"✅ Email scheduled for {scheduled_datetime.strftime('%Y-%m-%d %H:%M')}")

# --- SCHEDULED EMAILS QUEUE (from database) ---
st.markdown("---")
st.markdown("### 📅 Scheduled Emails Queue")

scheduled_rows = get_scheduled_emails()
if scheduled_rows:
    scheduled_df = pd.DataFrame(scheduled_rows, columns=['ID', 'Recipient', 'Subject', 'Scheduled Time', 'Status'])
    st.dataframe(scheduled_df, use_container_width=True)
    
    st.markdown("""
    <div style='background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; padding: 12px; margin: 10px 0;'>
        <p style='color: #9CA3AF; font-size: 12px; margin: 0;'>
            <strong>⚠️ Run the scheduler:</strong> Open a terminal and run <code>python scheduler.py</code> to process scheduled emails.
            The scheduler can run on any device with access to the database file.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Refresh Queue", use_container_width=True):
        st.rerun()
else:
    st.info("No scheduled emails. Schedule an email above to see it here.")

# Batch Processing Section
st.markdown("---")
st.markdown("### 📊 Batch Processing (CSV)")
st.markdown("Upload a CSV with columns: `Company Name`, `Website URL`, `Niche`, `Contact Email` (optional)")

uploaded_file = st.file_uploader("Upload CSV", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.dataframe(df.head())
    
    if st.button("🚀 Process All Leads", use_container_width=True):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            progress.progress((i + 1) / len(df))
            
            comp_name = str(row.get('Company Name', '')).strip()
            web_url = str(row.get('Website URL', '')).strip()
            comp_niche = str(row.get('Niche', '')).strip()
            contact_email = str(row.get('Contact Email', '')).strip() if 'Contact Email' in df.columns else ''
            
            status.write(f"Processing {i+1}/{len(df)}: {comp_name}...")
            
            # v1.1: URL normalization
            if web_url and not web_url.startswith(('http://', 'https://')):
                web_url = 'https://' + web_url
            
            # v1.1: Scrape with explicit error handling
            hp_text, srv_text = "", ""
            scrape_status = "No URL"
            
            if web_url:
                try:
                    hp_text, srv_text = scrape_website_text(web_url)
                    if hp_text and not hp_text.startswith("Error"):
                        scrape_status = "Success"
                    else:
                        scrape_status = f"Failed: {hp_text[:50]}" if hp_text else "Empty response"
                except Exception as e:
                    scrape_status = f"Error: {str(e)[:50]}"
                    hp_text, srv_text = "", ""
            
            # Analyze
            issues = analyze_website(comp_name, web_url, comp_niche, hp_text, srv_text)
            subject, email_body = generate_email(comp_name, comp_niche, issues)
            
            results.append({
                'Company Name': comp_name,
                'Website': web_url,
                'Contact Email': contact_email,
                'Niche': comp_niche,
                'Scrape Status': scrape_status,
                'Issues Found': ' | '.join(issues) if issues else 'None detected',
                'Subject Line': subject,
                'Email Body': email_body.replace('\n', ' ')
            })
            
            time.sleep(1)  # Rate limiting
        
        progress.empty()
        status.success(f"✅ Processed {len(results)} leads!")
        
        # Store results in session state for batch approval
        st.session_state['batch_results'] = results
        
        results_df = pd.DataFrame(results)
        st.dataframe(results_df)
        
        csv = results_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download All Results",
            csv,
            "lead_emails.csv",
            "text/csv",
            use_container_width=True
        )

# --- EMAIL TRACKING LOG (from database) ---
st.markdown("---")
st.markdown("### 📋 Email Tracking Log")

log_rows = get_email_log()
if log_rows:
    log_df = pd.DataFrame(log_rows, columns=['Timestamp', 'Company', 'Website', 'Email', 'Niche', 'Subject', 'Status', 'Notes'])
    st.dataframe(log_df, use_container_width=True)
    
    csv_log = log_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Export Log to CSV",
        csv_log,
        f"email_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "text/csv",
        use_container_width=True
    )
else:
    st.info("No emails logged yet. Send or save emails to see them here.")
