import logging
import json
import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from datetime import datetime

# Yuklash
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# Log sozlamalari
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode="HTML")  # HTML formatga o'zgartirildi
dp = Dispatcher(bot)

DATA_FILE = "data.json"
data = {"players": [], "games": []}
current_scores = {}

# Ma'lumotlarni yuklash/saqlash
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"players": [], "games": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

# Start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("1. O'yinchilarni boshqarish", callback_data="manage_players"),
        InlineKeyboardButton("2. Yangi o'yin yaratish", callback_data="start_game"),
        InlineKeyboardButton("3. Hisobotlar", callback_data="report"),
    )
    await message.answer("Mahjong botiga <b>xush kelibsiz!</b>", reply_markup=markup)

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
async def ask_player_name(call: types.CallbackQuery):
    await call.message.answer("Yangi o'yinchi ismini yozing:")
    dp.register_message_handler(save_new_player, state=None)

async def save_new_player(message: types.Message):
    name = message.text.strip()
    data["players"].append(name)
    save_data()
    await message.answer(f"<b>O'yinchi qo'shildi:</b> {name}")
    dp.message_handlers.unregister(save_new_player)
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
        await call.message.answer(f"<b>{name}</b> o'chirildi.")
        await send_welcome(message)
    else:
        await call.message.answer("O'yinchi topilmadi.")
        await send_welcome(call.message)

# Yangi o'yin boshlash
@dp.callback_query_handler(lambda c: c.data == 'start_game')
async def start_game(call: types.CallbackQuery):
    global current_scores
    current_scores = {}

    players_list = "\n".join([f"{name[0]} - {name}" for name in data["players"]])
    await call.message.answer(
        "🀄 <b>Yangi o'yin boshlandi!</b>\n"
        "Natijalarni quyidagi formatda yuboring:\n\n"
        "<code>B: 19+78+17</code>\n<code>F: 17+11+25</code>\n<code>M: 27+25+20</code>\n\n"
        f"O'yinchilar:\n{players_list}"
    )
    dp.register_message_handler(process_scores, state=None)

async def process_scores(message: types.Message):
    global current_scores
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
        except:
            await message.reply(f"Xato format: {line}")
            return

    if not current_scores:
        await message.reply("Hech qanday natija topilmadi.")
        await send_welcome(message)
        return

    dp.message_handlers.unregister(process_scores)
    await finalize_scores(message)

async def finalize_scores(message: types.Message):
    global current_scores
    winner = ""
    max_score = -1
    text = "<b>📊 Umumiy natijalar:</b>\n\n"

    for name, score in current_scores.items():
        text += f"<b>{name}</b>: {score['detail']} = {score['total']}\n"
        if score['total'] > max_score:
            max_score = score['total']
            winner = name

    date = datetime.now().strftime("%d.%m.%Y")
    final_text = f"📅 {date} - g'olib: 🏆 <b>{winner}</b> 🎉\n\n"

    # Foydalanuvchiga
    await message.answer(final_text)

    # Guruhga
    try:
        await bot.send_message(GROUP_CHAT_ID, final_text)
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

    text = "<b>📊 So'nggi 3 ta o'yin natijalari:</b>\n\n"
    for game in data["games"][-3:]:
        text += f"📅 {game['date']} - 🏆 <b>{game['winner']}</b>\n"
        for name, score in game["results"].items():
            text += f"{name}: {score['detail']} = {score['total']}\n"
        text += "\n"
    await call.message.answer(text)
    await send_welcome(call.message)

# Run
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
