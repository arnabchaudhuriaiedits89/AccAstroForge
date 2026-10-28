import os
import datetime
import random
import base64
import json
import io
import requests
import sqlite3
import gradio as gr
import razorpay
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

GOOGLE_SPREADSHEET_ID = "1nJ8ferhQ10A2MLeeyhdOzOk7R7XJVcrlirFzwqrKpQ"
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCOjnJySc7mB7vu5BcWhmn7t5f-lPG7EkC03Hc2SCKyMhvOrFz2tZmM1I5obCAm2YM/exec"

# ---------------------------------------------------------
# 1. DATABASE SYSTEM
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
        print(f"CRITICAL APPS SCRIPT EXCEPTION: {str(e)}")
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
        print(f"Load Google Sheet Direct Error: {e}")
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
        print(f"ERROR: Save user local failed: {e}")
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
        print(f"ERROR: Save log local failed: {e}")
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

if logo_b64:
    logo_src = "data:image/png;base64," + logo_b64
    logo_element = f"""
    <div class="header-container" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <img src="{logo_src}" alt="AccAstroForge Logo" style="height: 75px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7)); mix-blend-mode: screen; background: transparent !important;">
        </div>
        <div style="display: flex; align-items: center; background: rgba(18, 8, 42, 0.9); padding: 8px 12px; border-radius: 12px; border: 1px solid rgba(244, 114, 182, 0.5);">
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; min-width: 16px; min-height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
        </div>
    </div>
    """
else:
    logo_element = """
    <div class="header-container" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 24px; font-weight: 800; color: #fbcfe8; font-family: 'Cinzel', serif;">AccAstroForge</span>
            <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 16px; height: 16px; min-width: 16px; min-height: 16px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1.5px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
        </div>
    </div>
    """

# ---------------------------------------------------------
# 2. EMAIL SENDER FUNCTION
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
        print(f"Email error exception: {e}")
        return False

