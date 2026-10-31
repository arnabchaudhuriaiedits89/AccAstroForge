import os
import datetime
import random
import base64
import json
import requests
import sqlite3
import razorpay
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")

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

@app.get("/favicon.ico")
async def favicon():
    if os.path.exists("favicon.png"):
        return FileResponse("favicon.png")
    return JSONResponse({"error": "Not found"}, status_code=404)

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

def save_user_db_single(u_name, u_email, u_phone="N/A"):
    now_str = str(datetime.datetime.now())
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (name, email, phone, verified_at) VALUES (?, ?, ?, ?)", (u_name, u_email.lower(), u_phone, now_str))
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

def load_logs():
    sheet_logs = load_google_sheet_direct("AdminLogs")
    if sheet_logs and len(sheet_logs) > 0:
        formatted_logs = []
        for r in sheet_logs:
            if isinstance(r, dict):
                formatted_logs.append({
                    "timestamp": r.get("timestamp", r.get("Timestamp", "N/A")),
                    "full_name": r.get("full_name", r.get("Full_Name", r.get("Name", "N/A"))),
                    "service": r.get("service", r.get("Service", "N/A")),
                    "details": r.get("details", r.get("Details", "N/A")),
                    "payment_status": r.get("payment_status", r.get("Payment_Status", "Pending"))
                })
        if formatted_logs:
            return formatted_logs
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Load Logs Error: {e}")
        return []

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
    <div style="background: rgba(18, 8, 42, 0.70); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.4); backdrop-filter: blur(8px);">
        <h3 style="color: #fde047 !important; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{amt_val} ONLY)</h3>
        <p style="color: #f3e8ff !important; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePe, BHIM or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{amt_val}</p>
        <a href="{pay_url}" target="_blank" onclick="triggerPaymentLoader(event, this.href)" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">
            🚀 Proceed to Pay ₹{amt_val} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

# ---------------------------------------------------------
# PDF GENERATION WITH PERFECT PROPORTION HEADER STAMP LOGO
# ---------------------------------------------------------
def draw_clean_header_footer(canvas_obj, doc_obj):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica-Bold", 9)
    canvas_obj.setFillColor(colors.HexColor("#7c3aed"))
    canvas_obj.drawString(54, 750, "AccAstroForge - Official Astrological & Vastu Report")
    canvas_obj.setStrokeColor(colors.HexColor("#db2777"))
    canvas_obj.setLineWidth(1)
    canvas_obj.line(54, 742, 558, 742)
    
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#6b7280"))
    canvas_obj.drawString(54, 30, "Generated securely via AccAstroForge.in | All Rights Reserved")
    canvas_obj.drawRightString(558, 30, f"Page {doc_obj.page}")
    canvas_obj.restoreState()

def generate_pdf_report(filename, title, content_paragraphs):
    filepath = os.path.join(os.getcwd(), filename)
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=54, leftMargin=54, topMargin=40, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'PdfTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#7c3aed'),
        spaceAfter=12,
        alignment=1
    )
    
    body_style = ParagraphStyle(
        'PdfBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=10,
        leading=16
    )
    
    story = []
    
    # ADD PERFECT PROPORTION TOP HEADER STAMP LOGO (MATCHING KUNDALI STYLE: CLEAR & BALANCED)
    if os.path.exists("logo.png"):
        try:
            logo_img = RLImage("logo.png", width=130, height=52)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 6))
        except Exception:
            pass

    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 6))
    
    for para in content_paragraphs:
        story.append(Paragraph(para, body_style))
        story.append(Spacer(1, 6))
        
    doc.build(story, onFirstPage=draw_clean_header_footer, onLaterPages=draw_clean_header_footer)
    return filepath

