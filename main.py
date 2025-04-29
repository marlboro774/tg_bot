import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from av import TG_TOKEN
from telebot import types
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext, \
    Application

# Инициализация БД
conn = sqlite3.connect('finance.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    category TEXT,
    type TEXT,  -- 'income' или 'expense'
    date TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
''')
conn.commit()


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Добавляем пользователя в БД, если его нет
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

    await update.message.reply_text(
        """💰 *Финансовый трекер*
        
Привет, {}! Я тестовый бот для твоих финансов
Доступные команды:
/add_income - добавить доход
/add_expense - добавить расход
/stats - статистика
/report - отчет за месяц""".format(username)
    )


async def add_income(update: Update, context: CallbackContext):
    context.user_data['waiting_for'] = 'income_amount'
    await update.message.reply_text("Введите сумму дохода:")


async def add_expense(update: Update, context: CallbackContext):
    context.user_data['waiting_for'] = 'expense_amount'
    await update.message.reply_text("Введите сумму расхода:")


async def stats(update: Update, context: CallbackContext):
    context.user_data['waiting_for'] = 'stats'
    await update.message.reply_text("Ваша статистика:")


async def report(update: Update, context: CallbackContext):
    context.user_data['waiting_for'] = 'stats'
    await update.message.reply_text("Отчет за месяц:")


async def handle_amount(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    try:
        amount = float(text)
        if context.user_data.get('waiting_for') == 'income_amount':
            context.user_data['income_amount'] = amount
            await update.message.reply_text("Укажите категорию дохода (например, 'Зарплата'):")
            context.user_data['waiting_for'] = 'income_category'
        elif context.user_data.get('waiting_for') == 'expense_amount':
            context.user_data['expense_amount'] = amount
            await update.message.reply_text("Укажите категорию расхода (например, 'Еда'):")
            context.user_data['waiting_for'] = 'expense_category'
    except ValueError:
        await update.message.reply_text("Ошибка! Введите число.")


def main():
    app = Application.builder().token(TG_TOKEN).build()
    handler = MessageHandler(filters.TEXT & ~filters.COMMAND, start)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount))
    app.add_handler(handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("add_income", add_income))
    app.add_handler(CommandHandler("add_expense", add_expense))
    app.add_handler(CommandHandler("report", report))

    app.run_polling()


if __name__ == "__main__":
    main()