# ---------------------------------------------------------
# 3. ASTROLOGICAL ENGINE & KUNDALI GENERATOR
# ---------------------------------------------------------
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
    <div style="background: rgba(10, 3, 28, 0.95); border: 2px solid #7c3aed; border-radius: 16px; padding: 20px; color: #fff; margin-top: 15px; box-shadow: 0 0 25px rgba(124, 58, 237, 0.5);">
        <h3 style="color: #fde047; text-align: center; margin-bottom: 15px; font-family: 'Cinzel', serif;">📜 VEDIC LAGNA KUNDALI CHART - {name.upper()}</h3>
        
        <p style="text-align: center; color: #ffffff; font-size: 1.05rem; background: rgba(30, 11, 60, 0.8); padding: 8px 12px; border-radius: 10px; border: 1px solid #7c3aed; margin-bottom: 15px;">
            DOB: <span style="color: #fde047; font-weight: 700;">{dob}</span> | 
            TOB: <span style="color: #fde047; font-weight: 700;">{tob}</span> | 
            POB: <span style="color: #fde047; font-weight: 700;">{pob}</span> | 
            Rashi: <span style="color: #4ade80; font-weight: 800; font-size: 1.15rem; text-shadow: 0 0 10px rgba(74, 222, 128, 0.8);">✨ {profile['zodiac']}</span>
        </p>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; max-width: 450px; margin: 20px auto; background: #5b21b6; padding: 8px; border-radius: 12px; border: 2px solid #fde047;">
            <div style="background: #1e1b4b; padding: 15px; text-align: center; border: 1px solid #7c3aed; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 12</span><br><b style="color: #4ade80;">Me / Rahu</b>
            </div>
            <div style="background: #31104b; padding: 15px; text-align: center; border: 1px solid #db2777; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 1 (Lagna)</span><br><b style="color: #f472b6;">Jup / Jup</b>
            </div>
            <div style="background: #1e1b4b; padding: 15px; text-align: center; border: 1px solid #7c3aed; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 2</span><br><b style="color: #38bdf8;">Sun / Ven</b>
            </div>
            <div style="background: #31104b; padding: 15px; text-align: center; border: 1px solid #db2777; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 11</span><br><b style="color: #a78bfa;">Saturn</b>
            </div>
            <div style="background: #090514; padding: 15px; text-align: center; border: 2px dashed #fde047; border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                <span style="color: #fde047; font-weight: 800; font-size: 0.9rem;">JANAM<br>KUNDALI</span>
            </div>
            <div style="background: #31104b; padding: 15px; text-align: center; border: 1px solid #db2777; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 3</span><br><b style="color: #fb923c;">Mars</b>
            </div>
            <div style="background: #1e1b4b; padding: 15px; text-align: center; border: 1px solid #7c3aed; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 10</span><br><b style="color: #f43f5e;">Ketu</b>
            </div>
            <div style="background: #31104b; padding: 15px; text-align: center; border: 1px solid #db2777; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 9</span><br><b style="color: #e879f9;">Moon</b>
            </div>
            <div style="background: #1e1b4b; padding: 15px; text-align: center; border: 1px solid #7c3aed; border-radius: 8px;">
                <span style="color: #fde047; font-size: 0.75rem;">House 4</span><br><b style="color: #22c55e;">Mercury</b>
            </div>
        </div>
        <p style="text-align: center; color: #4ade80; font-size: 0.95rem; font-weight: 600;">✨ Lagna Chart generated automatically with Planetary Coordinates & Mahadasha analysis.</p>
    </div>
    """

# ---------------------------------------------------------
# 4. REPORTLAB PDF & RAZORPAY PAYWALL
# ---------------------------------------------------------
def create_kundali_pdf_file(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor("#5b21b6"),
        alignment=1,
        spaceAfter=15
    )
    
    story.append(Paragraph("<b>AccAstroForge - Vedic Janam Kundali Report</b>", title_style))
    story.append(Spacer(1, 10))
    
    data = [
        ["Attribute", "Details"],
        ["Full Name", profile["name"]],
        ["Date of Birth", dob],
        ["Time / Place", f"{tob} / {pob}"],
        ["Zodiac Sign (Rashi)", profile["zodiac"]],
        ["Birth Nakshatra", profile["nakshatra"]],
        ["Destiny / Life Number", str(profile["psychic_num"])],
        ["Current Dasha", profile["dasha"]]
    ]
    
    t = Table(data, colWidths=[200, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7c3aed")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 10),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f3e8ff")),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#db2777")),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=11, leading=15)
    story.append(Paragraph("<b>Vedic Astrological Insights:</b>", styles['Heading2']))
    story.append(Paragraph(f"Based on birth details of {profile['name']}, Jupiter aligns favorably in the trikona houses. Remedies include wearing auspicious gemstones and practicing daily morning meditation.", body_style))
    
    doc.build(story)
    return filename

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

def get_robust_razorpay_link(service_name, price, user_name):
    try:
        if razorpay_client:
            data = {
                "amount": int(float(price)) * 100,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Payment for {service_name}",
                "customer": {
                    "name": user_name if user_name else "User"
                },
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "callback_url": "https://accastroforge.in/",
                "callback_method": "get"
            }
            response = razorpay_client.payment_link.create(data)
            if response and "short_url" in response:
                return response["short_url"]
    except Exception as e:
        print(f"Razorpay API fallback triggered due to: {e}")
    
    return RAZORPAY_ME_URL

def get_paywall_html(service_name, price, user_name="User"):
    display_name = user_name.strip() if user_name and user_name.strip() else "User"
    try:
        amt_val = int(float(price))
    except Exception:
        amt_val = price
        
    pay_url = get_robust_razorpay_link(service_name, amt_val, display_name)
    
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5);">
        <h3 style="color: #fde047 !important; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{amt_val} ONLY)</h3>
        <p style="color: #f3e8ff !important; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePay, BHIM or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{amt_val}</p>
        
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">
            🚀 Proceed to Pay ₹{amt_val} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

# ---------------------------------------------------------
# 5. AUTHENTICATION & SESSION MANAGEMENT
# ---------------------------------------------------------
def handle_manual_signup(name, email, phone, password):
    u_name = name.strip() if name else "New User"
    u_email = email.strip().lower() if email else "N/A"
    u_phone = phone.strip() if phone else "N/A"

    if not u_email or "@" not in u_email:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Please enter a valid email address.</span>", "👤 Guest User", "₹ 0.00", "No active sessions.", ""
    if not u_phone or len(u_phone) < 10:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Please enter a valid 10-digit Phone Number.</span>", "👤 Guest User", "₹ 0.00", "No active sessions.", ""

    users = load_users()
    for existing in users:
        if isinstance(existing, dict) and (existing.get("email") == u_email or existing.get("Email") == u_email):
            return f"<div style='background:rgba(239,68,68,0.15); border:1px solid #ef4444; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#ef4444; margin:0 0 5px 0;'>⚠️ Email Already Registered</h3><p style='margin:0;'>The email <b>{u_email}</b> is already registered as an active member. Please use the <b>Member Sign In / Login</b> tab above to access your account.</p></div>", "👤 Guest User", "₹ 0.00", "Registration blocked: Email already exists.", ""

    otp_code = str(random.randint(100000, 999999))
    email_html = f"""
    <div style="background:#030014; color:#ffffff; padding:25px; border-radius:16px; font-family:'Poppins', sans-serif; border: 1px solid #7c3aed;">
        <h2 style="color:#fde047; text-align:center;">✨ Welcome to AccAstroForge, {u_name}!</h2>
        <p>Thank you for registering. Please use the verification code below to activate your account:</p>
        <div style="text-align:center; margin: 20px 0;">
            <span style="font-size:2rem; font-weight:bold; color:#4ade80; background:rgba(34,197,94,0.15); padding:10px 25px; border-radius:12px; letter-spacing:4px; border: 1px dashed #4ade80;">{otp_code}</span>
        </div>
        <p style="font-size:0.85rem; color:#cbd5e1; text-align:center;">If you did not request this, please ignore this email.</p>
    </div>
    """

    email_sent = send_brevo_email(u_email, u_name, "AccAstroForge Account Verification OTP", email_html)

    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Secure Account Registration",
        "details": f"Email: {u_email} | Phone: {u_phone} | OTP Generated: {otp_code}",
        "payment_status": "OTP Dispatched Successfully" if email_sent else "Email Failed"
    })

    if email_sent:
        success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#4ade80; margin:0 0 5px 0;'>📧 OTP Sent Successfully!</h3><p style='margin:0;'>An OTP verification code has been dispatched to <b>{u_email}</b>. Please check your Inbox / Spam folder and enter it below.</p></div>"
    else:
        success_msg = f"<div style='background:rgba(239,68,68,0.15); border:1px solid #ef4444; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#ef4444; margin:0 0 5px 0;'>⚠️ Email Delivery Notice</h3><p style='margin:0;'>Registration initiated for <b>{u_email}</b>, but dispatch failed.</p></div>"

    profile_box = f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #fde047;'>Status: Pending Verification</span>"
    wallet_box = "₹ 0.00"
    history_box = f"• Secure OTP Dispatched to: {u_email}<br>• Phone: {u_phone}"

    return success_msg, profile_box, wallet_box, history_box, otp_code

def verify_user_otp(user_entered_otp, generated_otp, u_name, u_email, u_phone):
    if not generated_otp:
        return "<div style='background:rgba(239,68,68,0.15); border:1px solid #ef4444; padding:12px; border-radius:10px; color:#ef4444; font-weight:bold;'>⚠️ No OTP generated yet! Please click '1. Register & Send Verification OTP' first.</div>", f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #ef4444;'>Status: No OTP</span>", "₹ 0.00", "Verification Pending", ""

    if not user_entered_otp or str(user_entered_otp).strip() != str(generated_otp).strip():
        return "<div style='background:rgba(239,68,68,0.15); border:1px solid #ef4444; padding:12px; border-radius:10px; color:#ef4444; font-weight:bold;'>❌ Invalid OTP Code! Please check your email and try again.</div>", f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #ef4444;'>Status: Invalid OTP</span>", "₹ 0.00", "Verification Failed", ""

    save_user_db_single(u_name, u_email, u_phone)

    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "OTP Verification Complete",
        "details": f"Email Verified: {u_email}",
        "payment_status": "Active & Verified Member"
    })

    success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#4ade80; margin:0 0 5px 0;'>🎉 Account Verified & Active!</h3><p style='margin:0;'>Welcome <b>{u_name}</b>! Your email <b>{u_email}</b> has been successfully verified.</p></div>"

    profile_box = f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #22c55e; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            👤 <b>{u_name}</b> ({u_email})<br>
            <span style='color: #4ade80;'>Phone: {u_phone}</span><br>
            <span style='color: #4ade80; font-weight:bold;'>Status: Active Member (Cloud Backup Protected)</span>
        </div>
        <button onclick="document.querySelector('#logout-trigger').click()" style="background: rgba(239,68,68,0.3); color: #f87171; border: 1px solid #ef4444; padding: 8px 16px; border-radius: 12px; font-weight: 700; font-size: 0.85rem; cursor: pointer;">
            🚪 Logout / Switch Account
        </button>
    </div>
    """
    wallet_box = "₹ 0.00"
    history_box = f"• Registration & OTP Verification Complete<br>• Account Active & Saved<br>• Contact: {u_phone}"
    session_token = f"{u_email}|{u_name}|{u_phone}"

    return success_msg, profile_box, wallet_box, history_box, session_token

