import base64
import datetime
import json
import os
import io
import random
import requests
import gradio as gr
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import razorpay

# ---------------------------------------------------------
# 0. CONFIGURATIONS & SECRETS (RAZORPAY & PROKERALA)
# ---------------------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_live_TpnrjMektRCWj8")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "tm4Ry6xdY63egZtf5cD0kP8T")
RAZORPAY_ME_URL = "https://razorpay.me/@accastroforge"

PROKERALA_CLIENT_ID = os.getenv("PROKERALA_CLIENT_ID", "ffb5cc5c-e8c7-4cde-bec3-3c608af33a33")
PROKERALA_CLIENT_SECRET = os.getenv("PROKERALA_CLIENT_SECRET", "LXih7EzrT4ym7GXA@4ykOyHv1mofs4RxmWhzChgX")

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
    <div style="display: flex; align-items: center; gap: 10px;">
        <img src="{logo_src}" alt="AccAstroForge Logo" style="height: 85px; filter: drop-shadow(0 0 16px rgba(244, 114, 182, 0.7)); mix-blend-mode: screen; background: transparent !important;">
        <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 14px; height: 14px; min-width: 14px; min-height: 14px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047; margin-bottom: 35px;"></span>
    </div>
    """
else:
    logo_element = """
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 28px; font-weight: 800; color: #fbcfe8;">AccAstroForge</span>
        <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 14px; height: 14px; min-width: 14px; min-height: 14px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
    </div>
    """

# ---------------------------------------------------------
# 2. PROKERALA API & LOCAL ASTROLOGICAL ENGINE
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


def fetch_prokerala_token():
    try:
        url = "https://api.prokerala.com/token"
        payload = {
            "client_id": PROKERALA_CLIENT_ID,
            "client_secret": PROKERALA_CLIENT_SECRET
        }
        response = requests.post(url, data=payload, timeout=5)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"Prokerala Token Error: {e}")
    return None


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


# ---------------------------------------------------------
# 3. REPORTLAB PDF GENERATOR & DUAL-FALLBACK RAZORPAY PAYWALL
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
    
    # Fallback to official verified Razorpay Me profile page
    return RAZORPAY_ME_URL


def get_paywall_html(service_name, price, user_name="User"):
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
# 4. SERVICE HANDLERS FOR GRADIO
# ---------------------------------------------------------
def run_daily_horoscope(sign):
    return f"### 🔮 Daily Vedic Horoscope for {sign}\nToday brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace in personal relationships. Wear yellow or amber for extra luck!"


def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b_name} & {g_name}", "service": "Kundali Matching", "payment_status": "Pending (₹399)"})
    
    teaser_text = f"### ❤️ Kundali Compatibility Teaser for {b_name} & {g_name}\nHigh Guna Milan score detected! Excellent long-term emotional and spiritual alignment observed."
    return teaser_text, get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")


def run_life_predictions(name, dob, tob, pob, focus_area, question, phone, email, address):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Complete Life Prediction", "payment_status": "Pending (₹499)"})
    
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"""### 🌟 ASTROLOGICAL TEASER FOR USER
- <span style="color: #fde047; font-weight: 700;">Rashi:</span> <span style="color: #ffffff; font-weight: 600;">{profile['zodiac']}</span>
- <span style="color: #fde047; font-weight: 700;">Nakshatra:</span> <span style="color: #ffffff; font-weight: 600;">{profile['nakshatra']}</span>
- <span style="color: #fde047; font-weight: 700;">Dasha:</span> <span style="color: #ffffff; font-weight: 600;">{profile['dasha']}</span>
- <span style="color: #fde047; font-weight: 700;">Insight:</span> <span style="color: #ffffff; font-weight: 600;">Great growth indicated in {focus_area}.</span>"""
    return teaser_text, get_paywall_html("Complete Deep Life Forecast & PDF", 499, u_name)


def run_gemstone_remedy(dob, zodiac):
    save_log({"timestamp": str(datetime.datetime.now()), "service": "Gemstone Remedy", "details": f"DOB: {dob} | Zodiac: {zodiac}", "payment_status": "Pending (₹299)"})
    teaser_text = f"### 💎 Gemstone Guidance Teaser\nFavorable alignment detected for {zodiac}. Emerald (Panna) or Yellow Sapphire (Pukhraj) recommended to boost career clarity."
    return teaser_text, get_paywall_html("Lucky Gemstone & Vedic Remedies Report", 299, "User")


def run_kundali_pdf(name, dob, tob, pob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Janam Kundali PDF", "payment_status": "Pending (₹299)"})
    
    pdf_file = create_kundali_pdf_file(u_name, dob if dob else "2000-01-01", tob, pob)
    teaser_text = f"### 📜 Janam Kundali PDF Ready for {u_name}\nYour detailed Lagna chart and PDF preview have been generated successfully."
    return teaser_text, pdf_file, get_paywall_html("Full Janam Kundali PDF Chart & Dasha Report", 299, u_name)


def run_numerology(name, dob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Numerology", "payment_status": "Pending (₹249)"})
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser_text = f"### 🔢 Numerology Preview for {u_name}\nYour Destiny Psychic Number is <span style='color: #fde047; font-size: 1.2rem; font-weight: bold;'>{profile['psychic_num']}</span>. High leadership potential and creative focus."
    return teaser_text, get_paywall_html("Detailed Numerology & Name Correction Report", 249, u_name)


def run_panchang(date_str, city, mode="free"):
    teaser = f"""Complete Vedic Panchang for {city} on {date_str}:
