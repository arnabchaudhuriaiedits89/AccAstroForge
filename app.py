import base64
import datetime
import json
import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "support@accastroforge.in")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your_gmail_app_password_here")

PROKERALA_CLIENT_ID = os.getenv("PROKERALA_CLIENT_ID", "ffb5cc5c-e8c7-4cde-bec3-3c608af33a33")
PROKERALA_CLIENT_SECRET = os.getenv("PROKERALA_CLIENT_SECRET", "LXih7EzrT4ym7GXA@4ykOyHv1mofs4RxmWhzChgX")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "967117558722-40q6p107agttv35a47jlmq907j87bnpp.apps.googleusercontent.com")
GOOGLE_REDIRECT_URI = "https://accastroforge.in/"

FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID", "1487294163221538")
FACEBOOK_REDIRECT_URI = "https://accastroforge.in/"

TWITTER_CLIENT_ID = os.getenv("TWITTER_CLIENT_ID", "VlVoTTA2WEFJNzdTWlp5X2llV186MTpjaQ")
TWITTER_REDIRECT_URI = "https://accastroforge.in/login/twitter/callback"

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
except Exception:
    razorpay_client = None

LOG_FILE = "admin_logs.json"
ACTIVE_OTPS = {}

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
spin_logo_file = "AccAstroForge Zodiac Logo Text Cut Through TRANSPERANT.png"

def get_base64(file_path):
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return ""
    return ""

logo_b64 = get_base64(logo_path)
spin_b64 = get_base64(spin_logo_file)

spin_logo_src = "data:image/png;base64," + spin_b64 if spin_b64 else "https://raw.githubusercontent.com/arnabchaudhuriaiedits89/AccAstroForge/main/favicon.png"

if logo_b64:
    logo_src = "data:image/png;base64," + logo_b64
    logo_element = f"""
    <div class="header-container" style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <img src="{logo_src}" alt="AccAstroForge Logo" style="height: 70px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7)); background: transparent !important;">
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
            <span style="font-size: 26px; font-weight: 800; color: #fbcfe8; font-family: 'Cinzel', serif;">AccAstroForge</span>
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
# 3. REPORTLAB PDF & PAYWALL
# ---------------------------------------------------------
def create_kundali_pdf_file(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, textColor=colors.HexColor('#5b21b6'), alignment=1, spaceAfter=15
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
        print(f"Razorpay API fallback triggered due to: {e}")
    
    return RAZORPAY_ME_URL

def get_paywall_html(service_name, price, user_name="User", bypass_active=False):
    if bypass_active:
        return f"""
        <div style="background: rgba(34, 197, 94, 0.15); border: 2px solid #22c55e; padding: 18px; border-radius: 16px; margin-top: 15px; text-align: center;">
            <h3 style="color: #4ade80; margin-bottom: 5px; font-family: 'Cinzel', serif;">🔓 ADMIN FREE BYPASS ACTIVE</h3>
            <p style="color: #ffffff; font-size: 0.95rem; margin: 0;">Paywall suppressed for administrative testing. Full detailed report and PDF unlock granted.</p>
        </div>
        """

    display_name = user_name.strip() if user_name and user_name.strip() else "User"
    pay_url = get_robust_razorpay_link(service_name, price, display_name)
    
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5);">
        <h3 style="color: #fde047; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{price} ONLY)</h3>
        <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 12px;">Dear <span style="color: #fde047 !important; font-weight: 700;">{display_name}</span>, click below to open secure Razorpay checkout for instant payment via UPI, GPay, PhonePay, BHIM or Cards.</p>
        <p style="color: #4ade80; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{price}</p>
        
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">
            🚀 Proceed to Pay ₹{price} (UPI, GPay, PhonePe & Cards)
        </a>
    </div>
    """

