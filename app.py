import base64
import datetime
import json
import os
import random
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

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")

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
    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 5px 0;">
        <img src="{logo_src}" alt="AccAstroForge" style="height: 65px; background: transparent !important;">
        <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 14px; height: 14px; background: #fde047; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 10px #fde047;"></span>
    </div>
    """
else:
    logo_element = """
    <div style="display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 5px 0;">
        <span style="font-size: 26px; font-weight: 800; color: #fde047; font-family: 'Cinzel', serif;">AccAstroForge</span>
        <span id="secret-admin-dot" title="Admin Trigger" onclick="document.querySelector('#real-hidden-trigger').click()" style="width: 14px; height: 14px; background: #fde047; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 10px #fde047;"></span>
    </div>
    """

# ---------------------------------------------------------
# 1. ASTROLOGY CALCULATIONS & ENGINE
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
            Rashi: <span style="color: #4ade80; font-weight: 800; font-size: 1.15rem;">✨ {profile['zodiac']}</span>
        </p>
    </div>
    """

def create_kundali_pdf_file(name, dob, tob, pob):
    profile = calculate_astrological_profile(name, dob)
    filename = f"Kundali_{name.replace(' ', '_')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, textColor=colors.HexColor('#5b21b6'), alignment=1, spaceAfter=15)
    story.append(Paragraph("<b>AccAstroForge - Vedic Janam Kundali Report</b>", title_style))
    story.append(Spacer(1, 10))
    data = [
        ["Attribute", "Details"],
        ["Full Name", profile["name"]],
        ["Date of Birth", dob],
        ["Time / Place", f"{tob} / {pob}"],
        ["Zodiac Sign (Rashi)", profile["zodiac"]],
        ["Birth Nakshatra", profile["nakshatra"]],
        ["Destiny Number", str(profile["psychic_num"])],
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
        print(f"Razorpay error: {e}")
    return RAZORPAY_ME_URL

def get_paywall_html(service_name, price, user_name="User"):
    pay_url = get_robust_razorpay_link(service_name, price, user_name)
    return f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5);">
        <h3 style="color: #fde047; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 UNLOCK {service_name.upper()} (₹{price} ONLY)</h3>
        <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 12px;">Click below to open secure Razorpay checkout.</p>
        <p style="color: #4ade80; font-size: 1.3rem; font-weight: bold; margin-bottom: 16px;">Total Payable: ₹{price}</p>
        <a href="{pay_url}" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; font-size: 1.15rem; display: inline-block;">
            🚀 Proceed to Pay ₹{price} (UPI, GPay, Cards)
        </a>
    </div>
    """

# ---------------------------------------------------------
# 2. CORE HANDLERS (UPDATED WITH PHONE NUMBER STORAGE)
# ---------------------------------------------------------
def handle_manual_signup(name, email, phone, password):
    u_name = name.strip() if name else "New User"
    u_email = email.strip() if email else "N/A"
    u_phone = phone.strip() if phone else "N/A"
    
    if not u_email or "@" not in u_email:
        return "❌ Please enter a valid email address.", "👤 Guest User", "₹ 0.00", "No active sessions."
    if not u_phone or len(u_phone) < 10:
        return "❌ Please enter a valid Phone Number (minimum 10 digits).", "👤 Guest User", "₹ 0.00", "No active sessions."
    
    save_log({
        "timestamp": str(datetime.datetime.now()),
        "full_name": u_name,
        "service": "Manual Account Registration",
        "details": f"Email: {u_email} | Phone: {u_phone}",
        "payment_status": "Registered & Active"
    })
    
    success_msg = f"### ✨ Welcome to AccAstroForge, {u_name}!\nYour account with phone **{u_phone}** has been registered successfully."
    profile_box = f"👤 <b>{u_name}</b> ({u_email})<br><span style='color: #4ade80;'>Phone: {u_phone}</span><br><span style='color: #fde047;'>Status: Active Member</span>"
    wallet_box = "₹ 0.00"
    history_box = f"• Registered Successfully<br>• Phone: {u_phone}<br>• Initial Wallet: ₹0.00"
    
    return success_msg, profile_box, wallet_box, history_box

def run_daily_horoscope(sign):
    return f"### 🔮 Daily Vedic Horoscope for {sign}\nToday brings high cosmic energy for {sign}. Jupiter's aspect promises financial opportunities and peace."

def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    b_name = boy_name.strip() if boy_name else "Boy"
    g_name = girl_name.strip() if girl_name else "Girl"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": f"{b_name} & {g_name}", "service": "Kundali Matching", "payment_status": "Pending"})
    return f"### ❤️ Kundali Compatibility Teaser\nHigh Guna Milan score detected for {b_name} & {g_name}!", get_paywall_html("Complete Kundali Matching Report", 399, f"{b_name} & {g_name}")

def run_life_predictions(name, dob, tob, pob, focus_area, question, phone, email, address):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Complete Life Prediction", "payment_status": "Pending"})
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    teaser = f"### 🌟 ASTROLOGICAL TEASER\nRashi: **{profile['zodiac']}** | Nakshatra: **{profile['nakshatra']}**\nGreat growth indicated in {focus_area}."
    return teaser, get_paywall_html("Complete Deep Life Forecast & PDF", 499, u_name)

def run_gemstone_remedy(dob, zodiac):
    save_log({"timestamp": str(datetime.datetime.now()), "service": "Gemstone Remedy", "payment_status": "Pending"})
    return f"### 💎 Gemstone Guidance\nFavorable alignment detected for {zodiac}. Emerald or Yellow Sapphire recommended.", get_paywall_html("Lucky Gemstone Report", 299, "User")

def run_kundali_pdf(name, dob, tob, pob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Janam Kundali PDF", "payment_status": "Pending"})
    chart_html = generate_visual_kundali_chart_html(u_name, dob if dob else "2000-01-01", tob, pob)
    pdf_file = create_kundali_pdf_file(u_name, dob if dob else "2000-01-01", tob, pob)
    return f"### 📜 Janam Kundali Generated for {u_name}", chart_html, pdf_file, get_paywall_html("Full Janam Kundali PDF Chart", 299, u_name)

def run_numerology(name, dob):
    u_name = name.strip() if name else "User"
    save_log({"timestamp": str(datetime.datetime.now()), "full_name": u_name, "service": "Numerology", "payment_status": "Pending"})
    profile = calculate_astrological_profile(u_name, dob if dob else "2000-01-01")
    return f"### 🔢 Numerology Preview\nDestiny Psychic Number: **{profile['psychic_num']}**", get_paywall_html("Detailed Numerology Report", 249, u_name)

def run_panchang(date_str, city, mode="free"):
    teaser = f"Complete Vedic Panchang for {city} on {date_str}:\n- Tithi: Shukla Paksha Navami\n- Nakshatra: Rohini\n- Rahu Kalam: 10:30 AM - 12:00 PM"
    if "Detailed" in mode:
        return f"### 📅 Detailed Shubh Muhurat Report\n{teaser}", get_paywall_html("Detailed Shubh Muhurat Report", 99, "User")
    return f"### 📅 Free Daily Panchang\n{teaser}", ""

def simple_astro_query(user_query):
    if not user_query or not user_query.strip():
        return "🙏 **Namaste!** Please ask any question regarding career, marriage, or health."
    return f"**Your Query:** {user_query}\n\n---\n\n🌟 **AI Astrologer Guidance:** Planetary alignments indicate favorable outcomes."

def recharge_wallet(amount):
    pay_url = get_robust_razorpay_link(f"AccAstroForge Wallet Topup (₹{amount})", amount, "Valued Customer")
    return f"""
    <div style="background: rgba(18, 8, 42, 0.9); border: 1px solid #4ade80; padding: 15px; border-radius: 12px; text-align: center;">
        <h4 style="color: #4ade80; margin-bottom: 5px;">💳 Add ₹{amount} Credits</h4>
        <a href="{pay_url}" target="_blank" style="background: #22c55e; color: white; padding: 8px 20px; border-radius: 8px; font-weight: bold; text-decoration: none; display: inline-block;">⚡ Pay ₹{amount} Now</a>
    </div>
    """

def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "❌ Incorrect Password! Access Denied."
    logs = load_logs()
    if not logs:
        return "📭 No user logs found yet."
    summary_md = f"### 🛡️ Admin Dashboard\n**Total Entries:** {len(logs)}\n\n| Timestamp | Name/Service | Details / Phone | Status |\n|---|---|---|---|\n"
    for log in reversed(logs):
        summary_md += f"| {log.get('timestamp', '')[:19]} | {log.get('full_name', 'N/A')} ({log.get('service', 'General')}) | {log.get('details', 'N/A')} | {log.get('payment_status', 'Pending')} |\n"
    return summary_md

# ---------------------------------------------------------
# 3. CLEAN & STABLE CSS + JAVASCRIPT (WITH PASSWORD EYE TOGGLE)
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

div[role="tablist"] {
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    gap: 4px !important;
    background: rgba(10, 3, 25, 0.9) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(244, 114, 182, 0.4) !important;
    padding: 6px !important;
}

button[role="tab"] {
    background: rgba(18, 8, 42, 0.9) !important;
    border: 1px solid rgba(244, 114, 182, 0.4) !important;
    color: #fef08a !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 700 !important;
    font-size: 0.65rem !important;
    border-radius: 8px !important;
    padding: 6px 10px !important;
}

button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border-color: #fde047 !important;
}

.gr-accordion, .accordion, div[data-testid="accordion"], fieldset {
    background: rgba(14, 5, 35, 0.95) !important;
    border: 1px solid rgba(244, 114, 182, 0.6) !important;
    border-radius: 16px !important;
    padding: 15px !important;
    color: #ffffff !important;
}

button.primary, .gr-button-primary {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border: 1px solid #fde047 !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
}

label span, .block span, .gr-input-label, span.svelte-1b6s6s, .label-wrap span {
    color: #fde047 !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}

input, textarea, select {
    background: rgba(22, 10, 48, 0.95) !important;
    border: 1.5px solid rgba(244, 114, 182, 0.7) !important;
    color: #ffffff !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
}

input::placeholder, textarea::placeholder {
    color: rgba(255, 255, 255, 0.5) !important;
}

/* PASSWORD EYE TOGGLE STYLING */
.pass-wrapper {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
}
.pass-toggle-btn {
    position: absolute !important;
    right: 15px !important;
    cursor: pointer !important;
    user-select: none !important;
    font-size: 1.2rem !important;
    z-index: 99 !important;
    filter: drop-shadow(0 0 5px rgba(253,224,71,0.5));
}

#manual-signup-trigger, #real-hidden-trigger {
    display: none !important;
}
"""

