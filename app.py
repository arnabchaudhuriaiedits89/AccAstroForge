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
# 0. CONFIGURATIONS & SECRETS (AccAstroForge)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_gemstones (
            email_key TEXT PRIMARY KEY,
            name TEXT,
            dob TEXT,
            zodiac TEXT,
            primary_gem TEXT,
            fortune_gem TEXT,
            updated_at TEXT
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

def check_user_exists_triple(email):
    email_clean = email.strip().lower()
    if not email_clean:
        return False
    users = load_users()
    for u in users:
        u_email = str(u.get("email", u.get("Email", ""))).strip().lower()
        if u_email == email_clean:
            return True
    return False

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
        name_seed = sum(ord(c) for c in name.lower()) if name else 42
        day_sum = sum(int(digit) for digit in dob_str if digit.isdigit())
        while day_sum > 9:
            day_sum = sum(int(d) for d in str(day_sum))
        zodiac_index = (dt.month + name_seed) % 12
        nakshatra_index = (dt.day + dt.month * 2 + name_seed) % 27
        planet_list = ['Jupiter', 'Saturn', 'Mercury', 'Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu']
        dasha_active = planet_list[(name_seed + dt.day) % len(planet_list)]
        return {
            "name": name if name else "User",
            "zodiac": ZODIAC_SIGNS[zodiac_index],
            "nakshatra": NAKSHATRAS[nakshatra_index],
            "psychic_num": day_sum,
            "dasha": f"Mahadasha of {dasha_active} is active."
        }
    except Exception:
        return {
            "name": name if name else "User",
            "zodiac": "Aries (Mesha)",
            "nakshatra": "Rohini",
            "psychic_num": 7,
            "dasha": "Favorable Planetary Dasha Cycle active."
        }