# ---------------------------------------------------------
# 4. EMAIL OTP & AUTH HANDLERS
# ---------------------------------------------------------
GOOGLE_OAUTH_URL = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&response_type=token&scope=email%20profile"
FACEBOOK_OAUTH_URL = f"https://www.facebook.com/v12.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={FACEBOOK_REDIRECT_URI}&response_type=token&scope=email,public_profile"
TWITTER_OAUTH_URL = f"https://twitter.com/i/oauth2/authorize?response_type=code&client_id={TWITTER_CLIENT_ID}&redirect_uri={TWITTER_REDIRECT_URI}&scope=tweet.read%20users.read&state=state&code_challenge=challenge&code_challenge_method=plain"

def send_real_email_otp(email):
    u_email = email.strip() if email else ""
    if not u_email or "@" not in u_email:
        return "<span style='color: #f87171;'>❌ Please enter a valid email address first.</span>"
    
    otp_code = str(random.randint(1000, 9999))
    ACTIVE_OTPS[u_email] = otp_code
    
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = u_email
        msg['Subject'] = "🔐 AccAstroForge - Email Verification OTP"
        
        body = f"""
        Namaste,
        
        Your verification code for AccAstroForge registration is: {otp_code}
        
        Please enter this 4-digit code in the registration form to verify your genuine email address.
        
        Regards,
        AccAstroForge Team
        https://accastroforge.in
        """
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, u_email, msg.as_string())
        server.quit()
        
        return f"<span style='color: #4ade80;'>✅ OTP successfully sent to <b>{u_email}</b>. (Also check Spam folder).</span>"
    except Exception as e:
        print(f"SMTP Error: {e}")
        # Reliable fallback display right on screen so you can test instantly without blocking
        return f"<span style='color: #fde047; font-weight: bold;'>✨ Verification OTP for {u_email}: <span style='background:#7c3aed; padding:2px 8px; border-radius:6px; color:#fff;'>{otp_code}</span> (Enter this code below)</span>"

def handle_manual_signup(name, email, phone, password, otp_input):
    u_name = name.strip() if name else ""
    u_email = email.strip() if email else ""
    u_phone = phone.strip() if phone else ""
    
    if not u_name:
        return "❌ Please enter your Full Name.", "👤 Guest User", "₹ 0.00", "No active sessions."
    if not u_email or "@" not in u_email:
        return "❌ Please enter a valid Email Address.", "👤 Guest User", "₹ 0.00", "No active sessions."
    if not u_phone or len(u_phone) < 10:
        return "❌ Phone Number is mandatory (minimum 10 digits required).", "👤 Guest User", "₹ 0.00", "No active sessions."
    if not password:
        return "❌ Please enter a Password.", "👤 Guest User", "₹ 0.00", "No active sessions."
    
    expected_otp = ACTIVE_OTPS.get(u_email, "")
    if not otp_input or otp_input.strip() != expected_otp:
        return "❌ Email Verification Failed: Invalid or missing OTP. Please click 'Send Verification OTP' and enter the correct code.", "👤 Guest User", "₹ 0.00", "No active sessions."

    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Manual Account Registration",
        "details": f"Email: {u_email} | Phone: {u_phone} | Status: Verified",
        "payment_status": "Registered & Active"
    })
    
    success_msg = f"### ✨ Welcome to AccAstroForge, {u_name}!\nYour account has been successfully verified and logged in with **{u_email}** (Phone: {u_phone})."
    profile_box = f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #4ade80;'>Status: Active Member (Verified)</span><br><span style='color: #fde047;'>Phone: {u_phone}</span>"
    wallet_box = "₹ 0.00"
    history_box = f"• Account Registered & Email Verified Successfully<br>• Contact: {u_phone}<br>• Initial Wallet: ₹0.00"
    
    return success_msg, profile_box, wallet_box, history_box

def run_daily_horoscope(sign):
    return f"### 🔮 Daily Vedic Horoscope for {sign}\nToday brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace in personal relationships. Wear yellow or amber for extra luck!"

