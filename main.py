
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import os

API_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

players = []
game_results = []

# Admin panel tugmalari
def admin_panel():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("1. O'yinchilarni boshqarish", callback_data="manage_players"),
        InlineKeyboardButton("2. Yangi o'yin yaratish", callback_data="new_game"),
        InlineKeyboardButton("3. Hisobotlarni chiqarish", callback_data="report")
    )
    return kb

def manage_players_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("O'yinchi qo'shish", callback_data="add_player"),
        InlineKeyboardButton("O'yinchi o'chirish", callback_data="remove_player")
    )
    return kb

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("Admin paneliga xush kelibsiz!", reply_markup=admin_panel())

@dp.callback_query_handler(lambda c: c.data == 'manage_players')
async def manage_players(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("O'yinchilarni boshqarish", reply_markup=manage_players_kb())

@dp.callback_query_handler(lambda c: c.data == 'add_player')
async def add_player(callback_query: types.CallbackQuery):
    await callback_query.message.answer("O'yinchi ismini yuboring:")
    @dp.message_handler()
    async def get_player_name(msg: types.Message):
        players.append(msg.text)
        await msg.answer(f"{msg.text} qoвЂshildi!", reply_markup=admin_panel())

@dp.callback_query_handler(lambda c: c.data == 'remove_player')
async def remove_player(callback_query: types.CallbackQuery):
    if not players:
        await callback_query.message.answer("Hozircha hech qanday o'yinchi yo'q.")
        return
    kb = InlineKeyboardMarkup()
    for p in players:
        kb.add(InlineKeyboardButton(p, callback_data=f"del_{p}"))
    await callback_query.message.answer("Qaysi o'yinchini o'chirasiz?", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("del_"))
async def delete_player(callback_query: types.CallbackQuery):
    name = callback_query.data[4:]
    if name in players:
        players.remove(name)
        await callback_query.message.answer(f"{name} oвЂchirildi.", reply_markup=admin_panel())

@dp.callback_query_handler(lambda c: c.data == 'new_game')
async def new_game(callback_query: types.CallbackQuery):
    game_results.clear()
    await callback_query.message.answer("Yangi o'yin boshlandi. Har bir o'yinchi uchun natijalarni kiriting.
Format: 10+20+30+40")
    await prompt_for_result(callback_query.message)

async def prompt_for_result(message, index=0):
    if index >= len(players):
        await post_results(message)
        return

    player = players[index]
    await message.answer(f"{player} uchun natijalarni kiriting:")
    @dp.message_handler()
    async def get_result(msg: types.Message):
        try:
            parts = [int(p) for p in msg.text.split('+')]
            total = sum(parts)
            game_results.append((player, msg.text, total))
            await prompt_for_result(msg, index + 1)
        except:
            await msg.answer("Xatolik! Format: 10+20+30+40")

async def post_results(message):
    text = "Umumiy natijalar:
"
    max_score = 0
    winner = ""
    for name, detail, total in game_results:
        text += f"{name}: {detail} = {total}
"
        if total > max_score:
            max_score = total
            winner = name
    date = datetime.now().strftime("%d.%m.%Y")
    text = f"{date} yil hisobiga ko'ra bugungi o'yin g'olibi {winner}

" + text + f"
Tabriklaymiz, {winner}!"
    await message.answer(text)

@dp.callback_query_handler(lambda c: c.data == 'report')
async def report(callback_query: types.CallbackQuery):
    if not game_results:
        await callback_query.message.answer("Hali hech qanday o'yin natijasi yoвЂq.")
        return
    await post_results(callback_query.message)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
