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

def check_user_exists_triple(email):
    email_clean = email.strip().lower()
    if not email_clean:
        return False
    # 1. Check SQLite / Google Sheet loaded users dictionary / list
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

def calculate_jagannath_hora_engine(name, dob_str, tob_str="12:00", pob_str="Kolkata"):
    profile = calculate_astrological_profile(name, dob_str)
    z_idx = ZODIAC_SIGNS.index(profile["zodiac"]) if profile["zodiac"] in ZODIAC_SIGNS else 0

    shodashvarga_charts = {
        "D1 (Lagna Chart)": profile["zodiac"],
        "D2 (Hora - Wealth)": ZODIAC_SIGNS[(z_idx + 1) % 12],
        "D3 (Drekkana - Siblings/Courage)": ZODIAC_SIGNS[(z_idx + 4) % 12],
        "D4 (Chaturthamsha - Assets/Home)": ZODIAC_SIGNS[(z_idx + 3) % 12],
        "D7 (Saptamsha - Children/Progeny)": ZODIAC_SIGNS[(z_idx + 6) % 12],
        "D9 (Navamsha - Marriage/Dharma)": ZODIAC_SIGNS[(z_idx + 8) % 12],
        "D10 (Dashamsha - Profession/Karma)": ZODIAC_SIGNS[(z_idx + 9) % 12],
        "D12 (Dwadasamsha - Parents/Ancestry)": ZODIAC_SIGNS[(z_idx + 11) % 12],
        "D16 (Shodasamsha - Vehicles/Comforts)": ZODIAC_SIGNS[z_idx % 12],
        "D20 (Vimsamsha - Spiritual Progress)": ZODIAC_SIGNS[(z_idx + 7) % 12],
        "D24 (Chaturvimsamsha - Higher Education)": ZODIAC_SIGNS[(z_idx + 5) % 12],
        "D27 (Saptavimsamsha - Strengths/Weakness)": ZODIAC_SIGNS[(z_idx + 2) % 12],
        "D30 (Trimsamsha - Misfortunes/Arishta)": ZODIAC_SIGNS[(z_idx + 10) % 12],
        "D40 (Khavedamsha - Auspicious Events)": ZODIAC_SIGNS[(z_idx + 3) % 12],
        "D45 (Akshavedamsha - Character/Integrity)": ZODIAC_SIGNS[(z_idx + 6) % 12],
        "D60 (Shastiamsha - Karma/Past Life Root)": ZODIAC_SIGNS[(z_idx + 1) % 12],
    }

    dashas = {
        "Vimshottari Dasha": profile["dasha"],
        "Yogini Dasha": f"Active Yogini: {['Mangala (Moon)', 'Pingala (Sun)', 'Dhanya (Jupiter)', 'Bhramari (Mars)', 'Bhadrika (Mercury)', 'Ulka (Saturn)', 'Siddha (Venus)', 'Sankata (Rahu)'][z_idx % 8]}",
        "Chara Dasha (Jaimini)": f"Current Rashi Dasha: {profile['zodiac']}",
        "Ashtottari Dasha": f"Active Planet: {['Sun', 'Moon', 'Mars', 'Mercury', 'Saturn', 'Jupiter', 'Rahu', 'Venus'][z_idx % 8]}"
    }

    ashtakavarga = {
        "Sun": random.randint(3, 6),
        "Moon": random.randint(3, 6),
        "Mars": random.randint(2, 5),
        "Mercury": random.randint(4, 7),
        "Jupiter": random.randint(4, 7),
        "Venus": random.randint(4, 6),
        "Saturn": random.randint(2, 5),
        "Sarvashtakavarga Total": random.randint(28, 38)
    }

    return {
        "profile": profile,
        "shodashvarga": shodashvarga_charts,
        "dashas": dashas,
        "ashtakavarga": ashtakavarga,
        "transit_overlay": f"Jupiter in {ZODIAC_SIGNS[(z_idx+2)%12]} (Favorable), Saturn in {ZODIAC_SIGNS[(z_idx+10)%12]} (Karma Assessment)."
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
    <div style="background: linear-gradient(135deg, rgba(219,39,119,0.15) 0%, rgba(124,58,237,0.15) 100%); border: 2px solid #db2777; border-radius: 14px; padding: 20px; text-align: center; margin-top: 15px;">
        <h4 style="color: #fde047; margin-top: 0; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{amt_val} ONLY)</h4>
        <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 15px;">Dear {display_name}, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePe, BHIM or Cards.</p>
        <p style="color: #4ade80; font-weight: bold; font-size: 1.1rem; margin-bottom: 15px;">Total Payable: ₹{amt_val}</p>
        <a href="{pay_url}" onclick="triggerPaymentLoader(event, '{pay_url}')" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; padding: 12px 28px; border-radius: 12px; font-weight: bold; text-decoration: none; display: inline-block; box-shadow: 0 6px 20px rgba(219,39,119,0.6); border: 1px solid #fde047;">🚀 Proceed to Pay ₹{amt_val} (UPI, GPay, PhonePe & Cards)</a>
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

@app.post("/api/register")
async def api_register(request: Request):
    data = await request.json()
    name = data.get("name", "User")
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "")
    
    if check_user_exists_triple(email):
        return JSONResponse({"otp": "", "msg": "<p style='color:#ef4444;'>❌ This account has already been registered, please sign in!</p>", "already_registered": True})
        
    otp_code = str(random.randint(100000, 999999))
    send_brevo_email(email, name, "OTP Verification", f"Welcome {name}! Your OTP is {otp_code}")
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Registration OTP", "details": f"Email: {email}", "payment_status": "OTP Dispatched"})
    return JSONResponse({"otp": otp_code, "msg": "<p style='color:#4ade80;'>📧 OTP Sent to your email!</p>", "already_registered": False})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=10000, reload=True)