def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob, bypass_active):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b_name} & {g_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)" if not bypass_active else "Admin Bypassed"})
    teaser_text = f"### ❤️ Kundali Compatibility Teaser for {b_name} & {g_name}\nHigh Guna Milan score detected! Excellent long-term emotional and spiritual alignment observed."
    return teaser_text, get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}", bypass_active)

def run_life_predictions(name, dob, tob, pob, focus_area, question, phone, email, address, bypass_active):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Complete Life Prediction", "payment_status": "Pending (₹499)" if not bypass_active else "Admin Bypassed"})
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"""### 🌟 ASTROLOGICAL TEASER FOR USER
- <span style="color: #fde047; font-weight: 700;">Rashi:</span> <span style="color: #ffffff; font-weight: 600;">{profile['zodiac']}</span>
- <span style="color: #fde047; font-weight: 700;">Nakshatra:</span> <span style="color: #ffffff; font-weight: 600;">{profile['nakshatra']}</span>
- <span style="color: #fde047; font-weight: 700;">Dasha:</span> <span style="color: #ffffff; font-weight: 600;">{profile['dasha']}</span>
- <span style="color: #fde047; font-weight: 700;">Insight:</span> <span style="color: #ffffff; font-weight: 600;">Great growth indicated in {focus_area}.</span>"""
    return teaser_text, get_paywall_html("Complete Deep Life Forecast & PDF", 499, u_name, bypass_active)

def run_gemstone_remedy(dob, zodiac, bypass_active):
    save_log({"timestamp": str(datetime.datetime.now()), "service": "Gemstone Remedy", "details": f"DOB: {dob} | Zodiac: {zodiac}", "payment_status": "Pending (₹299)" if not bypass_active else "Admin Bypassed"})
    teaser_text = f"### 💎 Gemstone Guidance Teaser\nFavorable alignment detected for {zodiac}. Emerald (Panna) or Yellow Sapphire (Pukhraj) recommended to boost career clarity."
    return teaser_text, get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User", bypass_active)

def run_kundali_pdf(name, dob, tob, pob, bypass_active):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Janam Kundali PDF", "payment_status": "Pending (₹299)" if not bypass_active else "Admin Bypassed"})
    chart_html = generate_visual_kundali_chart_html(u_name, dob if dob else "2000-01-01", tob, pob)
    pdf_file = create_kundali_pdf_file(u_name, dob if dob else "2000-01-01", tob, pob)
    teaser_text = f"### 📜 Janam Kundali & Birth Chart Generated for {u_name}\nYour detailed Lagna chart and PDF preview have been generated successfully below."
    return teaser_text, chart_html, pdf_file, get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, u_name, bypass_active)

def run_numerology(name, dob, bypass_active):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Numerology", "payment_status": "Pending (₹249)" if not bypass_active else "Admin Bypassed"})
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"### 🔢 Numerology Preview for {u_name}\nYour Destiny Psychic Number is <span style='color: #fde047; font-size: 1.2rem; font-weight: bold;'>{profile['psychic_num']}</span>. High leadership potential and creative focus."
    return teaser_text, get_paywall_html("Detailed Numerology & Name Correction Report", 249, u_name, bypass_active)

def run_panchang(date_str, city, mode="free", bypass_active=False):
    teaser = f"""Complete Vedic Panchang for {city} on {date_str}:
- <span style="color: #fde047; font-weight: 700;">Tithi:</span> <span style="color: #ffffff;">Shukla Paksha Navami</span>
- <span style="color: #fde047; font-weight: 700;">Nakshatra:</span> <span style="color: #ffffff;">Rohini</span>
- <span style="color: #fde047; font-weight: 700;">Rahu Kalam:</span> <span style="color: #ffffff;">10:30 AM - 12:00 PM</span>
- <span style="color: #fde047; font-weight: 700;">Shubh Muhurat:</span> <span style="color: #ffffff;">11:45 AM - 12:30 PM</span>"""
    if "Detailed" in mode:
        return f"### 📅 Detailed Shubh Muhurat Report\n{teaser}", get_paywall_html("Detailed Shubh Muhurat Report", 99, "User", bypass_active)
    return f"### 📅 Free Daily Panchang for {city}\n{teaser}", ""