@app.get("/download-pdf/{filename}")
async def download_pdf(filename: str):
    filepath = os.path.join(os.getcwd(), filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="application/pdf", filename=filename)
    return JSONResponse({"error": "File not found"}, status_code=404)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AccAstroForge - AI Astrology & Vastu Guidance</title>
    <link rel="icon" type="image/png" href="/favicon.ico">
    <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');

        html, body {
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
            margin: 0;
            padding: 20px;
        }

        .container { max-width: 1150px; margin: 0 auto; }
        
        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
            margin-bottom: 25px;
            flex-wrap: wrap;
            gap: 15px;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-area img {
            height: 75px;
            filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.9));
            mix-blend-mode: screen;
            background: transparent !important;
        }

        .admin-dot {
            width: 14px;
            height: 14px;
            min-width: 14px;
            min-height: 14px;
            background: radial-gradient(circle, #fde047 0%, #d97706 100%);
            border: 1.5px solid #fef08a;
            border-radius: 50%;
            display: inline-block;
            cursor: pointer;
            box-shadow: 0 0 12px #fde047;
            margin-left: 8px;
        }

        .header-right-area {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
            margin-top: 5px;
        }

        /* LIVE DIGITAL CLOCK STYLING */
        .live-digital-clock {
            background: rgba(18, 8, 42, 0.85);
            border: 1px solid #fde047;
            padding: 4px 12px;
            border-radius: 10px;
            font-family: 'Cinzel', serif;
            font-size: 0.85rem;
            font-weight: 700;
            color: #fde047;
            box-shadow: 0 0 12px rgba(253, 224, 71, 0.4);
            letter-spacing: 1px;
        }
        .clock-colon {
            animation: colonBlink 1s infinite;
        }
        @keyframes colonBlink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        .quick-logins {
            display: flex;
            align-items: center;
            background: rgba(18, 8, 42, 0.70);
            backdrop-filter: blur(8px);
            padding: 6px 14px;
            border-radius: 14px;
            border: 1px solid rgba(244, 114, 182, 0.4);
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            gap: 10px;
        }

        .tab-list {
            display: flex !important;
            flex-wrap: wrap !important;
            width: 100% !important;
            gap: 4px !important;
            padding: 6px !important;
            background: rgba(10, 3, 25, 0.70) !important;
            backdrop-filter: blur(8px);
            border-radius: 14px !important;
            border: 1px solid rgba(244, 114, 182, 0.4) !important;
            margin-bottom: 25px !important;
        }

        .tab-btn {
            background: rgba(18, 8, 42, 0.75) !important;
            border: 1px solid rgba(244, 114, 182, 0.35) !important;
            color: #fef08a !important;
            font-family: 'Cinzel', serif !important;
            font-weight: 700 !important;
            font-size: 0.72rem !important;
            border-radius: 10px !important;
            padding: 8px 12px !important;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .tab-btn.active {
            background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
            color: #ffffff !important;
            border-color: #fde047 !important;
            box-shadow: 0 0 15px rgba(219, 39, 119, 0.6);
        }

        .tab-content {
            display: none;
            background: rgba(14, 5, 35, 0.70);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border: 1px solid rgba(244, 114, 182, 0.45);
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 0 30px rgba(124, 58, 237, 0.25);
        }

        .tab-content.active { display: block; }

        h3, h4 { color: #fde047 !important; font-family: 'Cinzel', serif !important; }
        input, select, textarea {
            background: rgba(22, 10, 48, 0.85) !important;
            border: 1.5px solid rgba(244, 114, 182, 0.55) !important;
            color: #ffffff !important;
            border-radius: 14px !important;
            padding: 12px 16px !important;
            width: 100%;
            margin-bottom: 15px;
            box-sizing: border-box;
            font-family: 'Poppins', sans-serif;
        }

        button.primary-btn {
            background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
            color: #ffffff !important;
            border: 1px solid #fde047 !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            cursor: pointer;
            width: 100%;
            font-size: 1rem;
            box-shadow: 0 6px 20px rgba(219,39,119,0.8);
        }

        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        @media(max-width: 768px) { .row { grid-template-columns: 1fr; } }
        .card { 
            background: rgba(18, 8, 42, 0.70); 
            backdrop-filter: blur(8px); 
            -webkit-backdrop-filter: blur(8px); 
            border: 1px solid rgba(124, 58, 237, 0.5); 
            padding: 18px; 
            border-radius: 14px; 
            margin-bottom: 15px; 
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        
        .auth-container {
            border: 2px solid #db2777;
            background: rgba(18, 8, 42, 0.75);
            backdrop-filter: blur(8px);
            padding: 15px;
            border-radius: 14px;
            margin-top: 15px;
            display: none;
        }

        .password-container {
            position: relative;
            width: 100%;
        }
        .password-container input {
            padding-right: 45px !important;
        }
        .eye-icon {
            position: absolute;
            right: 15px;
            top: 42%;
            transform: translateY(-50%);
            cursor: pointer;
            color: #fde047;
            font-size: 1.1rem;
            user-select: none;
        }

        #loader-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(3, 0, 20, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            z-index: 99999;
            display: flex;
            justify-content: center;
            align-items: center;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.4s ease;
        }
        #loader-overlay.active {
            opacity: 1;
            pointer-events: auto;
        }
        .loader-logo {
            width: 220px;
            height: 220px;
            object-fit: contain;
            animation: spinZoomLoader 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
            filter: drop-shadow(0 0 35px rgba(244, 114, 182, 0.9));
        }
        @keyframes spinZoomLoader {
            0% {
                transform: scale(0.1) rotate(0deg);
                opacity: 0;
            }
            50% {
                transform: scale(1.15) rotate(180deg);
                opacity: 1;
            }
            100% {
                transform: scale(1.5) rotate(360deg);
                opacity: 0;
            }
        }
    </style>
</head>
<body>
    <div id="loader-overlay">
        <img src="https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/AccAstroForge%20Zodiac%20Logo%20Text%20Cut%20Through%20TRANSPERANT.png" alt="Cosmic Loader" class="loader-logo">
    </div>

    <div class="container">
        <!-- HEADER WITH LOGO, SECRET ADMIN DOT, LIVE DIGITAL CLOCK & QUICK LOGINS -->
        <div class="header-container">
            <div class="logo-area">
                LOGO_SRC_PLACEHOLDER
                <span class="admin-dot" title="Click to open Admin Portal" onclick="toggleAdminPanel()"></span>
            </div>
            <div class="header-right-area">
                <div id="live-digital-clock" class="live-digital-clock">00<span class="clock-colon">:</span>00<span class="clock-colon">:</span>00 IST</div>
                <div class="quick-logins">
                    <span style="font-size: 0.8rem; color: #fde047; font-weight: 600;">🔐 Quick Logins:</span>
                    <a href="GOOGLE_URL_PLACEHOLDER" target="_blank" style="color: #fff !important; background: #ea4335; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="FB_URL_PLACEHOLDER" target="_blank" style="color: #fff !important; background: #1877f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                </div>
            </div>
        </div>

        <!-- TABS BAR -->
        <div class="tab-list">
            <button class="tab-btn active" onclick="switchTab(event, 'tab-dashboard')">👤 DASHBOARD</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-life')">🌟 LIFE PREDICTION</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-horoscope')">☀️ HOROSCOPE</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-matching')">❤️ MATCHING</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-gemstones')">💎 GEMSTONES</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-vastu')">🏛️ VASTU SHASTRA</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-kundali')">📜 KUNDALI PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-numerology')">🔢 NUMEROLOGY</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-panchang')">📅 PANCHANG</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-ai')">🤖 AI ASSISTANT</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-legal')">⚖️ LEGAL</button>
        </div>

        <!-- TAB 1: DASHBOARD -->
        <div id="tab-dashboard" class="tab-content active">
            <h3>👤 User Profile, Wallet & Order History</h3>

            <div class="card" id="profile-box">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div id="session-display">
                        <h4>Active User Session</h4>
                        <p style="margin: 0;">Guest User (Please Sign Up / Login)</p>
                    </div>
                    <div id="auth-btn-area">
                        <button id="auth-toggle-btn" class="primary-btn" style="width: auto; padding: 10px 20px;" onclick="toggleAuthBox()">✨ SIGN UP / LOGIN</button>
                    </div>
                </div>

                <!-- COLLAPSIBLE AUTH CONTAINER -->
                <div id="auth-container" class="auth-container">
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                        <button class="tab-btn active" id="subtn-reg" onclick="switchAuthSub('reg')">📝 SIGN UP & VERIFY OTP</button>
                        <button class="tab-btn" id="subtn-log" onclick="switchAuthSub('log')">🔐 MEMBER SIGN IN</button>
                    </div>

                    <!-- REGISTRATION SECTION -->
                    <div id="auth-reg-section">
                        <div class="row">
                            <input type="text" id="su-name" name="new_user_full_name_xyz" placeholder="Full Name (e.g. Rajesh Sharma)" autocomplete="off">
                            <input type="email" id="su-email" name="new_user_email_address_xyz" placeholder="Email Address (e.g. user@gmail.com)" autocomplete="off">
                        </div>
                        <div class="row">
                            <input type="text" id="su-phone" name="new_user_phone_no_xyz" placeholder="Phone Number (e.g. 9876543210)" autocomplete="off">
                            <div class="password-container">
                                <input type="password" id="su-pass" name="new_user_password_xyz" placeholder="Create Secure Password" autocomplete="new-password">
                                <span class="eye-icon" onclick="togglePassword('su-pass', this)">👁️</span>
                            </div>
                        </div>
                        <button class="primary-btn" onclick="registerUser()">✨ 1. Register & Send Verification OTP</button>
                        <div id="su-output" style="margin-top: 10px;"></div>
                        <div style="margin-top: 15px;" class="row">
                            <input type="text" id="su-otp" name="user_otp_verification_xyz" placeholder="Enter 6-Digit Email OTP" autocomplete="off">
                            <button class="primary-btn" onclick="verifyOtp()">🔑 2. Verify OTP & Activate Account</button>
                        </div>
                    </div>

                    <!-- LOGIN SECTION -->
                    <div id="auth-log-section" style="display: none;">
                        <input type="email" id="li-email" name="login_member_email_xyz" placeholder="Registered Email Address (e.g. user@gmail.com)" autocomplete="off">
                        <div class="password-container">
                            <input type="password" id="li-pass" name="login_member_password_xyz" placeholder="Password" autocomplete="off">
                            <span class="eye-icon" onclick="togglePassword('li-pass', this)">👁️</span>
                        </div>
                        <button class="primary-btn" onclick="loginUser()">🚀 Sign In to Account</button>
                        <div id="li-output" style="margin-top: 10px;"></div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h4>💳 Wallet Balance: ₹ 0.00</h4>
                <p>Use credits for instant unlocking of reports.</p>
                <!-- 5 WALLET BUTTONS IN ONE ROW WITH ₹750 INCLUDED -->
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px;">
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(100)">⚡ ₹100</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(250)">⚡ ₹250</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(500)">⚡ ₹500</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(750)">⚡ ₹750</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(1000)">⚡ ₹1000</button>
                </div>
                <div id="wallet-result" style="margin-top:10px;"></div>
            </div>

            <div class="card">
                <h4>📦 Order History & Saved PDF Reports</h4>
                <p>No previous orders found for current guest session. Please register or login.</p>
            </div>

            <!-- HIDDEN ADMIN PORTAL AT THE BOTTOM (TRIGGERED BY LOGO DOT) -->
            <div id="admin-wrapper" class="card" style="display: none; border: 1.5px dashed #fde047; margin-top: 30px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0; color: #fde047;">🛡️ Owner Portal (Admin Dashboard)</h4>
                    <span style="font-size: 1.2rem; color: #fde047; cursor: pointer;" onclick="toggleAdminPanel()">✕</span>
                </div>
                <div id="admin-panel" style="margin-top: 15px;">
                    <div class="password-container">
                        <input type="password" id="admin-pass" name="admin_secret_pass_xyz" placeholder="Admin Password" autocomplete="off">
                        <span class="eye-icon" onclick="togglePassword('admin-pass', this)">👁️</span>
                    </div>
                    <button class="primary-btn" onclick="loadAdminDashboard()">Unlock Dashboard</button>
                    <div id="admin-output" style="margin-top: 15px;"></div>
                </div>
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
                <input type="text" id="life-tob" placeholder="Time of Birth (HH:MM)" onfocus="this.type='time'" onblur="if(!this.value)this.type='text'">
                <input type="text" id="life-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="submitLifePrediction()">✨ Reveal Life Insights (₹499)</button>
            <div id="life-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 3: HOROSCOPE -->
        <div id="tab-horoscope" class="tab-content">
            <h3>🔮 Daily Zodiac Predictions</h3>
            <select id="horo-sign">
                ZODIAC_OPTIONS_PLACEHOLDER
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

        <!-- TAB 6: VASTU SHASTRA -->
        <div id="tab-vastu" class="tab-content">
            <h3>🏛️ Vastu Shastra & Commercial/Home Property Analysis</h3>
            <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 15px;">Ensure positive energy flow (Vastu Purusha Mandala) for your home, office, or factory to maximize prosperity and success.</p>
            <div class="row">
                <input type="text" id="vastu-name" placeholder="Owner / Applicant Name" autocomplete="off">
                <select id="vastu-property-type">
                    <option value="Residential House / Flat">Residential House / Flat</option>
                    <option value="Commercial Office / Shop">Commercial Office / Shop</option>
                    <option value="Factory / Warehouse">Factory / Warehouse</option>
                    <option value="Plot / Land">Plot / Land</option>
                </select>
            </div>
            <div class="row">
                <select id="vastu-facing">
                    <option value="North Facing">North Facing (Kubera Direction)</option>
                    <option value="East Facing">East Facing (Surya Direction)</option>
                    <option value="South Facing">South Facing (Yama Direction)</option>
                    <option value="West Facing">West Facing (Varuna Direction)</option>
                    <option value="North-East (Ishan)">North-East (Ishan - Most Auspicious)</option>
                    <option value="South-East (Agneya)">South-East (Agneya - Fire Zone)</option>
                    <option value="South-West (Nairutya)">South-West (Nairutya - Earth Zone)</option>
                    <option value="North-West (Vayavya)">North-West (Vayavya - Air Zone)</option>
                </select>
                <input type="text" id="vastu-city" placeholder="City / Location" autocomplete="off">
            </div>
            <button class="primary-btn" onclick="submitVastuAnalysis()">🏛️ Generate Vastu Dosha & Remedy Report (₹349)</button>
            <div id="vastu-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 7: KUNDALI PDF -->
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

        <!-- TAB 8: NUMEROLOGY -->
        <div id="tab-numerology" class="tab-content">
            <h3>🔢 Numerology Check</h3>
            <div class="row">
                <input type="text" id="num-name" placeholder="Full Name">
                <input type="date" id="num-dob">
            </div>
            <button class="primary-btn" onclick="submitNumerology()">🔢 Analyze Numerology (₹249)</button>
            <div id="num-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 9: PANCHANG -->
        <div id="tab-panchang" class="tab-content">
            <h3>📅 Vedic Panchang & Shubh Muhurat</h3>
            <div class="row">
                <input type="date" id="p-date">
                <input type="text" id="p-city" placeholder="City">
            </div>
            <select id="p-mode" style="margin-top: 10px;">
                <option value="free">Free Daily Panchang</option>
                <option value="detailed">Detailed Shubh Muhurat Report (₹99)</option>
            </select>
            <button class="primary-btn" onclick="submitPanchang()" style="margin-top: 10px;">📅 Check Panchang</button>
            <div id="panchang-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 10: AI ASSISTANT -->
        <div id="tab-ai" class="tab-content">
            <h3>🤖 Ask Your Personal AI Astrologer</h3>
            <textarea id="ai-query" placeholder="Ask your question regarding career, marriage, health, vastu..."></textarea>
            <button class="primary-btn" onclick="askAi()">Ask Assistant ✨</button>
            <div id="ai-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TAB 11: LEGAL -->
        <div id="tab-legal" class="tab-content">
            <h3>⚖️ Terms & Social Handles</h3>
            <p>Welcome to AccAstroForge.in. All predictions are for guidance purposes.</p>
            <p><b>Support Email:</b> support@accastroforge.in</p>
            <p>Connect with us on our official social platforms:</p>
            <ul style="list-style-type: none; padding-left: 0; line-height: 2.2;">
                <li>🧳 <b style="color: #fde047;">Twitter (X):</b> <a href="https://x.com/AccAstroForge" target="_blank" style="color: #38bdf8;">https://x.com/AccAstroForge</a></li>
                <li>📸 <b style="color: #fde047;">Instagram:</b> <a href="https://www.instagram.com/accastroforge/" target="_blank" style="color: #f472b6;">https://www.instagram.com/accastroforge/</a></li>
                <li>🌀 <b style="color: #fde047;">Threads:</b> <a href="https://www.threads.com/@accastroforge" target="_blank" style="color: #e879f9;">https://www.threads.com/@accastroforge</a></li>
                <li>📘 <b style="color: #fde047;">Facebook:</b> <a href="https://www.facebook.com/accastroforge/" target="_blank" style="color: #60a5fa;">https://www.facebook.com/accastroforge/</a></li>
            </ul>
        </div>
    </div>

    <script>
        let generatedOtpStorage = "";
        let verifiedEmailStorage = "";
        let isAdminUnlocked = false;

        // LIVE 24-HOUR DIGITAL CLOCK SCRIPT WITH BLINKING COLON
        function updateLiveClock() {
            let now = new Date();
            let hours = String(now.getHours()).padStart(2, '0');
            let minutes = String(now.getMinutes()).padStart(2, '0');
            let seconds = String(now.getSeconds()).padStart(2, '0');
            let clockEl = document.getElementById('live-digital-clock');
            if(clockEl) {
                clockEl.innerHTML = `${hours}<span class="clock-colon">:</span>${minutes}<span class="clock-colon">:</span>${seconds} IST`;
            }
        }
        setInterval(updateLiveClock, 1000);

        window.onload = async function() {
            updateLiveClock();
            let hash = window.location.hash;
            if (hash && hash.includes("access_token")) {
                let params = new URLSearchParams(hash.substring(1));
                let accessToken = params.get("access_token");
                if (accessToken) {
                    let realEmail = "social.user@accastroforge.in";
                    let realName = "Social Member";

                    try {
                        if (window.location.href.includes("google") || accessToken.startsWith("ya29.")) {
                            let gRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
                                headers: { "Authorization": `Bearer ${accessToken}` }
                            });
                            let gData = await gRes.json();
                            if (gData && gData.email) {
                                realEmail = gData.email;
                                realName = gData.name || gData.email.split('@')[0];
                            }
                        } else {
                            let fbRes = await fetch(`https://graph.facebook.com/me?fields=id,name,email&access_token=${accessToken}`);
                            let fbData = await fbRes.json();
                            if (fbData && fbData.name) {
                                realName = fbData.name;
                                realEmail = fbData.email || `${fbData.name.toLowerCase().replace(/\\s+/g, '')}@facebook.com`;
                            }
                        }
                    } catch(e) {
                        console.log("Profile Fetch Error:", e);
                    }

                    try {
                        await fetch('/api/social-login', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({name: realName, email: realEmail})
                        });
                    } catch(err) {
                        console.log("Social sync error:", err);
                    }

                    setLoggedInUI(realName, realEmail);
                    window.history.replaceState({}, document.title, window.location.pathname);
                }
            }

            let savedEmail = localStorage.getItem('accastroforge_user');
            let savedName = localStorage.getItem('accastroforge_username') || savedEmail;
            if(savedEmail) {
                setLoggedInUI(savedName, savedEmail);
            }
        };

        function showMagicLoader(callback) {
            let overlay = document.getElementById('loader-overlay');
            overlay.classList.add('active');
            setTimeout(() => {
                overlay.classList.remove('active');
                if(callback) callback();
            }, 800);
        }

        function switchTab(evt, tabId) {
            showMagicLoader(() => {
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');
                evt.currentTarget.classList.add('active');
            });
        }

        function triggerPaymentLoader(event, targetUrl) {
            event.preventDefault();
            showMagicLoader(() => {
                window.open(targetUrl, '_blank');
            });
        }

        function toggleAuthBox() {
            let box = document.getElementById('auth-container');
            box.style.display = box.style.display === 'none' || box.style.display === '' ? 'block' : 'none';
        }

        function switchAuthSub(mode) {
            if(mode === 'reg') {
                document.getElementById('auth-reg-section').style.display = 'block';
                document.getElementById('auth-log-section').style.display = 'none';
                document.getElementById('subtn-reg').classList.add('active');
                document.getElementById('subtn-log').classList.remove('active');
            } else {
                document.getElementById('auth-reg-section').style.display = 'none';
                document.getElementById('auth-log-section').style.display = 'block';
                document.getElementById('subtn-log').classList.add('active');
                document.getElementById('subtn-reg').classList.remove('active');
            }
        }

        function toggleAdminPanel() {
            let wrapper = document.getElementById('admin-wrapper');
            wrapper.style.display = wrapper.style.display === 'none' || wrapper.style.display === '' ? 'block' : 'none';
            if(wrapper.style.display === 'block') {
                wrapper.scrollIntoView({ behavior: 'smooth' });
            }
        }

        function togglePassword(fieldId, iconEl) {
            let field = document.getElementById(fieldId);
            if(field.type === "password") {
                field.type = "text";
                iconEl.innerText = "🙈";
            } else {
                field.type = "password";
                iconEl.innerText = "👁️";
            }
        }

        function setLoggedInUI(name, email) {
            verifiedEmailStorage = email;
            localStorage.setItem('accastroforge_user', email);
            localStorage.setItem('accastroforge_username', name);
            document.getElementById('session-display').innerHTML = `
                <h4 style="color: #fde047; font-family: 'Cinzel', serif; margin: 0 0 4px 0;">🌟 ACTIVE MEMBER (${name})</h4>
                <p style="margin: 0; color: #4ade80; font-weight: 600; font-size: 1.05rem;">Logged In: ${email}</p>
            `;
            document.getElementById('auth-btn-area').innerHTML = `
                <div style="display: flex; gap: 10px;">
                    <button class="primary-btn" style="width: auto; padding: 10px 18px; background: #2563eb !important; font-size: 0.9rem;" onclick="switchAccount()">🔄 Switch Account</button>
                    <button class="primary-btn" style="width: auto; padding: 10px 18px; background: #dc2626 !important; font-size: 0.9rem;" onclick="logoutUser()">🚪 Log Out</button>
                </div>
            `;
            document.getElementById('auth-container').style.display = 'none';
        }

        function logoutUser() {
            localStorage.removeItem('accastroforge_user');
            localStorage.removeItem('accastroforge_username');
            verifiedEmailStorage = "";
            document.getElementById('session-display').innerHTML = `
                <h4>Active User Session</h4>
                <p style="margin: 0;">Guest User (Please Sign Up / Login)</p>
            `;
            document.getElementById('auth-btn-area').innerHTML = `
                <button id="auth-toggle-btn" class="primary-btn" style="width: auto; padding: 10px 20px;" onclick="toggleAuthBox()">✨ SIGN UP / LOGIN</button>
            `;
            document.getElementById('auth-container').style.display = 'none';
        }

        function switchAccount() {
            localStorage.removeItem('accastroforge_user');
            localStorage.removeItem('accastroforge_username');
            verifiedEmailStorage = "";
            document.getElementById('session-display').innerHTML = `
                <h4>Active User Session</h4>
                <p style="margin: 0;">Guest User (Please Sign Up / Login)</p>
            `;
            document.getElementById('auth-btn-area').innerHTML = `
                <button id="auth-toggle-btn" class="primary-btn" style="width: auto; padding: 10px 20px;" onclick="toggleAuthBox()">✨ SIGN UP / LOGIN</button>
            `;
            document.getElementById('auth-container').style.display = 'block';
            switchAuthSub('log');
        }

        async function loadAdminDashboard() {
            let pass = document.getElementById('admin-pass').value;
            let res = await fetch('/api/admin', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({password: pass}) });
            let data = await res.json();
            document.getElementById('admin-output').innerHTML = data.html;
            if(data.success) {
                isAdminUnlocked = true;
                alert("🛡️ Admin Mode Activated! All Paywalls are now Bypassed for testing.");
            }
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
            let name = document.getElementById('su-name').value;
            let email = document.getElementById('su-email').value;
            let phone = document.getElementById('su-phone').value;
            let res = await fetch('/api/verify-otp', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({otp: userOtp, gen_otp: generatedOtpStorage, name, email, phone}) });
            let data = await res.json();
            document.getElementById('su-output').innerHTML = data.msg;
            if(data.success) {
                setLoggedInUI(name, email);
            }
        }

        async function loginUser() {
            let email = document.getElementById('li-email').value;
            let res = await fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email}) });
            let data = await res.json();
            document.getElementById('li-output').innerHTML = data.msg;
            if(data.success) {
                setLoggedInUI(email.split('@')[0], email);
            }
        }

        async function topupWallet(amt) {
            showMagicLoader(async () => {
                let res = await fetch('/api/topup', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({amount: amt}) });
                let data = await res.json();
                document.getElementById('wallet-result').innerHTML = data.paywall;
            });
        }

        async function submitLifePrediction() {
            let name = document.getElementById('life-name').value;
            let dob = document.getElementById('life-dob').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/life', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('life-result').innerHTML = data.teaser + (data.paywall || '');
            });
        }

        async function getHoroscope() {
            let sign = document.getElementById('horo-sign').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/horoscope', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sign}) });
                let data = await res.json();
                document.getElementById('horo-result').innerHTML = data.html;
            });
        }

        async function submitMatching() {
            let boy_name = document.getElementById('b-name').value;
            let girl_name = document.getElementById('g-name').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/matching', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({boy_name, girl_name, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('matching-result').innerHTML = data.teaser + (data.paywall || '');
            });
        }

        async function submitGemstone() {
            let zodiac = document.getElementById('gem-zodiac').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/gemstone', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({zodiac, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('gem-result').innerHTML = data.teaser + (data.paywall || '');
            });
        }

        async function submitVastuAnalysis() {
            let name = document.getElementById('vastu-name').value;
            let p_type = document.getElementById('vastu-property-type').value;
            let facing = document.getElementById('vastu-facing').value;
            let city = document.getElementById('vastu-city').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/vastu', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, property_type: p_type, facing, city, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('vastu-result').innerHTML = data.teaser + (data.pdf_download_btn || '') + (data.paywall || '');
            });
        }

        async function submitKundaliPdf() {
            let name = document.getElementById('k-name').value;
            let dob = document.getElementById('k-dob').value;
            let tob = document.getElementById('k-tob').value;
            let pob = document.getElementById('k-pob').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/kundali-pdf', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, tob, pob, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('kundali-result').innerHTML = data.teaser + data.chart + (data.pdf_download_btn || '') + (data.paywall || '');
            });
        }

        async function submitNumerology() {
            let name = document.getElementById('num-name').value;
            let dob = document.getElementById('num-dob').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/numerology', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('num-result').innerHTML = data.teaser + (data.paywall || '');
            });
        }

        async function submitPanchang() {
            let city = document.getElementById('p-city').value;
            let date = document.getElementById('p-date').value;
            let mode = document.getElementById('p-mode').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/panchang', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({city, date, mode, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('panchang-result').innerHTML = data.html + (data.paywall || '');
            });
        }

        async function askAi() {
            let query = document.getElementById('ai-query').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/ai', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query}) });
                let data = await res.json();
                document.getElementById('ai-result').innerHTML = data.html;
            });
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    logo_html = f'<img src="{logo_src}" alt="AccAstroForge Logo">' if logo_src else '<span style="font-size: 26px; font-weight: 800; color: #fbcfe8; font-family: \'Cinzel\', serif;">AccAstroForge</span>'
    zodiac_options_html = "".join([f'<option value="{s}">{s}</option>' for s in ZODIAC_SIGNS])
    
    rendered_html = (
        HTML_TEMPLATE
        .replace("LOGO_SRC_PLACEHOLDER", logo_html)
        .replace("GOOGLE_URL_PLACEHOLDER", GOOGLE_OAUTH_URL)
        .replace("FB_URL_PLACEHOLDER", FACEBOOK_OAUTH_URL)
        .replace("ZODIAC_OPTIONS_PLACEHOLDER", zodiac_options_html)
    )
    return HTMLResponse(content=rendered_html)

