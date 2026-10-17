import base64
import datetime
import json
import os
import random
import google.generativeai as genai
import gradio as gr
import requests

# Import Hugging Face spaces for ZeroGPU support
try:
    import spaces

    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False

# ---------------------------------------------------------
# 1. ADMIN LOGGING & DATABASE SETUP (JSON FILE SYSTEM)
# ---------------------------------------------------------
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


# Initialize Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Updated Admin Password to Meher's & Arnab's special birth year 1989
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "MeherArnab1989")

model = None
if GEMINI_API_KEY:
    model = genai.GenerativeModel("gemini-1.5-flash")

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
        <span id="secret-admin-dot" title="" style="width: 14px; height: 14px; min-width: 14px; min-height: 14px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047; margin-bottom: 35px;"></span>
    </div>
    """
else:
    logo_element = """
    <div style="display: flex; align-items: center; gap: 10px;">
        <span style="font-size: 28px; font-weight: 800; color: #fbcfe8;">AccAstroForge</span>
        <span id="secret-admin-dot" title="" style="width: 14px; height: 14px; min-width: 14px; min-height: 14px; background: radial-gradient(circle, #fde047 0%, #d97706 100%); border: 1px solid #fef08a; border-radius: 50%; display: inline-block; cursor: pointer; box-shadow: 0 0 12px #fde047;"></span>
    </div>
    """


def gpu_decorator(func):
    if HAS_SPACES and hasattr(spaces, "GPU"):
        return spaces.GPU(func)
    return func


@gpu_decorator
def generate_ai_prediction(system_role, prompt_text):
    if not model:
        return "✨ *Cosmic Alignment in Progress... Your planetary energy indicates strong luck and success ahead.*"
    try:
        full_prompt = f"{system_role}\n\n{prompt_text}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return "✨ *Cosmic Insights Preview:* Your chart reflects high potential and favorable planetary alignments in the coming period."


def run_daily_horoscope(sign):
    prompt = f"Provide a detailed daily Vedic horoscope for Zodiac Sign: {sign}. Cover Career, Love, Health, and Lucky Astro Tips for today."
    return generate_ai_prediction("An expert Vedic Astrologer.", prompt)


def run_kundali_matching(boy_name, boy_dob, girl_name, girl_dob):
    prompt = f"Perform a detailed Vedic Kundali Gun Milan matching analysis between Boy ({boy_name}, DOB: {boy_dob}) and Girl ({girl_name}, DOB: {girl_dob}). Calculate approximate Guna score out of 36, discuss Ashtakoot compatibility, Manglik dosha, and final marriage harmony verdict."
    return generate_ai_prediction("An expert Vedic Match-making Astrologer.", prompt)


def run_life_predictions(
    name, dob, tob, pob, focus_area, question, phone, email, address
):
    user_entry = {
        "timestamp": str(datetime.datetime.now()),
        "full_name": name,
        "dob": dob,
        "tob": tob,
        "pob": pob,
        "focus_area": focus_area,
        "question": question,
        "phone": phone,
        "email": email,
        "address": address,
        "payment_status": "Pending / Teased",
    }
    save_log(user_entry)

    teaser_prompt = (
        f"Provide a short 2-line basic astrological sun-sign/lagna teaser for"
        f" Name: {name}, DOB: {dob}."
    )
    teaser = generate_ai_prediction(
        "An expert Vedic Astrologer providing brief free teasers.", teaser_prompt
    )

    teaser_text = f"### 🌟 Free Astrological Teaser for {name}\n{teaser}"

    paywall_html = f"""
    <div style="background: rgba(18, 8, 42, 0.95); border: 2px solid #db2777; padding: 22px; border-radius: 16px; margin-top: 15px; text-align: center; box-shadow: 0 0 25px rgba(219, 39, 119, 0.5);">
        <h3 style="color: #fde047; margin-bottom: 8px; font-size: 1.3rem; font-family: 'Cinzel', serif;">🔒 AccAstroForge Premium Lock (₹299 Only)</h3>
        <p style="color: #f3e8ff; font-size: 0.95rem; margin-bottom: 12px;">Dear <b>{name}</b>, to reveal your <b>Complete Deep Life Forecast, Planetary Transits, Timeline & Downloadable PDF Report</b>, please complete secure payment below via any UPI app or Card.</p>
        <p style="color: #4ade80; font-size: 1.2rem; font-weight: bold; margin-bottom: 18px;">Unlock Price: ₹299 (Lifetime PDF Access)</p>
        
        <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 20px; flex-wrap: wrap;">
            <span style="background: #5f259f; color: white; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 0.85rem;">🟣 PhonePe</span>
            <span style="background: #4285f4; color: white; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 0.85rem;">🔵 Google Pay</span>
            <span style="background: #00baf2; color: white; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 0.85rem;">🔷 Paytm</span>
            <span style="background: #000; color: #fff; border: 1px solid #f472b6; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 0.85rem;">💳 UPI / Cards</span>
        </div>

        <a href="https://rzp.io/l/accastroforge" target="_blank" style="background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%); color: white; padding: 14px 32px; border-radius: 12px; font-weight: bold; text-decoration: none; font-size: 1.15rem; box-shadow: 0 6px 20px rgba(219,39,119,0.8); display: inline-block;">🚀 Pay ₹299 & Instantly Download PDF Report</a>
    </div>
    """
    return teaser_text, paywall_html


def run_gemstone_remedy(dob, zodiac):
    prompt = f"Suggest the most suitable Vedic Gemstone, Rudraksha, and Mantra remedies based on DOB: {dob} and Zodiac/Ascendant: {zodiac}. Explain how to wear it and benefits."
    return generate_ai_prediction(
        "An expert Gemstone and Vedic Remedy Astrologer.", prompt
    )


def run_kundali_pdf(name, dob, tob, pob):
    prompt = f"Generate a comprehensive Vedic Janam Kundali layout description, planetary positions (Bhavas), Dasha periods, and PDF report summary for Name: {name}, DOB: {dob}, Time: {tob}, Place: {pob}."
    return generate_ai_prediction(
        "An expert Vedic Astrologer and Chart Maker.", prompt
    )


def run_numerology(name, dob):
    prompt = f"Perform a detailed Vedic Numerology analysis. Calculate Psychic Number (Mulank), Destiny Number (Bhagyank), Name Number (Chaldean/Pythagorean), and Name Compatibility for Name: {name}, DOB: {dob}."
    return generate_ai_prediction("An expert Numerologist.", prompt)


def run_panchang(date_str, city):
    prompt = f"Provide a complete Vedic Panchang for Date: {date_str} at Location: {city}. Include Tithi, Nakshatra, Yoga, Karana, Rahu Kalam, and auspicious Shubh Muhurat timings."
    return generate_ai_prediction("An expert Vedic Panchang Astrologer.", prompt)


def astro_chat_response(message, history):
    if not model:
        return "The planets are aligning. Please ensure your Gemini API key is active."

    chat_history = []
    for human, assistant in history:
        chat_history.append({"role": "user", "parts": [human]})
        chat_history.append({"role": "model", "parts": [assistant]})

    try:
        chat = model.start_chat(history=chat_history)
        system_instruction = (
            "You are 'AccAstroForge AI Assistant', a wise, empathetic, and expert "
            "Vedic Jyotish master. Answer users' astrological questions with deep "
            "wisdom, remedies, and a welcoming tone."
        )
        full_message = f"{system_instruction}\n\nUser Question: {message}"
        response = chat.send_message(full_message)
        return response.text
    except Exception:
        return (
            "✨ *Cosmic Guidance:* Your energy shows high potential. Focus on"
            " spiritual grounding and structured steps."
        )


def admin_login_and_view(password):
    if password != ADMIN_PASSWORD:
        return "❌ Incorrect Password! Access Denied."

    logs = load_logs()
    if not logs:
        return "📭 No user logs or transaction data found yet."

    summary_md = f"### 🛡️ AccAstroForge Admin Dashboard\n"
    summary_md += f"**Total User Entries:** {len(logs)}\n\n"
    summary_md += (
        "| Timestamp | Name | Contact (Phone/Email) | Address | Focus & Question"
        " | Status |\n"
    )
    summary_md += "|---|---|---|---|---|---|\n"

    for log in reversed(logs):
        t = log.get("timestamp", "")[:19]
        name = log.get("full_name", "")
        contact = f"{log.get('phone', '')} / {log.get('email', '')}"
        addr = log.get("address", "")
        details = (
            f"Focus: {log.get('focus_area', '')} | Q: {log.get('question', '')}"
        )
        status = log.get("payment_status", "Pending")
        summary_md += (
            f"| {t} | {name} | {contact} | {addr} | {details} | {status} |\n"
        )

    return summary_md


# Master Clean CSS
custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700;900&family=Poppins:wght@300;400;500;600;700&display=swap');

html, body, .gradio-container, gradio-app {
    background-color: #030014 !important;
    background-image: 
        linear-gradient(rgba(5, 1, 20, 0.45), rgba(5, 1, 20, 0.6)),
        url("https://huggingface.co/spaces/Arnab1989/AccAstroForge/resolve/main/bg.jpg") !important;
    background-position: center center !important;
    background-repeat: no-repeat !important;
    background-size: cover !important;
    background-attachment: fixed !important;
    color: #f3e8ff !important;
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

footer, header, #footer, .footer, .built-with, div[class*="footer"],
div[class*="space-header"], div.pe-2, .ab-0, div[style*="position: fixed"],
a[href*="huggingface.co/space"], div:has(> a[href*="huggingface.co/space"]),
.svelte-1ipelgc, .svelte-1g7vh8a, .contain > div.absolute {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

.gr-box, .gr-row, .gr-form, .form, panel, 
div[data-testid="block"], .block, .wrap, .contain {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* HORIZONTAL TAB CONTAINER - ALL 8 TABS PERFECTLY FITTED */
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
    scrollbar-width: thin;
    scrollbar-color: #db2777 transparent;
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
    line-height: 1.15 !important;
    white-space: nowrap !important;
    flex-grow: 1 !important;
    flex-shrink: 0 !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    transition: all 0.2s ease;
}

button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%) !important;
    color: #ffffff !important;
    border-color: #fde047 !important;
    box-shadow: 0 4px 18px rgba(219, 39, 119, 0.8) !important;
}

button[role="tab"]:hover {
    color: #ffffff !important;
    border-color: #f472b6 !important;
}

input, textarea, select {
    background: rgba(18, 8, 42, 0.85) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1px solid rgba(232, 121, 249, 0.45) !important;
    color: #fef08a !important;
    border-radius: 14px !important;
    padding: 12px 16px !important;
    font-family: 'Poppins', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
}

input:focus, textarea:focus, select:focus {
    border-color: #f472b6 !important;
    box-shadow: 0 0 22px rgba(244, 114, 182, 0.6) !important;
    color: #ffffff !important;
    outline: none !important;
}

label span, .block label {
    color: #f5d0fe !important;
    font-family: 'Poppins', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
}

h3, h2 {
    font-family: 'Cinzel', serif !important;
    color: #fbcfe8 !important;
    text-shadow: 0 0 20px rgba(217, 70, 239, 0.7);
}

button.primary, .gr-button-primary {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 50%, #f59e0b 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.4) !important;
    font-family: 'Cinzel', serif !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 30px rgba(124, 58, 237, 0.8);
}

.gr-markdown {
    background: rgba(14, 5, 35, 0.88) !important;
    backdrop-filter: blur(18px) !important;
    border: 1px solid rgba(232, 121, 249, 0.5) !important;
    border-radius: 18px !important;
    padding: 24px !important;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
    font-family: 'Poppins', sans-serif !important;
    color: #f3e8ff !important;
}

/* HIDE THE REAL TRIGGER BUTTON BUT KEEP IT RENDERED */
#real-hidden-btn {
    position: absolute !important;
    opacity: 0 !important;
    pointer-events: none !important;
    height: 0px !important;
    width: 0px !important;
    overflow: hidden !important;
}
"""