def simple_astro_query(user_query, bypass_active=False):
    if not user_query or not user_query.strip():
        return "🙏 **Namaste!** Please ask any question regarding career, marriage, health, or planetary transits."
    return f"**Your Query:** {user_query}\n\n---\n\n🌟 **AI Astrologer Guidance:** Planetary alignments indicate favorable outcomes if pursued with dedication and sincerity."

def recharge_wallet(amount):
    pay_url = get_robust_razorpay_link(f"AccAstroForge Wallet Topup (₹{amount})", amount, "Valued Customer")
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center; margin-top: 10px;">
        <h4 style="color: #4ade80; margin-bottom: 5px;">💳 Add ₹{amount} to AccAstroForge Credits</h4>
        <a href="{pay_url}" target="_blank" style="background: #22c55e; color: white; padding: 8px 20px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block;">
            ⚡ Pay ₹{amount} & Top Up Wallet
        </a>
    </div>
    """

def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "❌ Incorrect Password! Access Denied.", False
    logs = load_logs()
    summary_md = f"### 🛡️ AccAstroForge Admin Dashboard\n**Total User Entries:** {len(logs)}\n\n"
    if logs:
        summary_md += "| Timestamp | Name/Service | Details | Status |\n|---|---|---|---|\n"
        for log in reversed(logs):
            summary_md += f"| {log.get('timestamp', '')[:19]} | {log.get('full_name', 'N/A')} ({log.get('service', 'General')}) | {log.get('details', 'N/A')} | {log.get('payment_status', 'Pending')} |\n"
    else:
        summary_md += "📭 No user logs recorded yet.\n"
    return summary_md, True

def toggle_admin_bypass(current_state):
    new_state = not current_state
    msg = "🔓 **Admin Free Bypass Status: ENABLED**" if new_state else "🔒 **Admin Free Bypass Status: DISABLED**"
    return new_state, msg

# ---------------------------------------------------------
# 5. CSS & JAVASCRIPT (Fixed Text Colors & Eye Toggle)
# ---------------------------------------------------------
custom_css = f"""
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');

html, body, .gr-root, .gradio-container, gradio-app {{
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
}}

.gradio-container::after {{
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background-image: radial-gradient(white 1.2px, transparent 0), radial-gradient(rgba(252, 211, 77, 0.85) 1.8px, transparent 0);
    background-size: 140px 140px, 210px 210px;
    background-position: 0 0, 60px 80px;
    opacity: 0.5;
    pointer-events: none;
    z-index: 0;
}}

.gradio-container > * {{
    position: relative;
    z-index: 1;
}}

footer, header, #footer, .footer, .built-with, a[href*="huggingface.co/space"] {{
    display: none !important;
}}

div[role="tablist"] {{
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    width: 100% !important;
    gap: 2px !important;
    padding: 4px 2px !important;
    background: rgba(10, 3, 25, 0.9) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(244, 114, 182, 0.4) !important;
    justify-content: space-between !important;
}}

button[role="tab"] {{
    flex: 1 1 auto !important;
    min-width: 0 !important;
    background: rgba(18, 8, 42, 0.9) !important;
    border: 1px solid rgba(244, 114, 182, 0.45) !important;
    color: #fef08a !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 700 !important;
    font-size: 0.62rem !important;
    border-radius: 8px !important;
    padding: 6px 2px !important;
    margin: 0 !important;
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
    overflow: hidden !important;
    text-align: center !important;
}}

button[role="tab"][aria-selected="true"] {{
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border-color: #fde047 !important;
    box-shadow: 0 4px 12px rgba(219, 39, 119, 0.8) !important;
}}

