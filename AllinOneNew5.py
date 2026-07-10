import cloudscraper
import requests
import time
import re
import os
import sys
import pytz
import gc
import feedparser
import threading
import telebot
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from deep_translator import GoogleTranslator
from google import genai
from apscheduler.schedulers.background import BackgroundScheduler

# --- SYSTEM ENCODING ---
sys.stdout.reconfigure(encoding='utf-8')

# ==========================================================
# ⚙️ CONFIGURATION & BOT INTERFACE
# ==========================================================
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not all([TOKEN, CHAT_ID, GEMINI_API_KEY]):
    print("⚠️ Warning: Bot Token, Chat ID లేదా Gemini API Key సెట్ చేయబడలేదు! దయచేసి చెక్ చేయండి.")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=4)
MODEL_NAME = "gemini-2.5-flash" 
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- タイమ్‌ゾーンセタップ ---
IST = pytz.timezone("Asia/Kolkata")
US = pytz.timezone("US/Eastern")
EU = pytz.timezone("Europe/Berlin")
JP = pytz.timezone("Asia/Tokyo")
HK = pytz.timezone("Asia/Hong_Kong")

# ==========================================================
# 📊 DATA STORES & WATCHLISTS
# ==========================================================
rss_news_store = []
sent_links = set()
sent_news = set()
sent_alerts = {}
sudden_move_sent = {}
gap_alert_sent = {}
pinned_messages_store = []  # 🎯 పిన్ చేసిన మెసేజ్‌ల హిస్టరీ స్టోర్
last_reset_date = datetime.now(IST).date()

MAX_NEWS = 5000
CLEAR_COUNT = 1000
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

## 🔴 చంటి గారి 100% పక్కా మాస్టర్ వాచ్‌లిస్ట్
MY_WATCHLIST = [
    "ANANTRAJ", "ANANT RAJ", "APOLLO", "APOLLO HOSPITALS", "BBOX", "BLACK BOX", 
    "BEL", "BHARAT ELECTRONICS", "BHARTIARTL", "BHARTI AIRTEL", "AIRTEL", 
    "BLS", "BLS INTERNATIONAL", "BLUECLOUD", "BLUE CLOUD", "BSE", "BSE LTD",
    "CDSL", "CGPOWER", "CG POWER", "CHOLAFIN", "CHOLAMANDALAM", "CLEANMAX", "CLEAN MAX",
    "COFORGE", "DIXON", "DIXON TECH", "E2E", "E2E NETWORKS", "EIEL", "Enviro Infra Engineers Ltd", 
    "ETERNAL", "FRACTAL", "GMDCLTD", "GMDC", "GOKEX", "GOKALDAS EXPORTS", 
    "GROWW", "GRSE", "EMMVEE", "EMMVEE SOLAR", "EMMVEE PHOTOVOLTAIC", 
    "HAL", "HINDUSTAN AERONAUTICS", "HDFCBANK", "HDFC BANK", "HINDCOPPER", "HINDUSTAN COPPER",
    "IDEA", "VODAFONE IDEA", "IDFCFIRSTB", "IDFC FIRST", "INDIGO", "INTERGLOBE AVIATION",
    "INFY", "INFOSYS", "INTERARCH", "ITC", "ITCHOTELS", "ITC HOTELS", "JKTYRE", "JK TYRE",
    "JSWSTEEL", "JSW STEEL", "KALAMANDIR", "SAI SILKS", "KALYANKJIL", "KALYAN JEWELLERS", 
    "KAYNES", "KAYNES TECH", "KEC", "KEC INTERNATIONAL",
    "LEMONTREE", "LEMON TREE", "LENSKART", "LGEINDIA", "LG ELECTRONICS", "LT", "L&T", 
    "LARSEN", "M&M", "MAHINDRA", "MAZDOCK", "MAZAGON DOCK", "MCX", "MEESHO", 
    "NESTLEIND", "NESTLE", "NESTLE INDIA", "NH", "NARAYANA HRUDAYALAYA", 
    "NTPC", "NYKAA", "FSN E-COMMERCE","OLAELEC", "OLA ELECTRIC", "POLYCAB", "PROTEAN", 
    "RELIANCE", "RIL", "PROTEAN eGOV TECHNOLOGIES", "PROTEAN eGOV", "RELIANCE INDUSTRIES", "RELIANCE JIO", "RELIANCE RETAIL", 
    "SAILIFE", "SAI LIFE", "SBIN", "SBI", "STATE BANK", "SEPC", "SHAKTIPUMP", "SHakTI PUMPS",
    "SHRIRAMFIN", "SHRIRAM FINANCE", "SJS", "SJS ENTERPRISES", "SKIPPER", "SONACOMS", "SONA BLW",
    "SUZLON", "SUZLON ENERGY", "TATASTEEL", "TATA STEEL", "TCS", "TIPSMUSIC", "TIPS MUSIC",
    "TITAN", "TITAN COMPANY", "TVSMOTOR", "TVS MOTOR", "URBANCO", "URBAN COMPANY",
    "WABAG", "VA TECH WABAG", "WAAREEENER", "WAAREE ENERGIES", "YATHARTH", "YATHARTH HOSPITAL", 
    "YATRA", "YATRA ONLINE", "ZAGGLE", "ZAGGLE PREPAID", "bhel", "భెల్", "bharat heavy electricals", "bharat heavy electricals limited",
    "physicswallah", "physics wallah", "pwl ", "physicswallah limited"
]

