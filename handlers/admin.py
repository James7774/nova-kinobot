from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging
import re
import html

logger = logging.getLogger(__name__)

from keyboards.inline import get_admin_panel
from keyboards.reply import get_admin_reply_keyboard
from database.db import add_video, delete_code, get_all_codes, get_global_stats
from utils.states import AdminStates
from config import ADMINS

admin_router = Router()

# Admin check filter
admin_router.message.filter(F.from_user.id.in_(ADMINS))
admin_router.callback_query.filter(F.from_user.id.in_(ADMINS))


@admin_router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    await message.answer(
        "👨‍💻 <b>Admin Panel</b>\n\nQuyidagi menyudan foydalanishingiz mumkin:",
        reply_markup=get_admin_reply_keyboard(),
        parse_mode="HTML"
    )

# --- Button Handlers ---

@admin_router.message(F.text == "🎬 Kino qo'shish")
async def btn_admin_add(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔢 Kino uchun kodni kiriting (masalan: 123):")
    await state.set_state(AdminStates.waiting_for_code)

@admin_router.message(F.text == "🗑 Kinoni o'chirish")
async def btn_admin_delete_start(message: types.Message, state: FSMContext) :
    await state.clear()
    await message.answer("🗑 O'chirmoqchi bo'lgan kino kodini yuboring:")
    await state.set_state(AdminStates.waiting_for_code_delete)

@admin_router.message(F.text == "📜 Kinolar ro'yxati")
async def btn_admin_list(message: types.Message, state: FSMContext):
    await state.clear()
    codes = await get_all_codes()
    if not codes:
        await message.answer("📭 Hozircha kinolar qo'shilmagan.")
    else:
        text = "📜 <b>Barcha kinolar:</b>\n\n"
        messages = []
        for code, title in codes:
            line = f"• <code>{code}</code> - {html.quote(title)}\n"
            if len(text) + len(line) > 4000:
                messages.append(text)
                text = "📜 <b>Davomi:</b>\n\n" + line
            else:
                text += line
        messages.append(text)
        
        for msg in messages:
            await message.answer(msg, parse_mode="HTML")

@admin_router.message(F.text == "📊 Statistika")
async def btn_admin_stats(message: types.Message, state: FSMContext):
    await state.clear()
    users, videos = await get_global_stats()
    await message.answer(
        f"📊 <b>Bot Statistikasi:</b>\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {videos}\n",
        parse_mode="HTML"
    )

@admin_router.message(F.text == "👤 Foydalanuvchi rejimi")
async def btn_user_mode(message: types.Message, state: FSMContext):
    from keyboards.inline import get_language_keyboard
    await message.answer(
        "👤 Foydalanuvchi rejimiga o'tildi. Tilni tanlang:",
        reply_markup=get_language_keyboard()
    )

@admin_router.callback_query(F.data == "admin_add")
async def cb_admin_add(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔢 Kino uchun kodni kiriting (masalan: 123):")
    await state.set_state(AdminStates.waiting_for_code)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_code)
async def process_admin_code(message: types.Message, state: FSMContext):
    # Check for menu buttons
    menu_buttons = ["🎬 Kino qo'shish", "🗑 Kinoni o'chirish", "📜 Kinolar ro'yxati", "📊 Statistika", "👤 Foydalanuvchi rejimi"]
    if message.text in menu_buttons or (message.text and message.text.startswith('/')):
        await state.clear()
        if message.text == "📜 Kinolar ro'yxati": return await btn_admin_list(message, state)
        if message.text == "📊 Statistika": return await btn_admin_stats(message, state)
        if message.text == "🎬 Kino qo'shish": return await btn_admin_add(message, state)
        if message.text == "🗑 Kinoni o'chirish": return await btn_admin_delete_start(message, state)
        if message.text == "👤 Foydalanuvchi rejimi": return await btn_user_mode(message, state)
        return

    await state.update_data(code=message.text)
    await message.answer(
        f"✅ Kod saqlandi: <code>{html.quote(message.text)}</code>\n\n"
        f"Endi ushbu kod uchun kinoni yuboring. Sizda 2 xil yo'l bor:\n\n"
        f"1️⃣ <b>Fayl yuborish:</b> Kinoni to'g'ridan-to'g'ri shu yerga yuboring (Video ko'rinishida).\n"
        f"2️⃣ <b>Kanal orqali:</b> Saqlash kanalidagi postni shu yerga <b>forward</b> qiling yoki post <b>linkini</b> yuboring (t.me/kanal/123).",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_channel_post)

@admin_router.message(Command("add"))
async def cmd_add(message: types.Message, command: CommandObject, state: FSMContext):
    if not command.args:
        await message.answer("❌ Foydalanish: /add <kod> [--expires 24h]")
        return
    
    args = command.args.split()
    code = args[0]
    
    expires_at = None
    if "--expires" in args:
        idx = args.index("--expires")
        if idx + 1 < len(args):
            exp_str = args[idx+1]
            # Simple parse: 24h, 1d, etc.
            match = re.match(r"(\d+)([hd])", exp_str)
            if match:
                val, unit = match.groups()
                if unit == 'h':
                    expires_at = datetime.now() + timedelta(hours=int(val))
                elif unit == 'd':
                    expires_at = datetime.now() + timedelta(days=int(val))

    await state.update_data(code=code, expires_at=expires_at)
    await message.answer(
        f"✅ Kod saqlandi: <code>{html.quote(code)}</code>\n\n"
        f"Endi ushbu kod uchun kinoni yuboring (forward qiling, link yuboring yoki video fayl yuboring):",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_channel_post)

@admin_router.message(AdminStates.waiting_for_channel_post)
async def process_channel_post(message: types.Message, state: FSMContext, bot: Bot):
    storage_channel_id = None
    storage_message_id = None
    file_id = None
    file_type = 'video'

    # Option A: Forwarded message
    if message.forward_from_chat:
        storage_channel_id = message.forward_from_chat.id
        storage_message_id = message.forward_from_message_id
    # Option B: Link
    elif message.text and ("t.me/" in message.text):
        link = message.text
        # Patterns: https://t.me/username/123 or https://t.me/c/123456789/123
        match = re.search(r"t\.me/(?:c/)?([^/]+)/(\d+)", link)
        if match:
            channel_part = match.group(1)
            storage_message_id = int(match.group(2))
            if channel_part.isdigit() or channel_part.startswith('-100'):
                # Private channel ID in link
                if not channel_part.startswith('-100'):
                    storage_channel_id = int(f"-100{channel_part}")
                else:
                    storage_channel_id = int(channel_part)
            else:
                # Public channel username
                storage_channel_id = f"@{channel_part}"
    
    # Option C: Direct Video/File Upload
    if not storage_channel_id:
        if message.video:
            file_id = message.video.file_id
            file_type = 'video'
        elif message.document and (message.document.mime_type and message.document.mime_type.startswith('video')):
            file_id = message.document.file_id
            file_type = 'document'
        elif message.document:
            file_id = message.document.file_id
            file_type = 'document'
        elif message.animation:
            file_id = message.animation.file_id
            file_type = 'animation'
        
        if not file_id and not storage_channel_id:
            # Check if this is a menu button click to avoid error message
            menu_buttons = ["🎬 Kino qo'shish", "🗑 Kinoni o'chirish", "📜 Kinolar ro'yxati", "📊 Statistika", "👤 Foydalanuvchi rejimi"]
            if message.text in menu_buttons or message.text.startswith('/'):
                await state.clear()
                # Re-trigger the appropriate handler by sending the message again to the router
                # In aiogram 3, we can't easily re-trigger but we can just handle it here
                if message.text == "📜 Kinolar ro'yxati":
                    return await btn_admin_list(message, state)
                elif message.text == "📊 Statistika":
                    return await btn_admin_stats(message, state)
                elif message.text == "🎬 Kino qo'shish":
                    return await btn_admin_add(message, state)
                elif message.text == "🗑 Kinoni o'chirish":
                    return await btn_admin_delete_start(message, state)
                elif message.text == "👤 Foydalanuvchi rejimi":
                    return await btn_user_mode(message, state)
                # If command, let other handlers handle it after clearing state
                return

            await message.answer("❌ Xatolik! Iltimos, kanal postini forward qiling, link yuboring yoki video fayl yuboring.")
            return

    # Validate if channel post is accessible
    if storage_channel_id and storage_message_id:
        try:
            # Try to copy message to admin as a test
            test_msg = await bot.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=storage_channel_id,
                message_id=storage_message_id
            )
            await test_msg.delete()
        except Exception as e:
            await message.answer(f"❌ Xatolik! Bot ushbu kanalga yoki postga kira olmayapti.\nSabab: {e}")
            return

    await state.update_data(
        storage_channel_id=str(storage_channel_id) if storage_channel_id else None,
        storage_message_id=storage_message_id,
        file_id=file_id,
        file_type=file_type
    )
    await message.answer("📝 Video haqida ma'lumot kiriting (bu foydalanuvchiga caption sifatida ko'rinadi):")
    await state.set_state(AdminStates.waiting_for_title)

