import logging
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))  # Add your group ID in .env

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Data file
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"players": [], "games": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
current_scores = {}
current_game = []

# Start command
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("1. O'yinchilarni boshqarish", callback_data="manage_players"))
    markup.add(InlineKeyboardButton("2. Yangi o'yin yaratish", callback_data="start_game"))
    markup.add(InlineKeyboardButton("3. Hisobotlar", callback_data="report"))
    await message.answer("Mahjong botiga xush kelibsiz!", reply_markup=markup)

# Manage players
@dp.callback_query_handler(lambda c: c.data == 'manage_players')
async def manage_players(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("➕ O'yinchi qo'shish", callback_data="add_player"))
    markup.add(InlineKeyboardButton("➖ O'yinchi o'chirish", callback_data="remove_player"))
    await call.message.answer("O'yinchilarni boshqarish:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'add_player')
async def ask_player_name(call: types.CallbackQuery):
    await call.message.answer("Yangi o'yinchi ismini yuboring:")

    @dp.message_handler(lambda msg: True)
    async def save_new_player(message: types.Message):
        name = message.text.strip()
        if name and name not in data["players"]:
            data["players"].append(name)
            save_data(data)
            await message.answer(f"O'yinchi qo'shildi: {name}")
        else:
            await message.answer("❌ Noto'g'ri yoki takroriy ism.")
        await send_welcome(message)

@dp.callback_query_handler(lambda c: c.data == 'remove_player')
async def remove_player(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup()
    for p in data["players"]:
        markup.add(InlineKeyboardButton(p, callback_data=f"del_{p}"))
    await call.message.answer("O'chirmoqchi bo'lgan o'yinchini tanlang:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def delete_player(call: types.CallbackQuery):
    name = call.data[4:]
    if name in data["players"]:
        data["players"].remove(name)
        save_data(data)
        await call.message.answer(f"{name} o'chirildi.")
    await send_welcome(call.message)

# Start new game
@dp.callback_query_handler(lambda c: c.data == 'start_game')
async def start_game(call: types.CallbackQuery):
    global current_scores, current_game
    current_scores = {}
    current_game = data["players"][:]
    players_short = "\n".join([f"{name[0]} - {name}" for name in current_game])
    await call.message.answer(
        "🀄 Yangi o'yin boshlandi!\n"
        "Natijalarni quyidagi formatda yuboring:\n\n"
        "B: 19+78+17\nF: 17+11+25\nM: 27+25+20\n\n"
        f"⏳ O'yinchilar:\n{players_short}"
    )

    @dp.message_handler(lambda msg: True)
    async def process_scores(message: types.Message):
        global current_scores
        text = message.text.strip().replace(" ", "")
        lines = text.splitlines()
        player_map = {name[0].upper(): name for name in data["players"]}
        for line in lines:
            if ":" not in line:
                continue
            try:
                initial, score_str = line.split(":")
                name = player_map.get(initial.upper())
                if not name:
                    await message.reply(f"⚠️ {initial} mos kelmaydi.")
                    return
                parts = list(map(int, score_str.split("+")))
                total = sum(parts)
                current_scores[name] = {"detail": "+".join(map(str, parts)), "total": total}
            except:
                await message.reply(f"❌ Xato format: {line}")
                return
        if not current_scores:
            await message.reply("⚠️ Natijalar topilmadi.")
            return
        await finalize_scores(message)

async def finalize_scores(message):
    text = "📊 Umumiy natijalar:\n\n"
    winner = ""
    max_score = 0
    for name, score in current_scores.items():
        text += f"{name}: {score['detail']} = {score['total']}\n"
        if score['total'] > max_score:
            max_score = score['total']
            winner = name

    date = datetime.now().strftime("%d.%m.%Y")
    text = f"📅 {date} - g'olib: 🏆 *{winner}* 🎉\n\n{text}"

    await message.answer(text, parse_mode="Markdown")
    try:
        if GROUP_CHAT_ID != 0:
            await bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Guruhga yuborilmadi: {e}")

    data["games"].append({
        "date": date,
        "results": current_scores,
        "winner": winner
    })
    save_data(data)
    await send_welcome(message)

# Report
@dp.callback_query_handler(lambda c: c.data == 'report')
async def report(call: types.CallbackQuery):
    if not data["games"]:
        await call.message.answer("Hali hech qanday o'yin natijasi yo'q.")
        return
    text = "📊 So'nggi o'yinlar:\n\n"
    for game in data["games"][-3:]:
        text += f"📅 {game['date']} - 🏆 {game['winner']}\n"
        for name, score in game["results"].items():
            text += f"{name}: {score['detail']} = {score['total']}\n"
        text += "\n"
    await call.message.answer(text)
    await send_welcome(call.message)

# Detect group chat ID
@dp.message_handler()
async def detect_chat_id(message: types.Message):
    if message.chat.type in ["group", "supergroup"]:
        await message.answer(f"Guruh ID: `{message.chat.id}`", parse_mode="Markdown")
    else:
        await send_welcome(message)

# Run bot
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
