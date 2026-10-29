import os
import datetime
import random
import base64
import json
import requests
import sqlite3
import razorpay
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = FastAPI()

# ---------------------------------------------------------
# 0. CONFIGURATIONS & SECRETS
# ---------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_live_TpnrjMektRCWj8")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "tm4Ry6xdY63egZtf5cD0kP8T")
RAZORPAY_ME_URL = "https://razorpay.me/@accastroforge"

BREVO_API_KEY = os.getenv("BREVO_API_KEY")

GOOGLE_CLIENT_ID = "967117558722-40q6p107agttv35a47jlmq907j87bnpp.apps.googleusercontent.com"
GOOGLE_REDIRECT_URI = "https://accastroforge.in/"
FACEBOOK_APP_ID = "1487294163221538"
FACEBOOK_REDIRECT_URI = "https://accastroforge.in/"

GOOGLE_OAUTH_URL = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=token&scope=email%20profile"
FACEBOOK_OAUTH_URL = f"https://www.facebook.com/v12.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={FACEBOOK_REDIRECT_URI}&response_type=token&scope=email,public_profile"

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCOjnJySc7mB7vu5BcWhmn7t5f-lPG7EkC03Hc2SCKyMhvOrFz2tZmM1I5obCAm2YM/exec"
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
            params = {"worksheet": "Users", "name": values_list[0], "email": values_list[1], "phone": values_list[2], "verified_at": values_list[3]}
        else:
            params = {"worksheet": "AdminLogs", "timestamp": values_list[0], "full_name": values_list[1], "service": values_list[2], "details": values_list[3], "payment_status": values_list[4]}
        requests.get(APPS_SCRIPT_URL, params=params, allow_redirects=True, timeout=10)
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
        cursor.execute("INSERT OR REPLACE INTO users (name, email, phone, verified_at) VALUES (?, ?, ?, ?)", (u_name, u_email.lower(), u_phone, now_str))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save User DB Error: {e}")
    append_to_google_sheet_direct("Users", [u_name, u_email.lower(), u_phone, now_str])

def load_users():
    users_dict = {}
    sheet_rows = load_google_sheet_direct("Users")
    for row in sheet_rows:
        if isinstance(row, dict):
            email = str(row.get("email", row.get("Email", ""))).strip().lower()
            if email:
                users_dict[email] = {"name": row.get("name", row.get("Name", "User")), "email": email, "phone": row.get("phone", row.get("Phone", "N/A")), "verified_at": row.get("verified_at", row.get("Verified_At", str(datetime.datetime.now())))}
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
        print(f"Load Users Local Error: {e}")
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
        cursor.execute("INSERT INTO admin_logs (timestamp, full_name, service, details, payment_status) VALUES (?, ?, ?, ?, ?)", (ts, fn, srv, dtl, pst))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Save Log Error: {e}")
    append_to_google_sheet_direct("AdminLogs", [ts, fn, srv, dtl, pst])

def get_base64(file_path):
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return ""
    return ""

logo_b64 = get_base64("logo.png")
logo_src = "data:image/png;base64," + logo_b64 if logo_b64 else ""

favicon_b64 = get_base64("favicon.png")
favicon_src = "data:image/png;base64," + favicon_b64 if favicon_b64 else ""

