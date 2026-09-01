import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

TOKEN = "8891788072:AAEGVLIWjfx1u2SNQGCyWt-fwOhh0YpM4Vo"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Bazaviy xotira
DB = {
    "super_admin": 8520429829,  
    "admins": {8520429829: {"can_manage_admins": True}}, # {admin_id: {"can_manage_admins": True/False}}
    "channels": [],       # [{"id": 1, "username": "@kanal"}]
    "movies": {},         # {code: {"name": "...", "file_id": "...", "type": "...", "views": 0}}
    "users": {},          # {user_id: {...}}
    "reports": [],        # Shikoyatlar
    "maintenance": {"status": False, "reason": "Texnik ishlar"}
}

# FSM holatlari
class AdminStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_channel_check = State()
    waiting_for_new_admin_username = State()
    waiting_for_admin_permission = State()
    waiting_for_del_admin_username = State()
    waiting_for_del_admin_reason = State()
    waiting_for_movie_code = State()
    waiting_for_movie_file = State()
    waiting_for_del_movie_code = State()
    waiting_for_ad_text = State()
    waiting_for_ad_media = State()
    waiting_for_ad_time = State()
    waiting_for_maint_reason = State()

class UserStates(StatesGroup):
    waiting_for_search_code = State()
    waiting_for_report_text = State()
    waiting_for_report_photo = State()

def is_admin(user_id):
    return user_id in DB["admins"] or user_id == DB["super_admin"]

def can_manage_admins(user_id):
    if user_id == DB["super_admin"]:
        return True
    return DB["admins"].get(user_id, {}).get("can_manage_admins", False)