@app.post("/api/admin")
async def api_admin(request: Request):
    data = await request.json()
    if data.get("password") != ADMIN_PASSWORD:
        return JSONResponse({"success": False, "html": "<span style='color:#ef4444;'>❌ Incorrect Password! Access Denied.</span>"})
    
    users = load_users()
    logs = load_logs()
    
    summary_html = f"""<div style='color:#fff;'>
        <p style='color:#4ade80; font-weight:bold; font-size:1.05rem;'>✅ ADMIN DASHBOARD UNLOCKED (PAYWALL BYPASSED FOR TESTING)</p>
        <h4 style='color:#4ade80; margin-bottom: 8px;'>📋 Registered Users ({len(users)})</h4>
        <table style='width:100%; border-collapse:collapse; border:1px solid #7c3aed; margin-bottom:20px; font-size: 0.85rem;' border='1'>
            <tr style='background:#5b21b6;'><th>Name</th><th>Email</th><th>Phone</th></tr>"""
    for u in users:
        summary_html += f"<tr><td>{u.get('name', '')}</td><td>{u.get('email', '')}</td><td>{u.get('phone', '')}</td></tr>"
    summary_html += "</table>"

    summary_html += f"""
        <h4 style='color:#fde047; margin-bottom: 8px;'>📊 Live Activity & Payment Logs from Google Sheet ({len(logs)})</h4>
        <div style='max-height: 350px; overflow-y: auto;'>
        <table style='width:100%; border-collapse:collapse; border:1px solid #7c3aed; font-size: 0.82rem;' border='1'>
            <tr style='background:#5b21b6; position: sticky; top: 0;'><th>Timestamp</th><th>User / Name</th><th>Service / Action</th><th>Details</th><th>Status</th></tr>
    """
    for l in logs:
        summary_html += f"<tr><td>{l.get('timestamp', '')}</td><td>{l.get('full_name', '')}</td><td>{l.get('service', '')}</td><td>{l.get('details', '')}</td><td>{l.get('payment_status', '')}</td></tr>"
    summary_html += "</table></div></div>"

    return JSONResponse({"success": True, "html": summary_html})