def send_brevo_email(to_email, user_name, subject, html_content):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {"sender": {"name": "AccAstroForge", "email": "arnabchaudhuriaiedits@gmail.com"}, "to": [{"email": to_email, "name": user_name}], "subject": subject, "htmlContent": html_content}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Email Error: {e}")
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
                "customer": {"name": user_name if user_name else "User"},
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "callback_url": "https://accastroforge.in/",
                "callback_method": "get"
            }
            response = razorpay_client.payment_link.create(data)
            if response and "short_url" in response:
                return response["short_url"]
    except Exception as e:
        print(f"Razorpay Error: {e}")
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
        <p style="color: #f3e8ff !important; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePe, BHIM or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{amt_val}</p>
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">
            🚀 Proceed to Pay ₹{amt_val} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AccAstroForge - AI Astrology Guidance</title>
    <link rel="icon" type="image/png" href="{{ favicon_src }}">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #030014;
            background-image: 
                linear-gradient(rgba(5, 1, 20, 0.45), rgba(5, 1, 20, 0.6)),
                url("https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/bg.jpg");
            background-position: center center;
            background-repeat: no-repeat;
            background-size: cover;
            background-attachment: fixed;
            color: #ffffff;
            font-family: 'Poppins', sans-serif;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1100px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 15px; }
        .logo-area img { height: 75px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7)); mix-blend-mode: screen; background: transparent !important; }
        .social-links a { color: #fff; background: #ea4335; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; text-decoration: none; margin-left: 5px; }
        .social-links a.fb { background: #1877f2; }
        
        .tab-list { display: flex; flex-wrap: wrap; gap: 4px; background: rgba(10, 3, 25, 0.9); padding: 6px; border-radius: 12px; border: 1px solid rgba(244, 114, 182, 0.4); margin-bottom: 20px; }
        .tab-btn { background: rgba(18, 8, 42, 0.9); border: 1px solid rgba(244, 114, 182, 0.45); color: #fef08a; font-family: 'Cinzel', serif; font-weight: 700; font-size: 0.75rem; border-radius: 8px; padding: 8px 12px; cursor: pointer; transition: 0.3s; }
        .tab-btn.active { background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border-color: #fde047; }
        
        .tab-content { display: none; background: rgba(14, 5, 35, 0.95); border: 1px solid rgba(244, 114, 182, 0.6); border-radius: 16px; padding: 25px; box-shadow: 0 0 30px rgba(124, 58, 237, 0.3); }
        .tab-content.active { display: block; }
        
        h3, h4 { color: #fde047; font-family: 'Cinzel', serif; }
        input, select, textarea { background: rgba(22, 10, 48, 0.95); border: 1.5px solid rgba(244, 114, 182, 0.7); color: #ffffff; border-radius: 12px; padding: 12px 16px; width: 100%; margin-bottom: 15px; box-sizing: border-box; }
        button.primary-btn { background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border: 1px solid #fde047; font-weight: 700; border-radius: 12px; padding: 12px 24px; cursor: pointer; width: 100%; font-size: 1rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        @media(max-width: 768px) { .row { grid-template-columns: 1fr; } }
        .card { background: rgba(18, 8, 42, 0.9); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo-area">
                {% if logo_src %}
                <img src="{{ logo_src }}" alt="AccAstroForge Logo">
                {% else %}
                <span style="font-size: 26px; font-weight: 800; color: #fbcfe8; font-family: 'Cinzel', serif;">AccAstroForge</span>
                {% endif %}
            </div>
            <div class="social-links" style="display: flex; align-items: center; background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 8px 14px; border-radius: 14px;">
                <span style="font-size: 0.8rem; color: #fde047; font-weight: 600; margin-right: 6px;">🔐 Quick Logins:</span>
                <a href="{{ google_url }}" target="_blank">Google</a>
                <a href="{{ fb_url }}" target="_blank" class="fb">Facebook</a>
            </div>
        </div>

        <div class="tab-list">
            <button class="tab-btn active" onclick="switchTab(event, 'tab-dashboard')">👤 DASHBOARD</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-life')">🌟 LIFE PREDICTION</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-horoscope')">☀️ HOROSCOPE</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-matching')">❤️ MATCHING</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-gemstones')">💎 GEMSTONES</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-kundali')">📜 KUNDALI PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-numerology')">🔢 NUMEROLOGY</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-panchang')">📅 PANCHANG</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-ai')">🤖 AI ASSISTANT</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-legal')">⚖️ LEGAL</button>
        </div>

        <!-- TAB 1: DASHBOARD -->
        <div id="tab-dashboard" class="tab-content active">
            <h3>👤 User Profile, Wallet & Order History</h3>
            
            <div style="background: linear-gradient(135deg, rgba(69, 10, 10, 0.95), rgba(127, 29, 29, 0.9)); border: 2.5px solid #f87171; padding: 18px 22px; border-radius: 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 15px;">
                <div style="background: #fde047; color: #7f1d1d; width: 45px; height: 45px; min-width: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 900;">⚠️</div>
                <div>
                    <h4 style="color: #fef08a !important; margin: 0 0 4px 0; font-family: 'Cinzel', serif;">⚠️ CRITICAL WARNING: DO NOT REFRESH PAGE!</h4>
                    <p style="color: #ffffff !important; font-size: 0.92rem; margin: 0;">When logged in or performing wallet topups, <span style="color: #fca5a5; text-decoration: underline;">NEVER REFRESH THE PAGE</span> to avoid clearing active sessions.</p>
                </div>
            </div>

            <div class="card" id="profile-box">
                <h4>Active User Session</h4>
                <p>Guest User (Please Sign Up / Login)</p>
            </div>
            <div class="card">
                <h4>💳 Wallet Balance: ₹ 0.00</h4>
                <p>Use credits for instant unlocking of reports.</p>
                <div class="row" style="margin-top:10px;">
                    <button class="primary-btn" onclick="topupWallet(250)">⚡ Add ₹250</button>
                    <button class="primary-btn" onclick="topupWallet(500)">⚡ Add ₹500</button>
                </div>
                <div id="wallet-result" style="margin-top:10px;"></div>
            </div>
            <div class="card">
                <h4>📝 Sign Up & Verify OTP</h4>
                <div class="row">
                    <input type="text" id="su-name" placeholder="Full Name">
                    <input type="email" id="su-email" placeholder="Email Address">
                </div>
                <div class="row">
                    <input type="text" id="su-phone" placeholder="Phone Number">
                    <input type="password" id="su-pass" placeholder="Password">
                </div>
                <button class="primary-btn" onclick="registerUser()">✨ Register & Send OTP</button>
                <div id="su-output" style="margin-top: 10px;"></div>
                <div style="margin-top: 15px;" class="row">
                    <input type="text" id="su-otp" placeholder="Enter 6-Digit OTP">
                    <button class="primary-btn" onclick="verifyOtp()">🔑 Verify OTP</button>
                </div>
            </div>
            <div class="card">
                <h4>🔐 Member Sign In / Login</h4>
                <input type="email" id="li-email" placeholder="Registered Email">
                <input type="password" id="li-pass" placeholder="Password">
                <button class="primary-btn" onclick="loginUser()">🚀 Sign In</button>
                <div id="li-output" style="margin-top: 10px;"></div>
            </div>
        </div>

        <!-- TAB 2: LIFE PREDICTION -->
        <div id="tab-life" class="tab-content">
            <h3>🌌 Vedic Astrology & Deep Life Forecast</h3>
            <div class="row">
                <input type="text" id="life-name" placeholder="Full Name">
                <input type="date" id="life-dob">
            </div>
            <div class="row">
                <input type="time" id="life-tob">
                <input type="text" id="life-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="submitLifePrediction()">✨ Reveal Life Insights (₹499)</button>
            <div id="life-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 3: HOROSCOPE -->
        <div id="tab-horoscope" class="tab-content">
            <h3>🔮 Daily Zodiac Predictions</h3>
            <select id="horo-sign">
                {% for s in zodiacs %}
                <option value="{{ s }}">{{ s }}</option>
                {% endfor %}
            </select>
            <button class="primary-btn" onclick="getHoroscope()">🔮 Get Horoscope</button>
            <div id="horo-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 4: MATCHING -->
        <div id="tab-matching" class="tab-content">
            <h3>💍 Vedic Compatibility & Guna Milan</h3>
            <div class="row">
                <input type="text" id="b-name" placeholder="Boy's Name">
                <input type="date" id="b-dob">
            </div>
            <div class="row">
                <input type="text" id="g-name" placeholder="Girl's Name">
                <input type="date" id="g-dob">
            </div>
            <button class="primary-btn" onclick="submitMatching()">❤️ Match Kundalis Now (₹399)</button>
            <div id="matching-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 5: GEMSTONES -->
        <div id="tab-gemstones" class="tab-content">
            <h3>🧿 Lucky Gemstones & Cosmic Remedies</h3>
            <div class="row">
                <input type="date" id="gem-dob">
                <input type="text" id="gem-zodiac" placeholder="Zodiac Sign">
            </div>
            <button class="primary-btn" onclick="submitGemstone()">💎 Find My Gemstone (₹299)</button>
            <div id="gem-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 6: KUNDALI PDF -->
        <div id="tab-kundali" class="tab-content">
            <h3>📜 Janam Kundali & Lagna Birth Chart Generator</h3>
            <div class="row">
                <input type="text" id="k-name" placeholder="Full Name">
                <input type="date" id="k-dob">
            </div>
            <div class="row">
                <input type="text" id="k-tob" placeholder="Time of Birth (HH:MM)">
                <input type="text" id="k-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="submitKundaliPdf()">📜 Generate Kundali & PDF (₹299)</button>
            <div id="kundali-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 7: NUMEROLOGY -->
        <div id="tab-numerology" class="tab-content">
            <h3>🔢 Numerology Check</h3>
            <div class="row">
                <input type="text" id="num-name" placeholder="Full Name">
                <input type="date" id="num-dob">
            </div>
            <button class="primary-btn" onclick="submitNumerology()">🔢 Analyze Numerology (₹249)</button>
            <div id="num-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 8: PANCHANG -->
        <div id="tab-panchang" class="tab-content">
            <h3>📅 Vedic Panchang & Shubh Muhurat</h3>
            <div class="row">
                <input type="date" id="p-date">
                <input type="text" id="p-city" placeholder="City">
            </div>
            <button class="primary-btn" onclick="submitPanchang()">📅 Check Panchang</button>
            <div id="panchang-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 9: AI ASSISTANT -->
        <div id="tab-ai" class="tab-content">
            <h3>🤖 Ask Your Personal AI Astrologer</h3>
            <textarea id="ai-query" placeholder="Ask your question regarding career, marriage, health..."></textarea>
            <button class="primary-btn" onclick="askAi()">Ask Assistant ✨</button>
            <div id="ai-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 10: LEGAL -->
        <div id="tab-legal" class="tab-content">
            <h3>⚖️ Terms & Social Handles</h3>
            <p>Welcome to AccAstroForge.in. All predictions are for guidance purposes.</p>
            <p><b>Support Email:</b> support@accastroforge.in</p>
            <ul>
                <li>Twitter: <a href="https://x.com/AccAstroForge" target="_blank" style="color:#38bdf8;">https://x.com/AccAstroForge</a></li>
                <li>Instagram: <a href="https://www.instagram.com/accastroforge/" target="_blank" style="color:#f472b6;">https://www.instagram.com/accastroforge/</a></li>
            </ul>
        </div>
    </div>

    <script>
        let generatedOtpStorage = "";
        let verifiedEmailStorage = "";

        function switchTab(evt, tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
        }

        async function registerUser() {
            let name = document.getElementById('su-name').value;
            let email = document.getElementById('su-email').value;
            let phone = document.getElementById('su-phone').value;
            let res = await fetch('/api/register', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, email, phone}) });
            let data = await res.json();
            generatedOtpStorage = data.otp;
            verifiedEmailStorage = email;
            document.getElementById('su-output').innerHTML = data.msg;
        }

        async function verifyOtp() {
            let userOtp = document.getElementById('su-otp').value;
            if(userOtp === generatedOtpStorage) {
                document.getElementById('profile-box').innerHTML = `<h4>👤 Active Member</h4><p>Verified: ${verifiedEmailStorage}</p>`;
                alert("Account verified successfully!");
            } else { alert("Invalid OTP!"); }
        }

        async function loginUser() {
            let email = document.getElementById('li-email').value;
            let res = await fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email}) });
            let data = await res.json();
            document.getElementById('li-output').innerHTML = data.msg;
            if(data.success) {
                document.getElementById('profile-box').innerHTML = `<h4>👤 Active Member</h4><p>Logged In: ${email}</p>`;
            }
        }

        async function topupWallet(amt) {
            let res = await fetch('/api/topup', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({amount: amt}) });
            let data = await res.json();
            document.getElementById('wallet-result').innerHTML = data.paywall;
        }

        async function submitLifePrediction() {
            let name = document.getElementById('life-name').value;
            let dob = document.getElementById('life-dob').value;
            let res = await fetch('/api/life', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob}) });
            let data = await res.json();
            document.getElementById('life-result').innerHTML = data.teaser + data.paywall;
        }

        async function getHoroscope() {
            let sign = document.getElementById('horo-sign').value;
            let res = await fetch('/api/horoscope', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sign}) });
            let data = await res.json();
            document.getElementById('horo-result').innerHTML = data.html;
        }

        async function submitMatching() {
            let boy_name = document.getElementById('b-name').value;
            let girl_name = document.getElementById('g-name').value;
            let res = await fetch('/api/matching', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({boy_name, girl_name}) });
            let data = await res.json();
            document.getElementById('matching-result').innerHTML = data.teaser + data.paywall;
        }

        async function submitGemstone() {
            let zodiac = document.getElementById('gem-zodiac').value;
            let res = await fetch('/api/gemstone', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({zodiac}) });
            let data = await res.json();
            document.getElementById('gem-result').innerHTML = data.teaser + data.paywall;
        }

        async function submitKundaliPdf() {
            let name = document.getElementById('k-name').value;
            let dob = document.getElementById('k-dob').value;
            let tob = document.getElementById('k-tob').value;
            let pob = document.getElementById('k-pob').value;
            let res = await fetch('/api/kundali-pdf', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, tob, pob}) });
            let data = await res.json();
            document.getElementById('kundali-result').innerHTML = data.teaser + data.chart + data.paywall;
        }

        async function submitNumerology() {
            let name = document.getElementById('num-name').value;
            let dob = document.getElementById('num-dob').value;
            let res = await fetch('/api/numerology', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob}) });
            let data = await res.json();
            document.getElementById('num-result').innerHTML = data.teaser + data.paywall;
        }

        async function submitPanchang() {
            let city = document.getElementById('p-city').value;
            let date = document.getElementById('p-date').value;
            let res = await fetch('/api/panchang', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({city, date}) });
            let data = await res.json();
            document.getElementById('panchang-result').innerHTML = data.html;
        }

        async function askAi() {
            let query = document.getElementById('ai-query').value;
            let res = await fetch('/api/ai', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query}) });
            let data = await res.json();
            document.getElementById('ai-result').innerHTML = data.html;
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    rendered_html = HTML_TEMPLATE.replace("{{ favicon_src }}", favicon_src).replace("{{ logo_src }}", logo_src).replace("{{ google_url }}", GOOGLE_OAUTH_URL).replace("{{ fb_url }}", FACEBOOK_OAUTH_URL)
    for s in ZODIAC_SIGNS:
        rendered_html = rendered_html.replace("{% for s in zodiacs %}", f"<option value='{s}'>{s}</option>\n{{% for s in zodiacs %}}", 1)
    rendered_html = rendered_html.replace("{% for s in zodiacs %}", "").replace("{% endfor %}", "")
    return HTMLResponse(content=rendered_html)