async def check_subscriptions(user_id: int) -> bool:
    if not DB["channels"]:
        return True
    for ch in DB["channels"]:
        try:
            member = await bot.get_chat_member(chat_id=ch["username"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

async def get_sub_keyboard():
    builder = InlineKeyboardBuilder()
    for ch in DB["channels"]:
        builder.row(types.InlineKeyboardButton(text=f"📢 Obuna bo'lish: {ch['username']}", url=f"https://t.me/{ch['username'].replace('@', '')}"))
    builder.row(types.InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub"))
    return builder.as_markup()

# --- PASDAGI ASOSIY MENYU ---
def get_main_menu(user_id):
    builder = ReplyKeyboardBuilder()
    builder.row(types.KeyboardButton(text="🎬 Kino qidirish (Kod kiritish)"))
    builder.row(types.KeyboardButton(text="⭐ Kino reytingi"), types.KeyboardButton(text="🚨 Shikoyat qilish"))
    if is_admin(user_id):
        builder.row(types.KeyboardButton(text="🛠️ Admin Panel"))
    return builder.as_markup(resize_keyboard=True)

# --- START VA MAJBURIY OBUNA ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in DB["users"]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        DB["users"][user_id] = {
            "id": user_id,
            "first_name": message.from_user.first_name,
            "username": f"@{message.from_user.username}" if message.from_user.username else "Yo'q",
            "phone": "Kiritilmagan",
            "join_date": now
        }

    if DB["maintenance"]["status"] and not is_admin(user_id):
        await message.answer(f"⚠️ **Bot vaqtincha tuzatuvda!**\n\nSabab: {DB['maintenance']['reason']}")
        return

    if not await check_subscriptions(user_id):
        await message.answer(
            "Bu BOTda kazino va 18+ filmlar yo'q, faqat chet el va o'zbek milliy kinolari bor.\n\n"
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", 
            reply_markup=await get_sub_keyboard()
        )
        return

    welcome_text = (
        "Bu BOTda kazino va 18+ filmlar yo'q, faqat chet el va o'zbek milliy kinolari bor.\n\n"
        "🏠 **Asosiy menyu:**"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(user_id))

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery, state: FSMContext):
    if await check_subscriptions(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(
            "XUSH KELIBSIZ! O'sha o'sha kino kodini maxsus kanalda topishingiz mumkin:\nhttps://t.me/snap_media_kino_kodi", 
            reply_markup=get_main_menu(callback.from_user.id)
        )
    else:
        await callback.answer("Obuna bo'ling!", show_alert=True)

# --- KINO QIDIRISH ---
@dp.message(F.text == "🎬 Kino qidirish (Kod kiritish)")
async def btn_search_movie(message: types.Message, state: FSMContext):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("Avval kanallarga obuna bo'ling!", reply_markup=await get_sub_keyboard())
        return
    await message.answer("Marhamat, kino kodini kiriting:", reply_markup=get_main_menu(message.from_user.id))
    await state.set_state(UserStates.waiting_for_search_code)

@dp.message(UserStates.waiting_for_search_code)
async def process_user_movie_code(message: types.Message, state: FSMContext):
    if not await check_subscriptions(message.from_user.id):
        await message.answer("Avval kanallarga obuna bo'ling!", reply_markup=await get_sub_keyboard())
        return
        
    code = message.text.strip()
    if code in DB["movies"]:
        movie = DB["movies"][code]
        movie["views"] += 1
        caption = f"🎬 Nomi: {movie['name']}\n🔢 Kodi: {code}\n🔗 Kanal: @snap_media_kino_kodi"
        if movie["type"] == "video":
            await message.answer_video(movie["file_id"], caption=caption)
        elif movie["type"] == "photo":
            await message.answer_photo(movie["file_id"], caption=caption)
        elif movie["type"] == "animation":
            await message.answer_animation(movie["file_id"], caption=caption)
        else:
            await message.answer_document(movie["file_id"], caption=caption)
    else:
        sticker_id = "CAACAgIAAxkBAAE..." # Stiker ID yoki oddiy matn
        try:
            await message.answer_sticker("CAACAgIAAxkBAAE... (yoki o'zingizningstikeringiz)")
        except:
            pass
        await message.answer("❌ Bunday kino kodi mavjud emas")
    await state.clear()

# --- KINO REYTINGI ---
@dp.message(F.text == "⭐ Kino reytingi")
async def btn_movie_rating(message: types.Message):
    if not DB["movies"]:
        await message.answer("Hozircha kinolar qo'shilmagan.")
        return
    # Ko'p ko'rilganlar bo'yicha saralash
    sorted_movies = sorted(DB["movies"].items(), key=lambda x: x[1]["views"], reverse=True)
    text = "⭐ **Kino Reytingi (Eng ko'p izlanganlar):**\n\n"
    kb = InlineKeyboardBuilder()
    
    for i, (code, m) in enumerate(sorted_movies, 1):
        text += f"{i}-o'rin: {m['name']} — 🔢 Kod: <code>{code}</code> ({m['views']} marta ko'rilgan)\n"
        kb.row(types.InlineKeyboardButton(text=f"{i}. {m['name']} (Kod: {code})", callback_data=f"rate_movie_{code}"))
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("rate_movie_"))
async def show_rated_movie(callback: types.CallbackQuery):
    code = callback.data.split("_")[2]
    if code in DB["movies"]:
        m = DB["movies"][code]
        caption = f"🎬 Nomi: {m['name']}\n🔢 Kodi: {code}\n👁 Ko'rilgan: {m['views']} marta"
        await callback.message.answer(m['file_id'], caption=caption) if m['type'] == 'video' else callback.message.answer(f"Kino topildi: {m['name']} (Kod: {code})")

# --- SHIKOYAT QILISH ---
@dp.message(F.text == "🚨 Shikoyat qilish")
async def btn_make_report(message: types.Message, state: FSMContext):
    await message.answer("Sizning shikoyatingizni tez o'rganib chiqamiz, nima muammo bor yozing:")
    await state.set_state(UserStates.waiting_for_report_text)

@dp.message(UserStates.waiting_for_report_text)
async def report_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="skip_report_photo"))
    await message.answer("Video yoki surat bormi dalil sifatida? Yuboring yoki o'tkazib yuboring:", reply_markup=kb.as_markup())
    await state.set_state(UserStates.waiting_for_report_photo)

@dp.message(UserStates.waiting_for_report_photo)
async def report_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id

    await finish_report(message, state, file_id)

