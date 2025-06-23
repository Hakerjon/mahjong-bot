import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Bu yerga o'z tokeningizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

players = {}
game_sessions = []
current_results = {}

def create_admin_panel():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("1. O'yinchilarni boshqarish", callback_data='manage_players'),
        InlineKeyboardButton("2. Yangi o'yin yaratish", callback_data='new_game'),
        InlineKeyboardButton("3. Hisobotlarni chiqarish", callback_data='report')
    )
    return markup

def create_player_manage_panel():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("O'yinchini qo'shish", callback_data='add_player'),
        InlineKeyboardButton("O'yinchini o'chirish", callback_data='remove_player')
    )
    return markup

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("Admin panel:", reply_markup=create_admin_panel())

@dp.callback_query_handler(lambda c: c.data == 'manage_players')
async def manage_players(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text("O'yinchilarni boshqarish:", reply_markup=create_player_manage_panel())

@dp.callback_query_handler(lambda c: c.data == 'add_player')
async def add_player(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Yangi o'yinchi ismini kiriting:")
    await dp.current_state(user=callback_query.from_user.id).set_state("awaiting_new_player")

@dp.message_handler(state="awaiting_new_player")
async def process_new_player(message: types.Message, state):
    name = message.text.strip()
    players[name] = []
    await message.answer(f"{name} qo'''shildi.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'remove_player')
async def remove_player(callback_query: types.CallbackQuery):
    if not players:
        await callback_query.message.answer("O'yinchi ro'yxati bo'sh.")
        return
    markup = InlineKeyboardMarkup()
    for name in players:
        markup.add(InlineKeyboardButton(name, callback_data=f'remove_{name}'))
    await callback_query.message.edit_text("Qaysi o'yinchini o'chirasiz?", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('remove_'))
async def confirm_remove_player(callback_query: types.CallbackQuery):
    name = callback_query.data.replace("remove_", "")
    players.pop(name, None)
    await callback_query.message.edit_text(f"{name} o'chirildi.")

@dp.callback_query_handler(lambda c: c.data == 'new_game')
async def start_new_game(callback_query: types.CallbackQuery):
    global current_results
    current_results = {}
    await callback_query.message.answer("Yangi o'yin boshlandi. Har bir o'yinchi uchun natijalarni kiriting.")
    for name in players:
        await bot.send_message(callback_query.from_user.id, f"{name} uchun natijalarni kiriting (masalan: 10+20+30):")
        await dp.current_state(user=callback_query.from_user.id).set_state(f"awaiting_result_{name}")

@dp.message_handler(lambda message: message.text and '+' in message.text)
async def process_results(message: types.Message):
    global current_results

    name = None
    for state_name in message.conf.get("aiogram_state"):
        if state_name.startswith("awaiting_result_"):
            name = state_name.replace("awaiting_result_", "")
            break

    if not name:
        return

    raw = message.text.strip()
    try:
        numbers = list(map(int, raw.split('+')))
        total = sum(numbers)
        players[name].append((raw, total))
        current_results[name] = (raw, total)
        await message.answer(f"{name}: {raw} = {total}")
        await dp.current_state(user=message.from_user.id).reset_state()

        if len(current_results) == len(players):
            date = datetime.now().strftime("%d.%m.%Y")
            sorted_results = sorted(current_results.items(), key=lambda x: x[1][1], reverse=True)
            winner = sorted_results[0][0]

            result_lines = [f"{name}: {v[0]} = {v[1]}" for name, v in sorted_results]
            text = f"{date} yil hisobiga ko'ra bugungi o'yin g'olibi {winner}" + ''.join(result_lines)
            await bot.send_message(message.chat.id, text)

    except Exception as e:
        await message.answer("Xatolik! Natijalarni 10+20+30 ko'rinishida yuboring.")

@dp.callback_query_handler(lambda c: c.data == 'report')
async def show_report(callback_query: types.CallbackQuery):
    if not players:
        await callback_query.message.answer("O'yinchilar mavjud emas.")
        return
    text = "Umumiy natijalar:\n"
    for name, records in players.items():
        total = sum(r[1] for r in records)
        text += f"{name}: {total} ball
"
    await callback_query.message.answer(text)
