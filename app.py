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

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

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
# 1. DATABASE & GOOGLE SHEETS SYNC
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
        requests.get(APPS_SCRIPT_URL, params=params, allow_redirects=True, timeout=10)
        return True
    except Exception as e:
        print(f"Apps Script Exception: {e}")
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
        print(f"Load Google Sheet Error: {e}")
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
        print(f"Save user local failed: {e}")
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
        print(f"Load users local error: {e}")
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
        print(f"Save log local failed: {e}")
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
    <div class="header-container" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <img src="{logo_src}" alt="AccAstroForge Logo" style="height: 75px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7));">
        </div>
        <div style="display: flex; align-items: center; background: rgba(18, 8, 42, 0.9); padding: 8px 12px; border-radius: 12px; border: 1px solid rgba(244, 114, 182, 0.5);">
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer;"></span>
        </div>
    </div>
    """
else:
    logo_element = """
    <div class="header-container" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px; font-weight: 800; color: #fbcfe8; font-family: 'Cinzel', serif;">AccAstroForge</span>
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer;"></span>
        </div>
    </div>
    """

# ---------------------------------------------------------
# 2. EMAIL, ASTROLOGY & RAZORPAY FUNCTIONS
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

def calculate_astrological_profile(name, dob_str):
    try:
        dt = datetime.datetime.strptime(dob_str, "%Y-%m-%d")
        day_sum = sum(int(digit) for digit in dob_str if digit.isdigit())
        while day_sum > 9:
            day_sum = sum(int(d) for d in str(day_sum))
        zodiac_index = (dt.month - 1 + (dt.day // 3)) % 12
        return {
            "name": name if name else "User",
            "zodiac": ZODIAC_SIGNS[zodiac_index],
            "psychic_num": day_sum,
            "dasha": f"Mahadasha of {['Jupiter', 'Saturn', 'Mercury', 'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu'][day_sum % 9]} is active."
        }
    except Exception:
        return {"name": name if name else "User", "zodiac": "Aries (Mesha)", "psychic_num": 7, "dasha": "Favorable Dasha active."}

def run_daily_horoscope(sign):
    return f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>🔮 Daily Vedic Horoscope for {sign}</h3><p>Today brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace in personal relationships. Wear yellow or amber for extra luck!</p></div>"""

def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b_name} & {g_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)"})
    teaser = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>❤️ Kundali Compatibility Teaser for {b_name} & {g_name}</h3><p>High Guna Milan score detected! Excellent long-term emotional alignment observed.</p></div>"""
    return teaser, get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")

def generate_visual_kundali_chart_html(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    return f"""
    <div style="background: rgba(10, 3, 28, 0.95); border: 2px solid #7c3aed; border-radius: 16px; padding: 20px; color: #fff; margin-top: 15px;">
        <h3 style="color: #fde047; text-align: center;">📜 VEDIC LAGNA KUNDALI CHART - {name.upper()}</h3>
        <p style="text-align: center; color: #ffffff;">DOB: <b>{dob}</b> | TOB: <b>{tob}</b> | POB: <b>{pob}</b> | Rashi: <b style="color: #4ade80;">{profile['zodiac']}</b></p>
    </div>
    """

def create_kundali_pdf_file(name, dob, tob, pob):
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("<b>AccAstroForge - Janam Kundali Report</b>", styles['Heading1']), Spacer(1, 10)]
    doc.build(story)
    return filename

def get_robust_razorpay_link(service_name, price, user_name):
    try:
        if razorpay_client:
            data = {
                "amount": int(price) * 100,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Payment for {service_name}",
                "customer": {"name": user_name if user_name else "User"},
                "callback_url": "https://accastroforge.in/",
                "callback_method": "get"
            }
            response = razorpay_client.payment_link.create(data)
            if response and "short_url" in response:
                return response["short_url"]
    except Exception as e:
        print(f"Razorpay API error: {e}")
    return f"{RAZORPAY_ME_URL}?amount={price}"

def get_paywall_html(service_name, price, user_name="User"):
    display_name = user_name.strip() if user_name and user_name.strip() else "User"
    pay_url = get_robust_razorpay_link(service_name, price, display_name)
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; text-align: center;">
        <h3 style="color: #fde047 !important;">🔒 UNLOCK {service_name.upper()} (₹{price} ONLY)</h3>
        <p style="color: #f3e8ff !important;">Dear <b style="color: #fde047;">{display_name}</b>, click below to pay via UPI or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold;">Total Payable: ₹{price}</p>
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; display: inline-block;">🚀 Proceed to Pay ₹{price}</a>
    </div>
    """