def calculate_jagannath_hora_engine(name, dob, tob, pob):
    try:
        seed = sum(ord(c) for c in (name + dob + pob).lower()) if (name or dob) else 108
    except Exception:
        seed = 108
    
    shodashvarga_charts = {
        "D1 (Lagna / Main Body)": ZODIAC_SIGNS[seed % 12],
        "D2 (Hora / Wealth & Assets)": "Sun & Moon Hora Balanced",
        "D3 (Drekkana / Siblings & Courage)": ZODIAC_SIGNS[(seed + 2) % 12],
        "D4 (Chaturthamsa / Property & Fortune)": ZODIAC_SIGNS[(seed + 4) % 12],
        "D7 (Saptamsha / Progeny & Children)": ZODIAC_SIGNS[(seed + 6) % 12],
        "D9 (Navamsha / Marriage & Soul Purpose)": ZODIAC_SIGNS[(seed + 8) % 12],
        "D10 (Dashamsha / Career & Profession)": ZODIAC_SIGNS[(seed + 10) % 12],
        "D12 (Dwadasamsa / Parents & Lineage)": ZODIAC_SIGNS[(seed + 1) % 12],
        "D16 (Shodasamsa / Vehicles & Comforts)": ZODIAC_SIGNS[(seed + 3) % 12],
        "D20 (Vimsamsa / Spiritual Progress)": ZODIAC_SIGNS[(seed + 5) % 12],
        "D24 (Chaturvimshamsha / Knowledge & Learning)": ZODIAC_SIGNS[(seed + 7) % 12],
        "D27 (Bhamsha / Strengths & Weaknesses)": ZODIAC_SIGNS[(seed + 9) % 12],
        "D30 (Trimsamsa / Misfortunes & Neutralization)": ZODIAC_SIGNS[(seed + 11) % 12],
        "D40 (Khavedamsa / Auspicious & Inauspicious Events)": ZODIAC_SIGNS[(seed + 4) % 12],
        "D45 (Akshavedamsa / General Character & Ethics)": ZODIAC_SIGNS[(seed + 2) % 12],
        "D60 (Shastiamsha / Past Karma & Overall Destiny)": ZODIAC_SIGNS[seed % 12]
    }
    
    dashas = {
        "Vimshottari Mahadasha": "Jupiter / Saturn Active Cycle",
        "Yogini Dasha": "Bhadrika (Mercury) Yoga active",
        "Chara Dasha": "Aries (Mesha) Direct Rashi Dasha",
        "Ashtottari Dasha": "Rahu / Venus Protection Phase"
    }
    
    ashtakavarga = {
        "Sarvashtakavarga Total": 285 + (seed % 35),
        "Sun Ashtakavarga": "29 Points (Favorable)",
        "Moon Ashtakavarga": "31 Points (Strong)",
        "Jupiter Ashtakavarga": "34 Points (Highly Auspicious)"
    }
    
    profile = calculate_astrological_profile(name, dob)
    return {
        "profile": profile,
        "shodashvarga": shodashvarga_charts,
        "dashas": dashas,
        "ashtakavarga": ashtakavarga,
        "transit_overlay": "Jupiter in 9th house bringing wealth and spiritual expansion."
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

def draw_clean_pdf_decorations(canvas_obj, doc_obj):
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
    
    if os.path.exists("logo.png"):
        try:
            logo_img = RLImage("logo.png", width=85, height=85)
            logo_img.hAlign = 'CENTER'
            story.append(logo_img)
            story.append(Spacer(1, 10))
        except Exception:
            pass

    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 6))
    
    for para in content_paragraphs:
        story.append(Paragraph(para, body_style))
        story.append(Spacer(1, 6))
        
    doc.build(story, onFirstPage=draw_clean_pdf_decorations, onLaterPages=draw_clean_pdf_decorations)
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
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
            background: radial-gradient(circle, #fde047 0%, #d97706 100%);
            border: 2px solid #fef08a;
            border-radius: 50%;
            display: inline-block;
            cursor: pointer;
            box-shadow: 0 0 15px #fde047;
            margin-left: 10px;
            z-index: 999;
        }

        .header-right-area {
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
            margin-top: 5px;
        }

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

        select option {
            background-color: #160a30 !important;
            color: #fef08a !important;
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
        <!-- HEADER WITH LOGO, ADMIN DOT, LIVE DIGITAL CLOCK & QUICK LOGINS -->
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
            <button class="tab-btn" onclick="switchTab(event, 'tab-hub')">🌟 MY COSMIC HUB</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-jh')">☸️ JAGANNATH HORA PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-explorer')">🧭 KUNDALI EXPLORER</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-dasha')">⏳ DASHA TIMELINE</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-transit')">🪐 TRANSIT TRACKER</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-life')">🌟 LIVE PREDICTION PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-horoscope')">☀️ HOROSCOPE</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-matching')">❤️ MATCHING PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-gemstones')">💎 GEMSTONES PDF</button>
            <button class="tab-btn" onclick="switchTab(event, 'tab-vastu')">🏛️ VASTU SHASTRA PDF</button>
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

                <div id="auth-container" class="auth-container">
                    <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                        <button class="tab-btn active" id="subtn-reg" onclick="switchAuthSub('reg')">📝 SIGN UP & VERIFY OTP</button>
                        <button class="tab-btn" id="subtn-log" onclick="switchAuthSub('log')">🔐 MEMBER SIGN IN</button>
                    </div>

                    <div id="auth-reg-section">
                        <div class="row">
                            <input type="text" id="su-name" placeholder="Full Name (e.g. Rajesh Sharma)" autocomplete="off">
                            <input type="email" id="su-email" placeholder="Email Address (e.g. user@gmail.com)" autocomplete="off">
                        </div>
                        <div class="row">
                            <input type="text" id="su-phone" placeholder="Phone Number (e.g. 9876543210)" autocomplete="off">
                            <div class="password-container">
                                <input type="password" id="su-pass" placeholder="Create Secure Password" autocomplete="new-password">
                                <span class="eye-icon" onclick="togglePassword('su-pass', this)">👁️</span>
                            </div>
                        </div>
                        <button class="primary-btn" onclick="registerUser()">✨ 1. Register & Send Verification OTP</button>
                        <div id="su-output" style="margin-top: 10px;"></div>
                        <div style="margin-top: 15px;" class="row">
                            <input type="text" id="su-otp" placeholder="Enter 6-Digit Email OTP" autocomplete="off">
                            <button class="primary-btn" onclick="verifyOtp()">🔑 2. Verify OTP & Activate Account</button>
                        </div>
                    </div>

                    <div id="auth-log-section" style="display: none;">
                        <input type="email" id="li-email" placeholder="Registered Email Address (e.g. user@gmail.com)" autocomplete="off">
                        <div class="password-container">
                            <input type="password" id="li-pass" placeholder="Password" autocomplete="off">
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
                <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-top: 10px;">
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(99)">⚡ ₹99</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(199)">⚡ ₹199</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(299)">⚡ ₹299</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(399)">⚡ ₹399</button>
                    <button class="primary-btn" style="padding: 10px 4px; font-size: 0.85rem;" onclick="topupWallet(499)">⚡ ₹499</button>
                </div>
                <div id="wallet-result" style="margin-top:10px;"></div>
            </div>

            <div class="card">
                <h4>📦 Order History & Saved PDF Reports</h4>
                <p>No previous orders found for current guest session. Please register or login.</p>
            </div>

            <div id="admin-wrapper" class="card" style="display: none; border: 1.5px dashed #fde047; margin-top: 30px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h4 style="margin: 0; color: #fde047;">🛡️ Owner Portal (Admin Dashboard)</h4>
                    <span style="font-size: 1.2rem; color: #fde047; cursor: pointer;" onclick="toggleAdminPanel()">✕</span>
                </div>
                <div id="admin-panel" style="margin-top: 15px;">
                    <div class="password-container">
                        <input type="password" id="admin-pass" placeholder="Admin Password" autocomplete="off">
                        <span class="eye-icon" onclick="togglePassword('admin-pass', this)">👁️</span>
                    </div>
                    <button class="primary-btn" onclick="loadAdminDashboard()">Unlock Dashboard</button>
                    <div id="admin-output" style="margin-top: 15px;"></div>
                </div>
            </div>
        </div>

        <!-- MY COSMIC HUB -->
        <div id="tab-hub" class="tab-content">
            <h3>🌟 My Cosmic Profile / Birth Chart Hub</h3>
            <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 15px;">Enter your birth details **once** here to automatically feed Kundali generation, Dasha Timeline, Transit Tracker, and AI Astrologer without re-typing!</p>
            <div class="row">
                <input type="text" id="hub-name" placeholder="Full Name">
                <input type="date" id="hub-dob">
            </div>
            <div class="row">
                <input type="text" id="hub-tob" placeholder="Time of Birth (HH:MM)">
                <input type="text" id="hub-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="saveCosmicHub()">✨ Save & Sync Across All Features</button>
            <div id="hub-result" style="margin-top: 15px;"></div>
        </div>

        <!-- JAGANNATH HORA -->
        <div id="tab-jh" class="tab-content">
            <h3>☸️ Jagannath Hora Vedic Calculations (16 Shodashvarga & Advanced Dashas) PDF</h3>
            <div class="row">
                <input type="text" id="jh-name" placeholder="Full Name">
                <input type="date" id="jh-dob">
            </div>
            <div class="row">
                <input type="text" id="jh-tob" placeholder="Time of Birth (HH:MM)">
                <input type="text" id="jh-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="submitJhEngine()">☸️ Generate Jagannath Hora Vedic Analysis (₹59)</button>
            <div id="jh-result" style="margin-top: 15px;"></div>
        </div>

        <!-- KUNDALI EXPLORER -->
        <div id="tab-explorer" class="tab-content">
            <h3>🧭 Interactive Kundali & Divisional Chart Explorer</h3>
            <div class="row" style="margin-top: 15px;">
                <input type="text" id="exp-name" placeholder="Full Name">
                <select id="exp-chart-type">
                    <option value="D1">D1 - Lagna Chart (Main Body & Life)</option>
                    <option value="D9">D9 - Navamsha Chart (Marriage & Soul)</option>
                    <option value="D10">D10 - Dashamsha Chart (Career & Profession)</option>
                    <option value="D7">D7 - Saptamsha Chart (Children & Progeny)</option>
                </select>
            </div>
            <button class="primary-btn" onclick="exploreKundali()">🧭 Load Interactive Chart Grid</button>
            <div id="explorer-result" style="margin-top: 15px;"></div>
        </div>

        <!-- DASHA TIMELINE -->
        <div id="tab-dasha" class="tab-content">
            <h3>⏳ Personal Dasha Timeline</h3>
            <div class="row" style="margin-top: 15px;">
                <input type="text" id="dasha-name" placeholder="Full Name">
                <input type="date" id="dasha-dob">
            </div>
            <button class="primary-btn" onclick="loadDashaTimeline()">⏳ Calculate Dasha Timeline</button>
            <div id="dasha-result" style="margin-top: 15px;"></div>
        </div>

        <!-- TRANSIT TRACKER -->
        <div id="tab-transit" class="tab-content">
            <h3>🪐 Live Planetary Transit Tracker</h3>
            <div class="row" style="margin-top: 15px;">
                <input type="text" id="transit-name" placeholder="Full Name (Auto-synced from Cosmic Hub)" autocomplete="off">
                <select id="transit-planet">
                    <option value="Jupiter">Jupiter (Guru - Wealth & Expansion)</option>
                    <option value="Saturn">Saturn (Shani - Karma & Discipline)</option>
                    <option value="Rahu">Rahu (Ambition & Technology)</option>
                    <option value="Ketu">Ketu (Spiritual Liberation)</option>
                </select>
            </div>
            <button class="primary-btn" onclick="loadTransitTracker()">🪐 Check Current Planetary Transits</button>
            <div id="transit-result" style="margin-top: 15px;"></div>
        </div>

        <!-- LIFE PREDICTION -->
        <div id="tab-life" class="tab-content">
            <h3>🌌 Vedic Astrology & Deep Life Forecast PDF</h3>
            <div class="row">
                <input type="text" id="life-name" placeholder="Full Name">
                <input type="date" id="life-dob">
            </div>
            <div class="row">
                <input type="text" id="life-tob" placeholder="Time of Birth (HH:MM)" onfocus="this.type='time'" onblur="if(!this.value)this.type='text'">
                <input type="text" id="life-pob" placeholder="Place of Birth">
            </div>
            <button class="primary-btn" onclick="submitLifePrediction()">✨ Reveal Life Insights & PDF (₹149)</button>
            <div id="life-result" style="margin-top: 15px;"></div>
        </div>

        <!-- HOROSCOPE -->
        <div id="tab-horoscope" class="tab-content">
            <h3>🔮 Daily Zodiac Predictions</h3>
            <select id="horo-sign">
                ZODIAC_OPTIONS_PLACEHOLDER
            </select>
            <button class="primary-btn" onclick="getHoroscope()">🔮 Get Horoscope</button>
            <div id="horo-result" style="margin-top: 15px;"></div>
        </div>

        <!-- MATCHING -->
        <div id="tab-matching" class="tab-content">
            <h3>💍 Vedic Compatibility & Guna Milan PDF</h3>
            <div class="row">
                <input type="text" id="b-name" placeholder="Boy's Name">
                <input type="date" id="b-dob">
            </div>
            <div class="row">
                <input type="text" id="g-name" placeholder="Girl's Name">
                <input type="date" id="g-dob">
            </div>
            <button class="primary-btn" onclick="submitMatching()">❤️ Match Kundalis & PDF Now (₹59)</button>
            <div id="matching-result" style="margin-top: 15px;"></div>
        </div>

        <!-- GEMSTONES -->
        <div id="tab-gemstones" class="tab-content">
            <h3>💎 LUCKY GEMSTONES & COSMIC REMEDIES PDF</h3>
            <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 15px;">Enter your birth details or select your zodiac sign to calculate your precise primary life gemstone (Lagna Stone) and fortune crystal with complete wearing rituals.</p>
            <div class="row">
                <input type="text" id="gem-name" placeholder="Full Name (e.g. Rajesh Sharma)">
                <input type="date" id="gem-dob">
            </div>
            <div class="row">
                <select id="gem-zodiac">
                    ZODIAC_OPTIONS_PLACEHOLDER
                </select>
                <input type="text" id="gem-pob" placeholder="Place of Birth (e.g. Kolkata)">
            </div>
            <button class="primary-btn" onclick="submitGemstone()">💎 Calculate Precise Lucky Gemstone & Rituals (₹59)</button>
            <div id="gem-result" style="margin-top: 15px;"></div>
        </div>

        <!-- VASTU SHASTRA -->
        <div id="tab-vastu" class="tab-content">
            <h3>🏛️ VASTU SHASTRA & PROPERTY ANALYSIS PDF</h3>
            <div class="row">
                <input type="text" id="vastu-name" placeholder="Owner / Applicant Name" autocomplete="off">
                <select id="vastu-property-type">
                    <option value="Residential House / Flat">Residential House / Flat</option>
                    <option value="Commercial Office / Shop">Commercial Office / Shop</option>
                    <option value="Factory / Manufacturing Unit">Factory / Manufacturing Unit</option>
                    <option value="Warehouse / Storage Hub">Warehouse / Storage Hub</option>
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
            <button class="primary-btn" onclick="submitVastuAnalysis()">🏛️ Generate Property-Specific Vastu Report (₹149)</button>
            <div id="vastu-result" style="margin-top: 15px;"></div>
        </div>

        <!-- KUNDALI PDF -->
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
            <button class="primary-btn" onclick="submitKundaliPdf()">📜 Generate Kundali & PDF (₹59)</button>
            <div id="kundali-result" style="margin-top: 15px;"></div>
        </div>

        <!-- NUMEROLOGY -->
        <div id="tab-numerology" class="tab-content">
            <h3>🔢 Numerology Check</h3>
            <div class="row">
                <input type="text" id="num-name" placeholder="Full Name">
                <input type="date" id="num-dob">
            </div>
            <button class="primary-btn" onclick="submitNumerology()">🔢 Analyze Numerology (₹69)</button>
            <div id="num-result" style="margin-top: 15px;"></div>
        </div>

        <!-- PANCHANG -->
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

        <!-- AI PALMISTRY -->
        <div id="tab-palm" class="tab-content">
            <h3>🖐️ Interactive Palmistry & Hand Analysis PDF</h3>
            <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 15px;">Select your primary palm characteristics below for a precise, logical astrological and hand-reading assessment:</p>
            
            <div class="row">
                <div>
                    <label style="font-size: 0.85rem; color: #fde047; display: block; margin-bottom: 5px;">Focus Area:</label>
                    <select id="palm-focus">
                        <option value="Career & Wealth">Career & Wealth</option>
                        <option value="Health & Vitality">Health & Vitality</option>
                        <option value="Relationships & Marriage">Relationships & Marriage</option>
                        <option value="Spiritual Growth">Spiritual Growth</option>
                    </select>
                </div>
                <div>
                    <label style="font-size: 0.85rem; color: #fde047; display: block; margin-bottom: 5px;">Life Line Type:</label>
                    <select id="palm-life">
                        <option value="Deep and Unbroken">Deep and Unbroken (Robust Vitality)</option>
                        <option value="Sweeping & Curved">Sweeping & Curved (High Energy)</option>
                        <option value="Chained Initial">Chained Initial (Evolving Strength)</option>
                        <option value="Double Line (Mars)">Double Line / Martian Line (Protective)</option>
                    </select>
                </div>
            </div>

            <div class="row" style="margin-top: 10px;">
                <div>
                    <label style="font-size: 0.85rem; color: #fde047; display: block; margin-bottom: 5px;">Head Line (Mind) Type:</label>
                    <select id="palm-head">
                        <option value="Straight and Clear">Straight and Clear (Practical Intellect)</option>
                        <option value="Sloping to Luna">Sloping to Luna (Creative Vision)</option>
                        <option value="Forked (Writer's Fork)">Forked / Writer's Fork (Adaptable)</option>
                        <option value="High near Jupiter">High near Jupiter (Independent Thinker)</option>
                    </select>
                </div>
                <div>
                    <label style="font-size: 0.85rem; color: #fde047; display: block; margin-bottom: 5px;">Heart Line (Emotion) Type:</label>
                    <select id="palm-heart">
                        <option value="Curved and Warm">Curved and Warm (Balanced & Empathetic)</option>
                        <option value="Under Jupiter">Under Jupiter Mount (Sincere & Devoted)</option>
                        <option value="Upward Branches">Upward Branches (Joyful & Resilient)</option>
                        <option value="Trishul Marked">Trishul / Trident Marked (Spiritual & Popular)</option>
                    </select>
                </div>
            </div>

            <button class="primary-btn" onclick="analyzePalm()" style="margin-top: 20px;">🖐️ Generate Palmistry Report & PDF (₹79)</button>
            <div id="palm-result" style="margin-top: 15px;"></div>
        </div>

        <!-- AI ASSISTANT -->
        <div id="tab-ai" class="tab-content">
            <h3>🤖 AI Kundli Interpreter & Personal Astrologer</h3>
            <p style="color: #f3e8ff; font-size: 0.95rem;">Ask your question regarding career, marriage, health, vastu... AI answers in English based on your saved chart data.</p>
            <textarea id="ai-query" placeholder="Ask your question..."></textarea>
            <button class="primary-btn" onclick="askAi()">Ask AI Assistant ✨</button>
            <div id="ai-result" style="margin-top: 15px;"></div>
        </div>

        <!-- LEGAL -->
        <div id="tab-legal" class="tab-content">
            <h3>⚖️ Terms & Social Handles</h3>
            <p>Welcome to AccAstroForge.in. All predictions are for guidance purposes.</p>
            <p><b>Support Email:</b> support@accastroforge.in</p>
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
            
            if(localStorage.getItem('hub_name')) {
                let savedN = localStorage.getItem('hub_name');
                let savedD = localStorage.getItem('hub_dob') || '';
                let savedT = localStorage.getItem('hub_tob') || '';
                let savedP = localStorage.getItem('hub_pob') || '';

                ['hub-name', 'jh-name', 'exp-name', 'dasha-name', 'transit-name', 'life-name', 'k-name', 'num-name', 'vastu-name', 'gem-name'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && !el.value) el.value = savedN;
                });
                ['hub-dob', 'jh-dob', 'dasha-dob', 'life-dob', 'gem-dob', 'k-dob', 'num-dob', 'p-date'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && !el.value && savedD) el.value = savedD;
                });
                ['hub-tob', 'jh-tob', 'k-tob', 'life-tob'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && !el.value && savedT) el.value = savedT;
                });
                ['hub-pob', 'jh-pob', 'k-pob', 'p-city', 'vastu-city', 'gem-pob'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && !el.value && savedP) el.value = savedP;
                });
            }

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
                                realEmail = fbData.email || `${fbData.name.toLowerCase().replace(/\s+/g, '')}@facebook.com`;
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
            if(wrapper) {
                let isHidden = wrapper.style.display === 'none' || wrapper.style.display === '';
                wrapper.style.display = isHidden ? 'block' : 'none';
                if(isHidden) {
                    wrapper.scrollIntoView({ behavior: 'smooth' });
                }
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
            if(data.already_registered) {
                document.getElementById('su-output').innerHTML = data.msg;
                return;
            }
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

        async function saveCosmicHub() {
            let name = document.getElementById('hub-name').value;
            let dob = document.getElementById('hub-dob').value;
            let tob = document.getElementById('hub-tob').value;
            let pob = document.getElementById('hub-pob').value;
            showMagicLoader(() => {
                localStorage.setItem('hub_name', name);
                localStorage.setItem('hub_dob', dob);
                localStorage.setItem('hub_tob', tob);
                localStorage.setItem('hub_pob', pob);
                
                ['hub-name', 'jh-name', 'exp-name', 'dasha-name', 'transit-name', 'life-name', 'k-name', 'num-name', 'vastu-name', 'gem-name'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el) el.value = name;
                });
                ['hub-dob', 'jh-dob', 'dasha-dob', 'life-dob', 'gem-dob', 'k-dob', 'num-dob', 'p-date'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && dob) el.value = dob;
                });
                ['hub-tob', 'jh-tob', 'k-tob', 'life-tob'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && tob) el.value = tob;
                });
                ['hub-pob', 'jh-pob', 'k-pob', 'p-city', 'vastu-city', 'gem-pob'].forEach(id => {
                    let el = document.getElementById(id);
                    if(el && pob) el.value = pob;
                });

                document.getElementById('hub-result').innerHTML = `<p style="color:#4ade80;">✅ Success! Birth details saved & synced across all modules.</p>`;
            });
        }

        async function submitJhEngine() {
            let name = document.getElementById('jh-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('jh-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            let tob = document.getElementById('jh-tob').value || localStorage.getItem('hub_tob') || '12:00';
            let pob = document.getElementById('jh-pob').value || localStorage.getItem('hub_pob') || 'Kolkata';
            showMagicLoader(async () => {
                try {
                    let res = await fetch('/api/jagannath-hora', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, tob, pob, is_admin: isAdminUnlocked}) });
                    let data = await res.json();
                    let outputHtml = (data.teaser || '') + (data.full_report || '') + (data.pdf_download_btn || '') + (data.paywall || '');
                    document.getElementById('jh-result').innerHTML = outputHtml;
                } catch(err) {
                    console.log("JH Error:", err);
                    document.getElementById('jh-result').innerHTML = "<p style='color:#ef4444;'>❌ Processing error. Please try again.</p>";
                }
            });
        }

        async function exploreKundali() {
            let name = document.getElementById('exp-name').value || localStorage.getItem('hub_name') || 'User';
            let chart = document.getElementById('exp-chart-type').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/explorer', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, chart}) });
                let data = await res.json();
                document.getElementById('explorer-result').innerHTML = data.html;
            });
        }

        async function loadDashaTimeline() {
            let name = document.getElementById('dasha-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('dasha-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            showMagicLoader(async () => {
                let res = await fetch('/api/dasha', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob}) });
                let data = await res.json();
                document.getElementById('dasha-result').innerHTML = data.html;
            });
        }

        async function loadTransitTracker() {
            let name = document.getElementById('transit-name').value || localStorage.getItem('hub_name') || 'User';
            let planet = document.getElementById('transit-planet').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/transit', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, planet}) });
                let data = await res.json();
                document.getElementById('transit-result').innerHTML = data.html;
            });
        }

        async function submitLifePrediction() {
            let name = document.getElementById('life-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('life-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            showMagicLoader(async () => {
                try {
                    let res = await fetch('/api/life', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, is_admin: isAdminUnlocked}) });
                    let data = await res.json();
                    let outputHtml = (data.teaser || '') + (data.full_report || '') + (data.pdf_download_btn || '') + (data.paywall || '');
                    document.getElementById('life-result').innerHTML = outputHtml;
                } catch(err) {
                    console.log("Life Error:", err);
                    document.getElementById('life-result').innerHTML = "<p style='color:#ef4444;'>❌ Processing error. Please try again.</p>";
                }
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
            let boy_name = document.getElementById('b-name').value || 'Boy';
            let girl_name = document.getElementById('g-name').value || 'Girl';
            showMagicLoader(async () => {
                let res = await fetch('/api/matching', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({boy_name, girl_name, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('matching-result').innerHTML = data.teaser + (data.full_report || '') + (data.pdf_download_btn || '') + (data.paywall || '');
            });
        }

        async function submitGemstone() {
            let name = document.getElementById('gem-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('gem-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            let zodiac = document.getElementById('gem-zodiac').value || 'Aries (Mesha)';
            let pob = document.getElementById('gem-pob').value || localStorage.getItem('hub_pob') || 'Kolkata';
            showMagicLoader(async () => {
                try {
                    let res = await fetch('/api/gemstone', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, zodiac, pob, is_admin: isAdminUnlocked}) });
                    let data = await res.json();
                    let outputHtml = (data.teaser || '') + (data.full_report || '') + (data.pdf_download_btn || '') + (data.paywall || '');
                    document.getElementById('gem-result').innerHTML = outputHtml;
                } catch(err) {
                    console.log("Gemstone Error:", err);
                    document.getElementById('gem-result').innerHTML = "<p style='color:#ef4444;'>❌ Processing error. Please try again.</p>";
                }
            });
        }

        async function submitVastuAnalysis() {
            let name = document.getElementById('vastu-name').value || localStorage.getItem('hub_name') || 'User';
            let p_type = document.getElementById('vastu-property-type').value;
            let facing = document.getElementById('vastu-facing').value;
            let city = document.getElementById('vastu-city').value || 'Kolkata';
            showMagicLoader(async () => {
                let res = await fetch('/api/vastu', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, property_type: p_type, facing, city, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('vastu-result').innerHTML = data.teaser + (data.full_report || '') + (data.pdf_download_btn || '') + (data.paywall || '');
            });
        }

        async function submitKundaliPdf() {
            let name = document.getElementById('k-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('k-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            let tob = document.getElementById('k-tob').value || localStorage.getItem('hub_tob') || '12:00';
            let pob = document.getElementById('k-pob').value || localStorage.getItem('hub_pob') || 'Kolkata';
            showMagicLoader(async () => {
                let res = await fetch('/api/kundali-pdf', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, tob, pob, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('kundali-result').innerHTML = data.teaser + data.chart + (data.pdf_download_btn || '') + (data.paywall || '');
            });
        }

        async function submitNumerology() {
            let name = document.getElementById('num-name').value || localStorage.getItem('hub_name') || 'User';
            let dob = document.getElementById('num-dob').value || localStorage.getItem('hub_dob') || '2000-01-01';
            showMagicLoader(async () => {
                let res = await fetch('/api/numerology', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, dob, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('num-result').innerHTML = data.teaser + (data.full_report || '') + (data.paywall || '');
            });
        }

        async function submitPanchang() {
            let city = document.getElementById('p-city').value || 'Kolkata';
            let date = document.getElementById('p-date').value || 'Today';
            let mode = document.getElementById('p-mode').value;
            showMagicLoader(async () => {
                let res = await fetch('/api/panchang', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({city, date, mode, is_admin: isAdminUnlocked}) });
                let data = await res.json();
                document.getElementById('panchang-result').innerHTML = data.html + (data.paywall || '');
            });
        }

        async function askAi() {
            let query = document.getElementById('ai-query').value;
            let hName = localStorage.getItem('hub_name') || 'User';
            showMagicLoader(async () => {
                let res = await fetch('/api/ai', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query, name: hName}) });
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
    logo_html = f'<img src="{logo_src}" alt="AccAstroForge Logo">' if logo_src else '<span style="font-size: 26px; font-weight: 800; color: #fbcfe8; font-family: sans-serif;">AccAstroForge</span>'
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
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "")
    
    if check_user_exists_triple(email):
        return JSONResponse({"otp": "", "msg": "<p style='color:#ef4444;'>❌ This account has already been registered, please sign in!</p>", "already_registered": True})
        
    otp_code = str(random.randint(100000, 999999))
    send_brevo_email(email, name, "OTP Verification", f"<h2>Welcome {name}! Your OTP is {otp_code}</h2>")
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Registration OTP", "details": f"Email: {email}", "payment_status": "OTP Dispatched"})
    return JSONResponse({"otp": otp_code, "msg": "<p style='color:#4ade80;'>📧 OTP Sent to your email!</p>", "already_registered": False})

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
    return JSONResponse({"success": False, "msg": "<p style='color:#4ade80;'>❌ Account not found. Please register first.</p>"})

@app.post("/api/topup")
async def api_topup(request: Request):
    data = await request.json()
    amt = data.get("amount", 99)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "Valued Customer", "service": "Wallet Topup", "details": f"Amount: ₹{amt}", "payment_status": "Pending"})
    paywall = get_paywall_html(f"Wallet Topup (₹{amt})", amt, "User")
    return JSONResponse({"paywall": paywall})

@app.post("/api/jagannath-hora")
async def api_jagannath_hora(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    dob = data.get("dob", "2000-01-01")
    tob = data.get("tob", "12:00")
    pob = data.get("pob", "Kolkata")
    is_admin = data.get("is_admin", False)

    jh_data = calculate_jagannath_hora_engine(name, dob, tob, pob)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Jagannath Hora Vedic Calculations", "details": f"DOB: {dob}, POB: {pob}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹59)"})

    filename = f"Jagannath_Hora_{name.replace(' ', '_')}.pdf"
    shodash_list_pdf = [f"{k}: {v}" for k, v in jh_data["shodashvarga"].items()]
    dasha_list_pdf = [f"{k}: {v}" for k, v in jh_data["dashas"].items()]
    
    generate_pdf_report(
        filename,
        f"Jagannath Hora Vedic Analysis - {name}",
        [
            f"Date of Birth: {dob} | Time: {tob} | Place: {pob}",
            f"Ascendant (Lagna): {jh_data['profile']['zodiac']} | Nakshatra: {jh_data['profile']['nakshatra']}",
            "--- 16 Shodashvarga Divisional Charts ---"
        ] + shodash_list_pdf + [
            "--- Advanced Dasha Cycles ---"
        ] + dasha_list_pdf + [
            f"Sarvashtakavarga Strength: {jh_data['ashtakavarga']['Sarvashtakavarga Total']} Points",
            f"Transit Impact: {jh_data['transit_overlay']}"
        ]
    )

    pdf_btn_html = f"""<div style='margin-top:15px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:12px 24px; border-radius:10px; font-weight:bold; text-decoration:none; display:inline-block; box-shadow: 0 4px 15px rgba(16,185,129,0.4);'>📥 Download Jagannath Hora PDF Report</a></div>"""

    shodash_list = "".join([f"<li><b>{k}:</b> {v}</li>" for k, v in jh_data["shodashvarga"].items()])
    dasha_list = "".join([f"<li><b>{k}:</b> {v}</li>" for k, v in jh_data["dashas"].items()])

    teaser = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <h4 style='color:#fde047; margin-top:0;'>☸️ Jagannath Hora Vedic Calculations Output for {name.upper()}</h4>
        <p><b>Ascendant (Lagna):</b> {jh_data['profile']['zodiac']} | <b>Nakshatra:</b> {jh_data['profile']['nakshatra']}</p>
    </div>
    """

    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:22px; border-radius:16px; border:2px solid #4ade80; margin-top:15px; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h4 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>☸️ COMPLETE 16 SHODASHVARGA & ADVANCED DASHAS REPORT FOR {name.upper()}</h4>
        <div style='display:grid; grid-template-columns: 1fr 1fr; gap:15px; margin-top:12px;'>
            <div>
                <h5 style='color:#fde047; margin-bottom:6px;'>All 16 Shodashvarga Divisional Charts:</h5>
                <ul style='font-size:0.85rem; padding-left:18px; margin:0; line-height:1.6;'>{shodash_list}</ul>
            </div>
            <div>
                <h5 style='color:#fde047; margin-bottom:6px;'>Advanced Dasha Cycles & Ashtakavarga:</h5>
                <ul style='font-size:0.85rem; padding-left:18px; margin:0; line-height:1.6;'>{dasha_list}</ul>
                <p style='margin-top:10px; font-size:0.9rem;'><b>Sarvashtakavarga Strength:</b> {jh_data['ashtakavarga']['Sarvashtakavarga Total']} Points</p>
                <p style='font-size:0.9rem;'><b>Transit Impact:</b> {jh_data['transit_overlay']}</p>
            </div>
        </div>
        <p style='color: #4ade80; margin-top: 15px; font-weight: bold;'>✅ Full Jagannath Hora Report Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""

    paywall = "" if is_admin else get_paywall_html("Full 16 Shodashvarga & Ephemeris Report", 59, name)
    download_btn = pdf_btn_html if is_admin else ""

    return JSONResponse({"teaser": teaser, "full_report": full_report, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/explorer")
async def api_explorer(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip()
    chart = data.get("chart", "D1")
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Interactive Kundali Explorer", "details": f"Chart: {chart}", "payment_status": "Free Interactive"})
    
    name_seed = sum(ord(c) for c in name.lower()) if name else 42
    
    zodiac_pool = [
        "Aries (Mesha)", "Taurus (Vrishabha)", "Gemini (Mithuna)", "Cancer (Karka)",
        "Leo (Simha)", "Virgo (Kanya)", "Libra (Tula)", "Scorpio (Vrischika)",
        "Sagittarius (Dhanu)", "Capricorn (Makara)", "Aquarius (Kumbha)", "Pisces (Meena)"
    ]
    
    lagna_idx = (name_seed + (0 if chart == "D1" else 3 if chart == "D9" else 6 if chart == "D10" else 9)) % 12
    h4_idx = (lagna_idx + 3) % 12
    h7_idx = (lagna_idx + 6) % 12
    h10_idx = (lagna_idx + 9) % 12
    
    chart_descriptions = {
        "D1": f"D1 Lagna Chart for {name} (Main Body, Physical Path & Life Foundation).",
        "D9": f"D9 Navamsha Chart for {name} (Soul Purpose, Inner Strength & Post-Marriage Life Blueprint).",
        "D10": f"D10 Dashamsha Chart for {name} (Career Heights, Professional Authority & Public Status).",
        "D7": f"D7 Saptamsha Chart for {name} (Progeny, Children, Creation & Creative Legacy)."
    }
    
    desc = chart_descriptions.get(chart, f"Divisional Chart Analysis for {name}.")
    houses_str = f"House 1 (Ascendant): {zodiac_pool[lagna_idx]} | House 4: {zodiac_pool[h4_idx]} | House 7: {zodiac_pool[h7_idx]} | House 10: {zodiac_pool[h10_idx]}"
    
    html = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <h4 style='color:#fde047;'>🧭 Interactive {chart} Chart Explorer for {name.upper()}</h4>
        <p style='color: #f3e8ff;'><b>Focus & Blueprint:</b> {desc}</p>
        <p><b>Divisional Grid Houses:</b> {houses_str}.</p>
        <p style='color:#4ade80;'>✅ Unique planetary alignments, divisional lordships, and house strengths calculated dynamically for {name} in {chart}.</p>
    </div>
    """
    return JSONResponse({"html": html})

@app.post("/api/dasha")
async def api_dasha(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip()
    dob = data.get("dob", "2000-01-01").strip()
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Personal Dasha Timeline", "details": f"DOB: {dob}", "payment_status": "Free Timeline"})
    
    seed = sum(ord(c) for c in (name + dob).lower()) if (name or dob) else 108
    planets = ["Jupiter (Guru)", "Saturn (Shani)", "Mercury (Budha)", "Venus (Shukra)", "Sun (Surya)", "Moon (Chandra)", "Mars (Mangal)", "Rahu", "Ketu"]
    
    maha_idx = seed % len(planets)
    antar_idx = (seed + 3) % len(planets)
    next_idx = (seed + 6) % len(planets)
    
    birth_year = 2000
    try:
        birth_year = int(dob.split("-")[0])
    except Exception:
        pass
    
    maha_end_year = birth_year + 20 + (seed % 10)
    transition_year = maha_end_year + 1
    
    html = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <h4 style='color:#fde047;'>⏳ Personal Dasha Timeline for {name.upper()} (DOB: {dob})</h4>
        <ul style='line-height:1.8; margin-top:10px;'>
            <li><b>Current Mahadasha:</b> {planets[maha_idx]} - Active until {maha_end_year}</li>
            <li><b>Current Antardasha:</b> {planets[antar_idx]} - Focus on structural growth, karmic balance and career stability</li>
            <li><b>Upcoming Dasha Transition:</b> {planets[next_idx]} starting from {transition_year} onwards</li>
        </ul>
        <p style='color:#4ade80; margin-top:10px;'>✅ Unique planetary Dasha sequence calculated dynamically for {name}.</p>
    </div>
    """
    return JSONResponse({"html": html})

@app.post("/api/transit")
async def api_transit(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip()
    planet = data.get("planet", "Jupiter").strip()
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Live Planetary Transit Tracker", "details": f"Planet: {planet}", "payment_status": "Free Live Tracker"})
    
    seed = sum(ord(c) for c in (name + planet).lower()) if (name or planet) else 77
    
    zodiac_signs_list = [
        "Aries (Mesha)", "Taurus (Vrishabha)", "Gemini (Mithuna)", "Cancer (Karka)",
        "Leo (Simha)", "Virgo (Kanya)", "Libra (Tula)", "Scorpio (Vrischika)",
        "Sagittarius (Dhanu)", "Capricorn (Makara)", "Aquarius (Kumbha)", "Pisces (Meena)"
    ]
    
    transit_sign = zodiac_signs_list[seed % 12]
    house_num = (seed % 12) + 1
    
    motion_types = ["Direct motion with expansion aspect", "Retrograde corrective phase", "Accelerated direct alignment", "Stationary stability transit"]
    impact_types = [
        "Favorable planetary aspect supporting career growth and financial accumulation.",
        "Karmic realignment demanding patience, discipline, and structural revision.",
        "Sudden breakthroughs in professional standing and technical innovation.",
        "Spiritual introspection, inner purification, and long-term asset security."
    ]
    
    chosen_motion = motion_types[seed % len(motion_types)]
    chosen_impact = impact_types[seed % len(impact_types)]
    
    html = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <h4 style='color:#fde047;'>🪐 Live Planetary Transit for {name.upper()} (Selected Planet: {planet})</h4>
        <p style='color: #f3e8ff; margin-bottom: 12px;'><b>Current Transit Sign:</b> {transit_sign} (House {house_num} from Ascendant)</p>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            <div style='background:rgba(255,255,255,0.05); padding:12px; border-radius:8px;'>
                <b style='color:#fde047;'>{planet} Movement:</b> {chosen_motion} influencing {name}'s chart.
            </div>
            <div style='background:rgba(255,255,255,0.05); padding:12px; border-radius:8px;'>
                <b style='color:#4ade80;'>Karmic Impact:</b> {chosen_impact}
            </div>
        </div>
        <p style='color:#4ade80; margin-top:12px; font-size:0.85rem;'>✅ Unique dynamic transit calculations tailored specifically for {name} under {planet}.</p>
    </div>
    """
    return JSONResponse({"html": html})
    
@app.post("/api/life")
async def api_life(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip() or "User"
    dob = data.get("dob", "2000-01-01").strip() or "2000-01-01"
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Life Prediction PDF", "details": f"DOB: {dob}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹149)"})
    
    profile = calculate_astrological_profile(name, dob)
    rashi = profile['zodiac']
    nakshatra = profile['nakshatra']
    psychic = profile['psychic_num']
    
    # 1. Core Personality Blueprint
    personality_insights = {
        "Aries (Mesha)": f"Under the profound influence of Aries, {name} possesses an innate fiery resilience, independent drive, and a magnetic leadership aura. Your psychic number {psychic} highlights strong pioneering capabilities and fierce determination.",
        "Taurus (Vrishabha)": f"Taurus endows {name} with steady patience, exceptional practical grounding, and an eye for enduring stability. Your psychic number {psychic} signifies deep loyalty, artistic appreciation, and quiet inner strength.",
        "Gemini (Mithuna)": f"Gemini's dual energy grants {name} sparkling wit, exceptional adaptability across technical or creative domains, and sharp communicative prowess. Your psychic number {psychic} amplifies intellectual curiosity.",
        "Cancer (Karka)": f"Cancerian intuitive depth gives {name} profound emotional intelligence, protective instincts, and creative vision. Your psychic number {psychic} drives your empathetic connections and inner resilience.",
        "Leo (Simha)": f"Leo's solar radiance instills {name} with majestic confidence, generous warmth, and natural authority. Your psychic number {psychic} highlights a magnetic presence that naturally draws people toward your vision.",
        "Virgo (Kanya)": f"Virgo's analytical precision equips {name} with methodical problem-solving skills, meticulous attention to detail, and a service-oriented mindset. Your psychic number {psychic} signifies continuous self-improvement.",
        "Libra (Tula)": f"Libra brings a natural grace, diplomatic balance, and an innate appreciation for harmony and aesthetics to {name}. Your psychic number {psychic} reflects strong partnership ethics and fairness.",
        "Scorpio (Vrischika)": f"Scorpio endows {name} with intense focus, transformative emotional depth, and unwavering investigative grit. Your psychic number {psychic} underscores a powerful secretive mystique and sharp intuition.",
        "Sagittarius (Dhanu)": f"Sagittarius fuels {name} with an adventurous philosophical spirit, boundless optimism, and a relentless quest for higher wisdom. Your psychic number {psychic} points toward expansive horizons.",
        "Capricorn (Makara)": f"Capricorn grants {name} disciplined ambition, structural mastery, and unyielding perseverance under pressure. Your psychic number {psychic} highlights long-term strategic vision and reliability.",
        "Aquarius (Kumbha)": f"Aquarius inspires {name} with progressive humanitarian ideals, inventive technical concepts, and independent originality. Your psychic number {psychic} marks you as a future-focused visionary.",
        "Pisces (Meena)": f"Pisces endows {name} with boundless imagination, spiritual sensitivity, and deep artistic empathy. Your psychic number {psychic} reflects mystical depth and compassionate understanding."
    }
    
    # 2. Career Evolution & Wealth
    career_insights = {
        "Aries (Mesha)": f"Stellar positions for {name} point toward extraordinary breakthroughs in software entrepreneurship, engineering consultancy, and executive leadership roles. Financial inflow surges through independent technical ventures.",
        "Taurus (Vrishabha)": f"Financial accumulation for {name} is heavily favored through long-term asset creation, real estate investments, secure banking portfolios, and high-value corporate consulting.",
        "Gemini (Mithuna)": f"Career growth for {name} accelerates through digital media campaigns, multi-lingual software platforms, publishing, and specialized technical communication roles.",
        "Cancer (Karka)": f"Professional success for {name} shines in user-centric design, administrative leadership, hospitality management, and intuitive backend application structuring.",
        "Leo (Simha)": f"Executive authority, brand building, large-scale media projects, and enterprise leadership bring remarkable financial rewards and public renown to {name}.",
        "Virgo (Kanya)": f"Specialized technical mastery, financial auditing, database architecture, and precision-driven project management bring steady wealth creation and career elevation to {name}.",
        "Libra (Tula)": f"Legal consultancy, creative design partnerships, public relations, and high-end client negotiations unlock lucrative financial streams and professional fame for {name}.",
        "Scorpio (Vrischika)": f"Deep technical research, financial analysis, crisis management, and specialized backend security systems position {name} for massive wealth breakthroughs.",
        "Sagittarius (Dhanu)": f"Global ventures, higher education consultancy, publishing, and expansive digital marketing initiatives bring international financial inflow and leadership status to {name}.",
        "Capricorn (Makara)": f"Corporate administration, cloud system deployment, large-scale infrastructural investments, and high-level management bring solid wealth security and authority to {name}.",
        "Aquarius (Kumbha)": f"Cutting-edge AI application design, scientific research, software development, and revolutionary tech startups favor extraordinary financial milestones for {name}.",
        "Pisces (Meena)": f"Creative arts, spiritual guidance, healing modalities, and immersive digital media storytelling bring both financial prosperity and profound inner fulfillment to {name}."
    }

    # 3. Relationships & Family Harmony
    relationship_insights = {
        "Aries (Mesha)": f"For {name}, 7th house alignments demand mutual respect and shared adventures. Direct, honest communication clears minor friction, bringing passionate domestic stability.",
        "Taurus (Vrishabha)": f"Deep emotional loyalty and sensual comfort characterize {name}'s partnerships. Unwavering support from your life partner creates a serene, peaceful family sanctuary.",
        "Gemini (Mithuna)": f"Intellectual rapport and lively conversations keep {name}'s relationships vibrant. Mutual curiosity and shared social circles strengthen marital bonds.",
        "Cancer (Karka)": f"Profound emotional nurturing and home-centric dedication anchor {name}'s family life. Deep empathy from your spouse brings ultimate domestic peace.",
        "Leo (Simha)": f"Warmth, grand gestures, and protective loyalty define {name}'s partnerships. Mutual admiration and shared celebration deepen your marital harmony.",
        "Virgo (Kanya)": f"Practical acts of service, shared organizational goals, and quiet mutual devotion fortify {name}'s domestic life, bringing structured peace.",
        "Libra (Tula)": f"Romance, elegance, and deep compromise form the bedrock of {name}'s relationships. Your partner acts as an equal sounding board, ensuring total harmony.",
        "Scorpio (Vrischika)": f"Intense emotional bonding and absolute faithfulness characterize {name}'s partnerships. Deep trust unlocks unbreakable domestic unity.",
        "Sagittarius (Dhanu)": f"Freedom coupled with shared philosophical pursuits brings joy to {name}'s home life. Partner travels and optimistic discussions strengthen family ties.",
        "Capricorn (Makara)": f"Reliability, shared responsibility, and long-term security anchor {name}'s marriage. Mutual respect for each other's career builds a steadfast home.",
        "Aquarius (Kumbha)": f"Friendship-based partnership, mutual independence, and intellectual freedom ensure a modern, harmonious domestic environment for {name}.",
        "Pisces (Meena)": f"Unconditional emotional compassion, spiritual connection, and gentle romantic devotion create a deeply healing family atmosphere for {name}."
    }

    # 4. Health & Vitality
    health_insights = {
        "Aries (Mesha)": f"High physical energy requires structured athletic outlets and cardio routines to channel {name}'s vitality. Regular grounding meditation prevents burnout.",
        "Taurus (Vrishabha)": f"Focus on clean nutrition and consistent metabolic exercise routines to sustain {name}'s steady vitality. Neck and throat alignment practices are beneficial.",
        "Gemini (Mithuna)": f"Nervous system relaxation and mindful breathing exercises are essential for {name} to maintain optimal mental clarity and physical stamina.",
        "Cancer (Karka)": f"Digestive wellness and emotional tranquility through hydro-therapy or gentle evening walks sustain robust health and high immunity for {name}.",
        "Leo (Simha)": f"Cardiovascular health and outdoor sun exposure invigorate {name}'s core vitality. Maintaining work-life balance prevents cardiac overexertion.",
        "Virgo (Kanya)": f"Gut health, disciplined dietary regimens, and restorative yoga keep {name}'s physical machinery running at peak performance.",
        "Libra (Tula)": f"Kidney health, proper hydration, and lumbar stretching exercises maintain elegant posture and boundless energy levels for {name}.",
        "Scorpio (Vrischika)": f"Emotional purging, detoxification practices, and high-intensity stamina training keep {name}'s transformative energy balanced and strong.",
        "Sagittarius (Dhanu)": f"Outdoor trekking, sports activities, and hip flexibility exercises preserve {name}'s natural athletic agility and high spirits.",
        "Capricorn (Makara)": f"Joint care, bone density maintenance, and structured stretching routines safeguard {name}'s physical endurance against long work hours.",
        "Aquarius (Kumbha)": f"Circulatory health, leg stretching, and tech-free digital detox hours revitalize {name}'s nervous system and overall wellness.",
        "Pisces (Meena)": f"Foot reflexology, adequate sleep cycles, and immersive water proximity restore {name}'s sensitive energetic aura and physical vitality."
    }

    p_text = personality_insights.get(rashi, f"Under the influence of {rashi}, {name} possesses strong leadership and resilience.")
    c_text = career_insights.get(rashi, f"Stellar positioning for {name} points toward remarkable career breakthroughs.")
    r_text = relationship_insights.get(rashi, f"7th house alignments denote loyalty and emotional intelligence in partnerships for {name}.")
    h_text = health_insights.get(rashi, f"Maintaining a balanced lifestyle and regular physical alignment sustains high energy levels for {name}.")

    filename = f"Life_Forecast_{name.replace(' ', '_')}.pdf"
    generate_pdf_report(
        filename,
        f"Vedic Astrology & Deep Life Forecast - {name}",
        [
            f"Date of Birth: {dob} | Rashi: {rashi} | Nakshatra: {nakshatra}",
            f"Active Dasha: {profile['dasha']} | Psychic Number: {psychic}",
            f"1. Core Personality & Karmic Blueprint: {p_text}",
            f"2. Career Evolution, Wealth & Financial Accumulation: {c_text}",
            f"3. Relationships, Marriage & Family Harmony: {r_text}",
            f"4. Health, Vitality & Recommended Remedies: {h_text} To neutralize minor planetary friction, wearing a certified natural gemstone aligned with your ascendant is recommended."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:15px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:12px 24px; border-radius:10px; font-weight:bold; text-decoration:none; display:inline-block; box-shadow: 0 4px 15px rgba(16,185,129,0.4);'>📥 Download Deep Life Forecast PDF Report</a></div>"""
    
    teaser = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed; margin-bottom: 12px;'>
        <h4 style='color:#fde047; margin-top:0;'>✨ Astrological Teaser for {name.upper()}</h4>
        <p style='font-size:1.05rem; color:#f3e8ff;'><b>Rashi:</b> {rashi} | <b>Nakshatra:</b> {nakshatra} | <b>Dasha:</b> {profile['dasha']}</p>
    </div>
    """
    
    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:24px; border-radius:16px; border:2px solid #4ade80; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h3 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>🌟 VEDIC ASTROLOGY & DEEP LIFE FORECAST PDF REPORT FOR {name.upper()}</h3>
        <p style='color: #fde047; font-weight: 600;'>Birth Profile Verified | Lagna Ascendant & Planetary Coordinates Active</p>
        
        <div style='margin-top: 15px; line-height: 1.8; color: #f3e8ff;'>
            <h4 style='color: #fde047;'>1. Core Personality & Karmic Blueprint ({rashi})</h4>
            <p>{p_text}</p>
            
            <h4 style='color: #fde047; margin-top: 15px;'>2. Career Evolution, Wealth & Financial Accumulation</h4>
            <p>{c_text}</p>
            
            <h4 style='color: #fde047; margin-top: 15px;'>3. Relationships, Marriage & Family Harmony</h4>
            <p>{r_text}</p>
            
            <h4 style='color: #fde047; margin-top: 15px;'>4. Health, Vitality & Recommended Remedies</h4>
            <p>{h_text} To neutralize minor planetary friction and amplify positive cosmic frequencies, wearing a certified natural gemstone aligned with your ascendant and engaging in meditative grounding practices is strongly recommended.</p>
        </div>
        <p style='color: #4ade80; margin-top: 15px; font-weight: bold;'>✅ Full 149/- Report Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""
    
    paywall = "" if is_admin else get_paywall_html("Complete Deep Life Forecast & PDF", 149, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "full_report": full_report, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/horoscope")
async def api_horoscope(request: Request):
    data = await request.json()
    raw_sign = data.get("sign", "Aries (Mesha)").strip()
    sign_name = raw_sign.split(" (")[0] if "(" in raw_sign else raw_sign
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "Guest/Member", "service": "Daily Horoscope", "details": f"Sign: {raw_sign}", "payment_status": "Free"})
    
    today_str = datetime.datetime.now().strftime("%B %d, %Y")
    seed_val = sum(ord(c) for c in (raw_sign + today_str))
    
    lucky_numbers = [3, 7, 9, 11, 14, 21, 27, 33, 45, 88]
    lucky_colors = ["Golden Yellow", "Deep Crimson", "Cosmic Violet", "Royal Blue", "Emerald Green", "Warm Orange", "Mystic Purple"]
    lucky_times = ["09:30 AM - 11:00 AM", "02:15 PM - 04:00 PM", "05:30 PM - 07:00 PM", "08:00 AM - 10:00 AM"]
    lucky_gems = ["Yellow Sapphire", "Red Coral", "Blue Sapphire", "Emerald", "Ruby", "Pearl", "Diamond"]
    
    l_num = lucky_numbers[seed_val % len(lucky_numbers)]
    l_col = lucky_colors[(seed_val + 2) % len(lucky_colors)]
    l_time = lucky_times[(seed_val + 4) % len(lucky_times)]
    l_gem = lucky_gems[seed_val % len(lucky_gems)]
    
    career_predictions = [
        "Jupiter's favorable trine brings unexpected momentum in ongoing projects and corporate discussions. Leadership qualities will shine brightly.",
        "Saturn demands structured planning and attention to detail. Avoid hasty decisions in contractual agreements today.",
        "Mercury elevates your analytical communication skills. Perfect day for client pitches, contract signings, or technical execution.",
        "Venus aligns with your career sector, opening doors to creative collaboration and positive recognition from senior management."
    ]
    
    love_predictions = [
        "Warm emotional harmony prevails. Open-hearted discussions with your partner will deepen mutual trust and understanding.",
        "Singles may feel a strong, spontaneous connection through mutual friends or workplace networking.",
        "Patience is key today. Give space to your loved ones and avoid bringing work-related stress into domestic life.",
        "A delightfully surprising romantic gesture or meaningful conversation will brighten your evening."
    ]
    
    health_predictions = [
        "High vitality levels today! Perfect time for outdoor physical exercises, yoga, and mindful meditation.",
        "Watch your digestion and hydration levels. Focus on clean nutrition and light evening walks.",
        "Mental relaxation is essential today. Take short micro-breaks during work hours to prevent fatigue.",
        "Cosmic planetary alignments boost your immune resilience. Maintain a balanced sleep cycle tonight."
    ]
    
    advice_tips = [
        "Offer water to the rising Sun (Surya Arghya) and stay centered in gratitude.",
        "Chant the Gayatri Mantra or Gayatri Meditation to clear mental clutter.",
        "Keep a piece of yellow cloth or brass coin in your wallet for financial positivity.",
        "Avoid unnecessary arguments in the afternoon; channel energy into productive execution."
    ]
    
    c_pred = career_predictions[seed_val % len(career_predictions)]
    l_pred = love_predictions[(seed_val + 1) % len(love_predictions)]
    h_pred = health_predictions[(seed_val + 2) % len(health_predictions)]
    tip = advice_tips[seed_val % len(advice_tips)]
    
    html = f"""
    <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #7c3aed; padding: 22px; border-radius: 16px; box-shadow: 0 0 25px rgba(124, 58, 237, 0.4); backdrop-filter: blur(8px); margin-top: 15px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid rgba(244, 114, 182, 0.4); padding-bottom: 12px; margin-bottom: 18px; flex-wrap: wrap; gap: 10px;'>
            <h3 style='color: #fde047 !important; margin: 0; font-family: "Cinzel", serif; font-size: 1.3rem;'>🔮 Daily Zodiac Horoscope: {raw_sign}</h3>
            <span style='background: rgba(124, 58, 237, 0.3); border: 1px solid #fde047; color: #fde047; padding: 4px 12px; border-radius: 8px; font-size: 0.85rem; font-weight: 600;'>📅 {today_str}</span>
        </div>
        
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px;'>
            <div style='background: rgba(124, 58, 237, 0.2); border: 1px solid rgba(244, 114, 182, 0.3); padding: 12px; border-radius: 10px; text-align: center;'>
                <span style='font-size: 0.78rem; color: #f3e8ff; display: block;'>🎲 Lucky Number</span>
                <b style='font-size: 1.2rem; color: #fde047;'>{l_num}</b>
            </div>
            <div style='background: rgba(124, 58, 237, 0.2); border: 1px solid rgba(244, 114, 182, 0.3); padding: 12px; border-radius: 10px; text-align: center;'>
                <span style='font-size: 0.78rem; color: #f3e8ff; display: block;'>🎨 Lucky Color</span>
                <b style='font-size: 1.1rem; color: #4ade80;'>{l_col}</b>
            </div>
            <div style='background: rgba(124, 58, 237, 0.2); border: 1px solid rgba(244, 114, 182, 0.3); padding: 12px; border-radius: 10px; text-align: center;'>
                <span style='font-size: 0.78rem; color: #f3e8ff; display: block;'>⏰ Shubh Muhurat / Lucky Hours</span>
                <b style='font-size: 0.95rem; color: #fde047;'>{l_time}</b>
            </div>
            <div style='background: rgba(124, 58, 237, 0.2); border: 1px solid rgba(244, 114, 182, 0.3); padding: 12px; border-radius: 10px; text-align: center;'>
                <span style='font-size: 0.78rem; color: #f3e8ff; display: block;'>💎 Favorable Gemstone</span>
                <b style='font-size: 1rem; color: #38bdf8;'>{l_gem}</b>
            </div>
        </div>
        
        <div style='line-height: 1.8; color: #f3e8ff;'>
            <div style='margin-bottom: 14px;'>
                <h4 style='color: #fde047 !important; margin: 0 0 4px 0; font-size: 1.05rem;'>💼 Career & Finances</h4>
                <p style='margin: 0; font-size: 0.95rem;'>{c_pred}</p>
            </div>
            
            <div style='margin-bottom: 14px;'>
                <h4 style='color: #fde047 !important; margin: 0 0 4px 0; font-size: 1.05rem;'>❤️ Love & Relationships</h4>
                <p style='margin: 0; font-size: 0.95rem;'>{l_pred}</p>
            </div>
            
            <div style='margin-bottom: 14px;'>
                <h4 style='color: #fde047 !important; margin: 0 0 4px 0; font-size: 1.05rem;'>🧘 Health & Wellness</h4>
                <p style='margin: 0; font-size: 0.95rem;'>{h_pred}</p>
            </div>
            
            <div style='background: rgba(74, 222, 128, 0.15); border-left: 4px solid #4ade80; padding: 10px 14px; border-radius: 6px; margin-top: 15px;'>
                <b style='color: #4ade80;'>✨ Daily Astrological Tip:</b> <span style='font-size: 0.92rem;'>{tip}</span>
            </div>
        </div>
    </div>
    """
    return JSONResponse({"html": html})

@app.post("/api/matching")
async def api_matching(request: Request):
    data = await request.json()
    b = data.get("boy_name", "Boy").strip() or "Boy"
    g = data.get("girl_name", "Girl").strip() or "Girl"
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b} & {g}", "service": "Vedic Kundali Matching PDF", "details": "Guna Milan Ashtakoota Analysis", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹59)"})
    
    seed = sum(ord(c) for c in (b + g).lower())
    guna_score = 18 + (seed % 15)
    match_pct = int((guna_score / 36.0) * 100)
    
    varna = 1 if seed % 2 == 0 else 0.5
    vashya = 2 if (seed + 1) % 3 != 0 else 1.5
    tara = 3 if seed % 4 != 0 else 1.5
    yoni = (seed % 4) + 1
    graha_maitri = 4 if seed % 2 == 0 else 3.0
    gana = 6 if seed % 3 != 0 else 4.0
    bhakoot = 7 if seed % 5 != 0 else 0.0
    nadi = 8 if seed % 7 != 0 else 0.0
    
    filename = f"Kundali_Matching_{b.replace(' ', '_')}_and_{g.replace(' ', '_')}.pdf"
    generate_pdf_report(
        filename,
        f"Vedic Horoscope Match & Guna Milan Report - {b} & {g}",
        [
            f"Groom (Boy): {b} | Bride (Girl): {g}",
            f"Total Guna Milan Score: {guna_score} / 36 ({match_pct}% Compatibility)",
            f"1. Varna (Work/Ego Alignment): {varna} / 1",
            f"2. Vashya (Mutual Attraction): {vashya} / 2",
            f"3. Tara (Health & Longevity): {tara} / 3",
            f"4. Yoni (Physical Compatibility): {yoni} / 4",
            f"5. Graha Maitri (Psychological Blend): {graha_maitri} / 5",
            f"6. Gana (Temperament Compatibility): {gana} / 6",
            f"7. Bhakoot (Emotional & Financial Growth): {bhakoot} / 7",
            f"8. Nadi (Genetic & Progeny Health): {nadi} / 8",
            "Astrological Verdict: Strong compatibility with high longevity and emotional harmony."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:15px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:12px 24px; border-radius:10px; font-weight:bold; text-decoration:none; display:inline-block; box-shadow: 0 4px 15px rgba(16,185,129,0.4);'>📥 Download Matching PDF Report</a></div>"""
    
    teaser = f"""
    <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #7c3aed; padding: 20px; border-radius: 14px; box-shadow: 0 0 20px rgba(124, 58, 237, 0.3); margin-top: 15px;'>
        <h4 style='color:#fde047; margin-top:0;'>❤️ Vedic Compatibility & Guna Milan PDF Preview for {b.upper()} & {g.upper()}</h4>
        <div style='display: flex; align-items: center; gap: 20px; margin-top: 10px;'>
            <div style='background: rgba(124, 58, 237, 0.3); border: 1.5px solid #4ade80; padding: 15px 25px; border-radius: 12px; text-align: center;'>
                <span style='color: #f3e8ff; font-size: 0.85rem; display: block;'>Total Guna Score</span>
                <b style='color: #4ade80; font-size: 1.8rem;'>{guna_score} <span style='font-size: 1rem; color: #fde047;'>/ 36</span></b>
            </div>
            <div>
                <p style='color: #f3e8ff; margin: 0;'><b>Compatibility Index:</b> <span style='color: #4ade80; font-weight: 700;'>{match_pct}% (Auspicious Alignment)</span></p>
                <p style='color: #f3e8ff; margin: 4px 0 0 0; font-size: 0.9rem;'><b>Nadi Status:</b> {'No Nadi Dosha Detected' if nadi > 0 else 'Mild Nadi Alignment'}</p>
            </div>
        </div>
    </div>
    """
    
    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:22px; border-radius:16px; border:2px solid #4ade80; margin-top:15px; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h4 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>💍 VEDIC COMPATIBILITY & GUNA MILAN PDF REPORT ({b.upper()} & {g.upper()})</h4>
        <table style='width:100%; border-collapse:collapse; margin-top:12px; font-size:0.9rem;' border='1'>
            <tr style='background:#5b21b6; color:#fde047;'><th>Koota Parameter</th><th>Obtained Points</th><th>Max Points</th><th>Vedic Influence</th></tr>
            <tr><td>Varna (Work & Ego)</td><td>{varna}</td><td>1</td><td>Mental & Career Alignment</td></tr>
            <tr><td>Vashya (Attraction)</td><td>{vashya}</td><td>2</td><td>Mutual Magnetism</td></tr>
            <tr><td>Tara (Longevity)</td><td>{tara}</td><td>3</td><td>Health & Prosperity</td></tr>
            <tr><td>Yoni (Physical Compatibility)</td><td>{yoni}</td><td>4</td><td>Intimacy & Vitality</td></tr>
            <tr><td>Graha Maitri (Psychological)</td><td>{graha_maitri}</td><td>5</td><td>Intellectual Friendship</td></tr>
            <tr><td>Gana (Temperament)</td><td>{gana}</td><td>6</td><td>Behavioral Synchronization</td></tr>
            <tr><td>Bhakoot (Financial Growth)</td><td>{bhakoot}</td><td>7</td><td>Wealth & Family Welfare</td></tr>
            <tr><td>Nadi (Genetics & Progeny)</td><td>{nadi}</td><td>8</td><td>Lineage & Biological Balance</td></tr>
        </table>
        <p style='color: #4ade80; font-weight: bold; margin-top: 15px;'>✅ Complete Kundali Matching Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""
    
    paywall = "" if is_admin else get_paywall_html("Complete Kundali Matching & Guna Report", 59, f"{b} & {g}")
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "full_report": full_report, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/gemstone")
async def api_gemstone(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip() or "User"
    dob = data.get("dob", "2000-01-01").strip() or "2000-01-01"
    raw_zodiac = data.get("zodiac", "Aries (Mesha)").strip() or "Aries (Mesha)"
    pob = data.get("pob", "Kolkata").strip() or "Kolkata"
    is_admin = data.get("is_admin", False)
    
    GEM_DB_TABLE = "user_gemstones_v2"
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {GEM_DB_TABLE} (
                email_key TEXT PRIMARY KEY,
                name TEXT,
                dob TEXT,
                zodiac TEXT,
                primary_gem TEXT,
                fortune_gem TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Table Creation Error: {e}")

    email_key = f"{name.lower().replace(' ', '_')}_{dob}_{raw_zodiac.lower().replace(' ', '_')}"
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Lucky Gemstone Guidance", "details": f"DOB: {dob}, Zodiac: {raw_zodiac}, POB: {pob}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹59)"})
    
    primary_gems = [
        ("Red Coral (Moonga)", "Mars (Mangal)", "Tuesday (Morning)", "Copper / Gold", "Ring Finger"),
        ("Diamond (Heera) / White Sapphire", "Venus (Shukra)", "Friday (Morning)", "Silver / White Gold", "Middle / Small Finger"),
        ("Emerald (Panna)", "Mercury (Budha)", "Wednesday (Morning)", "Bronze / Gold", "Little Finger"),
        ("Natural Pearl (Moti)", "Moon (Chandra)", "Monday (Evening)", "Pure Silver", "Little Finger"),
        ("Ruby (Manik)", "Sun (Surya)", "Sunday (Morning)", "Gold / Copper", "Ring Finger"),
        ("Yellow Sapphire (Pukhraj)", "Jupiter (Guru)", "Thursday (Morning)", "Yellow Gold", "Index Finger"),
        ("Blue Sapphire (Neelam)", "Saturn (Shani)", "Saturday (Evening)", "Steel / Silver", "Middle Finger")
    ]
    
    fortune_gems = [
        ("Red Coral (Moonga)", "Mars (Mangal)"),
        ("Diamond (Heera)", "Venus (Shukra)"),
        ("Emerald (Panna)", "Mercury (Budha)"),
        ("Natural Pearl (Moti)", "Moon (Chandra)"),
        ("Ruby (Manik)", "Sun (Surya)"),
        ("Yellow Sapphire (Pukhraj)", "Jupiter (Guru)"),
        ("Blue Sapphire (Neelam)", "Saturn (Shani)")
    ]
    
    # Complete 12 Zodiac Mapping restored here
    zodiac_mapping = {
        "Aries (Mesha)": (5, 0),        # Primary: Yellow Sapphire, Fortune: Red Coral
        "Taurus (Vrishabha)": (1, 2),    # Primary: Diamond, Fortune: Emerald
        "Gemini (Mithuna)": (2, 5),      # Primary: Emerald, Fortune: Yellow Sapphire
        "Cancer (Karka)": (3, 5),        # Primary: Natural Pearl, Fortune: Yellow Sapphire
        "Leo (Simha)": (4, 0),           # Primary: Ruby, Fortune: Red Coral
        "Virgo (Kanya)": (2, 1),         # Primary: Emerald, Fortune: Diamond
        "Libra (Tula)": (1, 2),          # Primary: Diamond, Fortune: Emerald
        "Scorpio (Vrischika)": (0, 6),   # Primary: Red Coral, Fortune: Blue Sapphire
        "Sagittarius (Dhanu)": (5, 4),   # Primary: Yellow Sapphire, Fortune: Ruby
        "Capricorn (Makara)": (6, 5),    # Primary: Blue Sapphire, Fortune: Yellow Sapphire
        "Aquarius (Kumbha)": (6, 1),     # Primary: Blue Sapphire, Fortune: Diamond
        "Pisces (Meena)": (5, 2)         # Primary: Yellow Sapphire, Fortune: Emerald
    }
    
    p_gem = None
    f_gem = None
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"SELECT primary_gem, fortune_gem FROM {GEM_DB_TABLE} WHERE email_key = ?", (email_key,))
        row = cursor.fetchone()
        if row:
            p_gem = json.loads(row[0])
            f_gem = json.loads(row[1])
        conn.close()
    except Exception as e:
        print(f"DB Fetch Error: {e}")
        
    if not p_gem or not f_gem:
        base_indices = zodiac_mapping.get(raw_zodiac, (5, 0))
        user_offset = sum(ord(c) for c in f"{name}_{dob}") % len(primary_gems)
        
        p_gem_idx = (base_indices[0] + user_offset) % len(primary_gems)
        f_gem_idx = (base_indices[1] + user_offset) % len(fortune_gems)
        
        p_gem = primary_gems[p_gem_idx]
        f_gem = fortune_gems[f_gem_idx]
        
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(f"""
                INSERT OR REPLACE INTO {GEM_DB_TABLE} (email_key, name, dob, zodiac, primary_gem, fortune_gem, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (email_key, name, dob, raw_zodiac, json.dumps(p_gem), json.dumps(f_gem), str(datetime.datetime.now())))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Save Error: {e}")
    
    filename = f"Gemstone_Report_{name.replace(' ', '_')}_{raw_zodiac.split(' ')[0]}.pdf"
    generate_pdf_report(
        filename,
        f"Vedic Gemstone & Remedial Report - {name} ({raw_zodiac})",
        [
            f"Client Name: {name} | DOB: {dob} | POB: {pob}",
            f"Zodiac / Ascendant: {raw_zoids if 'raw_zoids' in locals() else raw_zodiac}",
            f"Primary Life Stone (Lagna Ratna): {p_gem[0]}",
            f"Fortune & Wealth Stone (Bhagya Ratna): {f_gem[0]}",
            f"Ruling Planetary Lord: {p_gem[1]}",
            f"Recommended Metal: {p_gem[3]} | Wearing Finger: {p_gem[4]}",
            f"Auspicious Wearing Day: {p_gem[2]}",
            f"Ritual Instructions for {raw_zodiac}: Cleanse the gemstone in Gangajal and raw cow milk, energize with planetary mantras during Shukla Paksha, and wear with devotion."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:15px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:12px 24px; border-radius:10px; font-weight:bold; text-decoration:none; display:inline-block; box-shadow: 0 4px 15px rgba(16,185,129,0.4);'>📥 Download Gemstone & Rituals PDF Report</a></div>"""
    
    teaser = f"""
    <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #7c3aed; padding: 20px; border-radius: 14px; box-shadow: 0 0 20px rgba(124, 58, 237, 0.3); margin-top: 15px;'>
        <h4 style='color:#fde047; margin-top:0;'>💎 Dynamic Gemstone Analysis for {name.upper()} ({raw_zodiac})</h4>
        <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin-top:12px;'>
            <div style='background:rgba(124,58,237,0.25); padding:12px; border-radius:10px; border:1px solid rgba(244,114,182,0.3);'>
                <span style='color:#f3e8ff; font-size:0.8rem; display:block;'>Primary Life Stone (Lagna Ratna)</span>
                <b style='color:#4ade80; font-size:1.15rem;'>{p_gem[0]}</b>
            </div>
            <div style='background:rgba(124,58,237,0.25); padding:12px; border-radius:10px; border:1px solid rgba(244,114,182,0.3);'>
                <span style='color:#f3e8ff; font-size:0.8rem; display:block;'>Fortune & Wealth Stone (Bhagya Ratna)</span>
                <b style='color:#fde047; font-size:1.15rem;'>{f_gem[0]}</b>
            </div>
        </div>
        <p style='color:#f3e8ff; margin-top:12px;'><b>Ruling Planet:</b> {p_gem[1]} | <b>Auspicious Day:</b> {p_gem[2]}</p>
    </div>
    """
    
    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:22px; border-radius:16px; border:2px solid #4ade80; margin-top:15px; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h4 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>🧿 COMPLETE GEMSTONES, METALS & CONSECRATION RITUALS FOR {name.upper()} ({raw_zodiac})</h4>
        <ul style='line-height:1.8; color:#f3e8ff; font-size:0.95rem; margin-top:10px;'>
            <li><b>Recommended Metal:</b> {p_gem[3]}</li>
            <li><b>Wearing Finger:</b> {p_gem[4]} of the right hand</li>
            <li><b>Purification Protocol:</b> Submerge the gemstone ring or pendant in fresh Gangajal and raw unpasteurized cow milk for 15 minutes to cleanse all negative energies prior to wearing.</li>
            <li><b>Consecration & Mantra:</b> Wear during {p_gem[2]} while chanting the respective planetary Beeja mantra 108 times with complete focus and devotion.</li>
        </ul>
        <p style='color: #4ade80; font-weight: bold; margin-top: 15px;'>✅ Complete Gemstone Report & PDF Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""
    
    paywall = "" if is_admin else get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 59, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "full_report": full_report, "pdf_download_btn": download_btn, "paywall": paywall})
    
@app.post("/api/vastu")
async def api_vastu(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip() or "User"
    p_type = data.get("property_type", "Residential House / Flat").strip()
    facing = data.get("facing", "North Facing").strip()
    city = data.get("city", "Kolkata").strip() or "Kolkata"
    is_admin = data.get("is_admin", False)
    
    VASTU_DB_TABLE = "user_vastu_reports_v5"
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {VASTU_DB_TABLE} (
                vastu_key TEXT PRIMARY KEY,
                name TEXT,
                property_type TEXT,
                facing TEXT,
                city TEXT,
                analysis_text TEXT,
                zonal_text TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Vastu Table Creation Error: {e}")

    vastu_key = f"{name.lower().replace(' ', '_')}_{p_type.lower().replace(' ', '_').replace('/', '_')}_{facing.lower().replace(' ', '_')}_{city.lower().replace(' ', '_')}"
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Vastu Analysis PDF", "details": f"Property: {p_type}, Facing: {facing}, City: {city}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Pending (₹149)"})
    
    # Stronger ASCII Weights giving distinct prominence to City and Facing
    n_seed = sum(ord(c) * (i + 1) for i, c in enumerate(name.lower()))
    c_seed = sum(ord(c) * (i + 11) for i, c in enumerate(city.lower()))
    f_seed = sum(ord(c) * (i + 7) for i, c in enumerate(facing.lower()))
    p_seed = sum(ord(c) * (i + 13) for i, c in enumerate(p_type.lower()))
    
    # Highly decoupled composite seeds
    blueprint_seed = n_seed + (c_seed * 5) + f_seed + (p_seed * 3)
    zonal_seed = (n_seed * 2) + (c_seed * 7) + (f_seed * 3) + p_seed
    remedy_seed = n_seed + c_seed + (f_seed * 5) + (p_seed * 11)
    
    zone_dict = {
        "North Facing": ("Kubera (Lord of Wealth)", "North-East Ishan corner", "Northern portal flow"),
        "East Facing": ("Surya (Solar Prana & Vitality)", "Eastern window facade", "Eastern boundary perimeter"),
        "South Facing": ("Yama (Structural Stability)", "Southern and South-Western sectors", "Southern wall thickness"),
        "West Facing": ("Varuna (Auspicious Gains)", "Western storage zone", "North-West Vayavya sector"),
        "North-East (Ishan)": ("Divine Ishan Energy", "Central Brahmasthan alignment", "North-East water axis"),
        "South-East (Agneya)": ("Agni (Fire & Energy)", "South-East kitchen quadrant", "Electrical transformer placement"),
        "South-West (Nairutya)": ("Nairutya Earth Stability", "Master structural zone", "Heavy southern almirah grid"),
        "North-West (Vayavya)": ("Vayavya Air & Motion", "Dispatch and networking sector", "Ventilation and airflow ducts")
    }
    
    z_tuple = zone_dict.get(facing, ("Universal Panchamahabhuta Balance", "Central sector", "Boundary perimeter"))
    
    element_verbs = [
        "amplifies financial liquidity", "fortifies positive cosmic prana", 
        "sustains long-term structural harmony", "balances magnetic earth frequencies", 
        "enhances operational efficiency", "optimizes heavy inventory distribution", 
        "secures structural load-bearing balance", "accelerates commercial turnover"
    ]
    
    action_notes = [
        "maintaining clutter-free pathways", "optimizing natural daylight entry", 
        "placing corrective brass/copper helices", "securing heavy structural weight along southern margins", 
        "positioning ventilation shafts correctly", "balancing subterranean water levels", 
        "reinforcing boundary wall perimeters"
    ]
    
    city_modifiers = [
        f"tailored to regional climatic topography of {city}",
        f"synchronized with local geomagnetic vectors native to {city}",
        f"calibrated for atmospheric pressure trends across {city}",
        f"adjusted for urban micro-climate zoning prevalent in {city}"
    ]
    
    verb_chosen = element_verbs[blueprint_seed % len(element_verbs)]
    action_chosen = action_notes[blueprint_seed % len(action_notes)]
    city_mod_chosen = city_modifiers[c_seed % len(city_modifiers)]
    
    prop_focus_terms = {
        "Residential House / Flat": "family living quarters and bedroom zones",
        "Commercial Office / Shop": "client reception and cash counter placement",
        "Factory / Manufacturing Unit": "heavy machinery grid and power transformer bays",
        "Warehouse / Storage Hub": "pallet racking alignment and dispatch loading docks",
        "Plot / Land": "boundary slope inclination and foundational earth grading"
    }
    
    p_term = prop_focus_terms.get(p_type, "architectural layout")
    
    base_prop_note = (
        f"For {name}'s {p_type} situated in {city} with a {facing} alignment, "
        f"the internal zoning dedicated to {p_term}, {city_mod_chosen} and governed by {z_tuple[0]}, {verb_chosen}. "
        f"Special architectural focus must be directed toward the {z_tuple[1]} by {action_chosen}, "
        f"ensuring optimal energy distribution across all quadrants."
    )
    
    zonal_actions = [
        f"keeping the primary threshold illuminated and unobstructed, integrating elemental copper corrections in {city}",
        f"balancing the {z_tuple[1]} with high-frequency brass crystals suited for {city}'s environment",
        f"deploying protective geo-pathic neutralizing plates along the perimeter walls across {city}",
        f"re-aligning subterranean water drainage channels to prevent stagnation within {city}'s jurisdiction"
    ]
    
    z_act_chosen = zonal_actions[zonal_seed % len(zonal_actions)]
    
    specific_remedy = (
        f"Zonal assessment for {facing} ({z_tuple[2]}) indicates that {name}'s {p_type.lower()} in {city} "
        f"benefits immensely from {z_act_chosen}. "
        f"This precise geospatial adjustment will secure enduring prosperity and operational success for {name}."
    )
    
    remedial_options = [
        f"Deploy Vastu copper pyramids in afflicted South-West and South-East corners, install crystal grids tailored for {city}, and maintain pristine entrance lighting.",
        f"Fix brass helix correctors along cut boundaries, place sea salt bowls in restrooms across {city}, and keep the North-East zone strictly unburdened.",
        f"Erect protective boundary shielding matching local {city} soil attributes, install Surya yantras at the main portal, and keep central Brahmasthan open.",
        f"Incorporate color therapy remedies specific to {facing}, set up water fountains in northern sectors for {city} properties, and reinforce southern walls."
    ]
    
    chosen_remedy = remedial_options[remedy_seed % len(remedial_options)]
    
    filename = f"Vastu_Report_{name.replace(' ', '_')}_{p_type.split(' ')[0]}.pdf"
    generate_pdf_report(
        filename,
        f"Vastu Shastra Assessment for {name} ({p_type})",
        [
            f"Client Name: {name} | Property Type: {p_type}",
            f"Facing Direction: {facing} | Location: {city}",
            f"1. Algorithmic Vastu Blueprint: {base_prop_note}",
            f"2. Zonal Energy Breakdown: {specific_remedy}",
            f"3. Remedial Enhancements: {chosen_remedy}"
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:12px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:10px 20px; border-radius:8px; font-weight:bold; text-decoration:none; display:inline-block;'>📥 Download Vastu PDF Report</a></div>"""
    
    teaser = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <h4 style='color:#fde047; margin-top:0;'>🏛️ Vastu Analysis Preview for {name.upper()} ({p_type.upper()})</h4>
        <p style='color:#f3e8ff;'><b>Facing Direction:</b> {facing} | <b>Location:</b> {city}</p>
        <p style='color:#4ade80; font-size:0.92rem; margin-top:6px;'><b>Algorithmic Blueprint:</b> {base_prop_note}</p>
        <p style='color:#38bdf8; font-size:0.92rem; margin-top:4px;'><b>Zonal Insight:</b> {specific_remedy}</p>
    </div>
    """
    
    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:22px; border-radius:16px; border:2px solid #4ade80; margin-top:15px; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h4 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>🏛️ COMPREHENSIVE VASTU SHASTRA & PROPERTY ASSESSMENT REPORT FOR {name.upper()}</h4>
        <p style='color: #f3e8ff; line-height: 1.8;'><b>Property:</b> {p_type} | <b>Facing:</b> {facing} | <b>City:</b> {city}</p>
        <p style='color: #f3e8ff; line-height: 1.8; margin-top:8px;'><b>Algorithmic Property Analysis:</b> {base_prop_note}</p>
        <p style='color: #f3e8ff; line-height: 1.8; margin-top:8px;'><b>Detailed Zonal Breakdown:</b> {specific_remedy}</p>
        <p style='color: #f3e8ff; line-height: 1.8; margin-top:10px;'><b>Remedial Blueprint:</b> {chosen_remedy}</p>
        <p style='color: #4ade80; font-weight: bold; margin-top: 10px;'>✅ Full Vastu Report Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""

    paywall = "" if is_admin else get_paywall_html("Complete Vastu Dosha & Remedial PDF Report", 149, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "full_report": full_report, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/kundali-pdf")
async def api_kundali_pdf(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip() or "User"
    dob = data.get("dob", "2000-01-01").strip() or "2000-01-01"
    tob = data.get("tob", "12:00").strip() or "12:00"
    pob = data.get("pob", "Kolkata").strip() or "Kolkata"
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Janam Kundali PDF", "details": f"DOB: {dob}, POB: {pob}", "payment_status": "Admin Bypassed (PDF Active)" if is_admin else "Generated (₹59)"})
    
    profile = calculate_astrological_profile(name, dob)
    
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    generate_pdf_report(
        filename,
        f"Janam Kundali & Lagna Chart - {name}",
        [
            f"Date of Birth: {dob} | Time: {tob} | Place: {pob}",
            f"Ascendant (Lagna) Sign: {profile['zodiac']} | Birth Nakshatra: {profile['nakshatra']}",
            f"Planetary Positions (Graha Sthiti): Active Rashi lord {profile['zodiac']} with favorable divisional positioning.",
            f"Lagna Horoscope: Strong ascendant house under {profile['dasha']} indicating resilience, leadership, and long-term financial growth."
        ]
    )
    
    pdf_btn_html = f"""<div style='margin-top:12px;'><a href='/download-pdf/{filename}' target='_blank' style='background:#10b981; color:white; padding:10px 20px; border-radius:8px; font-weight:bold; text-decoration:none; display:inline-block;'>📥 Download Janam Kundali PDF</a></div>"""
    teaser = f"""<div style='background:#1e1b4b; padding:15px; border-radius:10px;'><h4 style='color:#fde047;'>📜 Janam Kundali Generated for {name} ({profile['zodiac']})</h4><p style='color:#4ade80;'>✅ Janam Kundali PDF report is ready for download.</p></div>"""
    chart = f"""<div style='background:#31104b; padding:15px; border-radius:10px; margin-top:10px; text-align:center;'><b style='color:#fde047;'>Lagna Chart Active | Rashi: {profile['zodiac']} | Nakshatra: {profile['nakshatra']} (DOB: {dob}, POB: {pob})</b></div>"""
    
    paywall = "" if is_admin else get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 59, name)
    download_btn = pdf_btn_html if is_admin else ""
    
    return JSONResponse({"teaser": teaser, "chart": chart, "pdf_download_btn": download_btn, "paywall": paywall})

@app.post("/api/numerology")
async def api_numerology(request: Request):
    data = await request.json()
    name = data.get("name", "User").strip() or "User"
    dob = data.get("dob", "2000-01-01").strip() or "2000-01-01"
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Vedic Numerology Analysis", "details": f"DOB: {dob}", "payment_status": "Admin Bypassed" if is_admin else "Pending (₹69)"})
    
    try:
        dt_parts = dob.split("-")
        # Handle YYYY-MM-DD format correctly where day is the last part or DD-MM-YYYY where day is first
        if len(dt_parts[0]) == 4:
            day = int(dt_parts[2])
        else:
            day = int(dt_parts[0])
    except Exception:
        day = 1

    # Mulank (Psychic Number): Sum of digits of birth day reduced to single digit
    mulank = sum(int(d) for d in str(day))
    while mulank > 9:
        mulank = sum(int(d) for d in str(mulank))
        
    # Bhagyank (Destiny Number): Sum of ALL digits in DOB reduced to single digit
    total_digits_sum = sum(int(d) for d in dob if d.isdigit())
    bhagyank = total_digits_sum
    while bhagyank > 9:
        bhagyank = sum(int(d) for d in str(bhagyank))
        
    ruling_planets = {
        1: "Sun (Surya)", 2: "Moon (Chandra)", 3: "Jupiter (Guru)",
        4: "Rahu", 5: "Mercury (Budha)", 6: "Venus (Shukra)",
        7: "Ketu", 8: "Saturn (Shani)", 9: "Mars (Mangal)"
    }
    ruling_p = ruling_planets.get(mulank, "Sun (Surya)")

    compatibility_map = {
        1: [1, 2, 3, 5, 9],
        2: [1, 2, 5, 3],
        3: [1, 3, 5, 7, 9],
        4: [1, 5, 6, 7],
        5: [1, 2, 3, 5, 6],
        6: [3, 5, 6, 9],
        7: [3, 4, 5, 7],
        8: [3, 5, 6, 7],
        9: [1, 3, 6, 9]
    }
    compat_nums = ", ".join(map(str, compatibility_map.get(mulank, [1, 3, 5])))

    teaser = f"""
    <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #7c3aed; padding: 20px; border-radius: 14px; box-shadow: 0 0 20px rgba(124, 58, 237, 0.3); margin-top: 15px;'>
        <h4 style='color:#fde047; margin-top:0;'>🔢 Numerology Analysis for {name.upper()} (DOB: {dob})</h4>
        <div style='display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin-top:10px;'>
            <div style='background:rgba(124,58,237,0.2); padding:12px; border-radius:10px; text-align:center;'>
                <span style='color:#f3e8ff; font-size:0.8rem;'>Psychic Number (Mulank)</span>
                <b style='color:#4ade80; font-size:1.5rem; display:block;'>{mulank}</b>
            </div>
            <div style='background:rgba(124,58,237,0.2); padding:12px; border-radius:10px; text-align:center;'>
                <span style='color:#f3e8ff; font-size:0.8rem;'>Destiny Number (Bhagyank)</span>
                <b style='color:#fde047; font-size:1.5rem; display:block;'>{bhagyank}</b>
            </div>
        </div>
        <p style='color:#f3e8ff; margin-top:12px;'><b>Ruling Planetary Lord:</b> <span style='color:#fde047;'>{ruling_p}</span></p>
    </div>
    """
    
    full_report = f"""
    <div style='background:rgba(22, 10, 48, 0.9); padding:22px; border-radius:16px; border:2px solid #4ade80; margin-top:15px; box-shadow: 0 0 30px rgba(74, 222, 128, 0.3);'>
        <h4 style='color: #4ade80 !important; margin-top:0; font-family: "Cinzel", serif;'>🔢 DETAILED NUMEROLOGY & NAME CORRECTION REPORT FOR {name.upper()}</h4>
        <p style='color:#f3e8ff;'><b>Name Energy Balance:</b> Your full name correlates closely with Mulank {mulank}. Maintaining spelling harmony enhances career luck and personal vitality.</p>
        <p style='color:#fde047;'><b>Compatible Numbers:</b> {compat_nums}</p>
        <p style='color: #4ade80; font-weight: bold; margin-top: 10px;'>✅ Complete Numerology Report Unlocked Successfully via Admin Access!</p>
    </div>
    """ if is_admin else ""
    
    paywall = "" if is_admin else get_paywall_html("Detailed Numerology & Name Correction Report", 69, name)
    return JSONResponse({"teaser": teaser, "full_report": full_report, "paywall": paywall})

@app.post("/api/panchang")
async def api_panchang(request: Request):
    data = await request.json()
    city = data.get("city", "Kolkata").strip() or "Kolkata"
    date_str = data.get("date", "Today").strip() or "Today"
    mode = data.get("mode", "free")
    is_admin = data.get("is_admin", False)
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": "User", "service": "Vedic Panchang", "details": f"City: {city}, Date: {date_str}, Mode: {mode}", "payment_status": "Free/Admin Bypassed" if (mode == "free" or is_admin) else "Pending (₹99)"})
    
    today_formatted = datetime.datetime.now().strftime("%B %d, %Y") if date_str in ["Today", ""] else date_str
    
    # Fully decoupled unique seed generation for city and date
    city_seed = sum(ord(c) * (i + 1) for i, c in enumerate(city.lower()))
    date_seed = sum(ord(c) * (i + 3) for i, c in enumerate(str(date_str)))
    combined_seed = city_seed + (date_seed * 7)
    
    tithis = [
        "Shukla Paksha Pratipada", "Shukla Paksha Tritiya", "Shukla Paksha Panchami", 
        "Shukla Paksha Ashtami", "Shukla Paksha Navami", "Shukla Paksha Ekadashi", 
        "Shukla Paksha Trayodashi", "Purnima", "Krishna Paksha Dwitiya", 
        "Krishna Paksha Chaturthi", "Krishna Paksha Saptami", "Krishna Paksha Dashami", "Amavasya"
    ]
    nakshatras = [
        "Ashwini Nakshatra", "Bharani Nakshatra", "Krittika Nakshatra", "Rohini Nakshatra", 
        "Mrigashira Nakshatra", "Ardra Nakshatra", "Punarvasu Nakshatra", "Pushya Nakshatra", 
        "Ashlesha Nakshatra", "Magha Nakshatra", "Purva Phalguni Nakshatra", "Uttara Phalguni Nakshatra", 
        "Hasta Nakshatra", "Chitra Nakshatra", "Swati Nakshatra", "Vishakha Nakshatra", 
        "Anuradha Nakshatra", "Jyeshtha Nakshatra", "Mula Nakshatra", "Shravana Nakshatra", "Revati Nakshatra"
    ]
    rahu_kalams = [
        "07:30 AM - 09:00 AM", "09:00 AM - 10:30 AM", "10:30 AM - 12:00 PM", 
        "12:00 PM - 01:30 PM", "01:30 PM - 03:00 PM", "03:00 PM - 04:30 PM", "04:30 PM - 06:00 PM",
        "08:00 AM - 09:30 AM", "01:00 PM - 02:30 PM", "03:30 PM - 05:00 PM"
    ]
    sun_rises = ["05:42 AM", "05:58 AM", "06:12 AM", "05:30 AM", "06:05 AM", "05:50 AM", "06:15 AM", "05:45 AM", "06:02 AM", "05:38 AM"]
    sun_sets = ["05:45 PM", "06:22 PM", "05:55 PM", "06:40 PM", "06:10 PM", "05:35 PM", "06:00 PM", "06:15 PM", "05:50 PM", "06:30 PM"]
    
    abhijits = [
        "11:35 AM - 12:20 PM", "11:45 AM - 12:32 PM", "11:50 AM - 12:40 PM", 
        "11:25 AM - 12:15 PM", "11:40 AM - 12:28 PM", "11:55 AM - 12:45 PM"
    ]
    amrits = [
        "04:20 AM - 05:08 AM", "05:10 AM - 05:58 AM", "03:50 AM - 04:40 AM", 
        "04:45 AM - 05:35 AM", "05:00 AM - 05:50 AM", "04:10 AM - 05:00 AM"
    ]
    yamagandas = [
        "03:15 PM - 04:45 PM", "09:00 AM - 10:30 AM", "01:15 PM - 02:45 PM", 
        "10:45 AM - 12:15 PM", "08:15 AM - 09:45 AM", "02:00 PM - 03:30 PM",
        "11:00 AM - 12:30 PM", "04:00 PM - 05:30 PM", "07:30 AM - 09:00 AM"
    ]
    horas = [
        "Surya Hora active in morning; Guru Hora supporting financial decisions.",
        "Chandra Hora active in morning; Shukra Hora supporting creative ventures.",
        "Mangal Hora active in morning; Budha Hora supporting business communication.",
        "Shani Hora active in morning; Guru Hora supporting long-term investments.",
        "Budha Hora active in morning; Surya Hora supporting administrative authority.",
        "Shukra Hora active in morning; Chandra Hora supporting artistic partnerships."
    ]
    
    tithi_val = tithis[combined_seed % len(tithis)]
    nak_val = nakshatras[(city_seed + date_seed * 2) % len(nakshatras)]
    rahu_val = rahu_kalams[(city_seed * 3 + date_seed) % len(rahu_kalams)]
    
    # Completely independent unique indices for Sunrise, Sunset, and Yamaganda
    rise_val = sun_rises[(city_seed + date_seed * 3) % len(sun_rises)]
    set_val = sun_sets[(date_seed * 4 + city_seed) % len(sun_sets)]
    
    abhijit_val = abhijits[(city_seed + date_seed) % len(abhijits)]
    amrit_val = amrits[(city_seed * 2 + date_seed) % len(amrits)]
    yamaganda_val = yamagandas[(date_seed * 5 + city_seed * 2) % len(yamagandas)]
    hora_val = horas[(city_seed * 7 + date_seed * 11 + 13) % len(horas)]

    if mode == "free":
        html = f"""
        <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #7c3aed; padding: 22px; border-radius: 16px; box-shadow: 0 0 25px rgba(124, 58, 237, 0.4); margin-top: 15px;'>
            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid rgba(244, 114, 182, 0.4); padding-bottom: 10px; margin-bottom: 15px; flex-wrap: wrap;'>
                <h4 style='color: #fde047 !important; margin: 0; font-family: "Cinzel", serif;'>📅 Free Daily Vedic Panchang ({city})</h4>
                <span style='color: #4ade80; font-weight: 600; font-size: 0.9rem;'>{today_formatted}</span>
            </div>
            
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;'>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px;'>
                    <b style='color: #fde047; display: block;'>📜 Tithi:</b>
                    <span style='color: #f3e8ff;'>{tithi_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px;'>
                    <b style='color: #fde047; display: block;'>⭐ Nakshatra:</b>
                    <span style='color: #f3e8ff;'>{nak_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px;'>
                    <b style='color: #ef4444; display: block;'>⚠️ Rahu Kalam:</b>
                    <span style='color: #f3e8ff;'>{rahu_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px;'>
                    <b style='color: #4ade80; display: block;'>☀️ Sun & Moon:</b>
                    <span style='color: #f3e8ff;'>Sunrise: {rise_val} | Sunset: {set_val}</span>
                </div>
            </div>
        </div>
        """
        return JSONResponse({"html": html, "paywall": ""})
    else:
        html = f"""
        <div style='background: rgba(18, 8, 42, 0.9); border: 2px solid #db2777; padding: 22px; border-radius: 16px; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5); margin-top: 15px;'>
            <div style='display: flex; justify-content: space-between; align-items: center; border-bottom: 1.5px solid rgba(244, 114, 182, 0.4); padding-bottom: 10px; margin-bottom: 15px; flex-wrap: wrap;'>
                <h4 style='color: #fde047 !important; margin: 0; font-family: "Cinzel", serif;'>🌟 All-in-One Complete Panchang & Detailed Shubh Muhurat Report ({city}, India)</h4>
                <span style='color: #fde047; font-weight: 600; font-size: 0.9rem;'>{date_str}</span>
            </div>
            
            <h5 style='color: #4ade80; margin-top: 5px; margin-bottom: 10px;'>📌 Basic Daily Panchang Details</h5>
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px;'>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px; border: 1px solid rgba(244, 114, 182, 0.3);'>
                    <b style='color: #fde047; display: block;'>📜 Tithi:</b>
                    <span style='color: #f3e8ff;'>{tithi_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px; border: 1px solid rgba(244, 114, 182, 0.3);'>
                    <b style='color: #fde047; display: block;'>⭐ Nakshatra:</b>
                    <span style='color: #f3e8ff;'>{nak_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px; border: 1px solid rgba(244, 114, 182, 0.3);'>
                    <b style='color: #ef4444; display: block;'>⚠️ Rahu Kalam:</b>
                    <span style='color: #f3e8ff;'>{rahu_val}</span>
                </div>
                <div style='background: rgba(124, 58, 237, 0.2); padding: 12px; border-radius: 10px; border: 1px solid rgba(244, 114, 182, 0.3);'>
                    <b style='color: #4ade80; display: block;'>☀️ Sun & Moon:</b>
                    <span style='color: #f3e8ff;'>Sunrise: {rise_val} | Sunset: {set_val}</span>
                </div>
            </div>

            <h5 style='color: #fde047; margin-top: 15px; margin-bottom: 10px;'>✨ Exclusive Shubh Muhurat & Ephemeris Details</h5>
            <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px;'>
                <div style='background: rgba(219, 39, 119, 0.2); padding: 14px; border-radius: 10px; border: 1px solid #db2777;'>
                    <b style='color: #fde047; display: block;'>✨ Abhijit Muhurat (Best for Starting New Work):</b>
                    <span style='color: #f3e8ff;'>{abhijit_val} (Highly Auspicious Vedic Window)</span>
                </div>
                <div style='background: rgba(219, 39, 119, 0.2); padding: 14px; border-radius: 10px; border: 1px solid #db2777;'>
                    <b style='color: #fde047; display: block;'>🌙 Amrit Kalam & Brahma Muhurat:</b>
                    <span style='color: #f3e8ff;'>{amrit_val} (Divine Spiritual Energy)</span>
                </div>
                <div style='background: rgba(219, 39, 119, 0.2); padding: 14px; border-radius: 10px; border: 1px solid #db2777;'>
                    <b style='color: #ef4444; display: block;'>⚠️ Yamaganda & Gulika Kalam:</b>
                    <span style='color: #f3e8ff;'>Yamaganda: {yamaganda_val} (Avoid New Ventures)</span>
                </div>
                <div style='background: rgba(219, 39, 119, 0.2); padding: 14px; border-radius: 10px; border: 1px solid #db2777;'>
                    <b style='color: #38bdf8; display: block;'>🪐 Hora Lords & Planetary Alignments:</b>
                    <span style='color: #f3e8ff;'>{hora_val}</span>
                </div>
            </div>
            <p style='color: #4ade80; margin-top: 15px; font-weight: bold;'>✅ Full Detailed All-in-One Panchang Report Unlocked Successfully via Paid Access (₹99)!</p>
        </div>
        """
        paywall = "" if is_admin else get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
        return JSONResponse({"html": html, "paywall": paywall})
        
@app.post("/api/ai")
async def api_ai(request: Request):
    data = await request.json()
    query = data.get("query", "").strip().lower()
    name = data.get("name", "User")
    
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "AI Kundli Interpreter", "details": f"Query: {query[:30]}...", "payment_status": "Free Answer"})
    
    if any(k in query for k in ["haunted", "graveyard", "vastu", "house", "flat", "location", "shifting", "property", "land", "building", "bardhaman"]):
        ai_reply = f"Hello {name}, evaluating energy fields, historical land Rahu-Ketu aspects, and Vastu alignment (such as plots near southern zones or old lands) is crucial before shifting location. Regarding concerns about past history or unusual sounds, proper Vastu Purusha analysis and spatial energy cleansing are essential. For a complete room-by-room Vastu Dosha report and energetic remedies, please check our <b>Vastu Shastra PDF</b> or <b>Life Prediction</b> tabs."
    elif any(k in query for k in ["threat", "political", "police", "danger", "fear", "life threat", "attack", "enemy", "party", "kill", "dominated"]):
        ai_reply = f"Hello {name}, planetary configurations indicate turbulence due to shifting 8th and 10th house energies regarding external conflicts and rivalries. For specialized protective astrological remedies, gemstone shielding, and detailed life forecasting, please check our <b>Life Prediction</b> or <b>Gemstones PDF</b> tabs."
    elif any(k in query for k in ["spirit", "mother", "father", "passed away", "departed", "midnight", "bed", "blessing", "presence", "soul"]) and not any(k in query for k in ["haunted", "graveyard", "vastu", "land", "property", "bardhaman"]):
        ai_reply = f"Hello {name}, feeling the spiritual presence or comforting energy of departed parents (Pitru/Matru blessings) during vulnerable hours is deeply emotional and connected to ancestral 9th and 4th house alignments in your chart. While rituals or yoga can help center mental peace, the deep emotional bond is a matter of inner solace. For emotional strength, mental peace, and spiritual remedies, please explore our <b>Life Prediction</b> and <b>Lucky Gemstones PDF</b> tabs."
    elif any(k in query for k in ["car", "suv", "vehicle", "four-wheeler", "accident", "drive", "ride", "hand rekhas", "road", "collision"]):
        ai_reply = f"Hello {name}, evaluating vehicle acquisitions (SUV/four-wheelers), transit safety, and potential road hazard predictions requires analyzing your D16 Shodashvarga (Vehicle & Conveyance chart) along with 4th and 8th house influences. For a comprehensive transit safety evaluation and divisional chart analysis, please check our <b>Jagannath Hora</b> and <b>Vastu Shastra PDF</b> tabs."
    elif any(k in query for k in ["hurt", "injured", "injury", "hit", "ball", "head", "back", "shoulder", "bandage", "wound", "harm", "cricket"]) and any(k in query for k in ["hurt", "injured", "injury", "hit", "bandage", "wound"]):
        ai_reply = f"Hello {name}, frequent physical injuries, sudden impacts during sports (like cricket), and bodily trauma are strongly influenced by afflicted Mars (Mangal), Rahu, and malefic 6th house transits governing physical resistance and accidents. To shield against negative planetary impacts, physical hurdles, and promote safe recovery, please explore our <b>Lucky Gemstones PDF</b> and <b style='color:#fde047;'>Life Prediction</b> tabs."
    elif any(k in query for k in ["career", "job", "it sector", "earning", "passion", "profession", "money", "income", "work", "office", "promotion"]):
        ai_reply = f"Hello {name}, evaluating a career transition between passion and corporate/IT earnings involves analyzing your 10th house of Karma, Sun's leadership aspects, and Saturn-Mars yogas. To explore deep career forecasts, divisional D10 charts, and professional alignment, please check our <b>Jagannath Hora</b> and <b>Kundali Explorer</b> tabs."
    elif any(k in query for k in ["marriage", "in-laws", "husband", "wife", "family", "wedding", "partner", "relationship", "love", "groom", "bride"]):
        ai_reply = f"Hello {name}, family decisions, spouse/in-law support, and marital harmony are governed by the 7th and 4th houses in your chart. When balancing domestic support with personal ambition, understanding Guna Milan and planetary compatibility is vital. Explore our <b>Matching</b> or <b>Life Prediction</b> tabs for detailed guidance."
    elif any(k in query for k in ["health", "diet", "food", "routine", "body", "stomach", "eat", "tiffin", "lunch", "dinner"]):
        ai_reply = f"Hello {name}, regarding your health and daily meal routine, planetary transits indicate that irregular eating habits impact your physical well-being. For a detailed health horoscope and customized gemstone/remedy guidelines, please check our <b>Lucky Gemstones PDF</b> or <b>Life Prediction</b> tabs."
    else:
        ai_reply = f"Hello {name}, I have carefully analyzed your cosmic query regarding '{query}'. Vedic principles indicate a transformative phase ahead. For a complete Janam Kundali chart and personalized astrological guidance, please explore our dedicated <b>Kundali PDF</b> or <b>Life Prediction</b> tabs."

    html = f"""
    <div style='background:#1e1b4b; padding:18px; border-radius:12px; border:1px solid #7c3aed;'>
        <p style='color:#fde047; margin-bottom:6px;'><b>Query:</b> {query}</p>
        <p style='color:#4ade80; line-height:1.7;'><b>AI Kundli Interpreter:</b> {ai_reply}</p>
    </div>
    """
    return JSONResponse({"html": html})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)