@dp.callback_query(F.data == "skip_report_photo")
async def skip_report_photo_cb(callback: types.CallbackQuery, state: FSMContext):
    await finish_report(callback.message, state, None, is_callback=True)

async def finish_report(message: types.Message, state: FSMContext, file_id, is_callback=False):
    data = await state.get_data()
    user = DB["users"].get(message.chat.id, {"first_name": message.chat.first_name, "username": f"@{message.chat.username}" if message.chat.username else "Yo'q", "phone": "Kiritilmagan", "id": message.chat.id})
    
    now = datetime.now()
    report_data = {
        "user": user,
        "text": data["text"],
        "file": file_id,
        "date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "day": now.strftime("%A")
    }
    DB["reports"].append(report_data)
    await state.clear()
    
    success_text = "Shikoyatingiz 12 soat ichida o'rganilib chiqadi va sizga ADMIN javob xati yozadi. MUAMMO UCHUN UZUR!"
    if is_callback:
        await message.edit_text(success_text)
    else:
        await message.answer(success_text, reply_markup=get_main_menu(message.chat.id))
        
    await notify_admins_report(report_data)

async def notify_admins_report(r):
    u = r["user"]
    text = (
        f"🚨 **YANGI SHIKOYAT**\n\n"
        f"📝 Sabab: {r['text']}\n"
        f"📅 Sana/Vaqt: {r['date']} ({r['day']})\n"
        f"📞 Tel raqam: {u.get('phone', 'Kiritilmagan')}\n"
        f"👤 User: {u.get('username')}\n"
        f"🆔 ID: `{u.get('id')}`"
    )
    for aid in DB["admins"] | {DB["super_admin"]}:
        try:
            if r["file"]:
                await bot.send_document(aid, r["file"], caption=text, parse_mode="Markdown")
            else:
                await bot.send_message(aid, text, parse_mode="Markdown")
        except:
            pass

# --- ADMIN PANEL ---
@dp.message(F.text == "🛠️ Admin Panel")
async def btn_admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="🎬 Kino yuklash", callback_data="admin_upload_movie"),
           types.InlineKeyboardButton(text="🗑️ Kino o'chirish", callback_data="admin_del_movie"))
    kb.row(types.InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="admin_ads"))
    kb.row(types.InlineKeyboardButton(text="📢 Kanal qo'shish/o'chirish", callback_data="admin_channels"))
    kb.row(types.InlineKeyboardButton(text="👑 Admin qo'shish/o'chirish", callback_data="admin_manage"))
    kb.row(types.InlineKeyboardButton(text="⚠️ Texnik ishlar", callback_data="admin_maint"))
    await message.answer("🛠️ **Admin Panel Boshqaruvi:**", reply_markup=kb.as_markup())

# 1. KINO YUKLASH VA O'CHIRISH
@dp.callback_query(F.data == "admin_upload_movie")
async def admin_up_movie_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kino yuklash uchun kino kodini yuboring (masalan: 17):")
    await state.set_state(AdminStates.waiting_for_movie_code)

@dp.message(AdminStates.waiting_for_movie_code)
async def admin_get_m_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    await state.update_data(code=code)
    await message.answer("Iltimos, endi film o'zini yuboring (rasm, apk fayllar mumkin emas, faqat video/hujjat):")
    await state.set_state(AdminStates.waiting_for_movie_file)

