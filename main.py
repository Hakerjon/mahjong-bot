import logging
import json
import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from datetime import datetime
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import threading

# Yuklash
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# Log sozlamalari
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode="MarkdownV2")
dp = Dispatcher(bot)

DATA_FILE = "data.json"
data = {"players": [], "games": []}
file_lock = threading.Lock()

# Ma'lumotlarni yuklash/saqlash
def load_data():
    with file_lock:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return {"players": [], "games": []}

def save_data():
    with file_lock:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)

data = load_data()

# MarkdownV2 uchun escape funksiyasi
def escape_markdown(text):
    chars = r"_*[]()~`>#+-=|{}.!"
    for char in chars:
        text = text.replace(char, f"\\{char}")
    return text

# Holatlar
class PlayerForm(StatesGroup):
    NAME = State()

class GameForm(StatesGroup):
    SCORES = State()

# Start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("1. O'yinchilarni boshqarish", callback_data="manage_players"),
        InlineKeyboardButton("2. Yangi o'yin yaratish", callback_data="start_game"),
        InlineKeyboardButton("3. Hisobotlar", callback_data="report"),
    )
    await message.answer("Mahjong botiga xush kelibsiz!", reply_markup=markup)

# O'yinchilarni boshqarish
@dp.callback_query_handler(lambda c: c.data == 'manage_players')
async def manage_players(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ O'yinchi qo'shish", callback_data="add_player"),
        InlineKeyboardButton("➖ O'yinchi o'chirish", callback_data="remove_player"),
    )
    await call.message.answer("O'yinchilarni boshqarish:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'add_player')
async def ask_player_name(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Yangi o'yinchi ismini yozing:")
    await PlayerForm.NAME.set()

@dp.message_handler(state=PlayerForm.NAME)
async def save_new_player(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if name in data["players"]:
        await message.answer(f"O'yinchi {name} allaqachon mavjud!")
        await state.finish()
        return
    data["players"].append(name)
    save_data()
    await message.answer(f"O'yinchi qo'shildi: {name}")
    await state.finish()
    await send_welcome(message)

@dp.callback_query_handler(lambda c: c.data == 'remove_player')
async def remove_player(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=1)
    for p in data["players"]:
        markup.add(InlineKeyboardButton(p, callback_data=f"del_{p}"))
    await call.message.answer("O'chirmoqchi bo'lgan o'yinchini tanlang:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def delete_player(call: types.CallbackQuery):
    name = call.data[4:]
    if name in data["players"]:
        data["players"].remove(name)
        save_data()
        await call.message.answer(f"{name} o'chirildi.")
    else:
        await call.message.answer("O'yinchi topilmadi.")
    await send_welcome(call.message)

# Yangi o'yin boshlash
@dp.callback_query_handler(lambda c: c.data == 'start_game')
async def start_game(call: types.CallbackQuery, state: FSMContext):
    if not data["players"]:
        await call.message.answer("O'yin boshlash uchun kamida bir o'yinchi qo'shing!")
        return
    await state.update_data(current_scores={})
    players_list = "\n".join([f"{name[0]} - {name}" for name in data["players"]])
    await call.message.answer(
        "🀄 Yangi o'yin boshlandi!\n"
        "Natijalarni quyidagi formatda yuboring:\n\n"
        "B: 19+78+17\nF: 17+11+25\nM: 27+25+20\n\n"
        f"O'yinchilar:\n{players_list}"
    )
    await GameForm.SCORES.set()

@dp.message_handler(state=GameForm.SCORES)
async def process_scores(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    current_scores = user_data.get("current_scores", {})

    lines = message.text.strip().replace(" ", "").splitlines()
    player_map = {name[0].upper(): name for name in data["players"]}

    for line in lines:
        if ":" not in line:
            continue
        try:
            initial, score_str = line.split(":")
            name = player_map.get(initial.upper())
            if not name:
                await message.reply(f"{initial} o'yinchi topilmadi.")
                return
            parts = list(map(int, score_str.split("+")))
            total = sum(parts)
            current_scores[name] = {"detail": "+".join(map(str, parts)), "total": total}
        except ValueError:
            await message.reply(f"Xato format: {line}. Raqamlar va '+' belgisidan foydalaning.")
            return

    if not current_scores:
        await message.reply("Hech qanday natija topilmadi.")
        return

    await state.update_data(current_scores=current_scores)
    await state.finish()
    await finalize_scores(message, current_scores)

async def finalize_scores(message: types.Message, current_scores):
    winner = ""
    max_score = -1
    text = "📊 Umumiy natijalar:\n\n"

    for name, score in current_scores.items():
        detail = escape_markdown(score['detail'])
        text += f"{escape_markdown(name)}: {detail} = {score['total']}\n"
        if score['total'] > max_score:
            max_score = score['total']
            winner = name

    date = datetime.now().strftime("%d.%m.%Y")
    final_text = f"📅 {date} - bugungi o'yin g'olibi 🏆 **{escape_markdown(winner)}**! 🎉\n\n{text}"

    await message.answer(final_text, parse_mode="MarkdownV2")
    try:
        await bot.send_message(GROUP_CHAT_ID, final_text, parse_mode="MarkdownV2")
    except Exception as e:
        await message.answer(f"Guruhga yuborilmadi: {e}")

    data["games"].append({
        "date": date,
        "results": current_scores,
        "winner": winner
    })
    save_data()
    await send_welcome(message)

# Hisobotlar
@dp.callback_query_handler(lambda c: c.data == 'report')
async def report(call: types.CallbackQuery):
    if not data["games"]:
        await call.message.answer("Hali hech qanday o'yin yo'q.")
        return

    text = "📊 So'nggi 3 ta o'yin natijalari:\n\n"
    for game in data["games"][-3:]:
        text += f"📅 {game['date']} - 🏆 {escape_markdown(game['winner'])}\n"
        for name, score in game["results"].items():
            detail = escape_markdown(score['detail'])
            text += f"{escape_markdown(name)}: {detail} = {score['total']}\n"
        text += "\n"
    await call.message.answer(text, parse_mode="MarkdownV2")

# Run
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