@app.post("/api/social-login")
async def api_social_login(request: Request):
    data = await request.json()
    name = data.get("name", "Social User")
    email = data.get("email", "").strip().lower()
    if email:
        save_user_db_single(name, email, "Social Quick Login")
        save_log({
            "timestamp": str(datetime.datetime.now()),
            "full_name": name,
            "service": "Quick Social Login",
            "details": f"Email: {email}",
            "payment_status": "Active & Verified"
        })
    return JSONResponse({"success": True})

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

@app.post("/api/verify-otp")
async def api_verify_otp(request: Request):
    data = await request.json()
    if str(data.get("otp")) != str(data.get("gen_otp")):
        return JSONResponse({"success": False, "msg": "<p style='color:#ef4444;'>❌ Invalid OTP!</p>"})
    save_user_db_single(data.get("name"), data.get("email"), data.get("phone"))
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": data.get("name", "User"), "service": "Account Verified", "details": f"Email: {data.get('email')}", "payment_status": "Active Session"})
    return JSONResponse({"success": True, "msg": "<p style='color:#4ade80;'>🎉 Account Verified & Active!</p>"})

@app.post("/api/login")
async def api_login(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    users = load_users()
    found_user = next((u for u in users if u.get("email") == email or u.get("Email") == email), None)
    if found_user:
        u_name = found_user.get("name", found_user.get("Name", "Member"))
        save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Member Sign In", "details": f"Email: {email}", "payment_status": "Active Session"})
        return JSONResponse({"success": True, "msg": "<p style='color:#4ade80;'>🎉 Login Successful!</p>"})
    return JSONResponse({"success": False, "msg": "<p style='color:#ef4444;'>❌ Account not found. Please register first.</p>"})

@app.post("/api/topup")
async def api_topup(request: Request):
    data = await request.json()
    amt = data.get("amount", 250)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "Valued Customer", "service": "Wallet Topup", "details": f"Amount: ₹{amt}", "payment_status": "Pending"})
    paywall = get_paywall_html(f"Wallet Topup (₹{amt})", amt, "User")
    return JSONResponse({"paywall": paywall})