MARKET_KEYWORDS = [
    "rbi rate", "repo rate", "rate cut", "rate hike", "fed decision", "fomc", "interest rate", "rate",
    "warsh", "kevin warsh", "malhotra", "sanjay malhotra", "shaktikanta", "shaktikanta das", "monetary policy", 
    "వడ్డీ రేటు", "రెపో రేటు",
    "budget 2026", "union budget", "budget", "gst rate change", "government policy", "corporate tax",
    "cabinet decision", "import duty", "export ban", "government decision", "govt decision", "gdp growth", 
    "us gdp", "cpi inflation", "india gdp", "inflation", "gdp", "cabinet meeting",
    "ప్రభుత్వ निर्णयం", "బడ్జెట్", "ద్రవ్యోల్బణం",
    "war", "strike", "strikes", "attack", "attacks", "military", "sanctions", "iran", "us-iran",
    "crude", "oil", "brent", "opec", "omc", "dollar", "crude spike", "above $", "surge",
    "యుద్ధం", "దాడి", "దాడులు", "సైనిక", "ఆंక్షలు", "ఇరాన్", "చమురు", "క్రూడ్", "డాలర్", "crude oil",
    "market crash", "circuit breaker", "scam", "sebi ban", "emergency", "urgent", "breaking",
    "అత్యవసర", "rbi mpc", "mpc", "rupee", "రూపాయి"
]

IMPORTANT_KEYWORDS = MARKET_KEYWORDS + [stock.lower() for stock in MY_WATCHLIST]

news_feeds = [
    "https://www.forexlive.com/rss",
    "https://www.investing.com/rss/news_1.rss",
    "https://www.investing.com/rss/news_301.rss",
]

TIMINGS = {
    "GIFT Nifty": ("06:30", "02:45"),
    "Nikkei (Japan)": ("05:30", "11:30"),
    "Hang Seng (HK)": ("06:45", "13:30"),
    "DAX (Germany)": ("12:30", "21:00"),
    "FTSE (UK)": ("12:30", "21:00"),
    "Dow Jones (US)": ("19:00", "01:30"),
    "Nasdaq (US)": ("19:00", "01:30"),
    "S&P 500 (US)": ("19:00", "01:30"),
    "Gold (Commodity)": ("04:30", "03:30"),
    "Silver (Commodity)": ("04:30", "03:30"),
    "Brent Oil": ("05:30", "03:30"),
    "WTI Crude (US Oil)": ("03:30", "02:30"),
    "US 10Y Yield": ("18:30", "03:30"),
    "Bitcoin (Daily)": ("05:30", "05:29"),
}

symbols = {
    "GIFT Nifty": "^NSEI", 
    "Dow Jones (US)": "^DJI",
    "Nasdaq (US)": "^IXIC",
    "S&P 500 (US)": "^GSPC",
    "Nikkei (Japan)": "^N225",
    "Hang Seng (HK)": "^HSI",
    "DAX (Germany)": "^GDAXI",
    "FTSE (UK)": "^FTSE",
    "Gold (Commodity)": "GC=F",
    "Silver (Commodity)": "SI=F",
    "Brent Oil": "BZ=F",
    "WTI Crude (US Oil)": "CL=F",
    "Bitcoin (Daily)": "BTC-USD",
    "US 10Y Yield": "^TNX",
}

# ==========================================================
# 🔍 LOGGING & CORE UTILITIES
# ==========================================================
def log(msg, level="INFO"):
    print(f"[{datetime.now(IST).strftime('%H:%M:%S')}] [{level}] {msg}")

def translate_to_telugu(text):
    try: return GoogleTranslator(source='auto', target='te').translate(text)
    except: return text 

def translate(text): return translate_to_telugu(text)

def safe_html_text(text):
    if not text: return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def clean_html_tags(text):
    if not text: return ""
    return re.sub('<[^>]+>', '', text).strip()

def check_if_important(text_to_check):
    if not text_to_check: return False
    lowercase_text = text_to_check.lower()
    for keyword in IMPORTANT_KEYWORDS:
        if re.search(r'\b' + re.escape(keyword) + r'\b', lowercase_text): return True
    return False

def is_duplicate_news(new_title):
    if not new_title: return False
    def clean_for_compare(t): return set(re.findall(r'\w+', t.lower()))
    new_words = clean_for_compare(new_title)
    if not new_words: return False
    now = datetime.now(IST)
    cutoff = now - timedelta(minutes=15)
    for n in reversed(rss_news_store):
        if isinstance(n, dict) and n.get('time') >= cutoff:
            existing_words = clean_for_compare(n.get('title', ''))
            if not existing_words: continue
            intersection = new_words.intersection(existing_words)
            smaller_len = min(len(new_words), len(existing_words))
            if smaller_len > 0:
                match_percentage = (len(intersection) / smaller_len) * 100
                if match_percentage >= 80: return True
    return False

# ==========================================================
# 📌 AUTO UNPIN OLD MESSAGES LOGIC
# ==========================================================
def auto_unpin_old_messages():
    global pinned_messages_store
    now = datetime.now(IST)
    cutoff_time = now - timedelta(days=2)  # 2 రోజుల కంటే పాత పిన్‌లను క్లీన్ చేస్తుంది
    remaining_pins = []
    
    for item in pinned_messages_store:
        if item["time"] < cutoff_time:
            try: 
                bot.unpin_chat_message(CHAT_ID, item["message_id"])
                log(f"🗑️ Automatically unpinned old message ID: {item['message_id']}")
            except Exception as e: 
                log(f"⚠️ Unpin Error: {e}", "WARNING")
        else: 
            remaining_pins.append(item)
    pinned_messages_store = remaining_pins

# ==========================================================
# 💬 TELEGRAM MESSAGE SENDING HANDLERS
# ==========================================================
def send_long_message(chat_id, text, parse_mode='HTML'):
    if len(text) <= 3800:
        try: bot.send_message(chat_id, text, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception as e:
            log(f"⚠️ HTML Parse Error, sending plain text: {e}", "WARNING")
            bot.send_message(chat_id, clean_html_tags(text))
        return

    lines = text.split('\n\n')
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) + 2 > 3800:
            try: bot.send_message(chat_id, current_chunk, parse_mode=parse_mode, disable_web_page_preview=True)
            except: bot.send_message(chat_id, clean_html_tags(current_chunk))
            current_chunk = line + '\n\n'
        else: current_chunk += line + '\n\n'
    if current_chunk:
        try: bot.send_message(chat_id, current_chunk, parse_mode=parse_mode, disable_web_page_preview=True)
        except: bot.send_message(chat_id, clean_html_tags(current_chunk))