.gr-accordion, .accordion, div[data-testid="accordion"], fieldset {{
    background: rgba(14, 5, 35, 0.95) !important;
    backdrop-filter: blur(18px) !important;
    border: 1px solid rgba(244, 114, 182, 0.6) !important;
    border-radius: 16px !important;
    padding: 15px !important;
    color: #ffffff !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8) !important;
    max-width: 800px !important;
    margin: 0 auto !important;
}}

button.primary, button.gr-button-primary, .gr-button-primary {{
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border: 1px solid #fde047 !important;
    box-shadow: 0 4px 15px rgba(219, 39, 119, 0.6) !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
}}

/* FIXED TEXT AND LABEL COLORS SO NOTHING IS BLACK */
label span, .block span, .gr-input-label, span.svelte-1b6s6s, .label-wrap span, .gr-block-label span {{
    color: #fde047 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}}

input, textarea, select {{
    background: rgba(22, 10, 48, 0.95) !important;
    border: 1.5px solid rgba(244, 114, 182, 0.7) !important;
    color: #ffffff !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    font-size: 0.98rem !important;
}}

input::placeholder, textarea::placeholder {{
    color: rgba(255, 255, 255, 0.6) !important;
}}

/* PASSWORD EYE TOGGLE STYLING */
.pass-wrapper {{
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
}}
.pass-toggle-btn {{
    position: absolute !important;
    right: 15px !important;
    cursor: pointer !important;
    user-select: none !important;
    font-size: 1.2rem !important;
    z-index: 99 !important;
    filter: drop-shadow(0 0 5px rgba(253,224,71,0.5));
}}

#manual-signup-trigger, #real-hidden-trigger {{
    display: none !important;
}}

/* 3D LOGO TRANSITION OVERLAY */
#astro-spin-overlay {{
    position: fixed;
    top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(3, 0, 20, 0.85);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 99999;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
}}
#astro-spin-overlay.active {{
    opacity: 1;
    pointer-events: all;
}}
.spinning-logo-img {{
    width: 150px;
    height: 150px;
    filter: drop-shadow(0 0 30px rgba(244, 114, 182, 0.95));
    animation: spinZoom 0.75s ease-in-out infinite;
}}
@keyframes spinZoom {{
    0% {{ transform: scale(0.5) rotate(0deg); opacity: 0.2; }}
    50% {{ transform: scale(1.2) rotate(180deg); opacity: 1; }}
    100% {{ transform: scale(0.5) rotate(360deg); opacity: 0.2; }}
}}
"""

head_html = f"""
<div id="astro-spin-overlay">
    <img src="{spin_logo_src}" class="spinning-logo-img" alt="Transitioning...">
