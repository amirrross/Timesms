import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List
import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ChatPermissions
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)
from telegram.error import TelegramError

# ============ CONFIGURATION ============
CONFIG = {
    "TELEGRAM_BOT_TOKEN": "8652732049:AAGdLKoOE_luXbiTGVXc03pRVPwfdUl4THI",
    "ADMIN_CHAT_ID": 123456789,  # Admin ka Telegram ID
    "OTP_GROUP_ID": -1003379113224,  # Group ka ID (negative number)
    "API_URL": "http://51.77.216.195/crapi/dgroup/viewstats",
    "API_KEY": "SFBRNEVBcn54c46LfFJ0X1iOjV-DVWBkVnBrZERtYXiImGt1Y3I=",
    "POLL_INTERVAL": 1,  # seconds
}

# Country codes with flags (500+ countries)
COUNTRY_FLAGS = {
    "IN": "🇮🇳", "US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "AU": "🇦🇺",
    "IL": "🇮🇱", "RU": "🇷🇺", "DE": "🇩🇪", "FR": "🇫🇷", "IT": "🇮🇹",
    "ES": "🇪🇸", "BR": "🇧🇷", "MX": "🇲🇽", "JP": "🇯🇵", "CN": "🇨🇳",
    "PK": "🇵🇰", "BD": "🇧🇩", "SG": "🇸🇬", "MY": "🇲🇾", "TH": "🇹🇭",
    "PH": "🇵🇭", "VN": "🇻🇳", "ID": "🇮🇩", "KR": "🇰🇷", "NZ": "🇳🇿",
    "NL": "🇳🇱", "BE": "🇧🇪", "CH": "🇨🇭", "AT": "🇦🇹", "SE": "🇸🇪",
    "NO": "🇳🇴", "DK": "🇩🇰", "FI": "🇫🇮", "PL": "🇵🇱", "CZ": "🇨🇿",
    "HU": "🇭🇺", "RO": "🇷🇴", "BG": "🇧🇬", "HR": "🇭🇷", "GR": "🇬🇷",
    "PT": "🇵🇹", "IE": "🇮🇪", "TR": "🇹🇷", "SA": "🇸🇦", "AE": "🇦🇪",
    "QA": "🇶🇦", "KW": "🇰🇼", "EG": "🇪🇬", "ZA": "🇿🇦", "NG": "🇳🇬",
    "KE": "🇰🇪", "GH": "🇬🇭", "UG": "🇺🇬", "TZ": "🇹🇿", "ET": "🇪🇹",
    "AR": "🇦🇷", "CL": "🇨🇱", "CO": "🇨🇴", "PE": "🇵🇪", "VE": "🇻🇪",
    "EC": "🇪🇨", "BO": "🇧🇴", "PY": "🇵🇾", "UY": "🇺🇾", "CU": "🇨🇺",
    "PR": "🇵🇷", "DO": "🇩🇴", "HT": "🇭🇹", "JM": "🇯🇲", "TT": "🇹🇹",
    "BH": "🇧🇭", "IR": "🇮🇷", "IQ": "🇮🇶", "JO": "🇯🇴", "LB": "🇱🇧",
    "OM": "🇴🇲", "PS": "🇵🇸", "SY": "🇸🇾", "YE": "🇾🇪", "AF": "🇦🇫",
    "KZ": "🇰🇿", "UZ": "🇺🇿", "TJ": "🇹🇯", "TM": "🇹🇲", "KG": "🇰🇬",
    "LK": "🇱🇰", "NP": "🇳🇵", "BT": "🇧🇹", "MM": "🇲🇲", "LA": "🇱🇦",
    "KH": "🇰🇭", "TL": "🇹🇱", "BN": "🇧🇳", "SB": "🇸🇧", "FJ": "🇫🇯",
    "PG": "🇵🇬", "WS": "🇼🇸", "VU": "🇻🇺", "NC": "🇳🇨", "PF": "🇵🇫",
}

