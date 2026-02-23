import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMINS = [int(admin_id) for admin_id in os.getenv("ADMINS", "12345678").split(",") if admin_id.strip()]
CHANNELS = [channel.strip() for channel in os.getenv("CHANNELS", "@novaxrasmiy").split(",") if channel.strip()]
INSTAGRAM_LINK = "https://www.instagram.com/nova_kino.uz/"
DATABASE_NAME = "bot_database.db"
DAILY_LIMIT = 5

LANGUAGES = {
    'uz': '🇺🇿 O\'zbekcha',
    'uz_cyr': '🇺🇿 Ўзбекча',
    'ru': '🇷🇺 Русский',
    'en': '🇺🇸 English'
}