# ---------------------------------------------------------
# 3. AUTH & HANDLERS
# ---------------------------------------------------------
def handle_manual_signup(name, email, phone, password):
    u_name = name.strip() if name else "New User"
    u_email = email.strip().lower() if email else "N/A"
    u_phone = phone.strip() if phone else "N/A"
    if not u_email or "@" not in u_email:
        return "<span style='color:#ef4444;'>❌ Valid email required.</span>", "👤 Guest User", "₹ 0.00", "Error", ""
    if not u_phone or len(u_phone) < 10:
        return "<span style='color:#ef4444;'>❌ Valid 10-digit phone required.</span>", "👤 Guest User", "₹ 0.00", "Error", ""

    users = load_users()
    for existing in users:
        if isinstance(existing, dict) and (existing.get("email") == u_email or existing.get("Email") == u_email):
            return "<span style='color:#ef4444;'>⚠️ Email already registered. Please login.</span>", "👤 Guest User", "₹ 0.00", "Exists", ""

    otp_code = str(random.randint(100000, 999999))
    email_html = f"<div style='background:#030014; color:#fff; padding:20px;'><h2>OTP: {otp_code}</h2></div>"
    send_brevo_email(u_email, u_name, "AccAstroForge OTP", email_html)
    return f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; color:#fff;'>📧 OTP sent to {u_email}.</div>", f"👤 <b>{u_name}</b> ({u_email})", "₹ 0.00", "Pending", otp_code

def verify_user_otp(user_entered_otp, generated_otp, u_name, u_email, u_phone):
    if not generated_otp or str(user_entered_otp).strip() != str(generated_otp).strip():
        return "<span style='color:#ef4444;'>❌ Invalid OTP.</span>", "👤 Guest User", "₹ 0.00", "Failed", ""
    save_user_db_single(u_name, u_email, u_phone)
    success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; color:#fff;'>🎉 Account Verified & Active!</div>"
    profile_box = f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #4ade80;'>Status: Active Member</span>"
    return success_msg, profile_box, "₹ 0.00", "Active", f"{u_email}|{u_name}|{u_phone}"

def handle_login(login_email, login_pass):
    l_email = login_email.strip().lower() if login_email else ""
    users = load_users()
    matched = next((u for u in users if str(u.get("email", u.get("Email", ""))).strip().lower() == l_email), None)
    if not matched:
        return "<span style='color:#ef4444;'>⚠️ Account not found.</span>", "👤 Guest User", "₹ 0.00", "Not found", ""
    u_name = matched.get("name", matched.get("Name", "User"))
    u_phone = matched.get("phone", matched.get("Phone", "N/A"))
    success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; color:#fff;'>🎉 Welcome back, {u_name}!</div>"
    profile_box = f"👤 <b>{u_name}</b> ({l_email})<br><span style='color: #4ade80;'>Status: Active Session</span>"
    return success_msg, profile_box, "₹ 0.00", "Active", f"{l_email}|{u_name}|{u_phone}"

def handle_logout():
    return "<div style='background:rgba(59,130,246,0.15); border:1px solid #3b82f6; padding:15px; color:#fff;'>🔒 Logged out successfully.</div>", "👤 Guest User", "₹ 0.00", "Guest", ""

def restore_session_from_token(token):
    if not token or "|" not in token:
        return gr.update(), gr.update(), gr.update()
    parts = token.split("|")
    return f"👤 <b>{parts[1]}</b> ({parts[0]})", "₹ 0.00", "Restored"