@app.post("/api/register")
async def api_register(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    email = data.get("email", "")
    phone = data.get("phone", "")
    otp_code = str(random.randint(100000, 999999))
    send_brevo_email(email, name, "OTP Verification", f"<h2>Welcome {name}! Your OTP is {otp_code}</h2>")
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Registration OTP", "details": f"Email: {email}", "payment_status": "OTP Dispatched"})
    return JSONResponse({"otp": otp_code, "msg": "<p style='color:#4ade80;'>📧 OTP Sent to your email!</p>"})

@app.post("/api/login")
async def api_login(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    users = load_users()
    found = any(u.get("email") == email or u.get("Email") == email for u in users)
    if found:
        save_log({"timestamp": str(datetime.datetime.now()), "full_name": email, "service": "Login", "payment_status": "Active Session"})
        return JSONResponse({"success": True, "msg": "<p style='color:#4ade80;'>🎉 Login Successful!</p>"})
    return JSONResponse({"success": False, "msg": "<p style='color:#ef4444;'>❌ Account not found. Please register first.</p>"})

@app.post("/api/topup")
async def api_topup(request: Request):
    data = await request.json()
    amt = data.get("amount", 250)
    paywall = get_paywall_html(f"Wallet Topup (₹{amt})", amt, "User")
    return JSONResponse({"paywall": paywall})

@app.post("/api/life")
async def api_life(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    profile = calculate_astrological_profile(name, dob)
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🌟 Astrological Teaser for {name.upper()}</h4><p><b>Rashi:</b> {profile['zodiac']} | <b>Nakshatra:</b> {profile['nakshatra']} | <b>Dasha:</b> {profile['dasha']}</p></div>"""
    paywall = get_paywall_html("Complete Deep Life Forecast & PDF", 499, name)
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/horoscope")
async def api_horoscope(request: Request):
    data = await request.json()
    sign = data.get("sign", "Aries")
    html = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🔮 Daily Horoscope for {sign}</h4><p>Today brings high cosmic energy. Jupiter's aspect promises financial opportunities and peace.</p></div>"""
    return JSONResponse({"html": html})

@app.post("/api/matching")
async def api_matching(request: Request):
    data = await request.json()
    b = data.get("boy_name", "Boy")
    g = data.get("girl_name", "Girl")
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>❤️ Compatibility Teaser for {b} & {g}</h4><p>High Guna Milan score detected! Excellent long-term emotional alignment.</p></div>"""
    paywall = get_paywall_html("Complete Kundali Matching Report", 399, f"{b} & {g}")
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/gemstone")
async def api_gemstone(request: Request):
    data = await request.json()
    z = data.get("zodiac", "Aries")
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>💎 Gemstone Guidance for {z}</h4><p>Emerald (Panna) or Yellow Sapphire recommended for career success.</p></div>"""
    paywall = get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/kundali-pdf")
async def api_kundali_pdf(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    tob = data.get("tob", "10:00")
    pob = data.get("pob", "Kolkata")
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>📜 Janam Kundali Generated for {name}</h4><p>Your Lagna birth chart preview is ready.</p></div>"""
    chart = f"""<div style='background:#31104b; padding:15px; border-radius:10px; margin-top:10px; text-align:center;'><b style='color:#fde047;'>Lagna Chart Active (DOB: {dob}, POB: {pob})</b></div>"""
    paywall = get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, name)
    return JSONResponse({"teaser": teaser, "chart": chart, "paywall": paywall})

@app.post("/api/numerology")
async def api_numerology(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    profile = calculate_astrological_profile(name, dob)
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🔢 Numerology Preview for {name}</h4><p>Destiny Psychic Number: <b style='color:#fde047;'>{profile['psychic_num']}</b></p></div>"""
    paywall = get_paywall_html("Detailed Numerology & Name Correction Report", 249, name)
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/panchang")
async def api_panchang(request: Request):
    data = await request.json()
    city = data.get("city", "Kolkata")
    date = data.get("date", "Today")
    html = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>📅 Vedic Panchang for {city} ({date})</h4><p><b>Tithi:</b> Shukla Paksha Navami<br><b>Nakshatra:</b> Rohini<br><b>Rahu Kalam:</b> 10:30 AM - 12:00 PM</p></div>"""
    return JSONResponse({"html": html})

@app.post("/api/ai")
async def api_ai(request: Request):
    data = await request.json()
    query = data.get("query", "")
    html = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><p><b>Query:</b> {query}</p><p style='color:#4ade80;'><b>AI Astrologer:</b> Planetary alignments show favorable outcomes for your career and relationships. Keep up regular meditation.</p></div>"""
    return JSONResponse({"html": html})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)
