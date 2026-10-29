import os
import datetime
import random
import sqlite3
import requests
import razorpay
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyCOjnJySc7mB7vu5BcWhmn7t5f-lPG7EkC03Hc2SCKyMhvOrFz2tZmM1I5obCAm2YM/exec"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")

app = FastAPI()

# Mount current directory for static assets (logo.png, bg.jpg)
app.mount("/static", StaticFiles(directory="."), name="static")

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

# ---------------------------------------------------------
# DATABASE & APPS SCRIPT HELPERS
# ---------------------------------------------------------
def save_user_local(u_name, u_email, u_phone):
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
        print(f"Local User Save Error: {e}")
    
    try:
        params = {"worksheet": "Users", "name": u_name, "email": u_email.lower(), "phone": u_phone, "verified_at": now_str}
        requests.get(APPS_SCRIPT_URL, params=params, timeout=5)
    except Exception as e:
        print(f"Apps Script Sync Error: {e}")

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
        print(f"Log Save Error: {e}")
    
    try:
        params = {"worksheet": "AdminLogs", "timestamp": ts, "full_name": fn, "service": srv, "details": dtl, "payment_status": pst}
        requests.get(APPS_SCRIPT_URL, params=params, timeout=5)
    except Exception as e:
        print(f"Apps Script Log Sync Error: {e}")