</div>
<script>
document.addEventListener("DOMContentLoaded", function() {{
    const overlay = document.getElementById("astro-spin-overlay");
    function triggerSpinOverlay() {{
        if(!overlay) return;
        overlay.classList.add("active");
        setTimeout(() => {{ overlay.classList.remove("active"); }}, 750);
    }}
    document.addEventListener("click", function(e) {{
        if (e.target && (e.target.matches('button[role="tab"]') || e.target.closest('button[role="tab"]'))) {{
            triggerSpinOverlay();
        }}
    }});

    // Robust Password Eye Toggle Injection
    setInterval(() => {{
        const passInputs = document.querySelectorAll('input[type="password"]');
        passInputs.forEach(input => {{
            if (!input.dataset.eyeInjected) {{
                input.dataset.eyeInjected = "true";
                const parent = input.parentElement;
                if(parent) {{
                    parent.classList.add("pass-wrapper");
                    const btn = document.createElement("span");
                    btn.innerHTML = "👁️";
                    btn.className = "pass-toggle-btn";
                    btn.onclick = function() {{
                        if(input.type === "password") {{
                            input.type = "text";
                            btn.innerHTML = "🙈";
                        }} else {{
                            input.type = "password";
                            btn.innerHTML = "👁️";
                        }}
                    }};
                    parent.appendChild(btn);
                }}
            }}
        }});
    }}, 400);
}});
</script>
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance", head=head_html) as demo:
    admin_bypass_state = gr.State(value=False)

    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8, min_width=300):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4, min_width=350):
                gr.HTML(f"""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 10px 18px; border-radius: 14px; display: flex; gap: 8px; align-items: center; justify-content: flex-end;">
                    <span style="font-size: 0.8rem; color: #fde047; font-weight: 600;">🔐 Quick Logins:</span>
                    <a href="{GOOGLE_OAUTH_URL}" target="_blank" style="color: #fff; background: #ea4335; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="{FACEBOOK_OAUTH_URL}" target="_blank" style="color: #fff; background: #1877f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                    <a href="{TWITTER_OAUTH_URL}" target="_blank" style="color: #fff; background: #1da1f2; padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Twitter</a>
                </div>
                """)

        with gr.Tabs() as main_tabs:
            # TAB 1: DASHBOARD
            with gr.TabItem("👤 DASHBOARD"):
                gr.Markdown("### 👤 User Profile, Wallet & Order History")
                
                with gr.Row():
                    with gr.Column():
                        user_profile_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #7c3aed; padding: 18px; border-radius: 14px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="color: #fde047; margin-bottom: 4px;">👤 Active User Session</h4>
                                <p style="color: #ffffff; font-size: 0.95rem; margin: 0;">Guest User (Please Sign Up / Login)</p>
                            </div>
                            <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #ffffff; border: 1px solid #fde047; padding: 8px 18px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; cursor: pointer;">
                                📝 SIGN UP
                            </button>
                        </div>
                        """)
                    with gr.Column():
                        wallet_balance_display = gr.HTML("""
                        <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #a78bfa; padding: 18px; border-radius: 14px; margin-bottom: 15px;">
                            <h4 style="color: #fde047; margin-bottom: 5px;">💳 Wallet Balance: <span style="color: #4ade80;">₹ 0.00</span></h4>
                            <p style="color: #f3e8ff; font-size: 0.8rem; margin: 0;">Use credits for instant unlocking of reports.</p>
                        </div>
                        """)

                with gr.Group(visible=False) as signup_group:
                    with gr.Accordion("📝 Create Your AccAstroForge Account (Email Verification)", open=True):
                        with gr.Row():
                            signup_name = gr.Textbox(label="Full Name *", placeholder="e.g. Rajesh Sharma")
                            signup_email = gr.Textbox(label="Email Address (OTP will be sent) *", placeholder="e.g. yourname@gmail.com")
                        with gr.Row():
                            signup_phone = gr.Textbox(label="Phone Number (Mandatory) *", placeholder="e.g. 9876543210")
                            signup_pass = gr.Textbox(label="Create Password *", type="password", placeholder="Enter secure password")
                        
                        with gr.Row():
                            send_otp_btn = gr.Button("📧 Send Verification OTP", variant="secondary")
                            otp_status = gr.HTML()
                        
                        signup_otp = gr.Textbox(label="Enter 4-digit Email OTP *", placeholder="Enter OTP received in email")
                        send_otp_btn.click(fn=send_real_email_otp, inputs=[signup_email], outputs=[otp_status])

                        signup_btn = gr.Button("✨ Verify OTP & Complete Sign Up", variant="primary")
                        signup_output = gr.Markdown()

                order_history_display = gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 15px; border-radius: 12px; margin-bottom: 20px;">
                    <h4 style="color: #fde047; margin-bottom: 6px; font-size: 1rem;">📦 Order History & Saved PDF Reports</h4>
                    <p style="color: #cbd5e1; font-size: 0.85rem; margin: 0;">No previous orders found for current guest session.</p>
                </div>
                """)

                with gr.Row():
                    topup_amount = gr.Radio(choices=["100", "250", "500", "1000"], value="250", label="Select Topup Amount (₹)")
                    topup_btn = gr.Button("⚡ Topup Wallet Credits", variant="primary")
                wallet_pay_output = gr.HTML()
                topup_btn.click(fn=recharge_wallet, inputs=[topup_amount], outputs=[wallet_pay_output])

                signup_btn.click(
                    fn=handle_manual_signup, 
                    inputs=[signup_name, signup_email, signup_phone, signup_pass, signup_otp], 
                    outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display]
                )

            # TAB 2: LIFE PREDICTION
            with gr.TabItem("🌟 LIFE PREDICTION"):
                gr.Markdown("### 🌌 Vedic Astrology & Deep Life Forecast")
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
                output_life_teaser = gr.Markdown()
                output_life_paywall = gr.HTML()
                submit_life.click(fn=run_life_predictions, inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input, admin_bypass_state], outputs=[output_life_teaser, output_life_paywall])

            # TAB 3: HOROSCOPE
            with gr.TabItem("☀️ HOROSCOPE"):
                gr.Markdown("### 🔮 Daily Zodiac Predictions (Free)")
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Select Zodiac Sign")
                submit_horoscope = gr.Button("🔮 Get Today's Horoscope", variant="primary")
                output_horoscope = gr.Markdown()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            # TAB 4: MATCHING
            with gr.TabItem("❤️ MATCHING"):
                gr.Markdown("### 💍 Vedic Compatibility & Guna Milan")
                with gr.Row():
                    boy_name = gr.Textbox(label="Boy's Name", placeholder="e.g. Rahul")
                    boy_dob = gr.Textbox(label="Boy's DOB (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                with gr.Row():
                    girl_name = gr.Textbox(label="Girl's Name", placeholder="e.g. Priya")
                    girl_dob = gr.Textbox(label="Girl's DOB (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                submit_matching = gr.Button("❤️ Match Kundalis Now (₹399)", variant="primary")
                output_matching = gr.Markdown()
                output_matching_paywall = gr.HTML()
                submit_matching.click(fn=run_kundali_matching, inputs=[boy_name, boy_dob, girl_name, girl_dob, admin_bypass_state], outputs=[output_matching, output_matching_paywall])

            # TAB 5: GEMSTONES
            with gr.TabItem("💎 GEMSTONES"):
                gr.Markdown("### 🧿 Lucky Gemstones & Cosmic Remedies")
                with gr.Row():
                    gem_dob = gr.Textbox(label="Date of Birth", placeholder="YYYY-MM-DD")
                    gem_zodiac = gr.Textbox(label="Zodiac Sign", placeholder="e.g. Aries (Mesha)")
                submit_gem = gr.Button("💎 Find My Gemstone (₹299)", variant="primary")
                output_gem = gr.Markdown()
                output_gem_paywall = gr.HTML()
                submit_gem.click(fn=run_gemstone_remedy, inputs=[gem_dob, gem_zodiac, admin_bypass_state], outputs=[output_gem, output_gem_paywall])

            # TAB 6: KUNDALI & BIRTH PDF
            with gr.TabItem("📜 KUNDALI & BIRTH PDF"):
                gr.Markdown("### 📜 Janam Kundali & Lagna Birth Chart Generator")
                with gr.Row():
                    k_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                    k_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                with gr.Row():
                    k_tob = gr.Textbox(label="Time of Birth", placeholder="HH:MM")
                    k_pob = gr.Textbox(label="Place of Birth", placeholder="City, Country")
                submit_kundali_pdf = gr.Button("📜 Generate Visual Birth Chart & Kundali PDF (₹299)", variant="primary")
                output_kundali_pdf_text = gr.Markdown()
                output_visual_chart = gr.HTML()
                output_kundali_file = gr.File(label="Download Generated Kundali PDF")
                output_kundali_paywall = gr.HTML()
                submit_kundali_pdf.click(fn=run_kundali_pdf, inputs=[k_name, k_dob, k_tob, k_pob, admin_bypass_state], outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall])

            # TAB 7: NUMEROLOGY
            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.Markdown("### 🔢 Numerology Check")
                with gr.Row():
                    n_name = gr.Textbox(label="Full Name", placeholder="e.g. Rajesh Sharma")
                    n_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                submit_num = gr.Button("🔢 Analyze Numerology (₹249)", variant="primary")
                output_num = gr.Markdown()
                output_num_paywall = gr.HTML()
                submit_num.click(fn=run_numerology, inputs=[n_name, n_dob, admin_bypass_state], outputs=[output_num, output_num_paywall])

            # TAB 8: PANCHANG
            with gr.TabItem("📅 PANCHANG"):
                gr.Markdown("### 📅 Vedic Panchang & Shubh Muhurat")
                with gr.Row():
                    p_date = gr.Textbox(label="Date (YYYY-MM-DD)", placeholder="YYYY-MM-DD")
                    p_city = gr.Textbox(label="City", placeholder="e.g. Kolkata")
                p_mode = gr.Radio(choices=["Free Daily Panchang", "Detailed Shubh Muhurat Report (₹99)"], value="Free Daily Panchang")
                submit_panchang = gr.Button("📅 Check Panchang", variant="primary")
                output_panchang = gr.Markdown()
                output_panchang_paywall = gr.HTML()
                submit_panchang.click(fn=run_panchang, inputs=[p_date, p_city, p_mode, admin_bypass_state], outputs=[output_panchang, output_panchang_paywall])

            # TAB 9: AI ASSISTANT
            with gr.TabItem("🤖 AI ASSISTANT"):
                gr.Markdown("### 🤖 Ask Your Personal AI Astrologer")
                ai_input = gr.Textbox(label="Type your query", placeholder="e.g. How is my career looking?")
                ai_submit = gr.Button("Ask Assistant ✨", variant="primary")
                ai_output = gr.Markdown()
                ai_submit.click(fn=simple_astro_query, inputs=[ai_input, admin_bypass_state], outputs=ai_output)

            # TAB 10: LEGAL & POLICIES
            with gr.TabItem("⚖️ LEGAL"):
                gr.Markdown("### ⚖️ Legal Terms & Privacy Policy")
                gr.HTML("""
                <div style="background: rgba(14, 5, 35, 0.9); border: 1px solid rgba(232, 121, 249, 0.5); padding: 20px; border-radius: 14px;">
                    <h4 style="color: #fde047;">📜 Terms of Service & Privacy</h4>
                    <p style="font-size: 0.85rem; color: #ddd;">Welcome to AccAstroForge.in. All data is protected and used strictly for astrological guidance.</p>
                </div>
                """)

        # HIDDEN TRIGGERS
        signup_state = gr.State(value=False)
        manual_signup_trigger = gr.Button("Trigger Signup", elem_id="manual-signup-trigger")
        manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state], outputs=[signup_state, signup_group])

        # SECRET ADMIN PORTAL
        with gr.Group(visible=False) as admin_group:
            with gr.Accordion("🔒 Owner Portal (Admin Dashboard)", open=True):
                secret_pass = gr.Textbox(label="Admin Secret Password", type="password", placeholder="Enter Password")
                unlock_btn = gr.Button("Unlock Dashboard", variant="primary")
                bypass_toggle_btn = gr.Button("🔓 Toggle Admin Free Bypass Mode", variant="secondary")
                bypass_status_md = gr.Markdown("🔒 **Admin Free Bypass Status: DISABLED**")
                secret_output = gr.Markdown()
                
                unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=[secret_output, admin_bypass_state])
                bypass_toggle_btn.click(fn=toggle_admin_bypass, inputs=[admin_bypass_state], outputs=[admin_bypass_state, bypass_status_md])

        admin_state = gr.State(value=False)
        real_hidden_trigger = gr.Button("Trigger", elem_id="real-hidden-trigger")
        real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, favicon_path="favicon.png")
