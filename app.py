import base64
import datetime
import hashlib
import io
import json
import os
import random
import gradio as gr
import razorpay
import requests
import sqlite3
from urllib.parse import quote_plus
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# ---------------------------------------------------------
# 0. CONFIGURATIONS & SECRETS
# ---------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_live_TpnrjMektRCWj8")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "tm4Ry6xdY63egZtf5cD0kP8T")
RAZORPAY_ME_URL = "https://razorpay.me/@accastroforge"

BREVO_API_KEY = os.getenv("BREVO_API_KEY")

GOOGLE_CLIENT_ID = "967117558722-40q6p107agttv35a47jlmq907j87bnpp.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "https://accastroforge.in/"

FACEBOOK_APP_ID = "1487294163221538"
FACEBOOK_APP_SECRET = "b0bacbcf5968b456843fe66aeea8af47"
FACEBOOK_REDIRECT_URI = "https://accastroforge.in/"

GOOGLE_OAUTH_URL = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=token&scope=email%20profile"
FACEBOOK_OAUTH_URL = f"https://www.facebook.com/v12.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={FACEBOOK_REDIRECT_URI}&response_type=token&scope=email,public_profile"

GOOGLE_SPREADSHEET_ID = "1nJ8ferhQ10A2MLeeyxhdOzOk7R7XJVcrlirFzwqrKpQ"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCOjnJySc7mB7vu5BcWhmn7t5f-lPG7EkC03Hc2SCKyMhvOrFz2tZmM1I5obCAm2YM/exec"

# ---------------------------------------------------------
# 1. DATABASE & GOOGLE SHEETS SYSTEM
# ---------------------------------------------------------
DB_FILE = "accastroforge.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            verified_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            full_name TEXT,
            service TEXT,
            details TEXT,
            payment_status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def append_to_google_sheet_direct(worksheet_name, values_list):
    try:
        if worksheet_name == "Users":
            params = {
                "worksheet": "Users",
                "name": values_list[0],
                "email": values_list[1],
                "phone": values_list[2],
                "verified_at": values_list[3]
            }
        else:
            params = {
                "worksheet": "AdminLogs",
                "timestamp": values_list[0],
                "full_name": values_list[1],
                "service": values_list[2],
                "details": values_list[3],
                "payment_status": values_list[4]
            }
        response = requests.get(APPS_SCRIPT_URL, params=params, allow_redirects=True, timeout=10)
        return True
    except Exception as e:
        print(f"Apps Script Error: {e}")
        return False

def load_google_sheet_direct(worksheet_name):
    try:
        url = f"{APPS_SCRIPT_URL}?action=get&worksheet={worksheet_name}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"Load Sheet Error: {e}")
    return []

def save_user_db_single(u_name, u_email, u_phone):
    now_str = str(datetime.datetime.now())
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO users (name, email, phone, verified_at)
            VALUES (?, ?, ?, ?)
        """, (u_name, u_email.lower(), u_phone, now_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save user error: {e}")
    append_to_google_sheet_direct("Users", [u_name, u_email.lower(), u_phone, now_str])

def load_users():
    users_dict = {}
    sheet_rows = load_google_sheet_direct("Users")
    for row in sheet_rows:
        if isinstance(row, dict):
            email = str(row.get("email", row.get("Email", ""))).strip().lower()
            if email:
                users_dict[email] = {
                    "name": row.get("name", row.get("Name", "User")),
                    "email": email,
                    "phone": row.get("phone", row.get("Phone", "N/A")),
                    "verified_at": row.get("verified_at", row.get("Verified_At", str(datetime.datetime.now())))
                }
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            d = dict(row)
            email = str(d.get("email", "")).strip().lower()
            if email and email not in users_dict:
                users_dict[email] = d
    except Exception as e:
        print(f"Load local users error: {e}")
    return list(users_dict.values())

def save_log(user_data):
    ts = user_data.get("timestamp", str(datetime.datetime.now()))
    fn = user_data.get("full_name", "N/A")
    srv = user_data.get("service", "General")
    dtl = user_data.get("details", "N/A")
    pst = user_data.get("payment_status", "Pending")

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO admin_logs (timestamp, full_name, service, details, payment_status)
            VALUES (?, ?, ?, ?, ?)
        """, (ts, fn, srv, dtl, pst))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save log error: {e}")
    append_to_google_sheet_direct("AdminLogs", [ts, fn, srv, dtl, pst])

