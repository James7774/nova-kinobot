from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.texts import TEXTS

def get_language_keyboard():
    from config import LANGUAGES
    builder = InlineKeyboardBuilder()
    for code, name in LANGUAGES.items():
        builder.add(InlineKeyboardButton(text=name, callback_data=f"set_lang:{code}"))
    builder.adjust(2)
    return builder.as_markup()

def get_main_menu(lang):
    t = TEXTS[lang]
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=t['btn_enter_code'], callback_data="enter_code"))
    builder.row(InlineKeyboardButton(text=t['btn_search_name'], callback_data="search_name"))
    builder.row(InlineKeyboardButton(text=t['btn_help'], callback_data="help"))
    return builder.as_markup()

def get_quality_keyboard(code, videos):
    builder = InlineKeyboardBuilder()
    for video in videos:
        builder.row(InlineKeyboardButton(
            text=f"{video[1]}", 
            callback_data=f"send_video:{video[4]}"
        ))
    return builder.as_markup()

def get_admin_cancel():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel"))
    return builder.as_markup()

def get_admin_panel():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Kino qo'shish", callback_data="admin_add"))
    builder.row(InlineKeyboardButton(text="🗑 Kino o'chirish", callback_data="admin_delete"))
    builder.row(InlineKeyboardButton(text="📜 Kinolar ro'yxati", callback_data="admin_list"))
    builder.row(InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"))
    return builder.as_markup()

def get_subscribe_keyboard(lang, missing_channels=None):
    from config import CHANNELS, INSTAGRAM_LINK
    t = TEXTS[lang]
    builder = InlineKeyboardBuilder()
    
    # 1-kanal: Telegram (config dagi CHANNELS dan olinadi)
    if CHANNELS:
        channel = CHANNELS[0]
        builder.row(InlineKeyboardButton(text=t['btn_sub'].format(n=1), url=f"https://t.me/{channel.strip('@')}"))
    
    # 2-kanal: Instagram
    builder.row(InlineKeyboardButton(text=t['btn_sub'].format(n=2), url=INSTAGRAM_LINK))
    
    builder.row(InlineKeyboardButton(text=t['btn_check_sub'], callback_data="check_subscription"))
    return builder.as_markup()