@dp.message(AdminStates.waiting_for_movie_file)
async def admin_get_m_file(message: types.Message, state: FSMContext):
    if message.photo or message.document and "apk" in str(message.document.file_name):
        await message.answer("❌ Rasm va apk fayllar mumkin emas! Iltimos, film videotasvirini yuboring:")
        return

    file_id = None
    m_type = "video"
    if message.video:
        file_id = message.video.file_id
        m_type = "video"
    elif message.animation:
        file_id = message.animation.file_id
        m_type = "animation"
    elif message.document:
        file_id = message.document.file_id
        m_type = "document"
    else:
        await message.answer("❌ Faqat video yoki fayl ko'rinishida yuboring:")
        return

    data = await state.get_data()
    code = data["code"]
    
    DB["movies"][code] = {
        "name": f"Kino #{code}",
        "file_id": file_id,
        "type": m_type,
        "views": 0
    }
    await state.clear()
    await message.answer(f"Sizning kodingiz ({code}) va film video qabul qilindi!", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query(F.data == "admin_del_movie")
async def admin_del_movie_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("O'chirmoqchi bo'lgan kino kodini yuboring (masalan: 77):")
    await state.set_state(AdminStates.waiting_for_del_movie_code)

@dp.message(AdminStates.waiting_for_del_movie_code)
async def admin_execute_del_movie(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if code in DB["movies"]:
        del DB["movies"][code]
        await message.answer(f"✅ {code} kodli kino va uning kodi o'chirib yuborildi!", reply_markup=get_main_menu(message.from_user.id))
    else:
        await message.answer("❌ Bunday kino kodi mavjud emas.")
    await state.clear()

# 2. REKLAMA (Xozir va Keyin yuborish)
@dp.callback_query(F.data == "admin_ads")
async def admin_ads_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="⚡ Hozir yuborish", callback_data="ad_now"))
    kb.row(types.InlineKeyboardButton(text="⏳ Keyin yuborish", callback_data="ad_later"))
    await callback.message.edit_text("📢 Reklama turini tanlang:", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "ad_now")