@app.post("/api/life")
async def api_life(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Life Prediction", "details": f"DOB: {dob}", "payment_status": "Admin Bypassed" if is_admin else "Pending (₹499)"})
    profile = calculate_astrological_profile(name, dob)
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🌟 Astrological Teaser for {name.upper()}</h4><p><b>Rashi:</b> {profile['zodiac']} | <b>Nakshatra:</b> {profile['nakshatra']} | <b>Dasha:</b> {profile['dasha']}</p></div>"""
    paywall = "" if is_admin else get_paywall_html("Complete Deep Life Forecast & PDF", 499, name)
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/horoscope")
async def api_horoscope(request: Request):
    data = await request.json()
    sign = data.get("sign", "Aries")
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "Guest/Member", "service": "Horoscope", "details": f"Sign: {sign}", "payment_status": "Free"})
    html = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🔮 Daily Horoscope for {sign}</h4><p>Today brings high cosmic energy. Jupiter's aspect promises financial opportunities and peace.</p></div>"""
    return JSONResponse({"html": html})

@app.post("/api/matching")
async def api_matching(request: Request):
    data = await request.json()
    b = data.get("boy_name", "Boy")
    g = data.get("girl_name", "Girl")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b} & {g}", "service": "Kundali Matching", "details": "Guna Milan Check", "payment_status": "Admin Bypassed" if is_admin else "Pending (₹399)"})
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>❤️ Compatibility Teaser for {b} & {g}</h4><p>High Guna Milan score detected! Excellent long-term emotional alignment.</p></div>"""
    paywall = "" if is_admin else get_paywall_html("Complete Kundali Matching Report", 399, f"{b} & {g}")
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/gemstone")
async def api_gemstone(request: Request):
    data = await request.json()
    z = data.get("zodiac", "Aries")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "User", "service": "Gemstone Remedy", "details": f"Zodiac: {z}", "payment_status": "Admin Bypassed" if is_admin else "Pending (₹299)"})
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>💎 Gemstone Guidance for {z}</h4><p>Emerald (Panna) or Yellow Sapphire recommended for career success.</p></div>"""
    paywall = "" if is_admin else get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/vastu")