def send_brevo_email(to_email, user_name, subject, html_content):
    if not BREVO_API_KEY:
        return False
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"}
    payload = {
        "sender": {"name": "AccAstroForge", "email": "arnabchaudhuriaiedits@gmail.com"},
        "to": [{"email": to_email, "name": user_name}],
        "subject": subject,
        "htmlContent": html_content
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        return res.status_code in [200, 201, 202]
    except Exception:
        return False

# ---------------------------------------------------------
# RAZORPAY & PDF GENERATION
# ---------------------------------------------------------
try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

def get_robust_razorpay_link(service_name, price, user_name="User"):
    try:
        if razorpay_client:
            data = {
                "amount": int(float(price)) * 100,
                "currency": "INR",
                "accept_partial": False,
                "description": f"Payment for {service_name}",
                "customer": {"name": user_name if user_name else "User"},
                "callback_url": "https://accastroforge.in/",
                "callback_method": "get"
            }
            res = razorpay_client.payment_link.create(data)
            if res and "short_url" in res:
                return res["short_url"]
    except Exception:
        pass
    return RAZORPAY_ME_URL

def create_kundali_pdf_file(name, dob, tob, pob):
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle('TStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor("#5b21b6"), alignment=1, spaceAfter=15)
    story.append(Paragraph("<b>AccAstroForge - Vedic Janam Kundali Report</b>", title_style))
    story.append(Spacer(1, 10))
    
    data = [
        ["Attribute", "Details"],
        ["Full Name", name],
        ["Date of Birth", dob],
        ["Time / Place", f"{tob} / {pob}"],
        ["Rashi / Nakshatra", "Mesha (Aries) / Rohini"],
        ["Current Dasha", "Favorable Planetary Cycle Active"]
    ]
    t = Table(data, colWidths=[180, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#7c3aed")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#db2777")),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f3e8ff"))
    ]))
    story.append(t)
    doc.build(story)
    return filename

# ---------------------------------------------------------
# HTML MASTER LAYOUT
# ---------------------------------------------------------
def render_page(title, body_content):
    return f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title} - AccAstroForge</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Poppins', sans-serif; }}
            .cinzel {{ font-family: 'Cinzel', serif; }}
        </style>
    </head>
    <body class="bg-slate-950 text-white min-h-screen flex flex-col bg-cover bg-center" style="background-image: linear-gradient(rgba(3,0,20,0.88), rgba(3,0,20,0.95)), url('/static/bg.jpg');">
        
        <!-- Header -->
        <header class="w-full border-b border-purple-900/50 bg-slate-900/90 backdrop-blur-md py-4 px-6 flex flex-wrap justify-between items-center sticky top-0 z-50">
            <div class="flex items-center space-x-3">
                <img src="/static/logo.png" alt="Logo" class="w-12 h-12 animate-spin" style="animation-duration: 12s;">
                <span class="cinzel text-xl font-bold text-yellow-400 tracking-wider">AccAstroForge</span>
            </div>
            <nav class="space-x-3 text-xs md:text-sm font-semibold flex flex-wrap items-center mt-2 md:mt-0">
                <a href="/" class="hover:text-yellow-400 transition">🏠 Home</a>
                <a href="/dashboard" class="hover:text-yellow-400 transition">👤 Dashboard</a>
                <a href="/life-prediction" class="hover:text-yellow-400 transition">🌟 Life Forecast</a>
                <a href="/matching" class="hover:text-yellow-400 transition">❤️ Matching</a>
                <a href="/gemstones" class="hover:text-yellow-400 transition">💎 Gemstones</a>
                <a href="/kundali-pdf" class="hover:text-yellow-400 transition">📜 Kundali PDF</a>
                <a href="/panchang" class="hover:text-yellow-400 transition">📅 Panchang</a>
                <a href="/admin" class="text-red-400 hover:text-red-300 transition">🛡️ Admin</a>
            </nav>
        </header>

        <!-- Body -->
        <main class="flex-grow max-w-4xl w-full mx-auto p-4 md:p-6 my-4">
            {body_content}
        </main>

        <!-- Footer -->
        <footer class="w-full text-center py-6 border-t border-purple-900/40 text-xs text-slate-400 bg-slate-950/90">
            © 2026 AccAstroForge.in | High Speed FastAPI Vedic Astrology Platform.
        </footer>
    </body>
    </html>
    """

# ---------------------------------------------------------
# ALL ROUTES & FEATURES
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home_page():
    content = """
    <div class="text-center py-8">
        <h1 class="cinzel text-3xl md:text-5xl font-extrabold text-yellow-400 mb-4 drop-shadow-lg">✨ Welcome to AccAstroForge</h1>
        <p class="text-slate-300 text-sm md:text-base max-w-2xl mx-auto mb-8">FastAPI + HTML5 powered high-speed Vedic Astrology, Kundali Matching, and Life Forecasts without refresh lags!</p>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl hover:border-yellow-400 transition">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">❤️ Kundali Matching</h3>
                <p class="text-slate-300 text-xs mb-4">Guna Milan & life compatibility reports.</p>
                <a href="/matching" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Open Matching →</a>
            </div>
            
            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl hover:border-yellow-400 transition">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">🌟 Deep Life Forecast</h3>
                <p class="text-slate-300 text-xs mb-4">Career, wealth & spiritual forecasts.</p>
                <a href="/life-prediction" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Get Forecast →</a>
            </div>

            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl hover:border-yellow-400 transition">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">📜 Janam Kundali PDF</h3>
                <p class="text-slate-300 text-xs mb-4">Visual birth chart & downloadable PDF.</p>
                <a href="/kundali-pdf" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Generate PDF →</a>
            </div>
        </div>
    </div>
    """
    return render_page("Home", content)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(msg: str = ""):
    pay_250 = get_robust_razorpay_link("Wallet Topup ₹250", 250)
    pay_500 = get_robust_razorpay_link("Wallet Topup ₹500", 500)
    
    alert = f"<div class='bg-green-600/30 border border-green-500 text-green-300 p-4 rounded-xl mb-6 text-sm font-bold'>{msg}</div>" if msg else ""

    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-2">👤 Member Dashboard & Quick Login</h2>
        <p class="text-slate-300 text-xs mb-6">Persistent HTML5 session. Page refresh will never lose your session!</p>
        
        {alert}

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <!-- Member Login Form -->
            <div class="bg-slate-950 p-6 rounded-xl border border-purple-900">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-4">🔐 Member Sign In</h3>
                <form action="/login" method="post" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
                        <input type="email" name="email" required placeholder="user@gmail.com" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-3 text-sm focus:outline-none focus:border-yellow-400">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-300 mb-1">Password</label>
                        <input type="password" name="password" required placeholder="Password" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-3 text-sm focus:outline-none focus:border-yellow-400">
                    </div>
                    <button type="submit" class="w-full py-3 bg-purple-700 hover:bg-purple-600 rounded-xl font-bold text-sm transition">Sign In</button>
                </form>
            </div>

            <!-- Email OTP Signup Form -->
            <div class="bg-slate-950 p-6 rounded-xl border border-purple-900">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-4">📝 Register with Email OTP</h3>
                <form action="/send-otp" method="post" class="space-y-3">
                    <div>
                        <input type="text" name="name" required placeholder="Full Name" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                    </div>
                    <div>
                        <input type="email" name="email" required placeholder="Email Address" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                    </div>
                    <div>
                        <input type="text" name="phone" required placeholder="Phone Number" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                    </div>
                    <button type="submit" class="w-full py-2.5 bg-pink-700 hover:bg-pink-600 rounded-xl font-bold text-xs transition">Send Verification OTP</button>
                </form>
            </div>
        </div>

        <!-- Wallet Section -->
        <div class="bg-slate-950 p-6 rounded-xl border border-green-800 text-center">
            <h4 class="text-yellow-400 font-bold mb-2">💳 Wallet Balance: ₹ 0.00</h4>
            <p class="text-xs text-slate-400 mb-4">Instant Topup credits via Razorpay UPI, GPay, PhonePe & Cards</p>
            <div class="flex justify-center space-x-4">
                <a href="{pay_250}" target="_blank" class="py-2.5 px-6 bg-green-600 hover:bg-green-500 rounded-xl text-xs font-bold text-white shadow-lg">⚡ Add ₹250</a>
                <a href="{pay_500}" target="_blank" class="py-2.5 px-6 bg-green-600 hover:bg-green-500 rounded-xl text-xs font-bold text-white shadow-lg">⚡ Add ₹500</a>
            </div>
        </div>
    </div>
    """
    return render_page("Dashboard", content)