def load_logs():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_logs")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Load logs error: {e}")
        return []

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")
logo_path = "logo.png" if os.path.exists("logo.png") else None

def get_base64(file_path):
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return ""
    return ""

logo_b64 = get_base64(logo_path)
logo_src = "data:image/png;base64," + logo_b64 if logo_b64 else ""

if logo_src:
    logo_element = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <img src="{logo_src}" alt="AccAstroForge Logo" style="height: 75px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7));">
        </div>
        <div style="display: flex; align-items: center; background: rgba(18, 8, 42, 0.9); padding: 8px 12px; border-radius: 12px; border: 1px solid rgba(244, 114, 182, 0.5);">
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
        </div>
    </div>
    """
else:
    logo_element = """
    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px; font-weight: 800; color: #fbcfe8; font-family: 'Cinzel', serif;">AccAstroForge</span>
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
        </div>
    </div>
    """

# ---------------------------------------------------------
# 2. EMAIL & ASTROLOGY ENGINE
# ---------------------------------------------------------
def send_brevo_email(to_email, user_name, subject, html_content):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": "AccAstroForge", "email": "arnabchaudhuriaiedits@gmail.com"},
        "to": [{"email": to_email, "name": user_name}],
        "subject": subject,
        "htmlContent": html_content
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Email error: {e}")
        return False

ZODIAC_SIGNS = [
    "Aries (Mesha)", "Taurus (Vrishabha)", "Gemini (Mithuna)", "Cancer (Karka)",
    "Leo (Simha)", "Virgo (Kanya)", "Libra (Tula)", "Scorpio (Vrischika)",
    "Sagittarius (Dhanu)", "Capricorn (Makara)", "Aquarius (Kumbha)", "Pisces (Meena)"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
    "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

def calculate_astrological_profile(name, dob_str):
    try:
        dt = datetime.datetime.strptime(dob_str, "%Y-%m-%d")
        day_sum = sum(int(digit) for digit in dob_str if digit.isdigit())
        while day_sum > 9:
            day_sum = sum(int(d) for d in str(day_sum))
        zodiac_index = (dt.month - 1 + (dt.day // 3)) % 12
        nakshatra_index = (dt.day + dt.month * 2) % 27
        return {
            "name": name if name else "User",
            "zodiac": ZODIAC_SIGNS[zodiac_index],
            "nakshatra": NAKSHATRAS[nakshatra_index],
            "psychic_num": day_sum,
            "dasha": f"Mahadasha of {['Jupiter', 'Saturn', 'Mercury', 'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu'][day_sum % 9]} is active."
        }
    except Exception:
        return {
            "name": name if name else "User",
            "zodiac": "Aries (Mesha)",
            "nakshatra": "Rohini",
            "psychic_num": 7,
            "dasha": "Favorable Planetary Dasha Cycle active."
        }

def generate_visual_kundali_chart_html(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    return f"""
    <div style="background: rgba(10, 3, 28, 0.95); border: 2px solid #7c3aed; border-radius: 16px; padding: 20px; color: #fff; margin-top: 15px;">
        <h3 style="color: #fde047; text-align: center; margin-bottom: 15px; font-family: 'Cinzel', serif;">📜 VEDIC LAGNA KUNDALI CHART - {name.upper()}</h3>
        <p style="text-align: center; color: #ffffff; background: rgba(30, 11, 60, 0.8); padding: 8px; border-radius: 10px; border: 1px solid #7c3aed;">
            DOB: <span style="color: #fde047;">{dob}</span> | TOB: <span style="color: #fde047;">{tob}</span> | Rashi: <span style="color: #4ade80; font-weight: 800;">{profile['zodiac']}</span>
        </p>
    </div>
    """

def create_kundali_pdf_file(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("<b>AccAstroForge - Vedic Janam Kundali Report</b>", styles['Heading1'])]
    doc.build(story)
    return filename

# ---------------------------------------------------------
# 3. ROBUST RAZORPAY PAYWALL FIX
# ---------------------------------------------------------
def get_robust_razorpay_link(service_name, price, user_name):
    clean_service = quote_plus(str(service_name).strip())
    clean_user = quote_plus(str(user_name).strip())
    return f"{RAZORPAY_ME_URL}?amount={price}&notes[service]={clean_service}&notes[user]={clean_user}"

def get_paywall_html(service_name, price, user_name="User"):
    display_name = user_name.strip() if user_name and user_name.strip() else "User"
    pay_url = get_robust_razorpay_link(service_name, price, display_name)
    
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center;">
        <h3 style="color: #fde047 !important; margin-bottom: 8px; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{price} ONLY)</h3>
        <p style="color: #f3e8ff !important; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below for instant secure checkout via UPI, GPay, PhonePe or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{price}</p>
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; display: inline-block;">
            🚀 Proceed to Pay ₹{price} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

# ---------------------------------------------------------
# 4. AUTH & SERVICES HANDLERS
# ---------------------------------------------------------
def handle_manual_signup(name, email, phone, password):
    u_name = name.strip() if name else "New User"
    u_email = email.strip().lower() if email else "N/A"
    u_phone = phone.strip() if phone else "N/A"

    if not u_email or "@" not in u_email:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Enter valid email.</span>", "👤 Guest User", "₹ 0.00", "", ""
    if not u_phone or len(u_phone) < 10:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Enter valid 10-digit phone.</span>", "👤 Guest User", "₹ 0.00", "", ""

    otp_code = str(random.randint(100000, 999999))
    email_html = f"<h3>OTP: {otp_code}</h3>"
    send_brevo_email(u_email, u_name, "OTP Verification", email_html)
    
    return "<div style='color:#4ade80;'>📧 OTP Dispatched Successfully!</div>", f"👤 <b>{u_name}</b> ({u_email})", "₹ 0.00", "OTP sent", otp_code

def verify_user_otp(user_entered_otp, generated_otp, u_name, u_email, u_phone):
    if not generated_otp or str(user_entered_otp).strip() != str(generated_otp).strip():
        return "<div style='color:#ef4444;'>❌ Invalid OTP</div>", "👤 Guest User", "₹ 0.00", "", ""
    
    save_user_db_single(u_name, u_email, u_phone)
    profile_box = f"👤 <b>{u_name}</b> ({u_email}) [Active]"
    session_token = f"{u_email}|{u_name}|{u_phone}"
    return "<div style='color:#4ade80;'>🎉 Verified!</div>", profile_box, "₹ 0.00", "Active Session", session_token

def handle_login(email, password):
    l_email = email.strip().lower()
    users = load_users()
    for u in users:
        if u.get("email") == l_email:
            name = u.get("name", "User")
            phone = u.get("phone", "N/A")
            return "<div style='color:#4ade80;'>Login Success!</div>", f"👤 <b>{name}</b> ({l_email})", "₹ 0.00", "Active", f"{l_email}|{name}|{phone}"
    return "<div style='color:#ef4444;'>User not found.</div>", "👤 Guest User", "₹ 0.00", "", ""

def handle_logout():
    return "<div style='color:#60a5fa;'>Logged out</div>", "👤 Guest User (Please Sign Up / Login)", "₹ 0.00", "No orders", ""

def restore_session_from_token(token):
    if not token or "|" not in token:
        return gr.update(), gr.update(), gr.update()
    parts = token.split("|")
    return f"👤 <b>{parts[1]}</b> ({parts[0]})", "₹ 0.00", f"Session restored for {parts[0]}"

def run_daily_horoscope(sign):
    return f"<div style='color:#fff;'>🔮 Horoscope for {sign}: Excellent cosmic energy today.</div>"

def run_kundali_matching(b_name, b_dob, g_name, g_dob):
    return f"<div style='color:#fff;'>❤️ Matching Teaser for {b_name} & {g_name}</div>", get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")

def run_life_predictions(name, dob, tob, pob, focus, q, phone, email, addr):
    u_name = name if name else "User"
    return f"<div style='color:#fff;'>🌟 Life Forecast Teaser for {u_name}</div>", get_paywall_html("Complete Deep Life Forecast & PDF", 499, u_name)

def run_gemstone_remedy(dob, zodiac):
    return f"<div style='color:#fff;'>💎 Gemstone Teaser for {zodiac}</div>", get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")

def run_kundali_pdf(name, dob, tob, pob):
    u_name = name if name else "User"
    chart = generate_visual_kundali_chart_html(u_name, dob, tob, pob)
    pdf = create_kundali_pdf_file(u_name, dob, tob, pob)
    return f"<div style='color:#fff;'>📜 Kundali Generated</div>", chart, pdf, get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, u_name)

def run_numerology(name, dob):
    return f"<div style='color:#fff;'>🔢 Numerology Teaser for {name}</div>", get_paywall_html("Detailed Numerology Report", 249, name)

def run_panchang(date_str, city, mode):
    teaser = f"<div style='color:#fff;'>📅 Panchang for {city} on {date_str}</div>"
    if "Detailed" in mode:
        return teaser, get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
    return teaser, ""

def simple_astro_query(q):
    return f"<div style='color:#fff;'>🤖 AI Answer to '{q}': Planetary positions are favorable.</div>"

def recharge_wallet(amount):
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center;">
        <h4 style="color: #4ade80 !important;">💳 Topup ₹{amount}</h4>
        <a href="{get_robust_razorpay_link(f'Wallet Topup ₹{amount}', amount, 'Customer')}" target="_blank" style="background: #22c55e; color: white !important; padding: 10px 24px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block; margin-top: 10px;">
            ⚡ Pay ₹{amount} via Razorpay
        </a>
    </div>
    """