async def api_vastu(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    p_type = data.get("property_type", "Residential")
    facing = data.get("facing", "North Facing")
    city = data.get("city", "Kolkata")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Vastu Analysis", "details": f"Property: {p_type}, Facing: {facing}, City: {city}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹349)"})
    
    filename = f"Vastu_Report_{name.replace(' ', '_')}.pdf"
    generate_pdf_report(
        filename,
        f"Vastu Shastra Assessment for {name}",
        [
            f"Property Type: {p_type}",
            f"Direction Facing: {facing}",
            f"Location: {city}",
            "Vastu Purusha Mandala Analysis: The main entrance and energy grids show favorable alignment with minor adjustments required in South-West zones.",
            "Recommended Remedies: Place Vastu Pyramids in affected corners and ensure water elements are placed in the North-East Ishan corner for maximum financial prosperity and stability."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:12px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:10px 20px; border-radius:8px; font-weight:bold; text-decoration:none; display:inline-block;'>📥 Download Vastu PDF Report</a></div>"""
    
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🏛️ Vastu Analysis Preview for {name} ({p_type})</h4><p><b>Facing:</b> {facing} | <b>Location:</b> {city}</p><p style='color:#4ade80;'>✅ Vastu PDF generated with proper balanced logo.</p></div>"""
    
    paywall = "" if is_admin else get_paywall_html("Complete Vastu Dosha & Remedial PDF Report", 349, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/kundali-pdf")
async def api_kundali_pdf(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    tob = data.get("tob", "10:00")
    pob = data.get("pob", "Kolkata")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Janam Kundali PDF", "details": f"DOB: {dob}, POB: {pob}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Generated (₹299)"})
    
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    generate_pdf_report(
        filename,
        f"Janam Kundali & Lagna Chart - {name}",
        [
            f"Date of Birth: {dob} | Time: {tob}",
            f"Place of Birth: {pob}",
            "Planetary Positions (Graha Sthiti): Sun in Aries, Moon in Taurus, Jupiter in Cancer.",
            "Lagna Horoscope: Strong ascendant house indicating resilience, leadership, and long-term financial growth."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:12px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:10px 20px; border-radius:8px; font-weight:bold; text-decoration:none; display:inline-block;'>📥 Download Janam Kundali PDF</a></div>"""
    
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>📜 Janam Kundali Generated for {name}</h4><p>Your Lagna birth chart preview is ready with proper clear logo.</p></div>"""
    chart = f"""<div style='background:#31104b; padding:15px; border-radius:10px; margin-top:10px; text-align:center;'><b style='color:#fde047;'>Lagna Chart Active (DOB: {dob}, POB: {pob})</b></div>"""
    
    paywall = "" if is_admin else get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "chart": chart, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/numerology")
async def api_numerology(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Numerology", "details": f"DOB: {dob}", "payment_status": "Admin Bypassed" if is_admin else "Pending (₹249)"})
    profile = calculate_astrological_profile(name, dob)
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>🔢 Numerology Preview for {name}</h4><p>Destiny Psychic Number: <b style='color:#fde047;'>{profile['psychic_num']}</b></p></div>"""
    paywall = "" if is_admin else get_paywall_html("Detailed Numerology & Name Correction Report", 249, name)
    return JSONResponse({"teaser": teaser, "paywall": paywall})

@app.post("/api/panchang")
async def api_panchang(request: Request):
    data = await request.json()
    city = data.get("city", "Kolkata")
    date = data.get("date", "Today")
    mode = data.get("mode", "free")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "User", "service": "Panchang", "details": f"City: {city}, Mode: {mode}", "payment_status": "Free/Admin Bypassed" if is_admin else "Free/Pending"})
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>📅 Vedic Panchang for {city} ({date})</h4><p><b>Tithi:</b> Shukla Paksha Navami<br><b>Nakshatra:</b> Rohini<br><b>Rahu Kalam:</b> 10:30 AM - 12:00 PM</p></div>"""
    paywall = ""
    if mode == "detailed" and not is_admin:
        paywall = get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
    return JSONResponse({"html": teaser, "paywall": paywall})

@app.post("/api/ai")
async def api_ai(request: Request):
    data = await request.json()
    query = data.get("query", "").strip().lower()
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "User", "service": "AI Assistant", "details": f"Query: {query[:30]}...", "payment_status": "Free Answer"})
    
    if any(k in query for k in ["vastu", "office", "house", "facing", "direction", "factory"]):
        ai_reply = "🏛️ Vastu Guidance: Ensuring your main entrance is in the North or East direction brings abundance. Keep the North-East (Ishan) zone clean and clutter-free."
    elif any(k in query for k in ["kundali", "birth chart", "lagna", "janam"]):
        ai_reply = "📜 Janam Kundali Insight: Your planetary positions indicate a strong Lagna house. Focus on consistent efforts in your professional sphere for optimal growth."
    elif any(k in query for k in ["gemstone", "panna", "stone", "ring", "ratna"]):
        ai_reply = "💎 Gemstone Recommendation: Based on cosmic alignments, wearing a certified Emerald (Panna) or Yellow Sapphire on an auspicious day will enhance focus and prosperity."
    elif any(k in query for k in ["career", "job", "business", "money", "finance", "success"]):
        ai_reply = "💼 Career & Wealth Forecast: Jupiter's transit brings favorable opportunities for career advancement and financial stability. Avoid impulsive investments."
    elif any(k in query for k in ["marriage", "love", "relationship", "match", "partner"]):
        ai_reply = "❤️ Relationship & Marriage Guidance: Venus harmony indicates positive emotional bonding. Transparent communication will resolve ongoing misunderstandings."
    else:
        ai_reply = f"✨ AI Astrologer Response for '{query}': Planetary transits show highly favorable outcomes for your endeavors. Keep up regular meditation and positive intent."

    html = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><p><b>Query:</b> {query}</p><p style='color:#4ade80;'><b>AI Astrologer:</b> {ai_reply}</p></div>"""
    return JSONResponse({"html": html})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)
