import os
import datetime
import random
import sqlite3
import requests
import razorpay
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# Static files mount
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
                "callback_url": "https://accastroforge.in/",
                "callback_method": "get"
            }
            response = razorpay_client.payment_link.create(data)
            if response and "short_url" in response:
                return response["short_url"]
    except Exception:
        pass
    return RAZORPAY_ME_URL

# ---------------------------------------------------------
# MASTER HTML TEMPLATE WITH FULL NAVIGATION
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
        
        <!-- Navbar -->
        <header class="w-full border-b border-purple-900/50 bg-slate-900/90 backdrop-blur-md py-4 px-6 flex flex-wrap justify-between items-center sticky top-0 z-50">
            <div class="flex items-center space-x-3">
                <img src="/static/logo.png" alt="Logo" class="w-12 h-12 animate-spin" style="animation-duration: 12s;">
                <span class="cinzel text-xl font-bold text-yellow-400 tracking-wider">AccAstroForge</span>
            </div>
            <nav class="space-x-3 text-xs md:text-sm font-semibold flex flex-wrap items-center">
                <a href="/" class="hover:text-yellow-400 transition">🏠 Home</a>
                <a href="/dashboard" class="hover:text-yellow-400 transition">👤 Dashboard</a>
                <a href="/life-prediction" class="hover:text-yellow-400 transition">🌟 Life Forecast</a>
                <a href="/horoscope" class="hover:text-yellow-400 transition">☀️ Horoscope</a>
                <a href="/matching" class="hover:text-yellow-400 transition">❤️ Matching</a>
                <a href="/kundali-pdf" class="hover:text-yellow-400 transition">📜 Kundali PDF</a>
                <a href="/admin" class="text-red-400 hover:text-red-300 transition">🛡️ Admin</a>
            </nav>
        </header>

        <!-- Main Body -->
        <main class="flex-grow max-w-4xl w-full mx-auto p-6 my-6">
            {body_content}
        </main>

        <!-- Footer -->
        <footer class="w-full text-center py-6 border-t border-purple-900/40 text-xs text-slate-400 bg-slate-950/90">
            © 2026 AccAstroForge.in | Vedic Astrology & AI Powered Solutions. All rights reserved.
        </footer>
    </body>
    </html>
    """

@app.get("/", response_class=HTMLResponse)
def home_page():
    content = """
    <div class="text-center py-12">
        <h1 class="cinzel text-4xl md:text-5xl font-extrabold text-yellow-400 mb-4 drop-shadow-lg">✨ Discover Your Cosmic Destiny</h1>
        <p class="text-slate-300 text-lg max-w-2xl mx-auto mb-8">Lightning-fast FastAPI + HTML5 Vedic Astrology, Janam Kundali matching, and Deep Life Forecast platform.</p>
        
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">❤️ Kundali Matching</h3>
                <p class="text-slate-300 text-xs mb-4">Check Guna Milan and compatibility.</p>
                <a href="/matching" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Open Matching →</a>
            </div>
            
            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">🌟 Life Forecast</h3>
                <p class="text-slate-300 text-xs mb-4">Detailed career and wealth reports.</p>
                <a href="/life-prediction" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Get Prediction →</a>
            </div>

            <div class="bg-slate-900/90 border border-purple-700/60 p-6 rounded-2xl shadow-xl">
                <h3 class="cinzel text-lg font-bold text-yellow-400 mb-2">📜 Janam Kundali PDF</h3>
                <p class="text-slate-300 text-xs mb-4">Generate Lagna chart & PDF report.</p>
                <a href="/kundali-pdf" class="inline-block py-2 px-4 bg-purple-700 hover:bg-purple-600 rounded-xl text-xs font-bold transition">Generate PDF →</a>
            </div>
        </div>
    </div>
    """
    return render_page("Home", content)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    content = """
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-8 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">👤 Member Dashboard & Secure Session</h2>
        <p class="text-slate-300 text-sm mb-6">High-speed FastAPI persistent session. No more Gradio refresh wiping!</p>
        
        <div class="bg-slate-950 p-6 rounded-xl border border-slate-800 mb-6">
            <h4 class="text-yellow-400 font-bold mb-2">💳 Wallet Balance: ₹ 0.00</h4>
            <p class="text-xs text-slate-400 mb-4">Top up credits via Razorpay UPI, GPay, PhonePe or Cards.</p>
            <a href="https://razorpay.me/@accastroforge" target="_blank" class="py-2 px-4 bg-green-600 hover:bg-green-500 rounded-xl text-sm font-bold text-white shadow-lg inline-block">⚡ Top Up Wallet (Razorpay)</a>
        </div>
    </div>
    """
    return render_page("Dashboard", content)

@app.get("/horoscope", response_class=HTMLResponse)
def horoscope_page():
    content = """
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-8 shadow-2xl text-center">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">🔮 Daily Vedic Horoscope</h2>
        <div class="max-w-md mx-auto bg-slate-950 p-6 rounded-xl border border-purple-900 mt-4">
            <p class="text-green-400 text-sm font-semibold">✨ Today brings high cosmic energy, financial opportunities, and peace in personal relationships. Wear yellow or amber for extra luck!</p>
        </div>
    </div>
    """
    return render_page("Horoscope", content)

@app.get("/matching", response_class=HTMLResponse)
def matching_page():
    paywall_link = get_robust_razorpay_link("Complete Kundali Matching Report", 399, "Valued User")
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-8 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">❤️ Vedic Kundali Compatibility & Guna Milan</h2>
        <div class="bg-slate-950 p-6 rounded-xl border border-pink-900/60 text-center mt-4">
            <h3 class="text-yellow-400 font-bold text-lg mb-2">🔒 Complete Kundali Matching Teaser</h3>
            <p class="text-slate-300 text-sm mb-4">High Guna Milan score detected! Excellent emotional and spiritual alignment.</p>
            <p class="text-green-400 text-xl font-bold mb-6">Total Payable: ₹399</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white shadow-xl hover:opacity-90 transition inline-block">
                🚀 Proceed to Pay ₹399 (UPI, GPay, Cards)
            </a>
        </div>
    </div>
    """
    return render_page("Kundali Matching", content)