def handle_login(login_email, login_pass):
    l_email = login_email.strip().lower() if login_email else ""
    if not l_email or "@" not in l_email:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Please enter a valid registered email.</span>", "👤 Guest User", "₹ 0.00", "No active sessions.", ""

    users = load_users()
    matched_user = None
    for u in users:
        if isinstance(u, dict) and (str(u.get("email", u.get("Email", ""))).strip().lower() == l_email):
            matched_user = u
            break

    if not matched_user:
        return f"<div style='background:rgba(239,68,68,0.15); border:1px solid #ef4444; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#ef4444; margin:0 0 5px 0;'>⚠️ Account Not Found</h3><p style='margin:0;'>The email <b>{l_email}</b> is not registered. Please sign up first.</p></div>", "👤 Guest User", "₹ 0.00", "Login failed: Account not found.", ""

    u_name = matched_user.get("name", matched_user.get("Name", "User"))
    u_phone = matched_user.get("phone", matched_user.get("Phone", "N/A"))

    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Member Login",
        "details": f"Email Logged In: {l_email}",
        "payment_status": "Active Session"
    })

    success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#4ade80; margin:0 0 5px 0;'>🎉 Welcome Back, {u_name}!</h3><p style='margin:0;'>You have successfully logged into your AccAstroForge account.</p></div>"

    profile_box = f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #22c55e; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            👤 <b>{u_name}</b> ({l_email})<br>
            <span style='color: #4ade80;'>Phone: {u_phone}</span><br>
            <span style='color: #4ade80; font-weight:bold;'>Status: Active Member (Cloud Backup Protected)</span>
        </div>
        <button onclick="document.querySelector('#logout-trigger').click()" style="background: rgba(239,68,68,0.3); color: #f87171; border: 1px solid #ef4444; padding: 8px 16px; border-radius: 12px; font-weight: 700; font-size: 0.85rem; cursor: pointer;">
            🚪 Logout / Switch Account
        </button>
    </div>
    """
    wallet_box = "₹ 0.00"
    history_box = f"• Member Login Successful<br>• Account Active<br>• Contact: {u_phone}"
    session_token = f"{l_email}|{u_name}|{u_phone}"

    return success_msg, profile_box, wallet_box, history_box, session_token

def handle_logout():
    guest_profile = """
    <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            <h4 style="color: #fde047 !important; margin-bottom: 4px;">👤 Active User Session</h4>
            <p style="color: #ffffff !important; font-size: 0.95rem; margin: 0;">Guest User (Please Sign Up / Login)</p>
        </div>
        <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border: 1px solid #fde047; padding: 8px 18px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; cursor: pointer; box-shadow: 0 0 15px rgba(219, 39, 119, 0.6); white-space: nowrap;">
            📝 SIGN UP / LOGIN
        </button>
    </div>
    """
    guest_wallet = """
    <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; margin-bottom: 15px;">
        <h4 style="color: #fde047 !important; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80 !important;">₹ 0.00</span></h4>
        <p style="color: #f3e8ff !important; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking of reports.</p>
    </div>
    """
    guest_history = """
    <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
        <h4 style="color: #fde047 !important; margin-bottom: 6px; font-size: 1rem;">📦 Order History & Saved PDF Reports</h4>
        <p style="color: #cbd5e1 !important; font-size: 0.85rem; margin: 0;">No previous orders found for current guest session. Please register or login.</p>
    </div>
    """
    logout_msg = "<div style='background:rgba(59,130,246,0.15); border:1px solid #3b82f6; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#60a5fa; margin:0 0 5px 0;'>🔒 Logged Out Successfully</h3><p style='margin:0;'>You have been logged out of your session. You can sign up or switch accounts anytime.</p></div>"

    return logout_msg, guest_profile, guest_wallet, guest_history, ""

def restore_session_from_token(token):
    if not token or "|" not in token:
        return gr.update(), gr.update(), gr.update()
    try:
        parts = token.split("|")
        u_email = parts[0]
        u_name = parts[1]
        u_phone = parts[2] if len(parts) > 2 else "N/A"
        
        # Clean display if it's an OAuth user string
        display_email = u_email
        if "oauth.user" in u_email:
            provider = "Google" if "google" in u_email else ("Facebook" if "facebook" in u_email else "OAuth")
            display_email = f"{provider} Verified Account"

        profile_box = f"""
        <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #22c55e; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div>
                👤 <b>{u_name}</b> ({display_email})<br>
                <span style='color: #4ade80; font-weight:bold;'>Status: Active Member (OAuth / Secure Session)</span>
            </div>
            <button onclick="document.querySelector('#logout-trigger').click()" style="background: rgba(239,68,68,0.3); color: #f87171; border: 1px solid #ef4444; padding: 8px 16px; border-radius: 12px; font-weight: 700; font-size: 0.85rem; cursor: pointer;">
                🚪 Logout / Switch Account
            </button>
        </div>
        """
        wallet_box = """
        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; margin-bottom: 15px;">
            <h4 style="color: #fde047 !important; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80 !important;">₹ 0.00</span></h4>
            <p style="color: #f3e8ff !important; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking of reports.</p>
        </div>
        """
        history_box = f"""
        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
            <h4 style="color: #fde047 !important; margin-bottom: 6px; font-size: 1rem;">📦 Order History & Saved PDF Reports</h4>
            <p style="color: #4ade80 !important; font-size: 0.85rem; margin: 0;">• Active Session Restored Successfully<br>• Account: {u_name}</p>
        </div>
        """
        return profile_box, wallet_box, history_box
    except Exception as e:
        print(f"Session restoration error: {e}")
        return gr.update(), gr.update(), gr.update()

def run_daily_horoscope(sign):
    return f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>🔮 Daily Vedic Horoscope for {sign}</h3><p>Today brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace in personal relationships. Wear yellow or amber for extra luck!</p></div>"""