@admin_router.message(AdminStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    # Check for menu buttons
    menu_buttons = ["🎬 Kino qo'shish", "🗑 Kinoni o'chirish", "📜 Kinolar ro'yxati", "📊 Statistika", "👤 Foydalanuvchi rejimi"]
    if message.text in menu_buttons or (message.text and message.text.startswith('/')):
        await state.clear()
        if message.text == "📜 Kinolar ro'yxati": return await btn_admin_list(message, state)
        if message.text == "📊 Statistika": return await btn_admin_stats(message, state)
        if message.text == "🎬 Kino qo'shish": return await btn_admin_add(message, state)
        if message.text == "🗑 Kinoni o'chirish": return await btn_admin_delete_start(message, state)
        if message.text == "👤 Foydalanuvchi rejimi": return await btn_user_mode(message, state)
        return

    data = await state.get_data()
    description = message.text
    
    await add_video(
        code=data['code'],
        title=description,
        quality="", 
        file_id=data.get('file_id'),
        file_type=data.get('file_type', 'video'),
        expires_at=data.get('expires_at'),
        storage_channel_id=data.get('storage_channel_id'),
        storage_message_id=data.get('storage_message_id')
    )
    
    await message.answer(f"✅ Video <code>{html.quote(data['code'])}</code> kodi bilan muvaffaqiyatli qo'shildi.", parse_mode="HTML")
    await state.clear()

@admin_router.message(AdminStates.waiting_for_code_delete)
async def process_admin_delete(message: types.Message, state: FSMContext):
    # Check for menu buttons
    menu_buttons = ["🎬 Kino qo'shish", "🗑 Kinoni o'chirish", "📜 Kinolar ro'yxati", "📊 Statistika", "👤 Foydalanuvchi rejimi"]
    if message.text in menu_buttons or (message.text and message.text.startswith('/')):
        await state.clear()
        if message.text == "📜 Kinolar ro'yxati": return await btn_admin_list(message, state)
        if message.text == "📊 Statistika": return await btn_admin_stats(message, state)
        if message.text == "🎬 Kino qo'shish": return await btn_admin_add(message, state)
        if message.text == "🗑 Kinoni o'chirish": return await btn_admin_delete_start(message, state)
        if message.text == "👤 Foydalanuvchi rejimi": return await btn_user_mode(message, state)
        return

    code = message.text
    await delete_code(code)
    await message.answer(f"✅ Kod <code>{html.quote(code)}</code> muvaffaqiyatli o'chirildi.", parse_mode="HTML")
    await state.clear()

@admin_router.callback_query(F.data == "admin_add")
async def cb_admin_add(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("🔢 Kino uchun kodni kiriting (masalan: 123):")
    await state.set_state(AdminStates.waiting_for_code)
    await callback.answer()

@admin_router.callback_query(F.data == "admin_list")
async def cb_admin_list(callback: types.CallbackQuery, state: FSMContext):
    await btn_admin_list(callback.message, state)
    await callback.answer()

@admin_router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery, state: FSMContext):
    await btn_admin_stats(callback.message, state)
    await callback.answer()

@admin_router.callback_query(F.data == "admin_delete")
async def cb_admin_delete_start_cb(callback: types.CallbackQuery, state: FSMContext):
    await btn_admin_delete_start(callback.message, state)
    await callback.answer()

@admin_router.message(Command("delete"))
async def cmd_delete(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("❌ Foydalanish: /delete <kod>")
        return
    await delete_code(command.args)
    await message.answer(f"✅ <code>{html.quote(command.args)}</code> kodi va unga tegishli fayllar o'chirildi.", parse_mode="HTML")

@admin_router.message(Command("list"))
async def cmd_list(message: types.Message):
    codes = await get_all_codes()
    if not codes:
        await message.answer("📭 Hozircha kinolar qo'shilmagan.")
        return
    text = "📜 <b>Saqlangan kinolar:</b>\n"
    for code, title in codes:
        text += f"• <code>{code}</code> - {html.quote(title)}\n"
    await message.answer(text, parse_mode="HTML")

@admin_router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    users, videos = await get_global_stats()
    await message.answer(
        f"📊 <b>Bot statistikasi:</b>\n"
        f"• Jami foydalanuvchilar: {users}\n"
        f"• Jami kinolar: {videos}\n",
        parse_mode="HTML"
    )
