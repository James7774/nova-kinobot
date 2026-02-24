from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, date
import asyncio
import logging
import html

logger = logging.getLogger(__name__)

from database.db import (
    add_user, get_user_stats, update_user_requests, 
    get_video_by_code, get_video_by_id, increment_views, search_videos_by_title,
    get_user_language, set_user_language, add_rating, get_rating_stats
)
import math

def format_size(bytes):
    if bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return f"{s} {size_name[i]}"
from keyboards.inline import (
    get_main_menu, get_quality_keyboard, 
    get_subscribe_keyboard, get_language_keyboard,
    get_video_share_keyboard, get_rating_selection_keyboard
)
from keyboards.reply import get_admin_reply_keyboard
from utils.states import UserStates
from utils.texts import TEXTS
from config import DAILY_LIMIT, CHANNELS, ADMINS

user_router = Router()

@user_router.message(Command("myid"))
async def cmd_myid(message: types.Message):
    await message.answer(f"Sizning Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await add_user(message.from_user.id, message.from_user.username)
    
    # Auto-detect Admin
    if message.from_user.id in ADMINS:
        await message.answer(
            "👨‍💻 <b>Admin Panel</b>\n\nXush kelibsiz, Admin! Quyidagi menyudan foydalanishingiz mumkin:",
            reply_markup=get_admin_reply_keyboard(),
            parse_mode="HTML"
        )
        return

    text = (
        "O'zingizga qulay tilni tanlang 🇺🇿\n\n"
        "Ўзингизга қулай тилни танланг 🇺🇿\n\n"
        "Выбери язык, который тебе нравится 🇷🇺\n\n"
        "Choose the language you like 🇺🇸"
    )
    await message.reply(
        text,
        reply_markup=get_language_keyboard()
    )

@user_router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_lang(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    lang = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    await set_user_language(user_id, lang)
    t = TEXTS[lang]
    await callback.message.answer(t['lang_selected'])
    
    # Check if user is subscribed to Telegram channel
    missing = await get_missing_channels(bot, user_id)
    if missing:
        await callback.message.answer(t['sub_required'], reply_markup=get_subscribe_keyboard(lang))
    else:
        name = html.quote(callback.from_user.full_name)
        await callback.message.answer(t['welcome'].format(name=name), parse_mode="HTML")
    
    await callback.answer()

@user_router.callback_query(F.data == "enter_code")
async def cb_enter_code(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    t = TEXTS[lang]
    await callback.message.answer(t['enter_code'])
    await state.set_state(UserStates.entering_code)
    await callback.answer()

@user_router.callback_query(F.data == "search_name")
async def cb_search_name(callback: types.CallbackQuery, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    t = TEXTS[lang]
    await callback.message.answer(t['search_name'])
    await state.set_state(UserStates.searching_name)
    await callback.answer()

# Click Instagram handler removed because buttons are now URL buttons

@user_router.callback_query(F.data == "help")
async def cb_help(callback: types.CallbackQuery):
    lang = await get_user_language(callback.from_user.id)
    t = TEXTS[lang]
    await callback.message.answer(t['help'], parse_mode="HTML")
    await callback.answer()

async def check_limit(user_id):
    stats = await get_user_stats(user_id)
    if not stats:
        return True
    requests, last_date = stats
    today = str(date.today())
    if last_date != today:
        await update_user_requests(user_id, 1, today)
        return True
    if requests >= DAILY_LIMIT:
        return False
    await update_user_requests(user_id, requests + 1, today)
    return True

async def check_single_channel(bot: Bot, user_id: int, idx: int, channel: str):
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        if member.status in ["creator", "administrator", "member", "restricted"]:
            return None
        return (idx, channel)
    except Exception:
        return (idx, channel)

async def get_missing_channels(bot: Bot, user_id: int):
    # Har bir kanalni parallel tekshirish (tezroq ishlashi uchun)
    tasks = [check_single_channel(bot, user_id, i, ch) for i, ch in enumerate(CHANNELS, 1)]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]

@user_router.message(UserStates.entering_code)
async def process_code(message: types.Message, state: FSMContext, bot: Bot):
    lang = await get_user_language(message.from_user.id)
    t = TEXTS[lang]
    
    code = message.text
    if not code.isdigit():
        await message.answer(t['invalid_code'])
        return

    # Real Sub check for Telegram
    missing = await get_missing_channels(bot, message.from_user.id)
    if missing:
        await message.answer(t['sub_required'], reply_markup=get_subscribe_keyboard(lang))
        return

    videos = await get_video_by_code(code)
    if not videos:
        await message.answer(t['not_found'])
    else:
        # video format: (title, quality, file_id, views_count, id, file_type, storage_channel_id, storage_message_id)
        title, quality, file_id, views_count, video_id, file_type, storage_channel_id, storage_message_id = videos[0]
        
        caption = f"{html.quote(title)}\n\n🤖 <b>Bot:</b> @{(await bot.get_me()).username}"
        avg_rating, count = await get_rating_stats(video_id)
        kb = get_video_share_keyboard((await bot.get_me()).username, video_id, avg_rating, count)

        try:
            if storage_channel_id and storage_message_id:
                # Instant delivery via copyMessage
                try:
                    await bot.copy_message(
                        chat_id=message.from_user.id,
                        from_chat_id=storage_channel_id,
                        message_id=storage_message_id,
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=kb
                    )
                    await increment_views(video_id)
                    await state.clear()
                    return
                except Exception as e:
                    logger.error(f"copyMessage failed: {e}. Falling back to forwardMessage.")
                    try:
                        await bot.forward_message(
                            chat_id=message.from_user.id,
                            from_chat_id=storage_channel_id,
                            message_id=storage_message_id
                        )
                        await increment_views(video_id)
                        await state.clear()
                        return
                    except Exception as e2:
                        logger.error(f"forwardMessage failed: {e2}")
            
            # Fallback or direct file delivery
            if file_id:
                if file_type == 'video':
                    await message.answer_video(video=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                elif file_type == 'document':
                    await message.answer_document(document=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                elif file_type == 'animation':
                    await message.answer_animation(animation=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                else:
                    await message.answer_video(video=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
                
                await increment_views(video_id)
            else:
                await message.answer("❌ Kinoni yuborishda xatolik yuz berdi (Fayl topilmadi).")
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            await message.answer("❌ Videoni yuborishda xatolik yuz berdi.")
        
    await state.clear()
    return

@user_router.message(UserStates.searching_name)
async def process_search_name(message: types.Message, state: FSMContext):
    lang = await get_user_language(message.from_user.id)
    t = TEXTS[lang]
    
    query = message.text
    results = await search_videos_by_title(query)
    
    if not results:
        await message.answer(t['no_results'])
    else:
        res_list = ""
        for code, title in results:
            res_list += f"• <code>{code}</code> - {html.quote(title)}\n"
        await message.answer(t['search_results'].format(results=res_list), parse_mode="HTML")
    
    await state.clear()

@user_router.callback_query(F.data == "check_subscription")
async def cb_check_sub(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    t = TEXTS[lang]
    name = callback.from_user.full_name
    
    missing = await get_missing_channels(bot, callback.from_user.id)
    if not missing:
        await callback.message.answer(t['sub_check'])
        try:
            await callback.message.delete()
        except Exception:
            pass
        name = html.quote(callback.from_user.full_name)
        await callback.message.answer(t['welcome'].format(name=name), parse_mode="HTML")
    else:
        await callback.answer(t['sub_failed'], show_alert=True)
    
    await callback.answer()

# Add a default numeric handler so users don't have to be in 'entering_code' state
@user_router.message(F.text.regexp(r'^\d+$'))
async def direct_code_lookup(message: types.Message, state: FSMContext, bot: Bot):
    await process_code(message, state, bot)

@user_router.callback_query(F.data.startswith("send_video:"))
async def cb_send_video(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    lang = await get_user_language(callback.from_user.id)
    t = TEXTS[lang]
    
    missing = await get_missing_channels(bot, callback.from_user.id)
    if missing:
        await callback.message.answer(t['sub_required'], reply_markup=get_subscribe_keyboard(lang))
        await callback.answer()
        return

    video_id = callback.data.split(":")[1]
    video_data = await get_video_by_id(video_id)
    
    if not video_data:
        await callback.answer("❌ Video topilmadi!")
        return
        
    # video format: (file_id, quality, title, views_count, file_type, storage_channel_id, storage_message_id)
    file_id, quality, title, views_count, file_type, storage_channel_id, storage_message_id = video_data
    
    caption = f"{html.quote(title)}\n\n🤖 <b>Bot:</b> @{(await bot.get_me()).username}"
    avg_rating, count = await get_rating_stats(video_id)
    kb = get_video_share_keyboard((await bot.get_me()).username, video_id, avg_rating, count)
    
    try:
        if storage_channel_id and storage_message_id:
            try:
                await bot.copy_message(
                    chat_id=callback.from_user.id,
                    from_chat_id=storage_channel_id,
                    message_id=storage_message_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb
                )
                await increment_views(video_id)
                await callback.answer()
                return
            except Exception as e:
                logger.error(f"cb copyMessage failed: {e}")

        # Send based on file type
        if file_id:
            if file_type == 'video':
                await callback.message.answer_video(video=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            elif file_type == 'document':
                await callback.message.answer_document(document=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            elif file_type == 'animation':
                await callback.message.answer_animation(animation=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
            else:
                await callback.message.answer_video(video=file_id, caption=caption, parse_mode="HTML", reply_markup=kb)
        else:
            await callback.answer("❌ Video topilmadi (Storage error)")
            return
    except Exception as e:
        logger.error(f"Error sending video {video_id}: {e}")
        await callback.answer("❌ Videoni yuborishda xatolik yuz berdi.")
        return

    await increment_views(video_id)
    await callback.answer()

@user_router.callback_query(F.data == "delete_msg")
async def cb_delete_msg(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        await callback.answer("❌ Xatolik: Xabarni o'chirib bo'lmadi.")
    await callback.answer()

@user_router.callback_query(F.data.startswith("rate_video:"))
async def cb_rate_video_start(callback: types.CallbackQuery, state: FSMContext):
    video_id = callback.data.split(":")[1]
    await callback.message.edit_reply_markup(reply_markup=get_rating_selection_keyboard(video_id))
    await callback.answer()

@user_router.callback_query(F.data.startswith("set_rate:"))
async def cb_set_rate(callback: types.CallbackQuery, bot: Bot):
    _, video_id, stars = callback.data.split(":")
    video_id = int(video_id)
    stars = int(stars)
    user_id = callback.from_user.id
    
    await add_rating(video_id, user_id, stars)
    await callback.answer(f"Rahmat! Siz {stars} ball berdingiz.", show_alert=True)
    
    # Update keyboard with new stats
    avg_rating, count = await get_rating_stats(video_id)
    kb = get_video_share_keyboard((await bot.get_me()).username, video_id, avg_rating, count)
    await callback.message.edit_reply_markup(reply_markup=kb)

@user_router.callback_query(F.data.startswith("back_to_video:"))
async def cb_back_to_video(callback: types.CallbackQuery, bot: Bot):
    video_id = int(callback.data.split(":")[1])
    avg_rating, count = await get_rating_stats(video_id)
    kb = get_video_share_keyboard((await bot.get_me()).username, video_id, avg_rating, count)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()