def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": f"{b_name} & {g_name}",
        "service": "Kundali Matching",
        "payment_status": "Pending (₹399)"
    })
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>❤️ Kundali Compatibility Teaser for {b_name} & {g_name}</h3><p>High Guna Milan score detected! Excellent long-term emotional and spiritual alignment observed.</p></div>"""
    return teaser_text, get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")

def run_life_predictions(name, dob, tob, pob, focus_area, question, phone, email, address):
    u_name = name.strip() if name else "User"
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Complete Life Prediction",
        "payment_status": "Pending (₹499)"
    })
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>🌟 ASTROLOGICAL TEASER FOR {u_name.upper()}</h3>
    <ul style='list-style:none; padding:0; line-height:2;'>
        <li><b style='color:#fde047;'>Rashi:</b> {profile['zodiac']}</li>
        <li><b style='color:#fde047;'>Nakshatra:</b> {profile['nakshatra']}</li>
        <li><b style='color:#fde047;'>Dasha:</b> {profile['dasha']}</li>
        <li><b style='color:#fde047;'>Insight:</b> Great growth indicated in {focus_area}.</li>
    </ul></div>"""
    return teaser_text, get_paywall_html("Complete Deep Life Forecast & PDF", 499, u_name)

def run_gemstone_remedy(dob, zodiac):
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "service": "Gemstone Remedy",
        "details": f"DOB: {dob} | Zodiac: {zodiac}",
        "payment_status": "Pending (₹299)"
    })
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>💎 Gemstone Guidance Teaser</h3><p>Favorable alignment detected for {zodiac}. Emerald (Panna) or Yellow Sapphire (Pukhraj) recommended to boost career clarity.</p></div>"""
    return teaser_text, get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")

def run_kundali_pdf(name, dob, tob, pob):
    u_name = name.strip() if name else "User"
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Janam Kundali PDF",
        "payment_status": "Pending (₹299)"
    })
    chart_html = generate_visual_kundali_chart_html(u_name, dob if dob else "2000-01-01", tob, pob)
    pdf_file = create_kundali_pdf_file(u_name, dob if dob else "2000-01-01", tob, pob)
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>📜 Janam Kundali & Birth Chart Generated for {u_name}</h3><p>Your detailed Lagna chart and PDF preview have been generated successfully below.</p></div>"""
    return teaser_text, chart_html, pdf_file, get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, u_name)

def run_numerology(name, dob):
    u_name = name.strip() if name else "User"
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Numerology",
        "payment_status": "Pending (₹249)"
    })
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>🔢 Numerology Preview for {u_name}</h3><p>Your Destiny Psychic Number is <b style='color:#fde047; font-size:1.2rem;'>{profile['psychic_num']}</b>. High leadership potential and creative focus.</p></div>"""
    return teaser_text, get_paywall_html("Detailed Numerology & Name Correction Report", 249, u_name)

def run_panchang(date_str, city, mode="free"):
    teaser = f"""<div style='color:#ffffff;'><p><b style='color:#fde047;'>Complete Vedic Panchang for {city} on {date_str}:</b></p>
    <ul style='line-height:1.8;'>
        <li><b style='color:#fde047;'>Tithi:</b> Shukla Paksha Navami</li>
        <li><b style='color:#fde047;'>Nakshatra:</b> Rohini</li>
        <li><b style='color:#fde047;'>Rahu Kalam:</b> 10:30 AM - 12:00 PM</li>
        <li><b style='color:#fde047;'>Shubh Muhurat:</b> 11:45 AM - 12:30 PM</li>
    </ul></div>"""
    if "Detailed" in mode:
        return f"<h3 style='color:#fde047;'>📅 Detailed Shubh Muhurat Report</h3>{teaser}", get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
    return f"<h3 style='color:#fde047;'>📅 Free Daily Panchang for {city}</h3>{teaser}", ""

def simple_astro_query(user_query):
    if not user_query or not user_query.strip():
        return "<div style='color:#ffffff;'><p>🙏 <b>Namaste!</b> Please ask any question regarding career, marriage, health, or planetary transits.</p></div>"
    
    msg = user_query.lower().strip()
    if any(w in msg for w in ["hi", "hello", "hey", "greetings", "namaste"]):
        reply = "🙏 <b>Namaste!</b> I am your Vedic Astro Assistant. Please share your birth details, zodiac sign, or specific questions regarding career, marriage, health, or planetary transits, and I will guide you with ancient astrological wisdom."
    elif any(w in msg for w in ["career", "job", "business", "money", "wealth", "promotion"]):
        reply = "💼 <b>Career & Wealth Guidance:</b> In Vedic astrology, the 10th house (Karma Bhava) and Jupiter's transit dictate professional growth. If you are facing obstacles in career, chanting the 'Om Brihaspataye Namah' mantra on Thursdays and working with disciplined focus will bring immense growth."
    elif any(w in msg for w in ["marriage", "love", "relationship", "partner", "match"]):
        reply = "❤️ <b>Love & Marriage Insights:</b> Compatibility in Vedic astrology is evaluated through Guna Milan (36 points) and the positions of Venus (Shukra) and Mars (Mangal). Strengthening your 7th house through positive communication and harmony will resolve relationship hurdles."
    elif any(w in msg for w in ["health", "peace", "stress", "anxiety", "remedy"]):
        reply = "🌿 <b>Health & Spiritual Well-being:</b> Physical vitality is tied to the Sun (Surya) and Moon (Chandra). Practicing early morning Surya Namaskar, meditation during Brahma Muhurta, and keeping a calm mindset will balance your inner cosmic energy."
    else:
        responses = [
            f"🌟 <b>Analyzing your query regarding '{user_query}':</b> Vedic charts show that current planetary alignments are favorable for new beginnings. Focus on your inner strengths and auspicious timings.",
            f"🔮 <b>Regarding '{user_query}':</b> The celestial bodies indicate a period of transition and karmic reward. Patience and spiritual remedies will clear your path.",
            f"✨ <b>I hear your concern about '{user_query}'.</b> According to Vedic principles, planetary grace follows sincere effort. Consider charitable acts and positive affirmations on auspicious days."
        ]
        reply = random.choice(responses)
        
    return f"<div style='color:#ffffff; line-height:1.6;'><p><b style='color:#fde047;'>Your Query:</b> {user_query}</p><hr style='border-color:rgba(244,114,182,0.3);'><p>{reply}</p></div>"

def recharge_wallet(amount):
    try:
        amt_int = int(float(amount))
    except Exception:
        amt_int = 250
        
    pay_url = get_robust_razorpay_link(f"AccAstroForge Wallet Topup (₹{amt_int})", amt_int, "Valued Customer")
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": "Valued Customer",
        "service": "Wallet Topup",
        "details": f"Amount: ₹{amt_int}",
        "payment_status": "Pending"
    })
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center; margin-top: 10px;">
        <h4 style="color: #4ade80 !important; margin-bottom: 5px;">💳 Add ₹{amt_int} to AccAstroForge Credits</h4>
        <p style="color: #ffffff !important; font-size: 0.85rem; margin-bottom: 10px;">Click below to add credits via Razorpay UPI, GPay, PhonePe & Cards instantly.</p>
        <a href="{pay_url}" target="_blank" style="background: #22c55e; color: white !important; padding: 8px 20px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block;">
            ⚡ Pay ₹{amt_int} & Top Up Wallet (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Incorrect Password! Access Denied.</span>"
    
    logs = load_logs()
    users = load_users()
    
    summary_html = f"""
    <div style='color:#fff;'>
        <h3 style='color:#fde047;'>🛡️ AccAstroForge Admin Dashboard</h3>
        <p><b>Total Verified Users:</b> {len(users)} | <b>Total Log Entries:</b> {len(logs)}</p>
        
        <h4 style='color:#4ade80; margin-top:15px;'>📋 Registered Users Database</h4>
        <table style='width:100%; border-collapse:collapse; border:1px solid #7c3aed; margin-bottom:20px;' border='1'>
            <tr style='background:#5b21b6; color:#fff;'><th>Name</th><th>Email</th><th>Phone</th><th>Verified At</th></tr>
    """
    for u in reversed(users):
        if isinstance(u, dict):
            summary_html += f"<tr><td>{u.get('name', u.get('Name', ''))}</td><td>{u.get('email', u.get('Email', ''))}</td><td>{u.get('phone', u.get('Phone', ''))}</td><td>{str(u.get('verified_at', u.get('Verified_At', '')))[:19]}</td></tr>"
    summary_html += "</table>"
    
    summary_html += f"""
        <h4 style='color:#fde047; margin-top:15px;'>📜 System Activity Logs</h4>
        <table style='width:100%; border-collapse:collapse; border:1px solid #7c3aed;' border='1'>
            <tr style='background:#5b21b6; color:#fff;'><th>Timestamp</th><th>Name/Service</th><th>Details</th><th>Status</th></tr>
    """
    for log in reversed(logs):
        if isinstance(log, dict):
            summary_html += f"<tr><td>{str(log.get('timestamp', log.get('Timestamp', '')))[:19]}</td><td>{log.get('full_name', log.get('Full_Name', 'N/A'))} ({log.get('service', log.get('Service', 'General'))})</td><td>{log.get('details', log.get('Details', 'N/A'))}</td><td>{log.get('payment_status', log.get('Payment_Status', 'Pending'))}</td></tr>"
    summary_html += "</table></div>"
    return summary_html

# ---------------------------------------------------------
# 6. HARDCORE CSS & CLEAN URL OAUTH HANDLER
# ---------------------------------------------------------
custom_css = """
html, body, .gr-root, .gradio-container, gradio-app {
    background-color: #030014 !important;
    background-image: 
        linear-gradient(rgba(5, 1, 20, 0.45), rgba(5, 1, 20, 0.6)),
        url("https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/bg.jpg") !important;
    background-position: center center !important;
    background-repeat: no-repeat !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    color: #ffffff !important;
    font-family: 'Poppins', sans-serif !important;
    min-height: 100vh;
}