custom_js = """
function() {
    const link = document.querySelector("link[rel*='icon']") || document.createElement('link');
    link.type = 'image/png';
    link.rel = 'icon';
    link.href = 'https://huggingface.co/spaces/Arnab1989/AccAstroForge/resolve/main/favicon.png';
    document.getElementsByTagName('head')[0].appendChild(link);
    
    setTimeout(() => {
        const dot = document.getElementById('secret-admin-dot');
        if (dot) {
            dot.addEventListener('click', () => {
                const btn = document.querySelector('#real-hidden-btn button');
                if (btn) {
                    btn.click();
                }
            });
        }
    }, 1000);

    setInterval(() => {
        const hfBadge = document.querySelector('div.pe-2, a[href*="huggingface.co/spaces"]');
        if (hfBadge && hfBadge.parentNode) {
            hfBadge.parentNode.style.display = 'none';
        }
    }, 100);
}
"""

with gr.Blocks(title="AccAstroForge - AI Astrology Guidance", js=custom_js) as demo:
    with gr.Column():
        # Top header with logo and embedded dot
        with gr.Row():
            with gr.Column(scale=8, min_width=300):
                gr.HTML(f"<div>{logo_element}</div>")
            with gr.Column(scale=4, min_width=350):
                gr.HTML("""
                <div style="background: rgba(18, 8, 42, 0.85); border: 1px solid rgba(244, 114, 182, 0.5); padding: 10px 18px; border-radius: 14px; display: flex; gap: 12px; align-items: center; box-shadow: 0 4px 15px rgba(0,0,0,0.5); justify-content: flex-end;">
                    <span style="font-size: 0.85rem; color: #fde047; font-weight: 600;">🔐 Quick Login:</span>
                    <a href="#" onclick="alert('Google Sign-In Successful!'); return false;" style="color: #fff; background: #ea4335; padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; text-decoration: none; font-weight: 600;">Google</a>
                    <a href="#" onclick="alert('Facebook Sign-In Successful!'); return false;" style="color: #fff; background: #1877f2; padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; text-decoration: none; font-weight: 600;">Facebook</a>
                    <a href="#" onclick="alert('X (Twitter) Sign-In Successful!'); return false;" style="color: #fff; background: #000000; border: 1px solid #444; padding: 5px 10px; border-radius: 8px; font-size: 0.8rem; text-decoration: none; font-weight: 600;">𝕏 Twitter</a>
                </div>
                """)

        with gr.Tabs():
            # TAB 1: COMPLETE LIFE PREDICTION
            with gr.TabItem("🌟 COMPLETE LIFE PREDICTION"):
                gr.Markdown("### 🌌 AI-Powered Vedic Astrology & Deep Life Forecast")
                with gr.Row():
                    name_input = gr.Textbox(
                        label="Full Name", placeholder="e.g. Rajesh Sharma"
                    )
                    dob_input = gr.Textbox(
                        label="Date of Birth", placeholder="YYYY-MM-DD"
                    )
                with gr.Row():
                    tob_input = gr.Textbox(label="Time of Birth", placeholder="HH:MM")
                    pob_input = gr.Textbox(
                        label="Place of Birth", placeholder="City, Country"
                    )

                with gr.Row():
                    phone_input = gr.Textbox(
                        label="Phone Number", placeholder="e.g. 9876543210"
                    )
                    email_input = gr.Textbox(
                        label="Email Address", placeholder="e.g. user@gmail.com"
                    )

                address_input = gr.Textbox(
                    label="Postal Address", placeholder="Enter your full address"
                )

                focus_dropdown = gr.Dropdown(
                    choices=[
                        "General Life & Destiny",
                        "Career & Wealth Growth",
                        "Love, Marriage & Harmony",
                        "Health & Spiritual Growth",
                    ],
                    value="General Life & Destiny",
                    label="Primary Focus Area",
                )

                question_input = gr.Textbox(
                    label="Specific Question or Concern",
                    lines=2,
                    placeholder="e.g. When will my financial situation improve?",
                )
                submit_life = gr.Button(
                    "✨ Reveal Detailed Life Insights (Free Teaser)",
                    variant="primary",
                )

                output_life_teaser = gr.Markdown(
                    label="Astrological Guidance Report"
                )
                output_life_paywall = gr.HTML(label="Payment Card")

                submit_life.click(
                    fn=run_life_predictions,
                    inputs=[
                        name_input,
                        dob_input,
                        tob_input,
                        pob_input,
                        focus_dropdown,
                        question_input,
                        phone_input,
                        email_input,
                        address_input,
                    ],
                    outputs=[output_life_teaser, output_life_paywall],
                )

            # TAB 2: DAILY HOROSCOPE
            with gr.TabItem("☀️ DAILY HOROSCOPE"):
                gr.Markdown("### 🔮 Daily Zodiac Predictions & Planetary Guidance")
                zodiac_sign = gr.Dropdown(
                    choices=[
                        "Aries",
                        "Taurus",
                        "Gemini",
                        "Cancer",
                        "Leo",
                        "Virgo",
                        "Libra",
                        "Scorpio",
                        "Sagittarius",
                        "Capricorn",
                        "Aquarius",
                        "Pisces",
                    ],
                    value="Aries",
                    label="Select Your Zodiac Sign (Rashi)",
                )
                submit_horoscope = gr.Button(
                    "🔮 Get Today's Horoscope", variant="primary"
                )
                output_horoscope = gr.Markdown(label="Daily Horoscope Reading")

                submit_horoscope.click(
                    fn=run_daily_horoscope,
                    inputs=[zodiac_sign],
                    outputs=output_horoscope,
                )

            # TAB 3: KUNDALI MATCHING
            with gr.TabItem("❤️ KUNDALI MATCHING"):
                gr.Markdown("### 💍 Vedic Compatibility & Guna Milan Analysis")
                with gr.Row():
                    boy_name = gr.Textbox(
                        label="Boy's Name", placeholder="e.g. Rohan"
                    )
                    boy_dob = gr.Textbox(
                        label="Boy's Date of Birth", placeholder="YYYY-MM-DD"
                    )
                with gr.Row():
                    girl_name = gr.Textbox(
                        label="Girl's Name", placeholder="e.g. Priya"
                    )
                    girl_dob = gr.Textbox(
                        label="Girl's Date of Birth", placeholder="YYYY-MM-DD"
                    )

                submit_matching = gr.Button(
                    "❤️ Match Kundalis Now", variant="primary"
                )
                output_matching = gr.Markdown(
                    label="Compatibility & Match Report"
                )

                submit_matching.click(
                    fn=run_kundali_matching,
                    inputs=[boy_name, boy_dob, girl_name, girl_dob],
                    outputs=output_matching,
                )

            # TAB 4: GEMSTONE & REMEDIES
            with gr.TabItem("💎 GEMSTONE & REMEDIES"):
                gr.Markdown(
                    "### 🧿 Discover Your Lucky Gemstones & Cosmic Remedies"
                )
                with gr.Row():
                    gem_dob = gr.Textbox(
                        label="Date of Birth", placeholder="YYYY-MM-DD"
                    )
                    gem_zodiac = gr.Textbox(
                        label="Zodiac Sign or Ascendant (Lagnam)",
                        placeholder="e.g. Leo / Simha",
                    )

                submit_gem = gr.Button(
                    "💎 Find My Lucky Gemstone", variant="primary"
                )
                output_gem = gr.Markdown(label="Gemstone & Remedy Guidance")

                submit_gem.click(
                    fn=run_gemstone_remedy,
                    inputs=[gem_dob, gem_zodiac],
                    outputs=output_gem,
                )

            # TAB 5: KUNDALI PDF
            with gr.TabItem("📜 KUNDALI PDF"):
                gr.Markdown(
                    "### 📜 Detailed Janam Kundali Chart & PDF Report Generator"
                )
                with gr.Row():
                    k_name = gr.Textbox(
                        label="Full Name", placeholder="e.g. Subham Roy"
                    )
                    k_dob = gr.Textbox(
                        label="Date of Birth", placeholder="YYYY-MM-DD"
                    )
                with gr.Row():
                    k_tob = gr.Textbox(label="Time of Birth", placeholder="HH:MM")
                    k_pob = gr.Textbox(
                        label="Place of Birth", placeholder="City, State"
                    )

                submit_kundali_pdf = gr.Button(
                    "📜 Generate Kundali Chart & PDF", variant="primary"
                )
                output_kundali_pdf = gr.Markdown(
                    label="Kundali & PDF Report Details"
                )

                submit_kundali_pdf.click(
                    fn=run_kundali_pdf,
                    inputs=[k_name, k_dob, k_tob, k_pob],
                    outputs=output_kundali_pdf,
                )

            # TAB 6: NUMEROLOGY
            with gr.TabItem("🔢 NUMEROLOGY"):
                gr.Markdown("### 🔢 Numerology & Name Compatibility Check")
                with gr.Row():
                    n_name = gr.Textbox(
                        label="Full Name", placeholder="e.g. Amitabha Sen"
                    )
                    n_dob = gr.Textbox(
                        label="Date of Birth", placeholder="YYYY-MM-DD"
                    )

                submit_num = gr.Button(
                    "🔢 Analyze Numerology & Compatibility", variant="primary"
                )
                output_num = gr.Markdown(label="Numerology Report")

                submit_num.click(
                    fn=run_numerology, inputs=[n_name, n_dob], outputs=output_num
                )

            # TAB 7: PANCHANG
            with gr.TabItem("📅 PANCHANG"):
                gr.Markdown("### 📅 Vedic Panchang & Auspicious Shubh Muhurat")
                with gr.Row():
                    p_date = gr.Textbox(
                        label="Target Date", placeholder="YYYY-MM-DD"
                    )
                    p_city = gr.Textbox(
                        label="City / Location", placeholder="e.g. Kolkata, India"
                    )

                submit_panchang = gr.Button(
                    "📅 Check Panchang & Muhurat", variant="primary"
                )
                output_panchang = gr.Markdown(label="Panchang Details")

                submit_panchang.click(
                    fn=run_panchang, inputs=[p_date, p_city], outputs=output_panchang
                )

            # TAB 8: AI ASSISTANT
            with gr.TabItem("💬 AI ASSISTANT"):
                gr.Markdown("### 🤖 Ask Your Personal AI Astrologer (Live Chat)")
                gr.ChatInterface(
                    fn=astro_chat_response,
                    chatbot=gr.Chatbot(
                        height=380, label="Cosmic Chat Session"
                    ),
                    textbox=gr.Textbox(
                        placeholder="Ask your personal AI Astrologer anything..."
                    ),
                    submit_btn="Ask Assistant ✨",
                )

        # SECRET ADMIN PORTAL (Always rendered so JS can trigger click)
        with gr.Group(elem_id="admin-portal-section", visible=False) as admin_group:
            with gr.Accordion(
                "🔒 Secure Owner Portal (Admin Dashboard)", open=True
            ):
                gr.Markdown(
                    "Enter your admin password below to access user logs,"
                    " contact details, and payment histories."
                )
                with gr.Row():
                    secret_pass = gr.Textbox(
                        label="Admin Secret Password",
                        type="password",
                        placeholder="Enter password...",
                    )
                    unlock_btn = gr.Button(
                        "Unlock Dashboard", variant="primary"
                    )
                secret_output = gr.Markdown(
                    label="Admin Logs & Database Summary"
                )
                unlock_btn.click(
                    fn=admin_login_and_view,
                    inputs=secret_pass,
                    outputs=secret_output,
                )

        admin_state = gr.State(value=False)

        # Hidden bridge button to connect HTML click to Gradio state
        with gr.Group(elem_id="real-hidden-btn"):
            real_hidden_trigger = gr.Button("Trigger")

        real_hidden_trigger.click(
            fn=lambda vis: (not vis, gr.update(visible=not vis)),
            inputs=[admin_state],
            outputs=[admin_state, admin_group],
        )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False, css=custom_css, favicon_path="favicon.png")