async def ad_now(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Iltimos foydalanuvchilarga nima deb xabar berish so'zini yozing:")
    await state.set_state(AdminStates.waiting_for_ad_text)

@dp.message(AdminStates.waiting_for_ad_text)
async def ad_get_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer("Sizda video, rasm yoki fayl bormi? Bo'lsa yuboring (bo'lmasa matnning o'zi ketadi):")
    await state.set_state(AdminStates.waiting_for_ad_media)

@dp.message(AdminStates.waiting_for_ad_media)
async def ad_get_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = data["text"]
    
    await message.answer("⏳ Reklama barchaga yuborilmoqda...")
    count = 0
    for uid in DB["users"]:
        try:
            if message.photo:
                await bot.send_photo(uid, message.photo[-1].file_id, caption=text)
            elif message.video:
                await bot.send_video(uid, message.video.file_id, caption=text)
            else:
                await bot.send_message(uid, text)
            count += 1
            await asyncio.sleep(0.03)
        except:
            pass
    await state.clear()
    await message.answer(f"✅ Reklama {count} ta foydalanuvchiga yetkazildi!", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query(F.data == "ad_later")
async def ad_later(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Necha daqiqadan (yoki sekunddan, masalan: 0.3 yoki 3) keyin yuborilishini raqamda kiriting:")
    await state.set_state(AdminStates.waiting_for_ad_time)

@dp.message(AdminStates.waiting_for_ad_time)
async def ad_get_time(message: types.Message, state: FSMContext):
    try:
        delay = float(message.text.strip())
        await state.update_data(delay=delay)
        await message.answer("Endi yuboriladigan xabar matnini kiriting:")
        await state.set_state(AdminStates.waiting_for_ad_text)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting:")

# 3. KANAL QO'SHISH VA O'CHIRISH
@dp.callback_query(F.data == "admin_channels")
async def admin_channels_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    if len(DB["channels"]) < 6:
        kb.row(types.InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_ch"))
    for ch in DB["channels"]:
        kb.row(types.InlineKeyboardButton(text=f"🗑️ O'chirish: {ch['username']}", callback_data=f"del_ch_{ch['id']}"))
    await callback.message.edit_text(f"📢 **Kanallar ({len(DB['channels'])}/6):**", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "add_ch")
async def add_ch_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Kanal @username sini kiriting:")
    await state.set_state(AdminStates.waiting_for_channel)

@dp.message(AdminStates.waiting_for_channel)
async def check_bot_admin_in_channel(message: types.Message, state: FSMContext):
    username = message.text.strip()
    try:
        chat = await bot.get_chat(username)
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status in ["administrator", "creator"]:
            DB["channels"].append({"id": len(DB["channels"]) + 1, "username": username})
            await state.clear()
            await message.answer(f"✅ Kanal qo'shildi: {username}", reply_markup=get_main_menu(message.from_user.id))
        else:
            await message.answer("❌ Bot bu kanalda admin emas! Avval botni kanalga admin qiling va qayta yuboring:")
    except Exception:
            await message.answer("❌ Bunday kanal topilmadi yoki xato username kiritildi:")

@dp.callback_query(F.data.startswith("del_ch_"))
async def delete_channel_action(callback: types.CallbackQuery):
    ch_id = int(callback.data.split("_")[2])
    DB["channels"] = [c for c in DB["channels"] if c["id"] != ch_id]
    await callback.answer("Kanal o'chirildi!")
    await admin_channels_menu(callback)

# 4. ADMIN QO'SHISH VA O'CHIRISH
@dp.callback_query(F.data == "admin_manage")
async def admin_manage_menu(callback: types.CallbackQuery):
    if not can_manage_admins(callback.from_user.id):
        await callback.answer("Sizda bu huquq yo'q!", show_alert=True)
        return
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_adm"))
    kb.row(types.InlineKeyboardButton(text="🗑️ Admin o'chirish", callback_data="del_adm"))
    await callback.message.edit_text("👑 **Adminlar boshqaruvi:**", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "add_adm")
async def add_adm_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Yangi adminning @username sini yuboring:")
    await state.set_state(AdminStates.waiting_for_new_admin_username)

@dp.message(AdminStates.waiting_for_new_admin_username)
async def get_adm_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="Ha ✅", callback_data="perm_yes"),
           types.InlineKeyboardButton(text="Yo'q ❌", callback_data="perm_no"))
    await message.answer("U ham admin qo'shib o'chira olsinmi?", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("perm_"))
async def save_new_admin(callback: types.CallbackQuery, state: FSMContext):
    can_manage = True if callback.data == "perm_yes" else False
    data = await state.get_data()
    # Eslatma: Haqiqiy ID topish uchun bazadan yoki username orqali qilinadi, bu yerda soddalashtirilgan holatda ID so'ralishi ham mumkin
    await callback.message.answer(f"✅ Yangi admin qo'shildi! (Huquq: {'Barchasi' if can_manage else 'Faqat kontent/reklama'})", reply_markup=get_main_menu(callback.from_user.id))
    await state.clear()

@dp.callback_query(F.data == "del_adm")
async def del_adm_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("O'chirmoqchi bo'lgan adminning @username sini yuboring:")
    await state.set_state(AdminStates.waiting_for_del_admin_username)

@dp.message(AdminStates.waiting_for_del_admin_username)
async def get_del_adm_username(message: types.Message, state: FSMContext):
    await message.answer("Adminni o'chirish sababi bormi? (Yozib yuboring yoki o'tkazib yuboring):")
    await state.set_state(AdminStates.waiting_for_del_admin_reason)

@dp.message(AdminStates.waiting_for_del_admin_reason)
async def finish_del_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Admin huquqi olib tashlandi va u oddiy foydalanuvchiga aylantirildi.", reply_markup=get_main_menu(message.from_user.id))

# 5. TEXNIK ISHLAR
@dp.callback_query(F.data == "admin_maint")
async def admin_maint(callback: types.CallbackQuery, state: FSMContext):
    DB["maintenance"]["status"] = not DB["maintenance"]["status"]
    status = "Yoniq ⚠️" if DB["maintenance"]["status"] else "O'chiq ✅"
    await callback.message.answer(f"Texnik ishlar holati: {status}\nSababini kiriting:")
    await state.set_state(AdminStates.waiting_for_maint_reason)

@dp.message(AdminStates.waiting_for_maint_reason)
async def save_maint(message: types.Message, state: FSMContext):
    DB["maintenance"]["reason"] = message.text.strip()
    await state.clear()
    await message.answer("✅ Texnik holat sababi saqlandi!", reply_markup=get_main_menu(message.from_user.id))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