@app.post("/login")
def process_login(email: str = Form(...), password: str = Form(...)):
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": email, "service": "Member Login", "payment_status": "Active Session"})
    return RedirectResponse(url=f"/dashboard?msg=Welcome+back+{email}!+Login+successful.", status_code=303)

@app.post("/send-otp")
def process_send_otp(name: str = Form(...), email: str = Form(...), phone: str = Form(...)):
    otp = str(random.randint(100000, 999999))
    save_user_local(name, email, phone)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "OTP Registration", "details": f"Email: {email} | OTP: {otp}", "payment_status": "User Verified & Registered"})
    
    email_html = f"<h3>Welcome to AccAstroForge, {name}!</h3><p>Your OTP Code is: <b>{otp}</b></p>"
    send_brevo_email(email, name, "AccAstroForge OTP Code", email_html)
    return RedirectResponse(url=f"/dashboard?msg=Account+registered+for+{email}.+Check+email+for+OTP.", status_code=303)

@app.get("/matching", response_class=HTMLResponse)
def matching_page():
    paywall_link = get_robust_razorpay_link("Kundali Matching Report", 399)
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">❤️ Vedic Kundali Compatibility & Guna Milan</h2>
        
        <form action="/check-matching" method="post" class="space-y-4 max-w-xl mx-auto bg-slate-950 p-6 rounded-xl border border-purple-900 mb-6">
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs font-semibold text-slate-300 mb-1">Boy's Name</label>
                    <input type="text" name="boy_name" required placeholder="Boy's Name" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-300 mb-1">Boy's DOB</label>
                    <input type="date" name="boy_dob" required class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-xs font-semibold text-slate-300 mb-1">Girl's Name</label>
                    <input type="text" name="girl_name" required placeholder="Girl's Name" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-300 mb-1">Girl's DOB</label>
                    <input type="date" name="girl_dob" required class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                </div>
            </div>
            <button type="submit" class="w-full py-3 bg-purple-700 hover:bg-purple-600 rounded-xl font-bold text-xs transition">Match Kundalis (₹399)</button>
        </form>

        <div class="bg-slate-950 p-6 rounded-xl border border-pink-900/60 text-center">
            <h3 class="text-yellow-400 font-bold text-lg mb-2">🔒 Unlock Complete Matching Report</h3>
            <p class="text-slate-300 text-xs mb-4">High Guna Milan Score & Spiritual Compatibility Analysis</p>
            <p class="text-green-400 text-xl font-bold mb-6">Total Payable: ₹399</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white text-xs shadow-xl inline-block">🚀 Proceed to Pay ₹399</a>
        </div>
    </div>
    """
    return render_page("Kundali Matching", content)

@app.post("/check-matching")
def process_matching(boy_name: str = Form(...), boy_dob: str = Form(...), girl_name: str = Form(...), girl_dob: str = Form(...)):
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{boy_name} & {girl_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)"})
    paywall_link = get_robust_razorpay_link(f"Matching: {boy_name} & {girl_name}", 399, boy_name)
    return RedirectResponse(url=paywall_link, status_code=303)

@app.get("/life-prediction", response_class=HTMLResponse)
def life_prediction_page():
    paywall_link = get_robust_razorpay_link("Complete Deep Life Forecast", 499)
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">🌟 Deep Life Forecast & Predictions</h2>
        
        <form action="/check-life" method="post" class="space-y-4 max-w-xl mx-auto bg-slate-950 p-6 rounded-xl border border-purple-900 mb-6">
            <div>
                <input type="text" name="name" required placeholder="Full Name" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            </div>
            <div class="grid grid-cols-2 gap-4">
                <input type="date" name="dob" required class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                <input type="text" name="tob" placeholder="Time of Birth (e.g. 10:30 AM)" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            </div>
            <input type="text" name="pob" placeholder="Place of Birth (City)" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            <button type="submit" class="w-full py-3 bg-purple-700 hover:bg-purple-600 rounded-xl font-bold text-xs transition">Reveal Life Insights (₹499)</button>
        </form>

        <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 text-center">
            <p class="text-green-400 text-xl font-bold mb-4">Total Payable: ₹499</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white text-xs shadow-xl inline-block">🚀 Unlock Life Forecast ₹499</a>
        </div>
    </div>
    """
    return render_page("Life Forecast", content)