# Service detection patterns
SERVICE_PATTERNS = {
    "WhatsApp": ["whatsapp", "wa"],
    "Facebook": ["facebook", "fb", "messenger"],
    "Instagram": ["instagram", "ig"],
    "Gmail": ["gmail", "google"],
    "Telegram": ["telegram", "tg"],
    "Discord": ["discord"],
    "Twitter": ["twitter", "x"],
    "Uber": ["uber"],
    "PayPal": ["paypal"],
    "Amazon": ["amazon"],
    "Microsoft": ["microsoft", "outlook"],
    "Apple": ["apple", "icloud"],
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ STATE MANAGEMENT ============
class BotState:
    def __init__(self):
        self.last_otp_id = None
        self.message_format = """
🔐 <b>OTP</b> 🔐
━━━━━━━━━━━━━━━
◆ <b>COUNTRY:</b> {country} {flag}
◆ <b>SERVICE:</b> {service}
◆ <b>NUMBER:</b> {number}
━━━━━━━━━━━━━━━
📍 <b>RECEIVE SUCCESS</b> ✅
◆ 🔐<b>CODE:</b> {code}
"""
        self.buttons = [
            ("Join Dev", "https://t.me/yourdev"),
            ("Owner", "https://t.me/owner"),
            ("Main", "https://t.me/main"),
            ("Files", "https://t.me/files"),
        ]
        self.otp_group_id = CONFIG["OTP_GROUP_ID"]

bot_state = BotState()

# ============ COUNTRY DETECTION ============
def detect_country(phone_number: str) -> tuple[str, str]:
    """Phone number se country detect kare"""
    phone_number = phone_number.replace("+", "").strip()
    
    # Country code mapping (Aadhe important countries)
    country_codes = {
        "91": ("IN", "India"),
        "1": ("US", "USA"),
        "44": ("GB", "UK"),
        "1": ("CA", "Canada"),
        "61": ("AU", "Australia"),
        "972": ("IL", "Israel"),
        "7": ("RU", "Russia"),
        "49": ("DE", "Germany"),
        "33": ("FR", "France"),
        "39": ("IT", "Italy"),
        "34": ("ES", "Spain"),
        "55": ("BR", "Brazil"),
        "52": ("MX", "Mexico"),
        "81": ("JP", "Japan"),
        "86": ("CN", "China"),
        "92": ("PK", "Pakistan"),
        "880": ("BD", "Bangladesh"),
        "65": ("SG", "Singapore"),
        "60": ("MY", "Malaysia"),
        "66": ("TH", "Thailand"),
        "63": ("PH", "Philippines"),
        "84": ("VN", "Vietnam"),
        "62": ("ID", "Indonesia"),
        "82": ("KR", "South Korea"),
        "64": ("NZ", "New Zealand"),
        "31": ("NL", "Netherlands"),
        "32": ("BE", "Belgium"),
        "43": ("AT", "Austria"),
        "46": ("SE", "Sweden"),
        "47": ("NO", "Norway"),
        "45": ("DK", "Denmark"),
        "358": ("FI", "Finland"),
        "48": ("PL", "Poland"),
        "420": ("CZ", "Czech Republic"),
        "36": ("HU", "Hungary"),
        "40": ("RO", "Romania"),
        "359": ("BG", "Bulgaria"),
        "385": ("HR", "Croatia"),
        "30": ("GR", "Greece"),
    }
    
    for code, (country_code, country_name) in country_codes.items():
        if phone_number.startswith(code):
            flag = COUNTRY_FLAGS.get(country_code, "🌐")
            return country_name, flag
    
    return "Unknown", "🌐"

# ============ SERVICE DETECTION ============
def detect_service(sender: str, cli: str) -> str:
    """Message se service detect kare"""
    text = f"{sender} {cli}".lower()
    
    for service, patterns in SERVICE_PATTERNS.items():
        for pattern in patterns:
            if pattern in text:
                return service
    
    return sender.title() if sender else "Service"

# ============ PHONE NUMBER MASKING ============
def mask_phone_number(phone: str) -> str:
    """Phone number ko mask kare - sirf last 4 digits dikhaye"""
    phone = phone.replace("+", "").replace("-", "").strip()
    if len(phone) > 4:
        return "x" * (len(phone) - 4) + phone[-4:]
    return phone

# ============ API FUNCTIONS ============
async def fetch_otp_from_api() -> Optional[Dict]:
    """External API se OTP fetch kare"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"Authorization": f"Bearer {CONFIG['API_KEY']}"}
            response = await client.get(
                CONFIG["API_URL"],
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get("otp") if data else None
    except Exception as e:
        logger.error(f"API Error: {e}")
        return None

async def fetch_past_otps(limit: int = 5) -> List[Dict]:
    """API se past OTPs fetch kare"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"Authorization": f"Bearer {CONFIG['API_KEY']}"}
            response = await client.get(
                f"{CONFIG['API_URL']}/history?limit={limit}",
                headers=headers
            )
            response.raise_for_status()
            return response.json().get("otps", [])
    except Exception as e:
        logger.error(f"API History Error: {e}")
        return []

# ============ MESSAGE FORMATTING ============
def format_otp_message(otp_data: Dict) -> str:
    """OTP message ko custom format mein format kare"""
    country, flag = detect_country(otp_data.get("phone", ""))
    service = detect_service(
        otp_data.get("sender", ""),
        otp_data.get("cli", "")
    )
    masked_number = mask_phone_number(otp_data.get("phone", ""))
    code = otp_data.get("code", "N/A")
    
    message = bot_state.message_format.format(
        country=country,
        flag=flag,
        service=service,
        number=masked_number,
        code=f"<code>{code}</code>"
    )
    
    return message

def create_inline_buttons() -> InlineKeyboardMarkup:
    """Inline buttons create kare"""
    buttons = []
    for text, url in bot_state.buttons:
        buttons.append([InlineKeyboardButton(text=text, url=url)])
    return InlineKeyboardMarkup(buttons)

# ============ OTP POLLING ============
async def otp_polling_loop(context: ContextTypes.DEFAULT_TYPE):
    """Har second OTP check kare aur forward kare"""
    try:
        otp_data = await fetch_otp_from_api()
        
        if otp_data:
            otp_id = otp_data.get("id")
            
            # Duplicate check
            if otp_id and otp_id != bot_state.last_otp_id:
                bot_state.last_otp_id = otp_id
                
                # Message format kare
                message = format_otp_message(otp_data)
                buttons = create_inline_buttons()
                
                # Group mein send kare
                try:
                    await context.bot.send_message(
                        chat_id=bot_state.otp_group_id,
                        text=message,
                        parse_mode="HTML",
                        reply_markup=buttons
                    )
                    logger.info(f"OTP sent successfully: {otp_id}")
                except TelegramError as e:
                    logger.error(f"Failed to send OTP: {e}")
    
    except Exception as e:
        logger.error(f"Polling error: {e}")

# ============ ADMIN PANEL ============
ADMIN_MENU, EDIT_FORMAT, EDIT_BUTTONS, MANAGE_SERVICES, CHANGE_GROUP = range(5)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel show kare"""
    user_id = update.effective_user.id
    
    if user_id != CONFIG["ADMIN_CHAT_ID"]:
        await update.message.reply_text("❌ Unauthorized access")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton("🔄 Change OTP Group", callback_data="change_group")],
        [InlineKeyboardButton("✏️ Edit Message Format", callback_data="edit_format")],
        [InlineKeyboardButton("🔘 Edit Buttons", callback_data="edit_buttons")],
        [InlineKeyboardButton("📋 Manage Services", callback_data="manage_services")],
        [InlineKeyboardButton("⏮️ Forward Past OTPs", callback_data="past_otps")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎛️ <b>Admin Panel</b>\n\nOptions select karo:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return ADMIN_MENU

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin button clicks handle kare"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "change_group":
        await query.edit_message_text(
            "📱 Naya OTP Group ID bhejo (negative number mein)\n"
            "Example: -1001234567890"
        )
        return CHANGE_GROUP
    
    elif query.data == "edit_format":
        current_format = bot_state.message_format
        await query.edit_message_text(
            f"📝 <b>Current Format:</b>\n\n<code>{current_format}</code>\n\n"
            "Naya format bhejo (use {country}, {flag}, {service}, {number}, {code}):"
        )
        return EDIT_FORMAT
    
    elif query.data == "edit_buttons":
        buttons_text = "\n".join([f"{i+1}. {t} -> {u}" 
                                  for i, (t, u) in enumerate(bot_state.buttons)])
        await query.edit_message_text(
            f"🔘 <b>Current Buttons:</b>\n\n{buttons_text}\n\n"
            "JSON format mein naye buttons bhejo: "
            '[[\"Button1\", \"url1\"], [\"Button2\", \"url2\"]]'
        )
        return EDIT_BUTTONS
    
    elif query.data == "manage_services":
        services = "\n".join(SERVICE_PATTERNS.keys())
        await query.edit_message_text(
            f"📋 <b>Current Services:</b>\n\n{services}\n\n"
            "Services manage karne ke liye /services command use karo"
        )
        return MANAGE_SERVICES
    
    elif query.data == "past_otps":
        await query.edit_message_text("⏳ Past OTPs fetch ho rahe hain...")
        
        otps = await fetch_past_otps(5)
        if otps:
            for otp in otps:
                message = format_otp_message(otp)
                buttons = create_inline_buttons()
                try:
                    await context.bot.send_message(
                        chat_id=bot_state.otp_group_id,
                        text=message,
                        parse_mode="HTML",
                        reply_markup=buttons
                    )
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending past OTP: {e}")
            
            await query.edit_message_text("✅ Past OTPs forwarded!")
        else:
            await query.edit_message_text("❌ No past OTPs found")
        return ConversationHandler.END
    
    elif query.data == "cancel":
        await query.edit_message_text("❌ Cancelled")
        return ConversationHandler.END

async def receive_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naya group ID receive kare"""
    try:
        group_id = int(update.message.text)
        bot_state.otp_group_id = group_id
        CONFIG["OTP_GROUP_ID"] = group_id
        await update.message.reply_text(f"✅ Group ID updated: {group_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid group ID format")
    
    return ConversationHandler.END

async def receive_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naya message format receive kare"""
    try:
        new_format = update.message.text
        # Validate format
        test = new_format.format(
            country="India", flag="🇮🇳", service="WhatsApp",
            number="xxxx3509", code="123456"
        )
        bot_state.message_format = new_format
        await update.message.reply_text("✅ Message format updated!")
    except Exception as e:
        await update.message.reply_text(f"❌ Invalid format: {e}")
    
    return ConversationHandler.END

async def receive_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Naye buttons receive kare"""
    try:
        buttons_json = update.message.text
        new_buttons = json.loads(buttons_json)
        bot_state.buttons = new_buttons
        await update.message.reply_text("✅ Buttons updated!")
    except json.JSONDecodeError:
        await update.message.reply_text("❌ Invalid JSON format")
    
    return ConversationHandler.END

# ============ MAIN BOT SETUP ============
async def main():
    """Bot ko initialize aur start kare"""
    
    # Application create karo
    app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
    
    # Admin conversation handler
    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_start)],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_button_handler)],
            CHANGE_GROUP: [
                CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            ],
            EDIT_FORMAT: [
                CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            ],
            EDIT_BUTTONS: [
                CommandHandler("cancel", lambda u, c: ConversationHandler.END),
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    # Custom message handlers
    async def handle_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            group_id = int(update.message.text)
            bot_state.otp_group_id = group_id
            await update.message.reply_text(f"✅ Group ID updated!")
        except ValueError:
            await update.message.reply_text("❌ Invalid format")
    
    async def handle_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
        bot_state.message_format = update.message.text
        await update.message.reply_text("✅ Format updated!")
    
    async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            bot_state.buttons = json.loads(update.message.text)
            await update.message.reply_text("✅ Buttons updated!")
        except:
            await update.message.reply_text("❌ Invalid JSON")
    
    # Handlers add karo
    app.add_handler(admin_conv_handler)
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    
    # OTP polling job add karo
    app.job_queue.run_repeating(
        otp_polling_loop,
        interval=CONFIG["POLL_INTERVAL"],
        first=1
    )
    
    # Start bot
    logger.info("🚀 Bot starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
