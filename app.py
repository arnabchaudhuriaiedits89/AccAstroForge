import base64
import datetime
import json
import os
import io
import random
import requests
import hashlib
import gradio as gr
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import razorpay

# ---------------------------------------------------------
# 0. CONFIGURATIONS & SECRETS
# ---------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_live_TpnrjMektRCWj8")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "tm4Ry6xdY63egZtf5cD0kP8T")
RAZORPAY_ME_URL = "https://razorpay.me/@accastroforge"

PROKERALA_CLIENT_ID = "ffb5cc5c-e8c7-4cde-bec3-3c608af33a33"
PROKERALA_CLIENT_SECRET = "LXih7EzrT4ym7GXA@4ykOyHv1mofs4RxmWhzChgX"

GOOGLE_CLIENT_ID = "967117558722-40q6p107agttv35a47jlmq907j87bnpp.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "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"
GOOGLE_REDIRECT_URI = "https://accastroforge.in/"

FACEBOOK_APP_ID = "1487294163221538"
FACEBOOK_APP_SECRET = "b0bacbcf5968b456843fe66aeea8af47"
FACEBOOK_REDIRECT_URI = "https://accastroforge.in/"

# OFFICIAL TWITTER DIRECT OAUTH 2.0 QUICK LOGIN (Updated & Cleaned)
TWITTER_CLIENT_ID = "Vy1ke1RKM1pjQWFQbzF1b1VPTGc6MTpjaQ"
TWITTER_CLIENT_SECRET = "ap6gCWmf05A9fcu7w6mKqKbyMkT1M_wry7uzRjSdtaPhQ1aXBj"
TWITTER_OAUTH_URL = f"https://x.com/i/oauth2/authorize?response_type=code&client_id={TWITTER_CLIENT_ID}&redirect_uri=https://accastroforge.in/login/twitter/callback&scope=users.read%20tweet.read&state=state&code_challenge=challenge&code_challenge_method=plain"

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

LOG_FILE = "admin_logs.json"


def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_log(user_data):
    logs = load_logs()
    logs.append(user_data)
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving log: {e}")


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")

logo_path = "logo.png" if os.path.exists("logo.png") else None


def get_base64(file_path):
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
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
# 2. ASTROLOGICAL ENGINE & KUNDALI GENERATOR
# ---------------------------------------------------------
ZODIAC_SIGNS = [
    "Aries (Mesha)", "Taurus (Vrishabha)", "Gemini (Mithuna)", "Cancer (Karka)",
    "Leo (Simha)", "Virgo (Kanya)", "Libra (Tula)", "Scorpio (Vrischika)",
    "Sagittarius (Dhanu)", "Capricorn (Makara)", "Aquarius (Kumbha)", "Pisces (Meena)"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
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
# 3. REPORTLAB PDF & RAZORPAY PAYWALL
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
        textColor=colors.HexColor('#5b21b6'),
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3e8ff')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#db2777')),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=11, leading=15)
    story.append(Paragraph("<b>Vedic Astrological Insights:</b>", styles['Heading2']))
    story.append(Paragraph(f"Based on birth details of {profile['name']}, Jupiter aligns favorably in the trikona houses. Remedies include wearing auspicious gemstones and practicing daily morning meditation.", body_style))
    
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
    pay_url = get_robust_razorpay_link(service_name, price, display_name)
    
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5);">
        <h3 style="color: #fde047 !important; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{price} ONLY)</h3>
        <p style="color: #f3e8ff !important; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePay, BHIM or Cards.</p>
        <p style="color: #4ade80 !important; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{price}</p>
        
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white !important; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">
            🚀 Proceed to Pay ₹{price} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """


# ---------------------------------------------------------
# 4. SOCIAL OAUTH & SIGNUP HANDLERS (GOOGLE, FACEBOOK & TWITTER)
# ---------------------------------------------------------
GOOGLE_OAUTH_URL = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=token&scope=email%20profile"
FACEBOOK_OAUTH_URL = f"https://www.facebook.com/v12.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={FACEBOOK_REDIRECT_URI}&response_type=token&scope=email,public_profile"


def handle_manual_signup(name, email, phone, password):
    u_name = name.strip() if name else "New User"
    u_email = email.strip() if email else "N/A"
    u_phone = phone.strip() if phone else "N/A"
    
    if not u_email or "@" not in u_email:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Please enter a valid email address.</span>", f"👤 Guest User", "₹ 0.00", "No active sessions."
    if not u_phone or len(u_phone) < 10:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Please enter a valid 10-digit Phone Number.</span>", f"👤 Guest User", "₹ 0.00", "No active sessions."
    
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Manual Account Registration",
        "details": f"Email: {u_email} | Phone: {u_phone}",
        "payment_status": "Registered & Active"
    })
    
    success_msg = f"<div style='background:rgba(34,197,94,0.15); border:1px solid #22c55e; padding:15px; border-radius:12px; color:#ffffff;'><h3 style='color:#4ade80; margin:0 0 5px 0;'>✨ Welcome to AccAstroForge, {u_name}!</h3><p style='margin:0;'>Your account has been created successfully with <b>{u_email}</b> (Phone: {u_phone}).</p></div>"
    profile_box = f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #4ade80;'>Phone: {u_phone}</span><br><span style='color: #fde047;'>Status: Active Member</span>"
    wallet_box = "₹ 0.00"
    history_box = f"• Account Registered Successfully<br>• Contact: {u_phone}<br>• Initial Wallet: ₹0.00"
    
    return success_msg, profile_box, wallet_box, history_box


def run_daily_horoscope(sign):
    return f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>🔮 Daily Vedic Horoscope for {sign}</h3><p>Today brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace in personal relationships. Wear yellow or amber for extra luck!</p></div>"""