def safe_send(msg, chat_id=CHAT_ID, parse_mode="HTML", disable_preview=True):
    MAX_LENGTH = 4000
    parts = [msg[i:i+MAX_LENGTH] for i in range(0, len(msg), MAX_LENGTH)] if len(msg) > MAX_LENGTH else [msg]
    for part in parts:
        for i in range(3):
            try:
                bot.send_message(chat_id, part, parse_mode=parse_mode, disable_web_page_preview=disable_preview)
                break
            except Exception as e:
                log(f"Retry {i+1} in safe_send: {e}", "WARNING")
                time.sleep(3)

def get_image_url(entry):
    try:
        if hasattr(entry, 'media_content') and entry.media_content:
            url = entry.media_content[0]['url']
            if str(url).startswith('http'): return url
        summary_raw = entry.get('summary') or entry.get('description') or ""
        soup = BeautifulSoup(str(summary_raw), 'html.parser')
        img = soup.find('img')
        if img and img.get('src'):
            url = img['src']
            if str(url).startswith('http'): return url
        if hasattr(entry, 'links'):
            for link in entry.links:
                if 'image' in link.get('type', ''): return link.get('href')
    except: return None
    return None

def manage_memory():
    global rss_news_store
    if len(rss_news_store) > MAX_NEWS:
        rss_news_store = rss_news_store[CLEAR_COUNT:]
        log(f"✅ Memory cleaned.")

# ==========================================================
# 🧠 GEMINI AI UTILITY
# ==========================================================
def safe_gemini(prompt):
    if not client: return "Gemini AI Key Error"
    for i in range(3):
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            return response.text
        except Exception as e:
            log(f"Gemini API Retry {i+1}: {e}", "WARNING")
            time.sleep(5)
    return "AI అందుబాటులో లేదు"

# ==========================================================
# 📈 MARKET DATA ENGINE & GAP ALERTS
# ==========================================================
def is_market_open(name):
    now_ist = datetime.now(IST)
    if "Bitcoin" in name or "BTC" in name: return "🟢"
    if any(x in name for x in ["GIFT Nifty", "WTI Crude", "Brent", "Gold", "Silver"]): return "🟢"

    mapping = {
        "Nikkei": (JP, "09:00", "15:00"), "Hang Seng": (HK, "09:30", "16:00"),
        "DAX": (EU, "09:00", "17:30"), "FTSE": (EU, "08:00", "16:30"),
        "Dow": (US, "09:30", "16:00"), "Nasdaq": (US, "09:30", "16:00"), 
        "S&P": (US, "09:30", "16:00"), "10Y": (US, "08:00", "17:00")
    }
    for key, (tz, start, end) in mapping.items():
        if key in name:
            now_local = now_ist.astimezone(tz).time()
            if datetime.strptime(start, "%H:%M").time() <= now_local < datetime.strptime(end, "%H:%M").time(): return "🟢"
            return "🔴"
    return "🔴" 

