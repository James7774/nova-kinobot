from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

from keyboards.inline import get_admin_panel
from keyboards.reply import get_admin_reply_keyboard
from database.db import add_video, delete_code, get_all_codes, get_global_stats
from utils.states import AdminStates
from config import ADMINS

admin_router = Router()

# Admin check middleware
@admin_router.message.middleware()
async def admin_check(handler, event, data):
    if event.from_user.id not in ADMINS:
        return
    return await handler(event, data)

@admin_router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    await message.answer(
        "👨‍💻 **Admin Panel**\n\nQuyidagi menyudan foydalanishingiz mumkin:",
        reply_markup=get_admin_reply_keyboard(),
        parse_mode="Markdown"
    )

# --- Button Handlers ---

@admin_router.message(F.text == "🎬 Kino qo'shish")
async def btn_admin_add(message: types.Message, state: FSMContext):
    await message.answer("🔢 Kino uchun kodni kiriting (masalan: 123):")
    await state.set_state(AdminStates.waiting_for_code)

@admin_router.message(F.text == "🗑 Kinoni o'chirish")
async def btn_admin_delete_start(message: types.Message, state: FSMContext) :
    await message.answer("🗑 O'chirmoqchi bo'lgan kino kodini yuboring:")
    await state.set_state(AdminStates.waiting_for_code_delete)

@admin_router.message(F.text == "📜 Kinolar ro'yxati")
async def btn_admin_list(message: types.Message):
    codes = await get_all_codes()
    if not codes:
        await message.answer("📭 Hozircha kinolar qo'shilmagan.")
    else:
        text = "📜 **Barcha kinolar:**\n\n"
        for code, title in codes:
            text += f"• `{code}` - {title}\n"
        await message.answer(text, parse_mode="Markdown")

@admin_router.message(F.text == "📊 Statistika")
async def btn_admin_stats(message: types.Message):
    users, videos = await get_global_stats()
    await message.answer(
        f"📊 **Bot Statistikasi:**\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {videos}\n",
        parse_mode="Markdown"
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
    await state.update_data(code=message.text)
    await message.answer(
        f"📹 Endi `{message.text}` kodi uchun video faylni yuboring:\n\n"
        f"⚠️ **Eslatma:** Kino katta bo'lib chiqishi uchun uni **Video** ko'rinishida yuboring (fayl emas).",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_video)

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
    await message.answer(f"📹 Iltimos, `{code}` kodi uchun video faylni yuboring:", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_video)

@admin_router.message(AdminStates.waiting_for_video)
async def process_video(message: types.Message, state: FSMContext):
    logger.info(f"Message received from admin {message.from_user.id} in waiting_for_video state. Content type: {message.content_type}")
    
    file_id = None
    file_type = 'video'
    
    if message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.document and (message.document.mime_type and message.document.mime_type.startswith('video')):
        file_id = message.document.file_id
        file_type = 'document'
    elif message.document:
        # Accept any document if needed, but warning
        file_id = message.document.file_id
        file_type = 'document'
    elif message.animation:
        file_id = message.animation.file_id
        file_type = 'animation'
    elif message.video_note:
        file_id = message.video_note.file_id
        file_type = 'video_note'
    
    if not file_id:
        await message.answer("❌ Iltimos, faqat video fayl yuboring! (Siz yuborgan narsa video deb topilmadi)")
        return
        
    await state.update_data(file_id=file_id, file_type=file_type)
    await message.answer("📝 Video haqida ma'lumot kiriting (bu foydalanuvchiga caption sifatida ko'rinadi):")
    await state.set_state(AdminStates.waiting_for_title)

@admin_router.message(AdminStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    data = await state.get_data()
    description = message.text # This is the full custom text from admin
    
    await add_video(
        code=data['code'],
        title=description, # Saving custom info as 'title'
        quality="", 
        file_id=data['file_id'],
        file_type=data.get('file_type', 'video'),
        expires_at=data.get('expires_at')
    )
    
    await message.answer(f"✅ Video `{data['code']}` kodi bilan muvaffaqiyatli qo'shildi.", parse_mode="Markdown")
    await state.clear()

@admin_router.callback_query(F.data == "admin_list")
async def cb_admin_list(callback: types.CallbackQuery):
    codes = await get_all_codes()
    if not codes:
        await callback.message.answer("📭 Hozircha kinolar qo'shilmagan.")
    else:
        text = "📜 **Barcha kinolar:**\n\n"
        for code, title in codes:
            text += f"• `{code}` - {title}\n"
        await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@admin_router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    users, videos = await get_global_stats()
    await callback.message.answer(
        f"📊 **Bot Statistikasi:**\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {videos}\n",
        parse_mode="Markdown"
    )
    await callback.answer()

@admin_router.callback_query(F.data == "admin_delete")
async def cb_admin_delete_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🗑 O'chirmoqchi bo'lgan kino kodini yuboring:")
    await state.set_state(AdminStates.waiting_for_code_delete)
    await callback.answer()

@admin_router.message(AdminStates.waiting_for_code_delete)
async def process_admin_delete(message: types.Message, state: FSMContext):
    code = message.text
    await delete_code(code)
    await message.answer(f"✅ Kod `{code}` muvaffaqiyatli o'chirildi.", parse_mode="Markdown")
    await state.clear()

@admin_router.message(Command("delete"))
async def cmd_delete(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("❌ Foydalanish: /delete <kod>")
        return
    await delete_code(command.args)
    await message.answer(f"✅ `{command.args}` kodi va unga tegishli fayllar o'chirildi.", parse_mode="Markdown")

@admin_router.message(Command("list"))
async def cmd_list(message: types.Message):
    codes = await get_all_codes()
    if not codes:
        await message.answer("📭 Hozircha kinolar qo'shilmagan.")
        return
    text = "📜 **Saqlangan kinolar:**\n"
    for code, title in codes:
        text += f"• `{code}` - {title}\n"
    await message.answer(text, parse_mode="Markdown")

@admin_router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    users, videos = await get_global_stats()
    await message.answer(
        f"📊 **Bot statistikasi:**\n"
        f"• Jami foydalanuvchilar: {users}\n"
        f"• Jami kinolar: {videos}\n",
        parse_mode="Markdown"
    )