- <span style="color: #fde047; font-weight: 700;">Tithi:</span> <span style="color: #ffffff;">Shukla Paksha Navami</span>
- <span style="color: #fde047; font-weight: 700;">Nakshatra:</span> <span style="color: #ffffff;">Rohini</span>
- <span style="color: #fde047; font-weight: 700;">Rahu Kalam:</span> <span style="color: #ffffff;">10:30 AM - 12:00 PM</span>
- <span style="color: #fde047; font-weight: 700;">Shubh Muhurat:</span> <span style="color: #ffffff;">11:45 AM - 12:30 PM</span>"""
    if "Detailed" in mode:
        return f"### 📅 Detailed Shubh Muhurat Report\n{teaser}", get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
    return f"### 📅 Free Daily Panchang for {city}\n{teaser}", ""


def simple_astro_query(user_query):
    if not user_query or not user_query.strip():
        return "🙏 **Namaste!** Please ask any question regarding career, marriage, health, or planetary transits."
    
    msg = user_query.lower().strip()
    
    if any(w in msg for w in ["hi", "hello", "hey", "greetings", "namaste"]):
        reply = "🙏 **Namaste!** I am your Vedic Astro Assistant. Please share your birth details, zodiac sign, or specific questions regarding career, marriage, health, or planetary transits, and I will guide you with ancient astrological wisdom."
    elif any(w in msg for w in ["career", "job", "business", "money", "wealth", "promotion"]):
        reply = "💼 **Career & Wealth Guidance:** In Vedic astrology, the 10th house (Karma Bhava) and Jupiter's transit dictate professional growth. If you are facing obstacles in career, chanting the 'Om Brihaspataye Namah' mantra on Thursdays and wearing a Yellow Sapphire or working with disciplined focus will bring immense growth."
    elif any(w in msg for w in ["marriage", "love", "relationship", "partner", "match"]):
        reply = "❤️ **Love & Marriage Insights:** Compatibility in Vedic astrology is evaluated through Guna Milan (36 points) and the positions of Venus (Shukra) and Mars (Mangal). Strengthening your 7th house through positive communication and harmony will resolve relationship hurdles."
    elif any(w in msg for w in ["health", "peace", "stress", "anxiety", "remedy"]):
        reply = "🌿 **Health & Spiritual Well-being:** Physical vitality is tied to the Sun (Surya) and Moon (Chandra). Practicing early morning Surya Namaskar, meditation during Brahma Muhurta, and keeping a calm mindset will balance your inner cosmic energy."
    else:
        responses = [
            f"🌟 **Analyzing your query regarding '{user_query}':** Vedic charts show that current planetary alignments are favorable for new beginnings. Focus on your inner strengths and auspicious timings.",
            f"🔮 **Regarding '{user_query}':** The celestial bodies indicate a period of transition and karmic reward. Patience and spiritual remedies will clear your path.",
            f"✨ **I hear your concern about '{user_query}'.** According to Vedic principles, planetary grace follows sincere effort. Consider charitable acts and positive affirmations on auspicious days."
        ]
        reply = random.choice(responses)

    return f"**Your Query:** {user_query}\n\n---\n\n{reply}"


def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "❌ Incorrect Password! Access Denied."

    logs = load_logs()
    if not logs:
        return "📭 No user logs found yet."

    summary_md = f"### 🛡️ AccAstroForge Admin Dashboard\n**Total User Entries:** {len(logs)}\n\n| Timestamp | Name/Service | Details | Status |\n|---|---|---|---|\n"
    for log in reversed(logs):
        summary_md += f"| {log.get('timestamp', '')[:19]} | {log.get('full_name', 'N/A')} ({log.get('service', 'General')}) | {log.get('details', 'N/A')} | {log.get('payment_status', 'Pending')} |\n"
    return summary_md


# ---------------------------------------------------------
# 5. CSS & JAVASCRIPT
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

.gradio-container::after {
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background-image: radial-gradient(white 1.2px, transparent 0), radial-gradient(rgba(252, 211, 77, 0.85) 1.8px, transparent 0);
    background-size: 140px 140px, 210px 210px;
    background-position: 0 0, 60px 80px;
    opacity: 0.5;
    pointer-events: none;
    z-index: 0;
}

.gradio-container > * {
    position: relative;
    z-index: 1;
}

footer, header, #footer, .footer, .built-with, a[href*="huggingface.co/space"] {
    display: none !important;
}

.gr-box, .gr-row, .gr-form, .form, panel, 
div[data-testid="block"], .block, .wrap, .contain {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Tab styling */
div[role="tablist"] {
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    width: 100% !important;
    gap: 6px !important;
    padding: 8px 10px !important;
    background: rgba(10, 3, 25, 0.85) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(244, 114, 182, 0.35) !important;
}

button[role="tab"] {
    background: rgba(18, 8, 42, 0.9) !important;
    border: 1px solid rgba(244, 114, 182, 0.45) !important;
    color: #fef08a !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 700 !important;
    font-size: 0.73rem !important;
    border-radius: 10px !important;
    padding: 9px 11px !important;
}

button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border-color: #fde047 !important;
    box-shadow: 0 4px 18px rgba(219, 39, 119, 0.8) !important;
}

/* Input Fields styling */
input, textarea, select {
    background: rgba(18, 8, 42, 0.85) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1px solid rgba(232, 121, 249, 0.45) !important;
    color: #ffffff !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    font-size: 0.95rem !important;
}

input:focus, textarea:focus, select:focus {
    border-color: #f472b6 !important;
    box-shadow: 0 0 22px rgba(244, 114, 182, 0.6) !important;
    color: #ffffff !important;
    outline: none !important;
}

/* File component */
.gr-file, .file-preview, .gr-file div, .gr-file span, .file-preview * {
    background: rgba(18, 8, 42, 0.95) !important;
    color: #fde047 !important;
    border-color: rgba(244, 114, 182, 0.5) !important;
}

.gr-file a, .file-name {
    color: #fde047 !important;
    font-weight: 700 !important;
}

/* DIRECT FORCE BLACK TEXT COLOR ON PANCHANG RADIO BUTTON LABELS */
.gr-radio label, .gr-radio label span, div[data-testid="radio"] label, div[data-testid="radio"] label span {
    color: #000000 !important;
    font-weight: 800 !important;
    font-size: 0.95rem !important;
}

/* MARKDOWN STYLING */
h1, h2, h3, h4, h5, h6, 
.gr-markdown h1, .gr-markdown h2, .gr-markdown h3,
.prose h1, .prose h2, .prose h3 {
    color: #fde047 !important;
    font-family: 'Cinzel', serif !important;
    text-shadow: 0 0 10px rgba(253, 224, 71, 0.4);
}

.gr-markdown, .prose, div[data-testid="markdown"] {
    background: rgba(14, 5, 35, 0.95) !important;
    backdrop-filter: blur(18px) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    border: 1px solid rgba(232, 121, 249, 0.6) !important;
    border-radius: 18px !important;
    padding: 24px 28px !important;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.7);
    color: #ffffff !important;
    margin-top: 10px !important;
}

.gr-markdown p, .gr-markdown li, .gr-markdown strong, .gr-markdown span,
.prose p, .prose li, .prose strong, .prose span,
div[data-testid="markdown"] p, div[data-testid="markdown"] span {
    color: #ffffff !important;
    padding-left: 0 !important;
    margin-left: 0 !important;
    text-indent: 0 !important;
    border-left: none !important;
    background: transparent !important;
}

/* Hide the trigger button while keeping it in DOM */
#real-hidden-trigger {
    display: none !important;
}
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance") as demo:
    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8, min_width=300):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4, min_width=350):
                gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 10px 18px; border-radius: 14px; display: flex; gap: 8px; align-items: center; justify-content: flex-end; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                    <span style="font-size: 0.8rem; color: #fde047; font-weight: 600;">🔐 Quick Logins:</span>
                    <a href="https://accounts.google.com/signin" target="_blank" style="color: #fff; background: #ea4335; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Google</a>
                    <a href="https://www.facebook.com/login" target="_blank" style="color: #fff; background: #1877f2; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Facebook</a>
                    <a href="https://twitter.com/login" target="_blank" style="color: #fff; background: #1da1f2; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; text-decoration: none;">Twitter</a>
                    <a href="https://accounts.google.com/signup" target="_blank" style="color: #fff; background: #7c3aed; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; text-decoration: none; font-weight: 700; border: 1px solid #fde047;">📝 Sign Up</a>
                </div>
                """)

        with gr.Tabs():
            # TAB 1: COMPLETE LIFE PREDICTION
            with gr.TabItem("🌟 COMPLETE LIFE PREDICTION"):
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
                submit_life.click(fn=run_life_predictions, inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input], outputs=[output_life_teaser, output_life_paywall])

            # TAB 2: DAILY HOROSCOPE
            with gr.TabItem("☀️ DAILY HOROSCOPE"):
                gr.Markdown("### 🔮 Daily Zodiac Predictions (Free)")
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Select Zodiac Sign")
                submit_horoscope = gr.Button("🔮 Get Today's Horoscope", variant="primary")
                output_horoscope = gr.Markdown()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            # TAB 3: KUNDALI MATCHING
            with gr.TabItem("❤️ KUNDALI MATCHING"):
                gr.Markdown("### 💍 Vedic Compatibility & Guna Milan")
                with gr.Row():
                    boy_name = gr.Textbox(label="Boy's Name")
                    boy_dob = gr.Textbox(label="Boy's DOB (YYYY-MM-DD)")
                with gr.Row():
                    girl_name = gr.Textbox(label="Girl's Name")
                    girl_dob = gr.Textbox(label="Girl's DOB (YYYY-MM-DD)")
                submit_matching = gr.Button("❤️ Match Kundalis Now (₹399)", variant="primary")
                output_matching = gr.Markdown()
                output_matching_paywall = gr.HTML()
                submit_matching.click(fn=run_kundali_matching, inputs=[boy_name, boy_dob, girl_name, girl_dob], outputs=[output_matching, output_matching_paywall])

            # TAB 4: GEMSTONE & REMEDIES
            with gr.TabItem("💎 GEMSTONE & REMEDIES"):
                gr.Markdown("### 🧿 Lucky Gemstones & Cosmic Remedies")
                with gr.Row():
                    gem_dob = gr.Textbox(label="Date of Birth")
                    gem_zodiac = gr.Textbox(label="Zodiac Sign")
                submit_gem = gr.Button("💎 Find My Gemstone (₹299)", variant="primary")
                output_gem = gr.Markdown()
                output_gem_paywall = gr.HTML()
                submit_gem.click(fn=run_gemstone_remedy, inputs=[gem_dob, gem_zodiac], outputs=[output_gem, output_gem_paywall])

            # TAB 5: KUNDALI PDF GENERATOR
            with gr.TabItem("📜 KUNDALI PDF"):
                gr.Markdown("### 📜 Janam Kundali Chart & PDF Report Generator")
                with gr.Row():
                    k_name = gr.Textbox(label="Full Name")
                    k_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)")
                with gr.Row():
                    k_tob = gr.Textbox(label="Time of Birth")
                    k_pob = gr.Textbox(label="Place of Birth")
                submit_kundali_pdf = gr.Button("📜 Generate Kundali PDF Report (₹299)", variant="primary")
                output_kundali_pdf_text = gr.Markdown()
                output_kundali_file = gr.File(label="Download Generated Kundali PDF")
                output_kundali_paywall = gr.HTML()
                submit_kundali_pdf.click(fn=run_kundali_pdf, inputs=[k_name, k_dob, k_tob, k_pob], outputs=[output_kundali_pdf_text, output_kundali_file, output_kundali_paywall])

            # TAB 6: NUMEROLOGY
            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.Markdown("### 🔢 Numerology Check")
                with gr.Row():
                    n_name = gr.Textbox(label="Full Name")
                    n_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)")
                submit_num = gr.Button("🔢 Analyze Numerology (₹249)", variant="primary")
                output_num = gr.Markdown()
                output_num_paywall = gr.HTML()
                submit_num.click(fn=run_numerology, inputs=[n_name, n_dob], outputs=[output_num, output_num_paywall])

            # TAB 7: PANCHANG
            with gr.TabItem("📅 PANCHANG"):
                gr.Markdown("### 📅 Vedic Panchang & Shubh Muhurat")
                with gr.Row():
                    p_date = gr.Textbox(label="Date (YYYY-MM-DD)")
                    p_city = gr.Textbox(label="City")
                p_mode = gr.Radio(choices=["Free Daily Panchang", "Detailed Shubh Muhurat Report (₹99)"], value="Free Daily Panchang")
                submit_panchang = gr.Button("📅 Check Panchang", variant="primary")
                output_panchang = gr.Markdown()
                output_panchang_paywall = gr.HTML()
                submit_panchang.click(fn=run_panchang, inputs=[p_date, p_city, p_mode], outputs=[output_panchang, output_panchang_paywall])

            # TAB 8: AI ASSISTANT
            with gr.TabItem("💬 AI ASSISTANT"):
                gr.Markdown("### 🤖 Ask Your Personal AI Astrologer")
                ai_input = gr.Textbox(label="Type your query (e.g., career, marriage, health)", placeholder="e.g. How is my career looking for next year?")
                ai_submit = gr.Button("Ask Assistant ✨", variant="primary")
                ai_output = gr.Markdown()
                ai_submit.click(fn=simple_astro_query, inputs=ai_input, outputs=ai_output)

        # SECRET ADMIN PORTAL (HIDDEN BY DEFAULT, OPENS ON DOT CLICK)
        with gr.Group(visible=False) as admin_group:
            with gr.Accordion("🔒 Owner Portal (Admin Dashboard)", open=True):
                secret_pass = gr.Textbox(label="Admin Secret Password", type="password", placeholder="Enter Password")
                unlock_btn = gr.Button("Unlock Dashboard", variant="primary")
                secret_output = gr.Markdown()
                unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=secret_output)

        admin_state = gr.State(value=False)
        real_hidden_trigger = gr.Button("Trigger", elem_id="real-hidden-trigger")
        real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, favicon_path="favicon.png")
