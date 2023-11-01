import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

class UserGameAdd(StatesGroup):
    name = State()
    price = State()

class UserCart(StatesGroup):
    cart = State()

bot = Bot(token='6660956711:AAFRKTEuy3wZl2GQ0NI2NzEVNcjg-0gfzDM')
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect('game_shop.db')
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY,
        name TEXT,
        price INTEGER
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_cart (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        game_id INTEGER
    );
""")
conn.commit()

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Inventory", callback_data='inventory'))
    keyboard.add(InlineKeyboardButton("Shop", callback_data='shop'))
    keyboard.add(InlineKeyboardButton("Add Game", callback_data='add_game'))
    keyboard.add(InlineKeyboardButton("Cart", callback_data='cart'))
    await message.reply("Welcome! Here are some useful buttons!", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'inventory')
async def show_inventory(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_inventory = cursor.execute("SELECT games.name, games.price FROM user_cart, games WHERE user_cart.user_id = ? AND user_cart.game_id = games.id", (user_id,))
    games_in_cart = cursor.fetchall()

    if games_in_cart:
        games_text = "\n".join([f"{game[0]} - {game[1]} UAH" for game in games_in_cart])
        await bot.send_message(user_id, f"Inventory:\n{games_text}")
    else:
        await bot.send_message(user_id, "Your inventory is empty.")

@dp.callback_query_handler(lambda c: c.data == 'shop')
async def shop_commands(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    games = cursor.execute("SELECT id, name, price FROM games").fetchall()
    for game in games:
        keyboard.add(InlineKeyboardButton(game[1], callback_data=f'shop_{game[0]}'))
    keyboard.add(InlineKeyboardButton("Back to start", callback_data='start'))

    await bot.send_message(callback_query.from_user.id, "Welcome to the shop! Choose a game to add to your cart:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('shop_'))
async def process_callback_shop(callback_query: types.CallbackQuery):
    game_id = int(callback_query.data.split('_')[1])
    game = cursor.execute("SELECT name, price FROM games WHERE id = ?", (game_id,)).fetchone()

    if game:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Add to Cart", callback_data=f'add_to_cart_{game_id}'))
        keyboard.add(InlineKeyboardButton("Back to shop", callback_data='shop'))
        await bot.send_message(callback_query.from_user.id, f"You are adding {game[0]} to your cart for {game[1]} UAH.", reply_markup=keyboard)
    else:
        await bot.send_message(callback_query.from_user.id, "Game not found.")

@dp.callback_query_handler(lambda c: c.data.startswith('add_to_cart_'))
async def process_callback_add_to_cart(callback_query: types.CallbackQuery):
    game_id = int(callback_query.data.split('_')[1])
    user_id = callback_query.from_user.id

    cursor.execute("INSERT INTO user_cart (user_id, game_id) VALUES (?, ?)", (user_id, game_id))
    conn.commit()

    await bot.send_message(user_id, "The game has been added to your cart!")

@dp.callback_query_handler(lambda c: c.data == 'cart')
async def view_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_cart = cursor.execute("SELECT games.name, games.price FROM user_cart, games WHERE user_cart.user_id = ? AND user_cart.game_id = games.id", (user_id,))
    games_in_cart = cursor.fetchall()
    game_names = []

    for game in games_in_cart:
        game_names.append(game[0])

    if game_names:
        games_text = ", ".join(game_names)
        total_price = sum([game[1] for game in games_in_cart])
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Buy Cart", callback_data='buy_cart'))
        await bot.send_message(user_id, f"Games in your cart: {games_text}\nTotal price: {total_price} UAH", reply_markup=keyboard)
    else:
        await bot.send_message(user_id, "Your cart is empty.")

@dp.callback_query_handler(lambda c: c.data == 'buy_cart')
async def buy_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_cart = cursor.execute("SELECT game_id FROM user_cart WHERE user_id = ?", (user_id,))
    games_in_cart = cursor.fetchall()

    if games_in_cart:
        cursor.executemany("INSERT INTO inventory (user_id, game_id) VALUES (?, ?)", [(user_id, game[0]) for game in games_in_cart])
        conn.commit()

        game_names = [cursor.execute("SELECT name FROM games WHERE id = ?", (game[0],)).fetchone()[0] for game in games_in_cart]
        total_price = sum([cursor.execute("SELECT price FROM games WHERE id = ?", (game[0],)).fetchone()[0] for game in games_in_cart])

        await bot.send_message(user_id, f"You have successfully purchased {', '.join(game_names)} for a total price of {total_price} UAH!")
    else:
        await bot.send_message(user_id, "Your cart is empty.")

@dp.message_handler(commands='add_game')
async def add_new_game(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await message.answer(text='Enter the name of your game.')
    await state.set_state('game_name')

@dp.message_handler(state='game_name')
async def game_name(message: types.Message, state: FSMContext):
    game_name = message.text

    await state.update_data(game_name=game_name)
    await message.answer(text='Now, enter the price of the game.')
    await state.set_state('game_price')

@dp.message_handler(lambda c: c.text.isdigit(), state='game_price')
async def game_price(message: types.Message, state: FSMContext):
    game_price = int(message.text)
    await state.update_data(game_price=game_price)

    user_data = await state.get_data()
    game_name = user_data['game_name']
    game_price = user_data['game_price']

    cursor.execute('INSERT INTO games (name, price) VALUES (?, ?)', (game_name, game_price))
    conn.commit()

    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)