def recharge_wallet(amount):
    pay_url = get_robust_razorpay_link(f"AccAstroForge Wallet Topup (₹{amount})", amount, "Valued Customer")
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center;">
        <h4 style="color: #4ade80 !important;">💳 Add ₹{amount} Credits</h4>
        <a href="{pay_url}" target="_blank" style="background: #22c55e; color: white !important; padding: 8px 20px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block;">⚡ Pay ₹{amount} & Top Up</a>
    </div>
    """

def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "<span style='color:#ef4444;'>❌ Incorrect Password!</span>"
    logs = load_logs()
    users = load_users()
    return f"<div style='color:#fff;'><h3 style='color:#fde047;'>🛡️ Admin Dashboard</h3><p>Users: {len(users)} | Logs: {len(logs)}</p></div>"

def simple_astro_query(user_query):
    return f"<div style='color:#ffffff;'><p><b style='color:#fde047;'>Query:</b> {user_query}</p><p>🙏 Namaste! Planetary alignments are favorable. Keep faith and work with dedication.</p></div>"

# ---------------------------------------------------------
# 4. CSS & UI BLOCK
# ---------------------------------------------------------
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');
html, body, .gr-root, .gradio-container, gradio-app {
    background-color: #030014 !important;
    background-image: linear-gradient(rgba(5, 1, 20, 0.45), rgba(5, 1, 20, 0.6)), url("https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/bg.jpg") !important;
    background-size: cover !important; background-attachment: fixed !important;
    color: #ffffff !important; font-family: 'Poppins', sans-serif !important; min-height: 100vh;
}
footer, header, #footer, .footer, .built-with { display: none !important; }
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
            setTimeout(() => {
                const syncBtn = document.querySelector('#session-sync-btn');
                if (syncBtn) syncBtn.click();
            }, 500);
        }
    }
}
setInterval(handlePersistentSession, 400);
</script>
"""

