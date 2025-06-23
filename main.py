import logging
import json
import os
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.filters import Command

API_TOKEN = os.getenv("BOT_TOKEN")  # Railway .env da saqlanadi

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "data.json"

# Foydalanuvchilar va o'yinlar ma'lumotlarini saqlovchi fayl
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"players": [], "games": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()
current_game = []
current_scores = {}
adding_scores = False
adding_player_index = 0

# Boshlanish
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Salom! Bu Mahjong natijalar botidir. Admin paneldan foydalaning.")

# Admin panel
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("1. O'yinchilarni boshqarish"))
main_menu.add(KeyboardButton("2. Yangi o'yin yaratish"))
main_menu.add(KeyboardButton("3. Hisobotlar"))

# O'yinchilarni boshqarish
@dp.callback_query_handler(lambda c: c.data == 'manage_players')
async def manage_players(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕ O'yinchi qo'shish", callback_data="add_player"),
        markup.add(InlineKeyboardButton("➖ O'yinchi o'chirish", callback_data="remove_player")
    ),
    await call.message.answer("O'yinchilarni boshqarish:", reply_markup=markup)

# O'yinchi qo'shish
@dp.callback_query_handler(lambda c: c.data == 'add_player')
async def ask_player_name(call: types.CallbackQuery):
    await call.message.answer("Yangi o'yinchi ismini yuboring:")
    dp.register_message_handler(save_new_player, content_types=types.ContentTypes.TEXT, state=None)

async def save_new_player(message: types.Message):
    name = message.text.strip()
    data["players"].append(name)
    save_data(data)
    await message.answer(f"O'yinchi qo'shildi: {name}")
    dp.message_handlers.unregister(save_new_player)

# O'yinchi o'chirish
@dp.callback_query_handler(lambda c: c.data == 'remove_player')
async def remove_player(call: types.CallbackQuery):
    markup = InlineKeyboardMarkup()
    for p in data["players"]:
        markup.add(InlineKeyboardButton(p, callback_data=f"del_{p}"))
    await call.message.answer("O'chirmoqchi bo'lgan o'yinchini tanlang:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('del_'))
async def delete_player(call: types.CallbackQuery):
    name = call.data[4:]
    data["players"].remove(name)
    save_data(data)
    await call.message.answer(f"{name} o'chirildi.")

# Yangi o'yin yaratish
@dp.callback_query_handler(lambda c: c.data == 'start_game')
async def start_game(call: types.CallbackQuery):
    global current_scores, current_game, adding_scores, adding_player_index
    current_scores = {}
    current_game = data["players"][:]
    adding_scores = True
    adding_player_index = 0
    await call.message.answer("Yangi o'yin boshlandi. Har bir o'yinchi uchun natijalarni kiriting.")
    await ask_score(call.message)

async def ask_score(message):
    global current_game, adding_player_index
    if adding_player_index < len(current_game):
        name = current_game[adding_player_index]
        await message.answer(f"{name} uchun natijani kiriting (masalan: 10+20+30+40):")
        dp.register_message_handler(get_score, content_types=types.ContentTypes.TEXT, state=None)
    else:
        await finalize_scores(message)

async def get_score(message: types.Message):
    global current_scores, adding_player_index
    name = current_game[adding_player_index]
    score_str = message.text.strip()
    try:
        parts = list(map(int, score_str.split("+")))
        total = sum(parts)
        current_scores[name] = {
            "detail": score_str,
            "total": total
        }
        adding_player_index += 1
        dp.message_handlers.unregister(get_score)
        await ask_score(message)
    except:
        await message.reply("Xatolik! Raqamlarni `+` bilan kiriting (masalan: 10+20+30+40)")

async def finalize_scores(message):
    text = "Umumiy natijalar:\n\n"
    winner = ""
    max_score = 0
    for name, score in current_scores.items():
        text += f"{name}: {score['detail']} = {score['total']}\n"
        if score['total'] > max_score:
            max_score = score['total']
            winner = name
    text += f"\n🏆 G'olib: {winner}\n\n"
    from datetime import datetime
    date = datetime.now().strftime("%d.%m.%Y")
    text = f"{date} yil hisobiga ko'ra bugungi o'yin g'olibi {winner}\n\n" + text
    await message.answer(text)

    # Saqlab qo'yamiz
    data["games"].append({
        "date": date,
        "results": current_scores,
        "winner": winner
    })
    save_data(data)

# Hisobot
@dp.callback_query_handler(lambda c: c.data == 'report')
async def report(call: types.CallbackQuery):
    if not data["games"]:
        await call.message.answer("Hali hech qanday o'yin natijasi yo'q.")
        return

    text = "📊 So'nggi o'yin natijalari:\n\n"
    for game in data["games"][-3:]:  # faqat oxirgi 3ta
        text += f"📅 {game['date']} - 🏆 {game['winner']}\n"
        for name, score in game["results"].items():
            text += f"{name}: {score['detail']} = {score['total']}\n"
        text += "\n"
    await call.message.answer(text)

# Run
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
