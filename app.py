import os
import datetime
import random
import sqlite3
import requests
import razorpay
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
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

# Mount static files (for logo.png, bg.jpg)
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
# DATABASE & BREVO / APPS SCRIPT HELPERS
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
        print(f"Local Save Error: {e}")
    
    try:
        params = {"worksheet": "Users", "name": u_name, "email": u_email.lower(), "phone": u_phone, "verified_at": now_str}
        requests.get(APPS_SCRIPT_URL, params=params, timeout=5)
    except Exception:
        pass

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
    except Exception:
        pass
    try:
        params = {"worksheet": "AdminLogs", "timestamp": ts, "full_name": fn, "service": srv, "details": dtl, "payment_status": pst}
        requests.get(APPS_SCRIPT_URL, params=params, timeout=5)
    except Exception:
        pass

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
# RAZORPAY & PDF GENERATOR
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
# MASTER GRADIO-LOOK HTML/CSS SINGLE PAGE
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index(msg: str = ""):
    pay_250 = get_robust_razorpay_link("Wallet Topup ₹250", 250)
    pay_500 = get_robust_razorpay_link("Wallet Topup ₹500", 500)
    alert_box = f"<div style='background:rgba(34,197,94,0.25); border:1px solid #22c55e; color:#4ade80; padding:12px; border-radius:12px; margin-bottom:15px; font-weight:bold; text-align:center; font-size:0.85rem;'>{msg}</div>" if msg else ""

    return f"""
    <!DOCTYPE html>
    <html lang="bn">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AccAstroForge - AI Astrology Guidance</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{
                background-color: #030014 !important;
                background-image: linear-gradient(rgba(5, 1, 20, 0.5), rgba(5, 1, 20, 0.75)), url('/static/bg.jpg') !important;
                background-position: center center !important;
                background-repeat: no-repeat !important;
                background-size: cover !important;
                background-attachment: fixed !important;
                color: #ffffff !important;
                font-family: 'Poppins', sans-serif !important;
                min-height: 100vh;
                margin: 0;
                padding: 15px;
            }}
            .cinzel {{ font-family: 'Cinzel', serif; }}
            .tab-btn {{
                background: rgba(18, 8, 42, 0.9);
                border: 1px solid rgba(244, 114, 182, 0.4);
                color: #fef08a;
                font-family: 'Cinzel', serif;
                font-weight: 700;
                font-size: 0.75rem;
                border-radius: 8px;
                padding: 8px 14px;
                cursor: pointer;
                transition: all 0.3s;
                white-space: nowrap;
            }}
            .tab-btn.active {{
                background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%);
                color: #ffffff;
                border-color: #fde047;
                box-shadow: 0 0 15px rgba(124, 58, 237, 0.6);
            }}
            .card-box {{
                background: rgba(14, 5, 35, 0.92);
                border: 1px solid rgba(244, 114, 182, 0.5);
                border-radius: 16px;
                padding: 22px;
                margin-top: 15px;
                box-shadow: 0 0 25px rgba(124, 58, 237, 0.25);
            }}
            input, select, textarea {{
                background: rgba(22, 10, 48, 0.95) !important;
                border: 1.5px solid rgba(244, 114, 182, 0.6) !important;
                color: #ffffff !important;
                border-radius: 12px !important;
                padding: 10px 14px !important;
                width: 100%;
                margin-top: 5px;
                margin-bottom: 12px;
                font-size: 0.85rem;
            }}
            label {{
                color: #fde047 !important;
                font-weight: 600;
                font-size: 0.85rem;
            }}
            .btn-primary {{
                background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%);
                color: white;
                border: 1px solid #fde047;
                font-weight: bold;
                border-radius: 12px;
                padding: 12px 20px;
                cursor: pointer;
                width: 100%;
                box-shadow: 0 4px 15px rgba(219, 39, 119, 0.4);
                font-size: 0.85rem;
            }}
            .btn-primary:hover {{
                opacity: 0.95;
            }}
        </style>
    </head>
    <body>
        <div class="max-w-5xl mx-auto">
            <!-- Header Bar -->
            <div class="flex justify-between items-center bg-slate-900/80 p-4 rounded-2xl border border-purple-900/50 backdrop-blur-md mb-4 flex-wrap gap-4">
                <div class="flex items-center space-x-3">
                    <img src="/static/logo.png" alt="Logo" class="w-12 h-12 animate-spin" style="animation-duration: 12s;">
                    <span class="cinzel text-2xl font-bold text-yellow-400">AccAstroForge</span>
                </div>
                <div class="flex items-center gap-2 bg-slate-950/80 px-4 py-2 rounded-xl border border-pink-500/40 text-xs">
                    <span class="text-yellow-400 font-semibold">🔐 Quick Logins:</span>
                    <a href="https://accounts.google.com" target="_blank" class="bg-red-600 text-white px-2.5 py-1 rounded-md font-bold hover:opacity-90">Google</a>
                    <a href="https://www.facebook.com" target="_blank" class="bg-blue-600 text-white px-2.5 py-1 rounded-md font-bold hover:opacity-90">Facebook</a>
                </div>
            </div>

            {alert_box}

            <!-- Tabs Navigation (Exact Gradio Look) -->
            <div class="flex overflow-x-auto gap-2 p-2 bg-slate-900/90 rounded-xl border border-pink-500/40 mb-4" id="tab-list">
                <button class="tab-btn active" onclick="switchTab('dashboard')">👤 DASHBOARD</button>
                <button class="tab-btn" onclick="switchTab('life')">🌟 LIFE PREDICTION</button>
                <button class="tab-btn" onclick="switchTab('horoscope')">☀️ HOROSCOPE</button>
                <button class="tab-btn" onclick="switchTab('matching')">❤️ MATCHING</button>
                <button class="tab-btn" onclick="switchTab('gemstones')">💎 GEMSTONES</button>
                <button class="tab-btn" onclick="switchTab('kundali')">📜 KUNDALI & BIRTH PDF</button>
                <button class="tab-btn" onclick="switchTab('numerology')">🔢 NUMEROLOGY</button>
                <button class="tab-btn" onclick="switchTab('panchang')">📅 PANCHANG</button>
                <button class="tab-btn" onclick="switchTab('ai')">🤖 AI ASSISTANT</button>
                <button class="tab-btn" onclick="switchTab('legal')">⚖️ LEGAL</button>
            </div>

            <!-- TAB 1: DASHBOARD -->
            <div id="tab-dashboard" class="tab-content card-box">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">👤 User Profile, Wallet & Order History</h3>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    <!-- Login Box -->
                    <div class="bg-slate-950 p-5 rounded-xl border border-purple-800">
                        <h4 class="text-yellow-400 font-bold text-sm mb-3">🔐 Active User Session</h4>
                        <p class="text-xs text-slate-300 mb-3">Sign in or register for full features</p>
                        <form action="/login" method="post" class="space-y-2">
                            <input type="email" name="email" required placeholder="Registered Email">
                            <input type="password" name="password" required placeholder="Password">
                            <button type="submit" class="btn-primary text-xs py-2">Sign In to Account</button>
                        </form>
                    </div>

                    <!-- Wallet Topup Box -->
                    <div class="bg-slate-950 p-5 rounded-xl border border-purple-800 text-center flex flex-col justify-between">
                        <div>
                            <h4 class="text-yellow-400 font-bold text-sm mb-1">💳 Wallet Balance: <span class="text-green-400">₹ 0.00</span></h4>
                            <p class="text-xs text-slate-300 mb-4">Instant topup credits via Razorpay UPI, Cards & Netbanking</p>
                        </div>
                        <div class="flex justify-center gap-3">
                            <a href="{pay_250}" target="_blank" class="w-full bg-green-600 hover:bg-green-500 text-white font-bold text-xs py-2.5 rounded-xl shadow-lg">⚡ Add ₹250</a>
                            <a href="{pay_500}" target="_blank" class="w-full bg-green-600 hover:bg-green-500 text-white font-bold text-xs py-2.5 rounded-xl shadow-lg">⚡ Add ₹500</a>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: LIFE PREDICTION -->
            <div id="tab-life" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">🌌 Vedic Astrology & Deep Life Forecast</h3>
                <form action="/check-life" method="post">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Full Name</label><input type="text" name="name" required placeholder="Full Name"></div>
                        <div><label>Date of Birth</label><input type="date" name="dob" required></div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Time of Birth</label><input type="text" name="tob" placeholder="e.g. 10:30 AM"></div>
                        <div><label>Place of Birth</label><input type="text" name="pob" placeholder="City, State"></div>
                    </div>
                    <button type="submit" class="btn-primary mt-2">✨ Reveal Detailed Life Insights (₹499)</button>
                </form>
            </div>

            <!-- TAB 3: HOROSCOPE -->
            <div id="tab-horoscope" class="tab-content card-box text-center" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">🔮 Daily Zodiac Predictions</h3>
                <select class="max-w-xs mx-auto mb-4">
                    <option>Aries (Mesha)</option><option>Taurus (Vrishabha)</option><option>Gemini (Mithuna)</option>
                    <option>Cancer (Karka)</option><option>Leo (Simha)</option><option>Virgo (Kanya)</option>
                </select>
                <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 max-w-lg mx-auto">
                    <p class="text-green-400 text-sm font-semibold">✨ Today brings high cosmic energy. Planetary transits indicate financial growth and emotional peace.</p>
                </div>
            </div>

            <!-- TAB 4: MATCHING -->
            <div id="tab-matching" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">💍 Vedic Compatibility & Guna Milan</h3>
                <form action="/check-matching" method="post">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Boy's Name</label><input type="text" name="boy_name" required placeholder="Boy's Name"></div>
                        <div><label>Boy's DOB</label><input type="date" name="boy_dob" required></div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Girl's Name</label><input type="text" name="girl_name" required placeholder="Girl's Name"></div>
                        <div><label>Girl's DOB</label><input type="date" name="girl_dob" required></div>
                    </div>
                    <button type="submit" class="btn-primary mt-2">❤️ Match Kundalis Now (₹399)</button>
                </form>
            </div>

            <!-- TAB 5: GEMSTONES -->
            <div id="tab-gemstones" class="tab-content card-box text-center" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">🧿 Lucky Gemstones & Remedies</h3>
                <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 max-w-md mx-auto">
                    <p class="text-slate-300 text-xs mb-4">Discover Emerald (Panna) or Yellow Sapphire (Pukhraj) suitability for success.</p>
                    <a href="{get_robust_razorpay_link('Gemstone Report', 299)}" target="_blank" class="btn-primary inline-block">🚀 Unlock Gemstone Report (₹299)</a>
                </div>
            </div>

            <!-- TAB 6: KUNDALI & BIRTH PDF -->
            <div id="tab-kundali" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">📜 Janam Kundali & Lagna Birth Chart Generator</h3>
                <form action="/generate-pdf" method="post">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Full Name</label><input type="text" name="name" required placeholder="Full Name"></div>
                        <div><label>Date of Birth</label><input type="date" name="dob" required></div>
                    </div>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div><label>Time of Birth</label><input type="text" name="tob" placeholder="e.g. 08:15 PM"></div>
                        <div><label>Place of Birth</label><input type="text" name="pob" placeholder="City"></div>
                    </div>
                    <button type="submit" class="btn-primary mt-2">📜 Generate Birth Chart & PDF (₹299)</button>
                </form>
            </div>

            <!-- TAB 7: NUMEROLOGY -->
            <div id="tab-numerology" class="tab-content card-box text-center" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">🔢 Numerology Calculator</h3>
                <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 max-w-md mx-auto">
                    <p class="text-yellow-400 text-lg font-bold mb-2">Psychic Life Number: 7</p>
                    <p class="text-xs text-slate-300">Strong analytical abilities and deep spiritual focus predicted.</p>
                </div>
            </div>

            <!-- TAB 8: PANCHANG -->
            <div id="tab-panchang" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">📅 Daily Vedic Panchang</h3>
                <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 max-w-md mx-auto">
                    <ul class="space-y-2 text-xs text-slate-300">
                        <li><b class="text-yellow-400">Tithi:</b> Shukla Paksha Navami</li>
                        <li><b class="text-yellow-400">Nakshatra:</b> Rohini</li>
                        <li><b class="text-yellow-400">Rahu Kalam:</b> 10:30 AM - 12:00 PM</li>
                    </ul>
                </div>
            </div>

            <!-- TAB 9: AI ASSISTANT -->
            <div id="tab-ai" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">🤖 Ask Your Personal AI Astrologer</h3>
                <textarea rows="3" placeholder="Ask any question regarding career, marriage, health..."></textarea>
                <button class="btn-primary mt-2">Ask Assistant ✨</button>
            </div>

            <!-- TAB 10: LEGAL -->
            <div id="tab-legal" class="tab-content card-box" style="display:none;">
                <h3 class="cinzel text-xl font-bold text-yellow-400 mb-4">⚖️ Terms & Social Handles</h3>
                <p class="text-xs text-slate-300 mb-4">All predictions are for guidance purposes based on traditional Vedic Astrology principles.</p>
                <p class="text-xs text-yellow-400 font-bold">Official Handles:</p>
                <ul class="text-xs text-slate-300 space-y-1 mt-2">
                    <li>Twitter (X): <a href="https://x.com/AccAstroForge" target="_blank" class="text-blue-400 underline">https://x.com/AccAstroForge</a></li>
                    <li>Instagram: <a href="https://www.instagram.com/accastroforge/" target="_blank" class="text-pink-400 underline">https://www.instagram.com/accastroforge/</a></li>
                </ul>
            </div>
        </div>

        <script>
            function switchTab(tabId) {{
                document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
                document.getElementById('tab-' + tabId).style.display = 'block';
                if(event && event.currentTarget) {{
                    event.currentTarget.classList.add('active');
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.post("/login")
def login(email: str = Form(...)):
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": email, "service": "Member Login", "payment_status": "Active Session"})
    return RedirectResponse(url="/?msg=Login+successful+for+" + email, status_code=303)

@app.post("/check-matching")
def matching(boy_name: str = Form(...), girl_name: str = Form(...)):
    link = get_robust_razorpay_link(f"Kundali Matching: {boy_name} & {girl_name}", 399, boy_name)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{boy_name} & {girl_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)"})
    return RedirectResponse(url=link, status_code=303)

@app.post("/check-life")
def life(name: str = Form(...)):
    link = get_robust_razorpay_link(f"Life Prediction: {name}", 499, name)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Life Prediction", "payment_status": "Pending (₹499)"})
    return RedirectResponse(url=link, status_code=303)

@app.post("/generate-pdf")
def pdf(name: str = Form(...), dob: str = Form(...), tob: str = Form(""), pob: str = Form("")):
    filename = create_kundali_pdf_file(name, dob, tob, pob)
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": name, "service": "Janam Kundali PDF", "details": filename, "payment_status": "Generated"})
    return FileResponse(filename, filename=filename, media_type='application/pdf')