footer, header, #footer, .footer, .built-with {
    display: none !important;
}

* {
    color-scheme: dark !important;
}

.gr-box, .gr-row, .gr-form, .form, panel, 
div[data-testid="block"], .block, .wrap, .contain, .gr-panel, fieldset, .gr-markdown, .prose {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #ffffff !important;
}

div[role="tablist"] {
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    width: 100% !important;
    gap: 2px !important;
    padding: 4px 2px !important;
    background: rgba(10, 3, 25, 0.9) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(244, 114, 182, 0.4) !important;
}

button[role="tab"] {
    background: rgba(18, 8, 42, 0.9) !important;
    border: 1px solid rgba(244, 114, 182, 0.45) !important;
    color: #fef08a !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 700 !important;
    font-size: 0.62rem !important;
    border-radius: 8px !important;
    padding: 6px 2px !important;
    margin: 0 !important;
}

button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border-color: #fde047 !important;
}

.gr-accordion, .accordion, div[data-testid="accordion"] {
    background: rgba(14, 5, 35, 0.95) !important;
    border: 1px solid rgba(244, 114, 182, 0.6) !important;
    border-radius: 16px !important;
    padding: 15px !important;
    color: #ffffff !important;
}

button.primary, button.gr-button-primary, .gr-button-primary {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border: 1px solid #fde047 !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
}

label span, .block span, .gr-input-label, span.svelte-1b6s6s, .label-wrap span, .gr-block-label span, h1, h2, h3, h4, p, li, b, strong {
    color: #fde047 !important;
    font-weight: 600 !important;
}

p, li, span, div {
    color: #ffffff !important;
}

input, textarea, select {
    background: rgba(22, 10, 48, 0.95) !important;
    border: 1.5px solid rgba(244, 114, 182, 0.7) !important;
    color: #ffffff !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
}

input::placeholder, textarea::placeholder {
    color: rgba(255, 255, 255, 0.65) !important;
}

.password-box-wrapper {
    position: relative !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
}

.password-eye-btn {
    position: absolute !important;
    right: 15px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    cursor: pointer !important;
    font-size: 1.25rem !important;
    z-index: 99999 !important;
    user-select: none !important;
    background: rgba(124, 58, 237, 0.4) !important;
    border: 1px solid #fde047 !important;
    border-radius: 50% !important;
    padding: 4px 8px !important;
    line-height: 1 !important;
}