def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "<span style='color:#ef4444;'>❌ Incorrect Password</span>"
    users = load_users()
    logs = load_logs()
    return f"<div style='color:#fff;'><h3>Admin Panel</h3><p>Users: {len(users)} | Logs: {len(logs)}</p></div>"

# ---------------------------------------------------------
# 5. UI & BLOCKS
# ---------------------------------------------------------
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');
html, body, .gr-root, .gradio-container, gradio-app {
    background-color: #030014 !important;
    background-image: linear-gradient(rgba(5, 1, 20, 0.45), rgba(5, 1, 20, 0.6)), url("https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/bg.jpg") !important;
    background-size: cover !important; background-attachment: fixed !important;
    color: #ffffff !important; font-family: 'Poppins', sans-serif !important;
}
footer, header, #footer, .footer { display: none !important; }
button[role="tab"][aria-selected="true"] { background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important; color: #fff !important; }
input, textarea, select { background: rgba(22, 10, 48, 0.95) !important; border: 1.5px solid rgba(244, 114, 182, 0.7) !important; color: #fff !important; border-radius: 14px !important; }
#manual-signup-trigger, #real-hidden-trigger, #logout-trigger, #session-sync-btn { display: none !important; }
"""

head_html = """
<script>
function handlePersistentSession() {
    const savedSession = localStorage.getItem('accastroforge_session');
    if (savedSession) {
        const hiddenInput = document.querySelector('#session-token-box input');
        if (hiddenInput && hiddenInput.value !== savedSession) {
            hiddenInput.value = savedSession;
            hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
            setTimeout(() => { document.querySelector('#session-sync-btn').click(); }, 500);
        }
    }
}
setInterval(handlePersistentSession, 500);
</script>
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance") as demo:
    otp_state = gr.State(value="")
    session_token_state = gr.Textbox(value="", elem_id="session-token-box", visible=False)

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4):
                gr.HTML(f"""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 10px 18px; border-radius: 14px; display: flex; gap: 8px; align-items: center; justify-content: flex-end;">
                    <span style="font-size: 0.8rem; color: #fde047;">🔐 Quick:</span>
                    <a href="{GOOGLE_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #ea4335; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="{FACEBOOK_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #1877f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                </div>
                """)

        with gr.Tabs():
            with gr.TabItem("👤 DASHBOARD"):
                gr.HTML("<h3 style='color:#fde047;'>👤 User Profile, Wallet & Order History</h3>")
                
                gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1.5px dashed #f1c40f; padding: 12px 18px; border-radius: 12px; margin: 10px 0 15px 0; text-align: center;">
                    <p style="color: #f39c12 !important; font-size: 0.88rem; font-weight: 600; margin: 0;">💡 <b style="color: #fff;">Mobile View Notice:</b> Look at the extreme end of visible tabs for three dots (...) to open the drop-down menu.</p>
                </div>
                <div style="background: rgba(239, 68, 68, 0.15); border: 1.5px solid #ef4444; padding: 12px 18px; border-radius: 12px; margin: 10px 0 15px 0; text-align: center;">
                    <p style="color: #fca5a5 !important; font-size: 0.88rem; font-weight: 600; margin: 0;">⚠️ <b style="color: #fff;">Important Notice:</b> Please DO NOT refresh the page while performing transactions or filling forms.</p>
                </div>
                """)

                with gr.Row():
                    user_profile_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; display: flex; justify-content: space-between; align-items: center; width: 100%;">
                        <div>
                            <h4 style="color: #fde047 !important; margin-bottom: 4px;">👤 Active User Session</h4>
                            <p style="color: #fff !important; margin: 0;">Guest User (Please Sign Up / Login)</p>
                        </div>
                        <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #fff; border: 1px solid #fde047; padding: 8px 18px; border-radius: 20px; font-weight: 800; cursor: pointer;">
                            📝 SIGN UP / SWITCH
                        </button>
                    </div>
                    """)
                    wallet_balance_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; width: 100%;">
                        <h4 style="color: #fde047 !important; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80 !important;">₹ 0.00</span></h4>
                        <p style="color: #f3e8ff !important; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking.</p>
                    </div>
                    """)

                with gr.Group(visible=False) as signup_group:
                    with gr.Tabs():
                        with gr.TabItem("📝 Sign Up & Verify OTP"):
                            with gr.Row():
                                signup_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                                signup_email = gr.Textbox(label="Email Address", placeholder="e.g. user@gmail.com")
                            with gr.Row():
                                signup_phone = gr.Textbox(label="Phone Number", placeholder="e.g. 9876543210")
                                signup_pass = gr.Textbox(label="Password", type="password", placeholder="Password")
                            signup_btn = gr.Button("✨ 1. Register & Send OTP", variant="primary")
                            signup_output = gr.HTML()
                            with gr.Row():
                                user_otp_input = gr.Textbox(label="6-Digit Email OTP", placeholder="123456", max_lines=1)
                                verify_otp_btn = gr.Button("🔑 2. Verify OTP", variant="primary")

                        with gr.TabItem("🔐 Sign In / Login"):
                            with gr.Row():
                                login_email_input = gr.Textbox(label="Email", placeholder="user@gmail.com")
                                login_pass_input = gr.Textbox(label="Password", type="password", placeholder="Password")
                            login_btn = gr.Button("🚀 Sign In", variant="primary")
                            login_output = gr.HTML()

                order_history_display = gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px;">
                    <h4 style="color: #fde047 !important; margin-bottom: 6px;">📦 Order History</h4>
                    <p style="color: #cbd5e1 !important; font-size: 0.85rem; margin: 0;">No previous orders found for current guest session.</p>
                </div>
                """)

                with gr.Row():
                    topup_amount = gr.Radio(choices=["100", "250", "500", "1000"], value="250", label="Topup Amount (₹)")
                    topup_btn = gr.Button("⚡ Topup Wallet", variant="primary")
                wallet_pay_output = gr.HTML()
                topup_btn.click(fn=recharge_wallet, inputs=[topup_amount], outputs=[wallet_pay_output])

                signup_btn.click(fn=handle_manual_signup, inputs=[signup_name, signup_email, signup_phone, signup_pass], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, otp_state])
                verify_otp_btn.click(fn=verify_user_otp, inputs=[user_otp_input, otp_state, signup_name, signup_email, signup_phone], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])
                login_btn.click(fn=handle_login, inputs=[login_email_input, login_pass_input], outputs=[login_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])

            with gr.TabItem("🌟 LIFE PREDICTION"):
                gr.HTML("<h3 style='color:#fde047;'>🌌 Vedic Astrology & Deep Life Forecast</h3>")
                with gr.Row():
                    name_input = gr.Textbox(label="Full Name")
                    dob_input = gr.Textbox(label="DOB", placeholder="YYYY-MM-DD")
                with gr.Row():
                    tob_input = gr.Textbox(label="Time", placeholder="HH:MM")
                    pob_input = gr.Textbox(label="Place")
                with gr.Row():
                    phone_input = gr.Textbox(label="Phone")
                    email_input = gr.Textbox(label="Email")
                address_input = gr.Textbox(label="Address")
                focus_dropdown = gr.Dropdown(choices=["General", "Career", "Love", "Health"], value="General", label="Focus")
                question_input = gr.Textbox(label="Question")
                submit_life = gr.Button("✨ Reveal Life Insights (₹499)", variant="primary")
                output_life_teaser, output_life_paywall = gr.HTML(), gr.HTML()
                submit_life.click(fn=run_life_predictions, inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input], outputs=[output_life_teaser, output_life_paywall])

            with gr.TabItem("☀️ HOROSCOPE"):
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Sign")
                submit_horoscope = gr.Button("🔮 Get Horoscope", variant="primary")
                output_horoscope = gr.HTML()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            with gr.TabItem("❤️ MATCHING"):
                with gr.Row():
                    boy_name, boy_dob = gr.Textbox(label="Boy Name"), gr.Textbox(label="Boy DOB")
                with gr.Row():
                    girl_name, girl_dob = gr.Textbox(label="Girl Name"), gr.Textbox(label="Girl DOB")
                submit_matching = gr.Button("❤️ Match (₹399)", variant="primary")
                output_matching, output_matching_paywall = gr.HTML(), gr.HTML()
                submit_matching.click(fn=run_kundali_matching, inputs=[boy_name, boy_dob, girl_name, girl_dob], outputs=[output_matching, output_matching_paywall])

            with gr.TabItem("💎 GEMSTONES"):
                with gr.Row():
                    gem_dob, gem_zodiac = gr.Textbox(label="DOB"), gr.Textbox(label="Zodiac")
                submit_gem = gr.Button("💎 Gemstone (₹299)", variant="primary")
                output_gem, output_gem_paywall = gr.HTML(), gr.HTML()
                submit_gem.click(fn=run_gemstone_remedy, inputs=[gem_dob, gem_zodiac], outputs=[output_gem, output_gem_paywall])

            with gr.TabItem("📜 KUNDALI & BIRTH PDF"):
                with gr.Row():
                    k_name, k_dob = gr.Textbox(label="Name"), gr.Textbox(label="DOB")
                with gr.Row():
                    k_tob, k_pob = gr.Textbox(label="Time"), gr.Textbox(label="Place")
                submit_kundali_pdf = gr.Button("📜 Kundali PDF (₹299)", variant="primary")
                output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall = gr.HTML(), gr.HTML(), gr.File(), gr.HTML()
                submit_kundali_pdf.click(fn=run_kundali_pdf, inputs=[k_name, k_dob, k_tob, k_pob], outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall])

            with gr.TabItem("🔢 NUMEROLOGY"):
                with gr.Row():
                    n_name, n_dob = gr.Textbox(label="Name"), gr.Textbox(label="DOB")
                submit_num = gr.Button("🔢 Numerology (₹249)", variant="primary")
                output_num, output_num_paywall = gr.HTML(), gr.HTML()
                submit_num.click(fn=run_numerology, inputs=[n_name, n_dob], outputs=[output_num, output_num_paywall])

            with gr.TabItem("📅 PANCHANG"):
                with gr.Row():
                    p_date, p_city = gr.Textbox(label="Date"), gr.Textbox(label="City")
                p_mode = gr.Radio(choices=["Free Daily Panchang", "Detailed Shubh Muhurat Report (₹99)"], value="Free Daily Panchang")
                submit_panchang = gr.Button("📅 Panchang", variant="primary")
                output_panchang, output_panchang_paywall = gr.HTML(), gr.HTML()
                submit_panchang.click(fn=run_panchang, inputs=[p_date, p_city, p_mode], outputs=[output_panchang, output_panchang_paywall])

            with gr.TabItem("🤖 AI ASSISTANT"):
                ai_input = gr.Textbox(label="Query")
                ai_submit = gr.Button("Ask Assistant", variant="primary")
                ai_output = gr.HTML()
                ai_submit.click(fn=simple_astro_query, inputs=ai_input, outputs=ai_output)

            with gr.TabItem("⚖️ LEGAL"):
                gr.HTML("<div style='color:#fff;'><h4>Legal & Support</h4><p>Contact: support@accastroforge.in</p></div>")

    signup_state = gr.State(value=False)
    manual_signup_trigger = gr.Button("Trigger Signup", elem_id="manual-signup-trigger")
    manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state], outputs=[signup_state, signup_group])

    logout_trigger = gr.Button("Trigger Logout", elem_id="logout-trigger")
    logout_trigger.click(fn=handle_logout, outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])

    session_sync_btn = gr.Button("Sync Session", elem_id="session-sync-btn")
    session_sync_btn.click(fn=restore_session_from_token, inputs=[session_token_state], outputs=[user_profile_display, wallet_balance_display, order_history_display])

    session_token_state.change(fn=None, inputs=[session_token_state], outputs=None, js="(token) => { if(token) localStorage.setItem('accastroforge_session', token); else localStorage.removeItem('accastroforge_session'); }")

    with gr.Group(visible=False) as admin_group:
        with gr.Accordion("🔒 Owner Portal", open=True):
            secret_pass = gr.Textbox(label="Password", type="password")
            unlock_btn = gr.Button("Unlock", variant="primary")
            secret_output = gr.HTML()
            unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=secret_output)

    admin_state = gr.State(value=False)
    real_hidden_trigger = gr.Button("Trigger", elem_id="real-hidden-trigger")
    real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, head=head_html, favicon_path="favicon.png")