def get_data(symbol):
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", headers=HEADERS, timeout=10)
        result = r.json()["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        if (price is None or price == 0) and "indicators" in result:
            closes = [c for c in result["indicators"]["quote"][0].get("close", []) if c]
            if closes: price = closes[-1]
        prev_close = meta.get("previousClose") or meta.get("chartPreviousClose")
        return price, prev_close
    except: return None, None 

def check_gap_alert(name, price, prev_close, current_date):
    if not price or not prev_close: return
    gap_percent = ((price - prev_close) / prev_close) * 100
    gap_key = f"{name}_{current_date}_gap"
    if gap_key not in gap_alert_sent and abs(gap_percent) >= 1.0:
        direction = "📈 **GAP UP**" if gap_percent > 0 else "📉 **GAP DOWN**"
        safe_send(f"🚨 <b>GAP ALERT!</b>\n\n{name}\n{direction}: {gap_percent:+.2f}%\nCurrent: {price:.2f} | Prev Close: {prev_close:.2f}")
        gap_alert_sent[gap_key] = True 

# ==========================================================
# ⏱️ NIGHT TIME PULSE GENERATOR (రాత్రి 8 నుండి ఉదయం 6 వరకు - 6 AM కి పంపబడుతుంది)
# ==========================================================
def send_night_pulse_report():
    log("⏰ Automatically generating Night Market Pulse Report (8 PM to 6 AM)...")
    try:
        now = datetime.now(IST)
        cutoff_time = now - timedelta(hours=10)
        
        recent_important_news = []
        for n in rss_news_store:
            if isinstance(n, dict) and n.get('time') >= cutoff_time and n.get('type') == "NORMAL":
                raw_title = n.get('full_text', '').split("   ")[0]
                subject_match = re.search(r'\b[a-zA-Z0-9\s\&]+', raw_title)
                subject_title = subject_match.group(0).strip() if subject_match else "Market Update"
                
                news_block = (
                    f"<b>{subject_title}:-</b>\n"
                    f"  {safe_html_text(n.get('title', ''))}\n"
                    f"<b>సమ్మరీ:-</b>\n"
                    f"  {safe_html_text(n.get('desc', ''))}"
                )
                recent_important_news.append(news_block)

        if not recent_important_news:
            no_news_msg = "⚡ <b>🎯 NIGHT MARKET PULSE (06:00 AM)</b> ⚡\n📌 <b>మార్కెట్ అప్‌డేట్:</b> నిన్న రాత్రి 8:00 PM నుండి ఈరోజు ఉదయం 6:00 AM వరకు కీలకమైన వార్తలు ఏవీ రాలేదు సార్."
            bot.send_message(CHAT_ID, no_news_msg, parse_mode='HTML')
            log("📌 Night Pulse Report Completed: No news recorded.")
            return

        recent_important_news = list(dict.fromkeys(recent_important_news))
        pulse_body = "\n\n🔹🔹🔹\n\n".join(recent_important_news)
        full_report_msg = f"⚡ <b>🎯 NIGHT MARKET PULSE (06:00 AM)</b> ⚡\n(రాత్రి 08:00 PM నుండి ఉదయం 6:00 AM వరకు వచ్చిన కీలకమైన వార్తలు)\n\n{pulse_body}"
        
        send_long_message(CHAT_ID, full_report_msg, parse_mode='HTML')
        log(f"📌 Night Pulse Report Sent Successfully. Total items: {len(recent_important_news)}")
    except Exception as e: log(f"❌ Night Pulse Error: {e}", "ERROR")

# ==========================================================
# 🔄 LIVE RSS LOOPS & FEEDS
# ==========================================================
RSS_FEEDS = {
    "CNBC": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/latest.xml",
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
}

X_RSS_FEEDS = {
    "NDTV Profit (X)": "https://nitter.net/NDTVProfitIndia/rss",
    "ET NOW (X)": "https://nitter.net/ETNOWlive/rss",
    "Redbox X": "https://nitter.net/REDBOXINDIA/rss" 
}

def clean_x_text(text):
    junk = [r'http\S+', r'www\.\S+', r'@\w+', r'#\w+', r'⤵️', r'\|']
    for p in junk: text = re.sub(p, '', text, flags=re.IGNORECASE)
    return clean_html_tags(re.sub(r'\s+', ' ', text).strip())

def fetch_normal_rss():
    log("🌍 NORMAL RSS LOOP STARTED...")
    while True:
        for name, url in RSS_FEEDS.items():
            try:
                res = requests.get(url, headers=HEADERS, timeout=15)
                feed = feedparser.parse(res.content)
                if not feed.entries: continue

                for entry in feed.entries[:10]:
                    link = entry.get("link", "").strip()
                    title = clean_html_tags(entry.get("title", ""))
                    tel_title = translate(title)

                    if not link or link in sent_links or is_duplicate_news(tel_title) or is_duplicate_news(title): continue
                    sent_links.add(link)
                    
                    summary_raw = entry.get("summary") or entry.get("description") or ""
                    clean_desc = clean_html_tags(summary_raw).replace("\n", " ")
                    tel_desc = translate(clean_desc[:800])
                    
                    msg = (
                        f"📌 <b>{safe_html_text(tel_title)}</b>\n\n"
                        f"🇬🇧 <b>English Title:</b>\n{safe_html_text(title)}\n\n"
                        f"🇮🇳 <b>తెలుగు సమ్మరీ:</b>\n{safe_html_text(tel_desc)}\n\n"
                        f"🌐 <b>{safe_html_text(name)}</b>\n"
                        f'🔗 <a href="https://translate.google.com/translate?sl=en&tl=te&u={link}">Read More in Telugu</a> | <a href="{link}">English Original</a>'
                    )
                    ist_now = datetime.now(IST)
                    rss_news_store.append({"time": ist_now, "type": "NORMAL", "source": name, "title": tel_title, "desc": tel_desc, "link": link, "full_text": title + " " + clean_desc})
                    manage_memory()

                    try:
                        bot.send_message(CHAT_ID, msg, parse_mode='HTML', disable_web_page_preview=False)
                    except Exception as e: log(f"❌ Telegram error in Normal RSS: {e}", "ERROR")
                    time.sleep(1)
            except Exception as e: log(f"❌ RSS Error {name}: {e}", "ERROR")
        time.sleep(120)

def fetch_x_rss():
    log("🐦 X RSS STARTED...")
    scraper = cloudscraper.create_scraper()
    while True:
        for name, url in X_RSS_FEEDS.items():
            try:
                res = scraper.get(url, timeout=20)
                if res.status_code != 200: continue
                feed = feedparser.parse(res.content)

                for entry in feed.entries[:5]:
                    link = entry.get("link", "").strip()
                    title = clean_x_text(entry.get("title", ""))
                    tel_title = translate(title)

                    if not link or link in sent_links or is_duplicate_news(tel_title) or is_duplicate_news(title): continue
                    sent_links.add(link)
                    
                    is_important = check_if_important(title) or check_if_important(tel_title)
                    g_trans_url = f"https://translate.google.com/translate?sl=en&tl=te&u={link}"

                    # 🎯 మెయిన్ ఛానల్ కోసం మీ ఒరిజినల్ హెడర్ ఫార్మాట్ అలాగే ఉంచాను సార్ (ఎలాంటి మార్పు లేదు)
                    header = f"🚀 <b>{safe_html_text(name)} Update</b>\n\n"
                    msg = f"{header}📌 <b>{safe_html_text(tel_title)}</b>\n\n🇬🇧 {safe_html_text(title)}\n\n🔗 <a href='{g_trans_url}'>Read More in Telugu</a> | <a href='{link}'>English Original</a>"
                    
                    ist_now = datetime.now(IST)
                    rss_news_store.append({"time": ist_now, "type": "X", "source": name, "title": tel_title, "link": link})
                    manage_memory()

                    image_url = get_image_url(entry)
                    try:
                        # 1. మెయిన్ ఛానల్‌కు అలర్ట్ మీ పాత పద్ధతిలోనే ఫోటో ఉంటే ఫోటోతో సహా వెళ్తుంది సార్
                        if image_url:
                            try: sent_msg = bot.send_photo(CHAT_ID, image_url, caption=msg[:1024], parse_mode='HTML')
                            except Exception: sent_msg = bot.send_photo(CHAT_ID, image_url, caption=clean_html_tags(msg)[:1024])
                        else:
                            sent_msg = bot.send_message(CHAT_ID, msg, parse_mode='HTML', disable_web_page_preview=False)
                            
                    except Exception as e: log(f"❌ X Telegram Error: {e}", "ERROR")
                    time.sleep(2)
            except Exception as e: log(f"❌ X RSS Error {name}: {e}", "ERROR")
        time.sleep(120)

def send_market_table():
    log("📊 Automatically broadcasting Global Market Live Table...")
    table_content = f"{'-' * 52}\n"
    table_content += f"{'Mkt':<14} {'Price':>9} {'+/-Pts':>8} {'%':>6} {'Trnd':>4}\n"
    table_content += f"{'-' * 52}\n"
    current_date = datetime.now(IST).date()
    
    for name, sym in symbols.items():
        price, prev_close = get_data(sym)
        if price and prev_close:
            diff = price - prev_close
            change = (diff / prev_close) * 100
            check_gap_alert(name, price, prev_close, current_date)
            trend = "📈" if change > 0.3 else ("📉" if change < -0.3 else "➖")
            status = is_market_open(name)
            short_name = name.split(' (')[0][:11]
            table_content += f"{status}{short_name:<12} {price:>9.1f} {diff:>8.1f} {change:>5.1f}% {trend:>2}\n"
    try: safe_send(f"📊 <b>Global Market Live</b>\n<pre>{table_content}</pre>")
    except Exception as e: print(e)

def calculate_historical_target_time(hour_input):
    now = datetime.now(IST)
    target = now.replace(hour=hour_input, minute=0, second=0, microsecond=0)
    if hour_input >= now.hour: target = target - timedelta(days=1)
    return target

def main_loop():
    global last_reset_date
    while True:
        try:
            now_ist_str = datetime.now(IST).strftime("%H:%M")
            current_date = datetime.now(IST).date()
            if current_date > last_reset_date:
                sent_alerts.clear()
                sudden_move_sent.clear()
                gap_alert_sent.clear()
                last_reset_date = current_date
                log("🔄 కొత్త రోజు ప్రారంభమైంది: డేటా రీసెట్ చేయబడింది.")

            for m_name, (o_time, _) in TIMINGS.items():
                alert_id = f"{m_name}_{current_date}"
                if now_ist_str == o_time and alert_id not in sent_alerts:
                    safe_send(f"🔔 <b>MARKET OPEN ALERT</b>\n\n🚀 {m_name} ప్రారంభమైంది! (IST: {o_time})")
                    sent_alerts[alert_id] = True 

            for name, sym in symbols.items():
                if is_market_open(name) == "🟢":
                    price, prev_close = get_data(sym)
                    if price and prev_close:
                        diff = price - prev_close
                        change = (diff / prev_close) * 100
                        check_gap_alert(name, price, prev_close, current_date) 
                        if abs(change) >= 1.50 and f"{name}_{current_date}_mv" not in sudden_move_sent:
                            safe_send(f"🚨 <b>VOLATILITY ALERT!</b>\n{name}: {change:.2f}% భారీ మార్పు!")
                            sudden_move_sent[f"{name}_{current_date}_mv"] = True 
        except Exception as e: print(f"Error in global loop: {e}")
        gc.collect() 
        time.sleep(60)

# ==========================================================
# 🤖 TELEGRAM BOT COMMAND HANDLERS
# ==========================================================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    log(f"📥 User {message.chat.id} triggered /start command.")
    safe_send("🚀 <b>బాట్ రెడీ చంటి గారు! అన్ని ఫిల్టర్స్ లోడ్ అయ్యాయి.</b>", chat_id=message.chat.id)

# ==========================================================
# ⏱️ FETCH NEWS BY HOUR (సరిచేసిన చంటి గారి పవర్‌ఫుల్ కమాండ్స్)
# ==========================================================
@bot.message_handler(commands=['get', 'getred', 'getx'])
def get_news_by_time(message):
    cmd_name = message.text.split()[0]
    log(f"📥 Command Received: User {message.chat.id} triggered '{message.text}'")
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit(): 
        log(f"⚠️ Command Rejected: Invalid or missing hour argument in '{message.text}'")
        return
    hour = int(args[1])
    
    log(f"⚡ Processing '{cmd_name} {hour}': Sending quick interactive response to Telegram...")
    waiting_msg = bot.send_message(
        message.chat.id, 
        "⏳ <b>చంటి గారు, RSS ఫీడ్‌లోని కీలకమైన వార్తలను తీసుకొస్తున్నాను... కొంచెం సమయం పడుతుంది సార్.</b>", 
        parse_mode='HTML'
    )
    
    target_time = calculate_historical_target_time(hour)
    raw_date_part = target_time.strftime('%d-%m-%Y')
    clean_date_part = "-".join([str(int(x)) for x in raw_date_part.split('-')])
    time_part = target_time.strftime('%I %p').lstrip('0')
    cutoff_display_str = f"{clean_date_part} {time_part}"
    
    current_date_str = datetime.now(IST).strftime('%d-%b-%Y')
    current_time_str = datetime.now(IST).strftime('%H:%M')
    
    source_type = "NORMAL"
    if 'getred' in message.text: source_type = "REDBOX"
    elif 'getx' in message.text: source_type = "X"
    
    log(f"🔍 Filtering rss_news_store since {cutoff_display_str} for source type: '{source_type}'...")
    filtered = []
    for n in rss_news_store:
        if isinstance(n, dict) and n.get('time') >= target_time:
            if source_type == "REDBOX" and n.get('source') == "Redbox X": filtered.append(n)
            elif source_type == "X" and n.get('type') == "X" and n.get('source') != "Redbox X": filtered.append(n)
            elif source_type == "NORMAL" and n.get('type') == "NORMAL": filtered.append(n)
            
    filtered.sort(key=lambda x: x['time'], reverse=True)
    log(f"📊 Found {len(filtered)} matching news items in store.")
    
    icon = "🕒" if source_type == "NORMAL" else ("🚩" if source_type == "REDBOX" else "🐦")
    title_label = "Normal RSS" if source_type == "NORMAL" else ("Redbox" if source_type == "REDBOX" else "X RSS")
    
    report_header = (
        f"{icon} <b>{title_label} ({cutoff_display_str} నుండి వచ్చిన మొత్తం వార్తలు):</b>\n"
        f"📅 <b>తేదీ:</b> {current_date_str} | <b>సమయం:</b> {current_time_str}\n"
        f"──────────────────────"
    )
    
    try: 
        bot.delete_message(message.chat.id, waiting_msg.message_id)
        log("🗑️ Quick interactive waiting message deleted successfully.")
    except Exception as err: 
        log(f"⚠️ Failed to delete waiting message: {err}", "WARNING")
    
    bot.send_message(message.chat.id, report_header, parse_mode='HTML')
    
    if not filtered:
        bot.send_message(message.chat.id, f"⏳ ఈ సమయం ({cutoff_display_str}) నుండి ఎటువంటి వార్తలు రికార్డ్ అవ్వలేదు సార్.", parse_mode='HTML')
        log(f"🔚 Finished '{cmd_name} {hour}': No data found to send.")
        return
        
    log(f"🚀 Broadcasting {len(filtered)} items sequentially to Chat ID {message.chat.id}...")
    for i, n in enumerate(filtered, 1):
        # వార్త టెలిగ్రామ్ బాట్ లోపలికి వచ్చిన కరెక్ట్ సమయం (IST)
        arrival_time = n['time'].astimezone(IST).strftime('%I:%M %p')
        
        if source_type == "NORMAL":
            raw_title = n.get('full_text', '').split("   ")[0]
            subject_match = re.search(r'\b[a-zA-Z0-9\s\&]+', raw_title)
            
            # ఇంగ్లీష్ పెద్ద టైటిల్స్ రాకుండా మొదటి 3 పదాల ముఖ్యాంశాన్ని మాత్రమే పట్టుకుంటుంది సార్
            if subject_match:
                full_subject = subject_match.group(0).strip()
                words = full_subject.split()
                subject_title = " ".join(words[:3]) if len(words) > 3 else full_subject
            else:
                subject_title = "Market Update"
                
            g_url = f"https://translate.google.com/translate?sl=en&tl=te&u={n.get('link','')}"
            
            # లోతైన పూర్తి వివరణ కోసం టైటిల్ మరియు డిస్క్రిప్షన్ రెండింటినీ కలిపి చూపిస్తుంది
            full_telugu_explanation = f"{n['title']}\n  {n.get('desc', '')}"
            
            msg_block = (
                f"⏰ <b>[{arrival_time}]</b>\n"
                f"<b>{subject_title}:-</b>\n\n"
                f"  {safe_html_text(full_telugu_explanation)}\n\n"
                f"🔗 <a href='{g_url}'>Read More in Telugu</a> | <a href='{n.get('link','')}'>English Original</a>"
            )
            bot.send_message(message.chat.id, msg_block, parse_mode='HTML', disable_web_page_preview=True)
        else:
            # X-RSS మరియు రెడ్‌బాక్స్ కోసం కూడా క్లీన్ షార్ట్ స్ట్రక్చర్
            raw_x_text = n['title']
            x_words = raw_x_text.split()
            short_x_subject = " ".join(x_words[:3]) if len(x_words) > 3 else "Flash Update"
            
            msg_block = (
                f"⏰ <b>[{arrival_time}]</b>\n"
                f"{icon} <b>{short_x_subject}:-</b>\n\n"
                f"  {safe_html_text(raw_x_text)}"
            )
            bot.send_message(message.chat.id, msg_block, parse_mode='HTML', disable_web_page_preview=True)
            
        time.sleep(0.3)
        
    bot.send_message(message.chat.id, f"──────────────────────\n📌 <b>మొత్తం వార్తల సంఖ్య: {len(filtered)}</b>", parse_mode='HTML')
    log(f"✅ Success: Completed broadcasting all {len(filtered)} news items for '{cmd_name} {hour}'.")
    
# ==========================================================
# 🎯 MASTER AI SUMMARY COMMAND (10-BATCH GEMINI SAFE SYSTEM)
# ==========================================================
@bot.message_handler(commands=['summary'])
def master_ai_summary_by_hours(message):
    # 📝 కమాండ్ రాగానే లాగ్ ప్రింట్ అవుతుంది సార్
    log(f"📥 Command Received: User {message.chat.id} triggered '{message.text}'")
    args = message.text.split()
    hour = int(args[1]) if len(args) > 1 and args[1].isdigit() else 6
    
    target_time = calculate_historical_target_time(hour)
    
    # కేవలం ET NOW & NDTV Profit వార్తలను మాత్రమే సేకరించడం
    x_news = [
        n for n in rss_news_store 
        if isinstance(n, dict) 
        and n.get('time') >= target_time 
        and n.get('type') == "X" 
        and n.get('source') != "Redbox X"
    ]
    total_news_count = len(x_news)
    
    if not x_news:
        bot.send_message(message.chat.id, f"⏳ <b>చంటి గారు, ఈ టైమ్ విండో ({hour} గంటలు) లో ET NOW లేదా NDTV Profit వార్తలు ఏవీ లేవు సార్.</b>", parse_mode='HTML')
        log(f"🔚 Finished /summary {hour}: No matching ET NOW / NDTV records found.")
        return

    # 🎯 20 చొప్పున బ్యాచ్‌లుగా విడదీయడం
    batch_size = 20
    total_batches = (total_news_count + batch_size - 1) // batch_size
    
    # ప్రతి బ్యాచ్ మధ్య 20 సెకన్ల గ్యాప్ ప్రకారం పట్టే మొత్తం అంచనా సమయం లెక్కింపు
    estimated_seconds = (total_batches - 1) * 20 
    minutes, seconds = divmod(estimated_seconds, 60)
    time_display = f"{minutes} నిమిషాల {seconds} సెకన్లు" if minutes > 0 else f"{seconds} సెకన్లు"

    log(f"⚡ Processing /summary {hour}: Broadcasting waiting status. Batches: {total_batches}, Est time: {time_display}")
    waiting_msg = bot.send_message(
        message.chat.id, 
        f"⏳ <b>చంటి గారు, గత {hour} గంటల ET NOW & NDTV Profit వార్తల సమాచారాన్ని సేకరిస్తున్నాను...</b>\n\n"
        f"📊 <b>మొత్తం వార్తలు:</b> {total_news_count} ({total_batches} బ్యాచ్‌లు)\n"
        f"⏰ <b>పట్టే అంచనా సమయం:</b> ~{time_display}\n\n"
        f"<i>⚠️ డైలీ కోటా అవ్వకుండా ఉండటానికి ప్రతి 20 వార్తలను ఒకే బ్యాచ్‌గా చేసి, బ్యాచ్ కి మధ్య 20 సెకన్ల విరామంతో జెమిని ఏఐ స్కాన్ చేస్తోంది సార్. దయచేసి ఓపిక పట్టండి...</i>", 
        parse_mode='HTML'
    )
    
    aggregated_analysis_chunks = []
    log(f"📋 Total items to process (10-Batch System): {total_news_count}. Total Batches: {total_batches}. Delay: 20s.")
    
    start_time = time.time()
    batch_counter = 1
    
    try:
        # 10 చొప్పున బల్క్ బ్యాచ్ లూప్ రన్ అవుతుంది
        for idx in range(0, total_news_count, batch_size):
            log(f"🧠 AI Batch #{batch_counter}/{total_batches} processing...")
            batch = x_news[idx : idx + batch_size]
            batch_text = "\n".join([f"- {n['title']}" for n in batch])
            
            # 🎯 ఇంటర్నేషనల్ రీసెర్చ్ హెడ్ ప్రాంప్ట్ ఇక్కడ బ్యాచ్‌కి జత చేసాను సార్
            chunk_prompt = f"""
            You are acting as the Head of an Elite International Research Team. Review this batch of market live updates:
            {batch_text}
            
            Extract and summarize all critical technical insights, corporate declarations, national developments, and macro global changes. 
            Keep the layout compact and concise for synthesis.
            """
            
            # జెమిని ఏఐ కాల్ (కేవలం బ్యాచ్ ల సంఖ్య మాత్రమే కాల్స్ వెళ్తాయి)
            chunk_analysis = safe_gemini(chunk_prompt)
            
            if "AI అందుబాటులో లేదు" in chunk_analysis or "Key Error" in chunk_analysis:
                raise Exception("Gemini API responding with errors or Rate Limits.")
                
            aggregated_analysis_chunks.append(chunk_analysis)
            log(f"✅ AI Batch #{batch_counter}/{total_batches} processed successfully.")
            
            # లైవ్‌గా టెలిగ్రామ్ స్క్రీన్‌పై టైమర్ కౌంట్‌డౌన్ అప్‌డేట్ చేస్తూ 20 సెకన్లు ఆగుతుంది సార్
            if idx + batch_size < total_news_count:
                remaining_batches = total_batches - batch_counter
                rem_seconds = remaining_batches * 20
                rem_min, rem_sec = divmod(rem_seconds, 60)
                rem_display = f"{rem_min}m {rem_sec}s" if rem_min > 0 else f"{rem_sec}s"
                
                try:
                    bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=waiting_msg.message_id,
                        text=f"⏳ <b>జెమిని ద్వారా బల్క్ బ్యాచ్ ప్రాసెసింగ్ జరుగుతోంది సార్...</b>\n\n"
                             f"🔄 <b>పూర్తయిన బ్యాచ్‌లు:</b> {batch_counter}/{total_batches}\n"
                             f"⏳ <b>మిగిలిన సమయం:</b> ~{rem_display}\n\n"
                             f"<i>📊 స్కాన్ అవుతున్న వార్తలు: {idx + batch_size} వరకు విజయవంతంగా పూర్తయింది.</i>",
                        parse_mode='HTML'
                    )
                except:
                    pass
                    
                log(f"💤 Sleeping for 20 seconds before next batch to completely avoid 429 RPM limit...")
                time.sleep(20) 
            batch_counter += 1
        
        # మాస్టర్ సమ్మరీ ప్రాంప్ట్ రన్ చేయడం
        log("🤖 All batches processed via Gemini. Triggering Final Master Synthesis Prompt...")
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=waiting_msg.message_id,
                text="<b>📝 అన్ని బ్యాచ్‌ల సేకరణ పూర్తయింది చంటి గారు! గ్లోబల్ రీసెర్చ్ టీమ్ హెడ్ ఫైనల్ మాస్టర్ రిపోర్ట్ తయారు చేస్తున్నారు... ఒకే ఒక్క నిమిషం సార్.</b>",
                parse_mode='HTML'
            )
        except:
            pass

        combined_raw_analysis = "\n\n".join(aggregated_analysis_chunks)
        
        master_research_prompt = f"""
        మీరు ఒక ఇంటర్నేషనల్ రీసెర్చ్ టీమ్ హెడ్ (Elite Global Institutional Research Team Head). 
        గత కొన్ని గంటలుగా సేకరించిన ఈ క్రింది కీలకమైన ఆర్థిక మరియు మార్కెట్ సమాచార సమూహాన్ని పూర్తిగా విశ్లేషించి, ఒక లోతైన ప్రొఫెషనల్ నివేదికను సిద్ధం చేయండి.
        
        DATASET TO ANALYZE:
        {combined_raw_analysis}
        
        Generate a highly polished, deep institutional summary in clean Telugu. Follow this explicit 5-part hierarchical structure strictly. Do not use generic markdown headers or cross-sectional merges. Every point must convey simple, sharp insight.
        
        1. Market Review
           Provide a sharp, definitive evaluation of the immediate market trajectory, momentum, and benchmark index drivers.
           
        2. Corporate Affairs
           Group corporate news explicitly SECTOR-BY-SECTOR (e.g., Defense, Renewable Energy, Railways, Banking, Tech). 
           Ensure there is a visible paragraph gap between distinct sectors, and a clear sub-bullet gap between corporate news items within the same sector. Do not blend stories together. Every entry must have a simple insight.
           
        3. National News
           Detail key domestic macroeconomic policy changes, regulatory updates, or government cabinet decisions inside India.
           
        4. Global News
           Outline critical international developments, cross-border geopolitical impacts, or global central bank shifts.
           
        5. AI Conclusion
           Deliver a single, unified, sophisticated macro synthesis explanation merging all sections to define the tactical market path forward.
           
        Formatting Constraints:
        - Language: Professional, business-grade Telugu script only.
        - Layout: Ensure visible structural spacing between segments. Keep sentences clear, accurate, and easy to understand for Chanti Garu.
        """
        
        final_master_summary = safe_gemini(master_research_prompt)
        
        # మొత్తం పట్టిన టైమ్ లెక్కింపు
        end_time = time.time()
        total_taken_seconds = int(end_time - start_time)
        t_min, t_sec = divmod(total_taken_seconds, 60)
        taken_display = f"{t_min} నిమిషాల {t_sec} సెకన్లు" if t_min > 0 else f"{t_sec} sec"

        try: 
            bot.delete_message(message.chat.id, waiting_msg.message_id)
            log("🗑️ Finalizing report: Waiting message deleted.")
        except: 
            pass
        
        current_time_str = datetime.now(IST).strftime('%I:%M %p')
        header = f"💥 <b>GLOBAL RESEARCH TEAM MASTER PULSE</b> 💥\n" \
                 f"🏢 <b>నివేదిక:</b> రీసెర్చ్ టీమ్ హెడ్ అనాలసిస్ (Gemini 10-Batch Safe System)\n" \
                 f"🕒 <b>విశ్లేషణ సమయం:</b> గత {hour} గంటల డేటా (Generated at {current_time_str})\n" \
                 f"📊 <b>మొత్తం స్కాన్ చేసిన వార్తలు:</b> {total_news_count}\n" \
                 f"⏱️ <b>మొత్తం పట్టిన సమయం:</b> {taken_display}\n" \
                 f"──────────────────────\n\n"
        
        send_long_message(message.chat.id, header + final_master_summary, parse_mode='HTML')
        log(f"✅ Success: Master AI Summary delivered in {taken_display} to user {message.chat.id}.")

    except Exception as e:
        log(f"❌ Master Summary Logic Error: {e}", "ERROR")
        try:
            bot.delete_message(message.chat.id, waiting_msg.message_id)
        except:
            pass
        bot.send_message(
            message.chat.id,
            f"❌ <b>సమ్మరీ లోపం (AI Error):</b>\n\n"
            f"చంటి గారు, జెమిని API కనెక్టివిటీ లో చిన్న లోపం వచ్చింది సార్.\n"
            f"<code>రిపోర్ట్ ఎర్రర్: {safe_html_text(str(e)[:200])}</code>\n\n"
            f"<i>💡 సూచన: కొద్దిసేపు ఆగి మళ్లీ ప్రయత్నించండి సార్, సమస్య సర్దుకుంటుంది!</i>",
            parse_mode='HTML'
        )