def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b_name} & {g_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)"})
    
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>❤️ Kundali Compatibility Teaser for {b_name} & {g_name}</h3><p>High Guna Milan score detected! Excellent long-term emotional and spiritual alignment observed.</p></div>"""
    return teaser_text, get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")


def run_life_predictions(name, dob, tob, pob, focus_area, question, phone, email, address):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Complete Life Prediction", "payment_status": "Pending (₹499)"})
    
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
    save_log({"timestamp": str(datetime.datetime.now()), "service": "Gemstone Remedy", "details": f"DOB: {dob} | Zodiac: {zodiac}", "payment_status": "Pending (₹299)"})
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>💎 Gemstone Guidance Teaser</h3><p>Favorable alignment detected for {zodiac}. Emerald (Panna) or Yellow Sapphire (Pukhraj) recommended to boost career clarity.</p></div>"""
    return teaser_text, get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")


def run_kundali_pdf(name, dob, tob, pob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Janam Kundali PDF", "payment_status": "Pending (₹299)"})
    
    chart_html = generate_visual_kundali_chart_html(u_name, dob if dob else "2000-01-01", tob, pob)
    pdf_file = create_kundali_pdf_file(u_name, dob if dob else "2000-01-01", tob, pob)
    teaser_text = f"""<div style='color:#ffffff;'><h3 style='color:#fde047;'>📜 Janam Kundali & Birth Chart Generated for {u_name}</h3><p>Your detailed Lagna chart and PDF preview have been generated successfully below.</p></div>"""
    return teaser_text, chart_html, pdf_file, get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, u_name)