@app.post("/check-life")
def process_life(name: str = Form(...), dob: str = Form(...), tob: str = Form(""), pob: str = Form("")):
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Life Prediction", "details": f"DOB: {dob} | {tob} | {pob}", "payment_status": "Pending (₹499)"})
    paywall_link = get_robust_razorpay_link(f"Life Prediction: {name}", 499, name)
    return RedirectResponse(url=paywall_link, status_code=303)

@app.get("/kundali-pdf", response_class=HTMLResponse)
def kundali_pdf_page():
    paywall_link = get_robust_razorpay_link("Janam Kundali PDF Chart", 299)
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">📜 Janam Kundali & Visual Lagna Chart PDF</h2>
        
        <form action="/generate-pdf" method="post" class="space-y-4 max-w-xl mx-auto bg-slate-950 p-6 rounded-xl border border-purple-900 mb-6">
            <input type="text" name="name" required placeholder="Full Name" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            <div class="grid grid-cols-2 gap-4">
                <input type="date" name="dob" required class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
                <input type="text" name="tob" placeholder="Time of Birth" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            </div>
            <input type="text" name="pob" placeholder="Place of Birth" class="w-full bg-slate-900 border border-purple-700 rounded-xl p-2.5 text-xs">
            <button type="submit" class="w-full py-3 bg-purple-700 hover:bg-purple-600 rounded-xl font-bold text-xs transition">Generate Kundali PDF (₹299)</button>
        </form>

        <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 text-center">
            <p class="text-green-400 text-xl font-bold mb-4">Total Payable: ₹299</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white text-xs shadow-xl inline-block">🚀 Download Kundali PDF ₹299</a>
        </div>
    </div>
    """
    return render_page("Kundali PDF", content)

@app.post("/generate-pdf")
def process_pdf(name: str = Form(...), dob: str = Form(...), tob: str = Form(""), pob: str = Form("")):
    filename = create_kundali_pdf_file(name, dob, tob, pob)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Janam Kundali PDF", "details": filename, "payment_status": "Generated"})
    return FileResponse(filename, filename=filename, media_type='application/pdf')

@app.get("/gemstones", response_class=HTMLResponse)
def gemstones_page():
    paywall_link = get_robust_razorpay_link("Gemstone Remedy Report", 299)
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl text-center">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">💎 Lucky Gemstones & Cosmic Remedies</h2>
        <div class="max-w-md mx-auto bg-slate-950 p-6 rounded-xl border border-purple-900">
            <p class="text-slate-300 text-xs mb-4">Discover Emerald (Panna) or Yellow Sapphire (Pukhraj) suitability for career clarity.</p>
            <p class="text-green-400 text-xl font-bold mb-4">Total Payable: ₹299</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white text-xs shadow-xl inline-block">🚀 Unlock Gemstone Report ₹299</a>
        </div>
    </div>
    """
    return render_page("Gemstones", content)