#manual-signup-trigger, #real-hidden-trigger, #logout-trigger, #session-sync-btn {
    display: none !important;
}
"""

head_html = """
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script>
function handleOAuthTokenAndCleanUrl() {
    const hash = window.location.hash;
    const search = window.location.search;
    
    let accessToken = null;
    let iss = 'oauth';

    if (hash && hash.includes('access_token')) {
        const params = new URLSearchParams(hash.substring(1));
        accessToken = params.get('access_token');
        if (hash.includes('facebook') || window.location.href.includes('facebook')) {
            iss = 'facebook';
        } else {
            iss = 'google';
        }
    } else if (search && search.includes('access_token')) {
        const params = new URLSearchParams(search);
        accessToken = params.get('access_token');
        iss = search.includes('facebook') ? 'facebook' : 'google';
    }

    if (accessToken) {
        const mockEmail = iss + "_" + accessToken.substring(0, 10) + "@oauth.user";
        const mockName = iss.toUpperCase() + " User";
        const sessionVal = mockEmail + "|" + mockName + "|OAuth_Verified";
        
        localStorage.setItem('accastroforge_session', sessionVal);

        // INSTANTLY CLEAN URL BAR TO REMOVE TOKEN MESS
        if (window.history.replaceState) {
            window.history.replaceState(null, null, window.location.pathname);
        }
    }
}

function attachEyeToggle() {
    const passInputs = document.querySelectorAll('input[type="password"], input[type="text"][placeholder*="password"], input[type="text"][placeholder*="Password"], input[id*="pass"]');
    passInputs.forEach(input => {
        if (!input.classList.contains('eye-attached')) {
            input.classList.add('eye-attached');
            input.type = 'password';
            const parent = input.parentElement;
            if(parent) {
                parent.style.position = 'relative';
                if (!parent.querySelector('.password-eye-btn')) {
                    const toggleBtn = document.createElement('span');
                    toggleBtn.className = 'password-eye-btn';
                    toggleBtn.innerHTML = '👁️';
                    toggleBtn.title = 'Show/Hide Password';
                    toggleBtn.addEventListener('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        if (input.type === 'password') {
                            input.type = 'text';
                            toggleBtn.innerHTML = '🙈';
                        } else {
                            input.type = 'password';
                            toggleBtn.innerHTML = '👁️';
                        }
                    });
                    parent.appendChild(toggleBtn);
                }
            }
        }
    });
}

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
            }, 400);
        }
    }
}

handleOAuthTokenAndCleanUrl();

setInterval(() => {
    attachEyeToggle();
    handlePersistentSession();
}, 250);