def run_numerology(name, dob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Numerology", "payment_status": "Pending (₹249)"})
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
    pay_url = get_robust_razorpay_link(f"AccAstroForge Wallet Topup (₹{amount})", amount, "Valued Customer")
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center; margin-top: 10px;">
        <h4 style="color: #4ade80 !important; margin-bottom: 5px;">💳 Add ₹{amount} to AccAstroForge Credits</h4>
        <p style="color: #ffffff !important; font-size: 0.85rem; margin-bottom: 10px;">Click below to add credits via Razorpay UPI or Cards instantly.</p>
        <a href="{pay_url}" target="_blank" style="background: #22c55e; color: white !important; padding: 8px 20px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block;">
            ⚡ Pay ₹{amount} & Top Up Wallet
        </a>
    </div>
    """


def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "<span style='color:#ef4444; font-weight:bold;'>❌ Incorrect Password! Access Denied.</span>"

    logs = load_logs()
    if not logs:
        return "<span style='color:#fde047;'>📭 No user logs found yet.</span>"

    summary_html = f"<div style='color:#fff;'><h3 style='color:#fde047;'>🛡️ AccAstroForge Admin Dashboard</h3><p><b>Total User Entries:</b> {len(logs)}</p><table style='width:100%; border-collapse:collapse; border:1px solid #7c3aed;' border='1'><tr style='background:#5b21b6; color:#fff;'><th>Timestamp</th><th>Name/Service</th><th>Details</th><th>Status</th></tr>"
    for log in reversed(logs):
        summary_html += f"<tr><td>{log.get('timestamp', '')[:19]}</td><td>{log.get('full_name', 'N/A')} ({log.get('service', 'General')})</td><td>{log.get('details', 'N/A')}</td><td>{log.get('payment_status', 'Pending')}</td></tr>"
    summary_html += "</table></div>"
    return summary_html


# ---------------------------------------------------------
# 5. HARDCORE CSS & INJECTED EYE-TOGGLE JAVASCRIPT
# ---------------------------------------------------------
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');

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

footer, header, #footer, .footer, .built-with, a[href*="huggingface.co/space"] {
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
    right: 12px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
    cursor: pointer !important;
    font-size: 1.2rem !important;
    z-index: 9999 !important;
    user-select: none !important;
    background: rgba(124, 58, 237, 0.3) !important;
    border: 1px solid #fde047 !important;
    border-radius: 50% !important;
    padding: 2px 6px !important;
    line-height: 1 !important;
}

#manual-signup-trigger, #real-hidden-trigger {
    display: none !important;
}
"""

head_html = """
<script>
function attachEyeToggle() {
    const passInputs = document.querySelectorAll('input[type="password"]');
    passInputs.forEach(input => {
        if (!input.classList.contains('eye-attached')) {
            input.classList.add('eye-attached');
            
            const parent = input.parentElement;
            if(parent) {
                parent.style.position = 'relative';
                
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
    });
}

setInterval(attachEyeToggle, 300);
document.addEventListener("DOMContentLoaded", attachEyeToggle);
</script>
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance", head=head_html, css=custom_css) as demo:
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
                    <a href="{TWITTER_OAUTH_URL}" target="_blank" style="color: #fff !important; background: #1da1f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Twitter</a>
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

                with gr.Row():
                    with gr.Column():
                        user_profile_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                            <div>
                                <h4 style="color: #fde047 !important; margin-bottom: 4px;">👤 Active User Session</h4>
                                <p style="color: #ffffff !important; font-size: 0.95rem; margin: 0;">Guest User (Please Sign Up / Login)</p>
                            </div>
                            <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border: 1px solid #fde047; padding: 8px 18px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; cursor: pointer; box-shadow: 0 0 15px rgba(219, 39, 119, 0.6); white-space: nowrap;">
                                📝 SIGN UP
                            </button>
                        </div>
                        """)
                    with gr.Column():
                        wallet_balance_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; margin-bottom: 15px;">
                            <h4 style="color: #fde047 !important; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80 !important;">₹ 0.00</span></h4>
                            <p style="color: #f3e8ff !important; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking of reports.</p>
                        </div>
                        """)

                with gr.Group(visible=False) as signup_group:
                    with gr.Accordion("📝 Create Your AccAstroForge Account (Manual Registration)", open=True):
                        with gr.Row():
                            signup_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                            signup_email = gr.Textbox(label="Email Address", placeholder="e.g. user@gmail.com")
                        with gr.Row():
                            signup_phone = gr.Textbox(label="Phone Number (Mandatory)", placeholder="e.g. 9876543210")
                            signup_pass = gr.Textbox(label="Create Password", type="password", placeholder="Enter secure password")
                        signup_btn = gr.Button("✨ Complete Manual Registration", variant="primary")
                        signup_output = gr.HTML()

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
                    outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display]
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
                submit_kundali_pdf.click(fn=run_kundali_pdf, inputs=[k_name, k_dob, k_tob, k_pob], outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall])

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
                    <p style="font-size: 0.85rem;">We value user privacy. User profile data collected during Google/Facebook/Twitter login is stored securely and never shared with third parties.</p>
                    <hr style="border-color: rgba(244, 114, 182, 0.2); margin: 15px 0;">
                    <h4 style="color: #fde047 !important;">📧 Support Contact & Official Handles</h4>
                    <p style="font-size: 0.85rem; margin-bottom: 8px;">For any support or queries, reach out to us at: <a href="mailto:support@accastroforge.in" style="color: #fde047 !important; font-weight: 700;">support@accastroforge.in</a></p>
                    <p style="font-size: 0.85rem;">Connect with us on our official social platforms:</p>
                    <ul style="list-style-type: none; padding-left: 0; margin-top: 10px; line-height: 2.2;">
                        <li>🌐 <span style="color: #fde047 !important; font-weight: 700;">Twitter (X):</span> <a href="https://x.com/AccAstroForge" target="_blank" style="color: #38bdf8 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://x.com/AccAstroForge</a></li>
                        <li>📸 <span style="color: #fde047 !important; font-weight: 700;">Instagram:</span> <a href="https://www.instagram.com/accastroforge/" target="_blank" style="color: #f472b6 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.instagram.com/accastroforge/</a></li>
                        <li>🌀 <span style="color: #fde047 !important; font-weight: 700;">Threads:</span> <a href="https://www.threads.com/@accastroforge" target="_blank" style="color: #e879f9 !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.threads.com/@accastroforge</a></li>
                        <li>📘 <span style="color: #fde047 !important; font-weight: 700;">Facebook:</span> <a href="https://www.facebook.com/accastroforge/" target="_blank" style="color: #60a5fa !important; font-weight: 600; text-decoration: underline; margin-left: 5px;">https://www.facebook.com/accastroforge/</a></li>
                    </ul>
                </div>
                """)

        signup_state = gr.State(value=False)
        manual_signup_trigger = gr.Button("Trigger Signup", elem_id="manual-signup-trigger")
        manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state], outputs=[signup_state, signup_group])

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