def get_commands_list_text():
    return ("╔════════════════════════╗\n    🤖  <b>MARKET BOT COMMANDS</b>  📊\n╚════════════════════════╝\n\n"
            "🧠 <b>AI DEEP RESEARCH SUMMARY</b>\n🔹 <code>/summary [hours]</code> (X-RSS 10-Batch Filter)\n\n"
            "⏱ <b>FETCH NEWS BY HOUR</b>\n🔸 <code>/get [hour]</code>\n🔸 <code>/getx [hour]</code>\n🔸 <code>/getred [hour]</code>\n"
            "──────────────────────\n📌 <i>చంటి గారు, కమాండ్ కాపీ చేయడానికి Tap చేయండి!</i>")

@bot.message_handler(commands=['list'])
def list_commands(message): 
    log(f"📥 User {message.chat.id} requested commands /list.")
    safe_send(get_commands_list_text(), chat_id=message.chat.id)

# ==========================================================
# ⏱️ BACKGROUND ALERTS & WEB SERVER 
# ==========================================================
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

scheduler.add_job(send_night_pulse_report, 'cron', hour=6, minute=0)
scheduler.add_job(send_market_table, 'interval', minutes=10)
scheduler.start()

app = Flask('')
@app.route('/')
def home(): return "Bot is running perfectly!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================================
# 🏁 MAIN EXECUTION EXECUTOR
# ==========================================================
if __name__ == "__main__":
    log("🚀 Starting Combined Master Market Bot...")
    try: safe_send("✅ చంటి గారు, కంబైన్డ్ మాస్టర్ బాట్ విజయవంతంగా ప్రారంభమైంది!")
    except: pass

    Thread(target=run_server).start()
    Thread(target=main_loop, daemon=True).start()
    Thread(target=fetch_normal_rss, daemon=True).start()
    Thread(target=fetch_x_rss, daemon=True).start()
    
    while True:
        try: bot.infinity_polling(timeout=90, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            log(f"⚠️ Connection lost, reconnecting in 10s: {e}", "WARNING")
            time.sleep(10)