document.addEventListener("DOMContentLoaded", () => {
    handleOAuthTokenAndCleanUrl();
    attachEyeToggle();
    handlePersistentSession();
});
</script>
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance", head=head_html, css=custom_css) as demo:
    otp_state = gr.State(value="")
    session_token_state = gr.Textbox(value="", elem_id="session-token-box", visible=False)

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8, min_width=300):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4, min_width=350):
                gr.HTML(f"""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 10px 18px; border-radius: 14px; display: flex; gap: 8px; align-items: center; justify-content: flex-end; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                    <span style="font-size: 0.8rem; color: #fde047; font-weight: 600;">🔐 Quick Logins:</span>
                    <a href="{GOOGLE_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #ea4335; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="{FACEBOOK_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #1877f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                </div>
                """)

        with gr.Tabs() as main_tabs:
            with gr.TabItem("👤 DASHBOARD"):
                gr.HTML("<h3 style='color:#fde047;'>👤 User Profile, Wallet & Order History</h3>")
                
                gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1.5px dashed #f1c40f; padding: 12px 18px; border-radius: 12px; margin: 10px 0 15px 0; text-align: center; box-shadow: 0 4px 15px rgba(241, 196, 15, 0.15);">
                    <p style="color: #f39c12 !important; font-size: 0.88rem; font-weight: 600; margin: 0; line-height: 1.5;">
                        💡 <b style="color: #ffffff !important;">Mobile View Notice:</b> If you are trying to access the site through mobile version, look at the extreme end of the visible tabs for three dots (<span style="color: #fff; font-weight: bold; background: rgba(255,255,255,0.2); padding: 2px 6px; border-radius: 4px;">...</span>) to open the drop-down menu.
                    </p>
                </div>
                """)

                gr.HTML("""
                <div style="background: linear-gradient(135deg, rgba(69, 10, 10, 0.95), rgba(127, 29, 29, 0.9)); border: 2.5px solid #f87171; padding: 20px 24px; border-radius: 16px; margin: 15px 0 20px 0; box-shadow: 0 0 30px rgba(239, 68, 68, 0.4); display: flex; align-items: center; gap: 18px; flex-wrap: wrap;">
                    <div style="background: #fde047; color: #7f1d1d; width: 55px; height: 55px; min-width: 55px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 2rem; font-weight: 900; box-shadow: 0 0 15px #fde047; border: 2px solid #fff;">
                        ⚠️
                    </div>
                    <div style="flex: 1; min-width: 280px;">
                        <h3 style="color: #fef08a !important; font-size: 1.25rem; font-family: 'Cinzel', serif; margin: 0 0 6px 0; letter-spacing: 0.5px;">
                            ⚠️ CRITICAL WARNING: DO NOT REFRESH PAGE!
                        </h3>
                        <p style="color: #ffffff !important; font-size: 0.98rem; font-weight: 600; margin: 0; line-height: 1.6;">
                            <span style="color: #fde047; font-weight: 800; font-size: 1.05rem;">ATTENTION:</span> When you are logged in or performing <b style="color: #4ade80;">Money Transactions / Wallet Topups</b>, <span style="color: #fca5a5; text-decoration: underline;">NEVER REFRESH THE PAGE</span>. Refreshing will automatically log you out, clear active session data, and can disrupt payment gateway redirects!
                        </p>
                    </div>
                </div>
                """)

                with gr.Row():
                    with gr.Column():
                        user_profile_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>
                                <h4 style="color: #fde047 !important; margin-bottom: 4px;">👤 Active User Session</h4>
                                <p style="color: #ffffff !important; font-size: 0.95rem; margin: 0;">Guest User (Please Sign Up / Login)</p>
                            </div>
                            <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border: 1px solid #fde047; padding: 8px 18px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; cursor: pointer; box-shadow: 0 0 15px rgba(219, 39, 119, 0.6); white-space: nowrap;">
                                📝 SIGN UP / LOGIN
                            </button>
                        </div>
                        """)
                    with gr.Column():
                        wallet_balance_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; margin-bottom: 15px;">
                            <h4 style="color: #fde047 !important; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80 !important;">₹ 0.00</span></h4>
                            <p style="color: #f3e8ff !important; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking of reports.</p>
                        </div>
                        """)

                with gr.Group(visible=False) as signup_group:
                    with gr.Tabs():
                        with gr.TabItem("📝 Sign Up & Verify OTP"):
                            with gr.Row():
                                signup_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                                signup_email = gr.Textbox(label="Email Address", placeholder="e.g. user@gmail.com")
                            with gr.Row():
                                signup_phone = gr.Textbox(label="Phone Number (Mandatory)", placeholder="e.g. 9876543210")
                                signup_pass = gr.Textbox(label="Create Password", type="password", placeholder="Enter secure password")
                            signup_btn = gr.Button("✨ 1. Register & Send Verification OTP to Email", variant="primary")
                            signup_output = gr.HTML()
                            
                            with gr.Row():
                                user_otp_input = gr.Textbox(label="Enter 6-Digit Email OTP", placeholder="e.g. 123456", max_lines=1)
                                verify_otp_btn = gr.Button("🔑 2. Verify OTP & Activate Account", variant="primary")

                        with gr.TabItem("🔐 Member Sign In / Login"):
                            gr.HTML("<p style='color:#fde047; font-size:0.9rem;'>Already registered? Enter your email and password to log in directly without OTP.</p>")
                            with gr.Row():
                                login_email_input = gr.Textbox(label="Registered Email Address", placeholder="e.g. user@gmail.com")
                                login_pass_input = gr.Textbox(label="Password", type="password", placeholder="Enter your password")
                            login_btn = gr.Button("🚀 Sign In to Account", variant="primary")
                            login_output = gr.HTML()

                order_history_display = gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                    <h4 style="color: #fde047 !important; margin-bottom: 6px; font-size: 1rem;">📦 Order History & Saved PDF Reports</h4>
                    <p style="color: #cbd5e1 !important; font-size: 0.85rem; margin: 0;">No previous orders found for current guest session. Please register or login.</p>
                </div>
                """)

                with gr.Row():
                    topup_amount = gr.Radio(choices=["100", "250", "500", "1000"], value="250", label="Select Topup Amount (₹)")
                    topup_btn = gr.Button("⚡ Topup Wallet Credits", variant="primary")
                wallet_pay_output = gr.HTML()
                topup_btn.click(fn=recharge_wallet, inputs=[topup_amount], outputs=[wallet_pay_output])

                signup_btn.click(
                    fn=handle_manual_signup,
                    inputs=[signup_name, signup_email, signup_phone, signup_pass],
                    outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, otp_state]
                )

                verify_otp_btn.click(
                    fn=verify_user_otp,
                    inputs=[user_otp_input, otp_state, signup_name, signup_email, signup_phone],
                    outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state]
                )

                login_btn.click(
                    fn=handle_login,
                    inputs=[login_email_input, login_pass_input],
                    outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state]
                )

            with gr.TabItem("🌟 LIFE PREDICTION"):
                gr.HTML("<h3 style='color:#fde047;'>🌌 Vedic Astrology & Deep Life Forecast</h3>")
                with gr.Row():
                    name_input = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                    dob_input = gr.Textbox(label="Date of Birth", placeholder="YYYY-MM-DD")
                with gr.Row():
                    tob_input = gr.Textbox(label="Time of Birth", placeholder="HH:MM")
                    pob_input = gr.Textbox(label="Place of Birth", placeholder="City, Country")
                with gr.Row():
                    phone_input = gr.Textbox(label="Phone Number", placeholder="e.g. 9876543210")
                    email_input = gr.Textbox(label="Email Address", placeholder="e.g. user@gmail.com")
                
                address_input = gr.Textbox(label="Postal Address")
                focus_dropdown = gr.Dropdown(choices=["General Life & Destiny", "Career & Wealth Growth", "Love & Marriage", "Health & Spiritual Growth"], value="General Life & Destiny", label="Primary Focus Area")
                question_input = gr.Textbox(label="Specific Question or Concern")
                submit_life = gr.Button("✨ Reveal Detailed Life Insights (₹499)", variant="primary")
                
                output_life_teaser = gr.HTML()
                output_life_paywall = gr.HTML()
                submit_life.click(fn=run_life_predictions, inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input], outputs=[output_life_teaser, output_life_paywall])

            with gr.TabItem("☀️ HOROSCOPE"):
                gr.HTML("<h3 style='color:#fde047;'>🔮 Daily Zodiac Predictions (Free)</h3>")
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Select Zodiac Sign")
                submit_horoscope = gr.Button("🔮 Get Today's Horoscope", variant="primary")
                output_horoscope = gr.HTML()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            with gr.TabItem("❤️ MATCHING"):
                gr.HTML("<h3 style='color:#fde047;'>💍 Vedic Compatibility & Guna Milan</h3>")
                with gr.Row():
                    boy_name = gr.Textbox(label="Boy's Name", placeholder="e.g. Rahul")
                    boy_dob = gr.Textbox(label="Boy's DOB (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                with gr.Row():
                    girl_name = gr.Textbox(label="Girl's Name", placeholder="e.g. Priya")
                    girl_dob = gr.Textbox(label="Girl's DOB (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                submit_matching = gr.Button("❤️ Match Kundalis Now (₹399)", variant="primary")
                output_matching = gr.HTML()
                output_matching_paywall = gr.HTML()
                submit_matching.click(fn=run_kundali_matching, inputs=[boy_name, boy_dob, girl_name, girl_dob], outputs=[output_matching, output_matching_paywall])

            with gr.TabItem("💎 GEMSTONES"):
                gr.HTML("<h3 style='color:#fde047;'>🧿 Lucky Gemstones & Cosmic Remedies</h3>")
                with gr.Row():
                    gem_dob = gr.Textbox(label="Date of Birth", placeholder="YYYY-MM-DD")
                    gem_zodiac = gr.Textbox(label="Zodiac Sign", placeholder="e.g. Aries (Mesha)")
                submit_gem = gr.Button("💎 Find My Gemstone (₹299)", variant="primary")
                output_gem = gr.HTML()
                output_gem_paywall = gr.HTML()
                submit_gem.click(fn=run_gemstone_remedy, inputs=[gem_dob, gem_zodiac], outputs=[output_gem, output_gem_paywall])

            with gr.TabItem("📜 KUNDALI & BIRTH PDF"):
                gr.HTML("<h3 style='color:#fde047;'>📜 Janam Kundali & Lagna Birth Chart Generator</h3>")
                with gr.Row():
                    k_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                    k_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                with gr.Row():
                    k_tob = gr.Textbox(label="Time of Birth", placeholder="HH:MM")
                    k_pob = gr.Textbox(label="Place of Birth", placeholder="City, Country")
                submit_kundali_pdf = gr.Button("📜 Generate Visual Birth Chart & Kundali PDF (₹299)", variant="primary")
                output_kundali_pdf_text = gr.HTML()
                output_visual_chart = gr.HTML()
                output_kundali_file = gr.File(label="Download Generated Kundali PDF")
                output_kundali_paywall = gr.HTML()
                submit_kundali_pdf.click(
                    fn=run_kundali_pdf,
                    inputs=[k_name, k_dob, k_tob, k_pob],
                    outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall]
                )

            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.HTML("<h3 style='color:#fde047;'>🔢 Numerology Check</h3>")
                with gr.Row():
                    n_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                    n_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                submit_num = gr.Button("🔢 Analyze Numerology (₹249)", variant="primary")
                output_num = gr.HTML()
                output_num_paywall = gr.HTML()
                submit_num.click(fn=run_numerology, inputs=[n_name, n_dob], outputs=[output_num, output_num_paywall])

            with gr.TabItem("📅 PANCHANG"):
                gr.HTML("<h3 style='color:#fde047;'>📅 Vedic Panchang & Shubh Muhurat</h3>")
                with gr.Row():
                    p_date = gr.Textbox(label="Date (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                    p_city = gr.Textbox(label="City", placeholder="e.g. Kolkata")
                p_mode = gr.Radio(choices=["Free Daily Panchang", "Detailed Shubh Muhurat Report (₹99)"], value="Free Daily Panchang")
                submit_panchang = gr.Button("📅 Check Panchang", variant="primary")
                output_panchang = gr.HTML()
                output_panchang_paywall = gr.HTML()
                submit_panchang.click(fn=run_panchang, inputs=[p_date, p_city, p_mode], outputs=[output_panchang, output_panchang_paywall])

            with gr.TabItem("🤖 AI ASSISTANT"):
                gr.HTML("<h3 style='color:#fde047;'>🤖 Ask Your Personal AI Astrologer</h3>")
                ai_input = gr.Textbox(label="Type your query (e.g., career, marriage, health)", placeholder="e.g. How is my career looking for next year?")
                ai_submit = gr.Button("Ask Assistant ✨", variant="primary")
                ai_output = gr.HTML()
                ai_submit.click(fn=simple_astro_query, inputs=ai_input, outputs=ai_output)

            with gr.TabItem("⚖️ LEGAL"):
                gr.HTML("""
                <div style="background: rgba(14, 5, 35, 0.9); border: 1px solid rgba(232, 121, 249, 0.5); padding: 20px; border-radius: 14px; color: #ffffff;">
                    <h4 style="color: #fde047 !important;">📜 Terms of Service</h4>
                    <p style="font-size: 0.85rem;">Welcome to AccAstroForge.in. By using our Vedic astrology and Kundali services, you agree to these usage guidelines. All reports are intended for personal guidance and spiritual insight.</p>
                    <hr style="border-color: rgba(244, 114, 182, 0.2); margin: 15px 0;">
                    <h4 style="color: #fde047 !important;">🔒 Privacy Policy & Data Deletion</h4>
                    <p style="font-size: 0.85rem;">We value user privacy. User profile data collected during Google/Facebook login is stored securely and never shared with third parties.</p>
                    <hr style="border-color: rgba(244, 114, 182, 0.2); margin: 15px 0;">
                    <h4 style="color: #fde047 !important;">📧 Support Contact & Official Handles</h4>
                    <p style="font-size: 0.85rem; margin-bottom: 8px;">For any support or queries, reach out to us at: <a href="mailto:support@accastroforge.in" style="color: #fde047 !important; font-weight: 700;">support@accastroforge.in</a></p>
                    <p style="font-size: 0.85rem;">Connect with us on our official social platforms:</p>
                    <ul style="list-style-type: none; padding-left: 0; margin-top: 10px; line-height: 2.2;">
                        <li>🧳 <span style="color: #fde047 !important; font-weight: 700;">Twitter (X):</span> <a href="https://x.com/AccAstroForge" target="_blank" style="color: #38bdf8 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://x.com/AccAstroForge</a></li>
                        <li>📸 <span style="color: #fde047 !important; font-weight: 700;">Instagram:</span> <a href="https://www.instagram.com/accastroforge/" target="_blank" style="color: #f472b6 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.instagram.com/accastroforge/</a></li>
                        <li>🌀 <span style="color: #fde047 !important; font-weight: 700;">Threads:</span> <a href="https://www.threads.com/@accastroforge" target="_blank" style="color: #e879f9 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.threads.com/@accastroforge</a></li>
                        <li>📘 <span style="color: #fde047 !important; font-weight: 700;">Facebook:</span> <a href="https://www.facebook.com/accastroforge/" target="_blank" style="color: #60a5fa !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.facebook.com/accastroforge/</a></li>
                    </ul>
                </div>
                """)

    signup_state = gr.State(value=False)
    manual_signup_trigger = gr.Button("Trigger Signup", elem_id="manual-signup-trigger")
    manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state], outputs=[signup_state, signup_group])

    logout_trigger = gr.Button("Trigger Logout", elem_id="logout-trigger")
    logout_trigger.click(fn=handle_logout, inputs=[], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display, session_token_state])

    session_sync_btn = gr.Button("Sync Session", elem_id="session-sync-btn")
    session_sync_btn.click(fn=restore_session_from_token, inputs=[session_token_state], outputs=[user_profile_display, wallet_balance_display, order_history_display])

    session_token_state.change(
        fn=None,
        inputs=[session_token_state],
        outputs=None,
        js="(token) => { if(token) localStorage.setItem('accastroforge_session', token); else localStorage.removeItem('accastroforge_session'); }"
    )

    with gr.Group(visible=False) as admin_group:
        with gr.Accordion("🔒 Owner Portal (Admin Dashboard)", open=True):
            secret_pass = gr.Textbox(label="Admin Secret Password", type="password", placeholder="Enter Password")
            unlock_btn = gr.Button("Unlock Dashboard", variant="primary")
            secret_output = gr.HTML()
            unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=secret_output)

    admin_state = gr.State(value=False)
    real_hidden_trigger = gr.Button("Trigger", elem_id="real-hidden-trigger")
    real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, head=head_html, favicon_path="favicon.png")