with gr.Blocks(title="AccAstroForge", css=custom_css, head=head_html) as demo:
    otp_state = gr.State(value="")
    session_token_state = gr.Textbox(value="", elem_id="session-token-box", visible=False)

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4):
                gr.HTML(f"""
                <div style="background: rgba(18, 8, 42, 0.85); padding: 10px 18px; border-radius: 14px; display: flex; gap: 8px; justify-content: flex-end;">
                    <span style="font-size: 0.8rem; color: #fde047;">🔐 Quick Logins:</span>
                    <a href="{GOOGLE_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #ea4335; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="{FACEBOOK_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #1877f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                </div>
                """)

        with gr.Tabs():
            with gr.TabItem("👤 DASHBOARD"):
                gr.HTML("<h3 style='color:#fde047;'>👤 User Profile, Wallet & Order History</h3>")
                with gr.Row():
                    user_profile_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; width: 100%; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="color: #fde047; margin-bottom: 4px;">👤 Active User Session</h4>
                            <p style="color: #ffffff; margin: 0;">Guest User (Please Sign Up / Login)</p>
                        </div>
                        <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; padding: 8px 18px; border-radius: 20px; font-weight: 800; cursor: pointer;">📝 SIGN UP / SWITCH</button>
                    </div>
                    """)
                    wallet_balance_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; width: 100%;">
                        <h4 style="color: #fde047; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80;">₹ 0.00</span></h4>
                        <p style="color: #f3e8ff; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking.</p>
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
                                signup_pass = gr.Textbox(label="Password", type="password")
                            signup_btn = gr.Button("✨ 1. Register & Send OTP", variant="primary")
                            signup_output = gr.HTML()
                            with gr.Row():
                                user_otp_input = gr.Textbox(label="Enter 6-Digit OTP", max_lines=1)
                                verify_otp_btn = gr.Button("🔑 2. Verify OTP", variant="primary")
                        with gr.TabItem("🔐 Member Login"):
                            with gr.Row():
                                login_email_input = gr.Textbox(label="Registered Email")
                                login_pass_input = gr.Textbox(label="Password", type="password")
                            login_btn = gr.Button("🚀 Sign In", variant="primary")
                            login_output = gr.HTML()

                order_history_display = gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                    <h4 style="color: #fde047 !important; margin-bottom: 6px; font-size: 1rem;">📦 Order History & Saved PDF Reports</h4>
                    <p style="color: #cbd5e1 !important; font-size: 0.85rem; margin: 0;">No previous orders found for current guest session.</p>
                </div>
                """)

                with gr.Row():
                    topup_amount = gr.Radio(choices=["100", "250", "500", "1000"], value="250", label="Select Topup Amount (₹)")
                    topup_btn = gr.Button("⚡ Topup Wallet Credits", variant="primary")
                wallet_pay_output = gr.HTML()
                topup_btn.click(fn=recharge_wallet, inputs=[topup_amount], outputs=[wallet_pay_output])

                signup_btn.click(fn=handle_manual_signup, inputs=[signup_name, signup_email, signup_phone, signup_pass], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, otp_state])
                verify_otp_btn.click(fn=verify_user_otp, inputs=[user_otp_input, otp_state, signup_name, signup_email, signup_phone], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])
                login_btn.click(fn=handle_login, inputs=[login_email_input, login_pass_input], outputs=[login_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])

            with gr.TabItem("🌟 LIFE PREDICTION"):
                gr.HTML("<h3 style='color:#fde047;'>🌌 Vedic Astrology & Deep Life Forecast</h3>")
                name_input = gr.Textbox(label="Full Name")
                dob_input = gr.Textbox(label="DOB (YYYY-MM-DD)")
                tob_input = gr.Textbox(label="TOB (HH:MM)")
                pob_input = gr.Textbox(label="POB")
                phone_input = gr.Textbox(label="Phone")
                email_input = gr.Textbox(label="Email")
                address_input = gr.Textbox(label="Address")
                focus_dropdown = gr.Dropdown(choices=["General Life & Destiny", "Career & Wealth Growth", "Love & Marriage", "Health & Spiritual Growth"], value="General Life & Destiny", label="Focus Area")
                question_input = gr.Textbox(label="Question")
                submit_life = gr.Button("✨ Reveal Detailed Life Insights (₹499)", variant="primary")
                output_life_teaser = gr.HTML()
                output_life_paywall = gr.HTML()
                submit_life.click(fn=lambda *args: ("<h3 style='color:#fde047;'>🌟 Life Forecast Teaser</h3>", get_paywall_html("Complete Deep Life Forecast & PDF", 499, args[0])), inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input], outputs=[output_life_teaser, output_life_paywall])

            with gr.TabItem("☀️ HOROSCOPE"):
                gr.HTML("<h3 style='color:#fde047;'>🔮 Daily Zodiac Predictions</h3>")
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Zodiac Sign")
                submit_horoscope = gr.Button("🔮 Get Horoscope", variant="primary")
                output_horoscope = gr.HTML()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            with gr.TabItem("❤️ MATCHING"):
                gr.HTML("<h3 style='color:#fde047;'>💍 Vedic Compatibility & Guna Milan</h3>")
                boy_name = gr.Textbox(label="Boy's Name")
                boy_dob = gr.Textbox(label="Boy's DOB")
                girl_name = gr.Textbox(label="Girl's Name")
                girl_dob = gr.Textbox(label="Girl's DOB")
                submit_matching = gr.Button("❤️ Match Kundalis Now (₹399)", variant="primary")
                output_matching = gr.HTML()
                output_matching_paywall = gr.HTML()
                submit_matching.click(fn=run_kundali_matching, inputs=[boy_name, boy_dob, girl_name, girl_dob], outputs=[output_matching, output_matching_paywall])

            with gr.TabItem("💎 GEMSTONES"):
                gr.HTML("<h3 style='color:#fde047;'>🧿 Lucky Gemstones</h3>")
                gem_dob = gr.Textbox(label="DOB")
                gem_zodiac = gr.Dropdown(choices=ZODIAC_SIGNS, label="Zodiac")
                submit_gem = gr.Button("💎 Find My Gemstone (₹299)", variant="primary")
                output_gem = gr.HTML()
                output_gem_paywall = gr.HTML()
                submit_gem.click(fn=lambda d, z: ("<h3 style='color:#fde047;'>💎 Gemstone Teaser</h3>", get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")), inputs=[gem_dob, gem_zodiac], outputs=[output_gem, output_gem_paywall])

            with gr.TabItem("📜 KUNDALI & BIRTH PDF"):
                gr.HTML("<h3 style='color:#fde047;'>📜 Janam Kundali & Lagna Birth Chart Generator</h3>")
                k_name = gr.Textbox(label="Full Name")
                k_dob = gr.Textbox(label="DOB (YYYY-MM-DD)")
                k_tob = gr.Textbox(label="TOB (HH:MM)")
                k_pob = gr.Textbox(label="POB")
                submit_kundali_pdf = gr.Button("📜 Generate PDF (₹299)", variant="primary")
                output_kundali_pdf_text = gr.HTML()
                output_visual_chart = gr.HTML()
                output_kundali_file = gr.File(label="Download PDF")
                output_kundali_paywall = gr.HTML()
                submit_kundali_pdf.click(fn=lambda n, d, t, p: ("<h3 style='color:#fde047;'>📜 Generated</h3>", generate_visual_kundali_chart_html(n, d, t, p), create_kundali_pdf_file(n, d, t, p), get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, n)), inputs=[k_name, k_dob, k_tob, k_pob], outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall])

            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.HTML("<h3 style='color:#fde047;'>🔢 Numerology Check</h3>")
                n_name = gr.Textbox(label="Name")
                n_dob = gr.Textbox(label="DOB")
                submit_num = gr.Button("🔢 Analyze (₹249)", variant="primary")
                output_num = gr.HTML()
                output_num_paywall = gr.HTML()
                submit_num.click(fn=lambda n, d: ("<h3 style='color:#fde047;'>Numerology Preview</h3>", get_paywall_html("Detailed Numerology & Name Correction Report", 249, n)), inputs=[n_name, n_dob], outputs=[output_num, output_num_paywall])

            with gr.TabItem("📅 PANCHANG"):
                gr.HTML("<h3 style='color:#fde047;'>📅 Vedic Panchang</h3>")
                p_date = gr.Textbox(label="Date")
                p_city = gr.Textbox(label="City")
                p_mode = gr.Radio(choices=["Free Daily Panchang", "Detailed Shubh Muhurat Report (₹99)"], value="Free Daily Panchang")
                submit_panchang = gr.Button("📅 Check", variant="primary")
                output_panchang = gr.HTML()
                output_panchang_paywall = gr.HTML()
                submit_panchang.click(fn=lambda d, c, m: ("<h3 style='color:#fde047;'>Panchang</h3>", get_paywall_html("Detailed Shubh Muhurat Report", 99, "User") if "Detailed" in m else ""), inputs=[p_date, p_city, p_mode], outputs=[output_panchang, output_panchang_paywall])

            with gr.TabItem("🤖 AI ASSISTANT"):
                gr.HTML("<h3 style='color:#fde047;'>🤖 Ask Astrologer</h3>")
                ai_input = gr.Textbox(label="Query")
                ai_submit = gr.Button("Ask ✨", variant="primary")
                ai_output = gr.HTML()
                ai_submit.click(fn=simple_astro_query, inputs=ai_input, outputs=ai_output)

        manual_signup_trigger = gr.Button("Trigger", elem_id="manual-signup-trigger")
        manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state := gr.State(value=False)], outputs=[signup_state, signup_group])

        session_sync_btn = gr.Button("Sync", elem_id="session-sync-btn")
        session_sync_btn.click(fn=restore_session_from_token, inputs=[session_token_state], outputs=[user_profile_display, wallet_balance_display, order_history_display := gr.HTML()])

        session_token_state.change(fn=None, inputs=[session_token_state], outputs=None, js="(token) => { if(token) localStorage.setItem('accastroforge_session', token); else localStorage.removeItem('accastroforge_session'); }")

        with gr.Group(visible=False) as admin_group:
            with gr.Accordion("🔒 Admin Dashboard", open=True):
                secret_pass = gr.Textbox(label="Password", type="password")
                unlock_btn = gr.Button("Unlock", variant="primary")
                secret_output = gr.HTML()
                unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=secret_output)

        real_hidden_trigger = gr.Button("Trigger Admin", elem_id="real-hidden-trigger")
        real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state := gr.State(value=False)], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, head=head_html, favicon_path="favicon.png")