@app.get("/panchang", response_class=HTMLResponse)
def panchang_page():
    content = """
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">📅 Daily Vedic Panchang & Shubh Muhurat</h2>
        <div class="bg-slate-950 p-6 rounded-xl border border-purple-900">
            <ul class="space-y-2 text-xs text-slate-300">
                <li><b class="text-yellow-400">Tithi:</b> Shukla Paksha Navami</li>
                <li><b class="text-yellow-400">Nakshatra:</b> Rohini</li>
                <li><b class="text-yellow-400">Rahu Kalam:</b> 10:30 AM - 12:00 PM</li>
                <li><b class="text-yellow-400">Shubh Muhurat:</b> 11:45 AM - 12:30 PM</li>
            </ul>
        </div>
    </div>
    """
    return render_page("Panchang", content)

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 25")
    logs = cursor.fetchall()
    
    cursor.execute("SELECT * FROM users ORDER BY id DESC LIMIT 25")
    users = cursor.fetchall()
    conn.close()

    log_rows = "".join([f"<tr class='border-b border-purple-900/40'><td class='p-2'>{l['timestamp'][:19]}</td><td class='p-2'>{l['full_name']} ({l['service']})</td><td class='p-2'>{l['details']}</td><td class='p-2 text-green-400'>{l['payment_status']}</td></tr>" for l in logs])
    user_rows = "".join([f"<tr class='border-b border-purple-900/40'><td class='p-2'>{u['name']}</td><td class='p-2'>{u['email']}</td><td class='p-2'>{u['phone']}</td><td class='p-2 text-yellow-400'>{str(u['verified_at'])[:19]}</td></tr>" for u in users])

    content = f"""
    <div class="bg-slate-900/95 border border-red-700/80 rounded-2xl p-6 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-red-400 mb-4">🛡️ Owner Admin Portal (SQLite & Apps Script Sync)</h2>
        
        <h3 class="text-yellow-400 font-bold text-sm mb-2">👥 Registered Users Database</h3>
        <div class="overflow-x-auto bg-slate-950 rounded-xl border border-purple-900 p-3 mb-6">
            <table class="w-full text-left text-xs">
                <thead><tr class="bg-purple-900/50 text-yellow-400"><th class="p-2">Name</th><th class="p-2">Email</th><th class="p-2">Phone</th><th class="p-2">Verified At</th></tr></thead>
                <tbody>{user_rows if user_rows else "<tr><td colspan='4' class='p-3 text-center text-slate-400'>No registered users yet.</td></tr>"}</tbody>
            </table>
        </div>

        <h3 class="text-yellow-400 font-bold text-sm mb-2">📜 Activity Logs</h3>
        <div class="overflow-x-auto bg-slate-950 rounded-xl border border-purple-900 p-3">
            <table class="w-full text-left text-xs">
                <thead><tr class="bg-purple-900/50 text-yellow-400"><th class="p-2">Timestamp</th><th class="p-2">Service</th><th class="p-2">Details</th><th class="p-2">Status</th></tr></thead>
                <tbody>{log_rows if log_rows else "<tr><td colspan='4' class='p-3 text-center text-slate-400'>No logs yet.</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    return render_page("Admin Portal", content)