@app.get("/life-prediction", response_class=HTMLResponse)
def life_prediction_page():
    paywall_link = get_robust_razorpay_link("Complete Life Prediction Report", 499, "Valued User")
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-8 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">🌟 Deep Life Forecast & Predictions</h2>
        <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 text-center mt-4">
            <h3 class="text-yellow-400 font-bold text-lg mb-2">🔒 Full Life Forecast PDF & Consultation</h3>
            <p class="text-slate-300 text-sm mb-4">Discover planetary transits affecting career, wealth, and marriage.</p>
            <p class="text-green-400 text-xl font-bold mb-6">Total Payable: ₹499</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white shadow-xl hover:opacity-90 transition inline-block">
                🚀 Unlock Life Forecast ₹499
            </a>
        </div>
    </div>
    """
    return render_page("Life Prediction", content)

@app.get("/kundali-pdf", response_class=HTMLResponse)
def kundali_pdf_page():
    paywall_link = get_robust_razorpay_link("Full Janam Kundali PDF Chart", 299, "Valued User")
    content = f"""
    <div class="bg-slate-900/95 border border-purple-800 rounded-2xl p-8 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-yellow-400 mb-4">📜 Janam Kundali & Lagna Chart PDF</h2>
        <div class="bg-slate-950 p-6 rounded-xl border border-purple-900 text-center mt-4">
            <h3 class="text-yellow-400 font-bold text-lg mb-2">🔒 Complete Lagna Kundali PDF Report</h3>
            <p class="text-slate-300 text-sm mb-4">Get your complete astrological birth chart and Dasha details.</p>
            <p class="text-green-400 text-xl font-bold mb-6">Total Payable: ₹299</p>
            <a href="{paywall_link}" target="_blank" class="py-3 px-6 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-bold text-white shadow-xl hover:opacity-90 transition inline-block">
                🚀 Download Kundali PDF ₹299
            </a>
        </div>
    </div>
    """
    return render_page("Kundali PDF", content)

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admin_logs ORDER BY id DESC LIMIT 25")
    logs = cursor.fetchall()
    conn.close()

    rows_html = ""
    for l in logs:
        rows_html += f"<tr class='border-b border-purple-900/40'><td class='p-3'>{l['timestamp'][:19]}</td><td class='p-3'>{l['full_name']} ({l['service']})</td><td class='p-3'>{l['details']}</td><td class='p-3 text-green-400'>{l['payment_status']}</td></tr>"

    content = f"""
    <div class="bg-slate-900/95 border border-red-700/80 rounded-2xl p-8 shadow-2xl">
        <h2 class="cinzel text-2xl font-bold text-red-400 mb-4">🛡️ Owner Admin Portal & System Logs</h2>
        <p class="text-slate-300 text-sm mb-6">Live SQLite database tracking of user activity and payments.</p>
        
        <div class="overflow-x-auto bg-slate-950 rounded-xl border border-purple-900 p-4">
            <table class="w-full text-left text-xs">
                <thead>
                    <tr class="bg-purple-900/50 text-yellow-400">
                        <th class="p-3">Timestamp</th>
                        <th class="p-3">Name / Service</th>
                        <th class="p-3">Details</th>
                        <th class="p-3">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else "<tr><td colspan='4' class='p-4 text-center text-slate-400'>No logs found yet.</td></tr>"}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_page("Admin Portal", content)