head_html = """
<script>
document.addEventListener("DOMContentLoaded", function() {
    setInterval(() => {
        const passInputs = document.querySelectorAll('input[type="password"]');
        passInputs.forEach(input => {
            if (!input.dataset.eyeInjected) {
                input.dataset.eyeInjected = "true";
                const parent = input.parentElement;
                if(parent) {
                    parent.classList.add("pass-wrapper");
                    const btn = document.createElement("span");
                    btn.innerHTML = "👁️";
                    btn.className = "pass-toggle-btn";
                    btn.onclick = function() {
                        if(input.type === "password") {
                            input.type = "text";
                            btn.innerHTML = "🙈";
                        } else {
                            input.type = "password";
                            btn.innerHTML = "👁️";
                        }
                    };
                    parent.appendChild(btn);
                }
            }
        });
    }, 400);
});
</script>
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance", head=head_html, css=custom_css) as demo:
    with gr.Column():
        with gr.Row():
            with gr.Column(scale=8):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4):
                gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 8px 14px; border-radius: 12px; display: flex; gap: 8px; align-items: center; justify-content: flex-end;">
                    <span style="font-size: 0.75rem; color: #fde047;">Quick Logins:</span>
                    <a href="https://accounts.google.com" target="_blank" style="color: #fff; background: #ea4335; padding: 3px 8px; border-radius: 5px; font-size: 0.7rem; text-decoration: none;">Google</a>
                    <a href="https://facebook.com" target="_blank" style="color: #fff; background: #1877f2; padding: 3px 8px; border-radius: 5px; font-size: 0.7rem; text-decoration: none;">Facebook</a>
                </div>
                """)

        with gr.Tabs() as main_tabs:
            # TAB 1: DASHBOARD
            with gr.TabItem("👤 DASHBOARD"):
                gr.Markdown("### 👤 User Profile, Wallet & Order History")
                with gr.Row():
                    user_profile_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #7c3aed; padding: 15px; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; width: 100%;">
                        <div>
                            <h4 style="color: #fde047; margin-bottom: 2px;">👤 Active Session</h4>
                            <p style="color: #fff; margin: 0; font-size: 0.9rem;">Guest User</p>
                        </div>
                        <button onclick="document.querySelector('#manual-signup-trigger').click()" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%); color: #fff; border: 1px solid #fde047; padding: 6px 14px; border-radius: 15px; font-weight: 700; cursor: pointer;">SIGN UP</button>
                    </div>
                    """)
                    wallet_balance_display = gr.HTML("""
                    <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid #a78bfa; padding: 15px; border-radius: 12px; width: 100%;">
                        <h4 style="color: #fde047; margin-bottom: 2px;">💳 Wallet: <span style="color: #4ade80;">₹ 0.00</span></h4>
                        <p style="color: #ddd; margin: 0; font-size: 0.8rem;">Instant report unlocking.</p>
                    </div>
                    """)

                with gr.Group(visible=False) as signup_group:
                    with gr.Accordion("📝 Account Registration (with Phone & Password Eye Toggle)", open=True):
                        with gr.Row():
                            signup_name = gr.Textbox(label="Full Name *", placeholder="e.g. Rajesh Sharma")
                            signup_email = gr.Textbox(label="Email Address *", placeholder="e.g. user@gmail.com")
                        with gr.Row():
                            signup_phone = gr.Textbox(label="Phone Number (Saved in Admin Log) *", placeholder="e.g. 9876543210")
                            signup_pass = gr.Textbox(label="Password *", type="password", placeholder="Enter secure password")
                        signup_btn = gr.Button("✨ Complete Registration", variant="primary")
                        signup_output = gr.Markdown()

                order_history_display = gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.4); padding: 12px; border-radius: 12px;">
                    <h4 style="color: #fde047; font-size: 0.95rem;">📦 Order History</h4>
                    <p style="color: #ddd; font-size: 0.85rem; margin: 0;">No previous orders found.</p>
                </div>
                """)

                signup_btn.click(fn=handle_manual_signup, inputs=[signup_name, signup_email, signup_phone, signup_pass], outputs=[signup_output, user_profile_display, wallet_balance_display, order_history_display])

            # TAB 2: LIFE PREDICTION
            with gr.TabItem("🌟 LIFE PREDICTION"):
                gr.Markdown("### 🌌 Vedic Astrology & Deep Life Forecast")
                with gr.Row():
                    name_input = gr.Textbox(label="Full Name")
                    dob_input = gr.Textbox(label="Date of Birth (YYYY-MM-DD)")
                with gr.Row():
                    tob_input = gr.Textbox(label="Time of Birth (HH:MM)")
                    pob_input = gr.Textbox(label="Place of Birth")
                with gr.Row():
                    phone_input = gr.Textbox(label="Phone Number")
                    email_input = gr.Textbox(label="Email Address")
                address_input = gr.Textbox(label="Postal Address")
                focus_dropdown = gr.Dropdown(choices=["General Life & Destiny", "Career & Wealth Growth", "Love & Marriage", "Health & Spiritual Growth"], value="General Life & Destiny", label="Primary Focus Area")
                question_input = gr.Textbox(label="Specific Question")
                submit_life = gr.Button("✨ Reveal Detailed Life Insights (₹499)", variant="primary")
                output_life_teaser = gr.Markdown()
                output_life_paywall = gr.HTML()
                submit_life.click(fn=run_life_predictions, inputs=[name_input, dob_input, tob_input, pob_input, focus_dropdown, question_input, phone_input, email_input, address_input], outputs=[output_life_teaser, output_life_paywall])

            # TAB 3: HOROSCOPE
            with gr.TabItem("☀️ HOROSCOPE"):
                gr.Markdown("### 🔮 Daily Zodiac Predictions (Free)")
                zodiac_sign = gr.Dropdown(choices=ZODIAC_SIGNS, value="Aries (Mesha)", label="Select Zodiac Sign")
                submit_horoscope = gr.Button("🔮 Get Horoscope", variant="primary")
                output_horoscope = gr.Markdown()
                submit_horoscope.click(fn=run_daily_horoscope, inputs=[zodiac_sign], outputs=output_horoscope)

            # TAB 4: MATCHING
            with gr.TabItem("❤️ MATCHING"):
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

            # TAB 5: GEMSTONES
            with gr.TabItem("💎 GEMSTONES"):
                gr.Markdown("### 🧿 Lucky Gemstones & Remedies")
                with gr.Row():
                    gem_dob = gr.Textbox(label="Date of Birth (YYYY-MM-DD)")
                    gem_zodiac = gr.Textbox(label="Zodiac Sign")
                submit_gem = gr.Button("💎 Find My Gemstone (₹299)", variant="primary")
                output_gem = gr.Markdown()
                output_gem_paywall = gr.HTML()
                submit_gem.click(fn=run_gemstone_remedy, inputs=[gem_dob, gem_zodiac], outputs=[output_gem, output_gem_paywall])

            # TAB 6: KUNDALI & BIRTH PDF
            with gr.TabItem("📜 KUNDALI & BIRTH PDF"):
                gr.Markdown("### 📜 Janam Kundali & Lagna Birth Chart")
                with gr.Row():
                    k_name = gr.Textbox(label="Full Name")
                    k_dob = gr.Textbox(label="DOB (YYYY-MM-DD)")
                with gr.Row():
                    k_tob = gr.Textbox(label="Time of Birth")
                    k_pob = gr.Textbox(label="Place of Birth")
                submit_kundali_pdf = gr.Button("📜 Generate PDF Chart (₹299)", variant="primary")
                output_kundali_pdf_text = gr.Markdown()
                output_visual_chart = gr.HTML()
                output_kundali_file = gr.File(label="Download PDF")
                output_kundali_paywall = gr.HTML()
                submit_kundali_pdf.click(fn=run_kundali_pdf, inputs=[k_name, k_dob, k_tob, k_pob], outputs=[output_kundali_pdf_text, output_visual_chart, output_kundali_file, output_kundali_paywall])

            # TAB 7: NUMEROLOGY
            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.Markdown("### 🔢 Numerology Check")
                with gr.Row():
                    n_name = gr.Textbox(label="Full Name")
                    n_dob = gr.Textbox(label="DOB (YYYY-MM-DD)")
                submit_num = gr.Button("🔢 Analyze Numerology (₹249)", variant="primary")
                output_num = gr.Markdown()
                output_num_paywall = gr.HTML()
                submit_num.click(fn=run_numerology, inputs=[n_name, n_dob], outputs=[output_num, output_num_paywall])

            # TAB 8: PANCHANG
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

            # TAB 9: AI ASSISTANT
            with gr.TabItem("🤖 AI ASSISTANT"):
                gr.Markdown("### 🤖 Ask Your Personal AI Astrologer")
                ai_input = gr.Textbox(label="Type your query")
                ai_submit = gr.Button("Ask Assistant ✨", variant="primary")
                ai_output = gr.Markdown()
                ai_submit.click(fn=simple_astro_query, inputs=ai_input, outputs=ai_output)

            # TAB 10: LEGAL
            with gr.TabItem("⚖️ LEGAL"):
                gr.Markdown("### ⚖️ Terms of Service & Privacy Policy")
                gr.HTML("""
                <div style="background: rgba(14, 5, 35, 0.9); border: 1px solid rgba(232, 121, 249, 0.5); padding: 15px; border-radius: 12px;">
                    <p style="font-size: 0.85rem; color: #ddd; margin: 0;">Welcome to AccAstroForge.in. All reports are intended for personal guidance and spiritual insight.</p>
                </div>
                """)

        # HIDDEN TRIGGERS
        signup_state = gr.State(value=False)
        manual_signup_trigger = gr.Button("Trigger Signup", elem_id="manual-signup-trigger")
        manual_signup_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[signup_state], outputs=[signup_state, signup_group])

        # SECRET ADMIN PORTAL
        with gr.Group(visible=False) as admin_group:
            with gr.Accordion("🔒 Owner Portal (Admin Dashboard)", open=True):
                secret_pass = gr.Textbox(label="Admin Secret Password", type="password")
                unlock_btn = gr.Button("Unlock Dashboard", variant="primary")
                secret_output = gr.Markdown()
                unlock_btn.click(fn=admin_login_and_view, inputs=secret_pass, outputs=secret_output)

        admin_state = gr.State(value=False)
        real_hidden_trigger = gr.Button("Trigger", elem_id="real-hidden-trigger")
        real_hidden_trigger.click(fn=lambda vis: (not vis, gr.update(visible=not vis)), inputs=[admin_state], outputs=[admin_state, admin_group])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, head=head_html, favicon_path="favicon.png")
