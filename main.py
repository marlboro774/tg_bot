import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Добавляем пользователя в БД, если его нет
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

    update.message.reply_text(
        "💰 *Финансовый трекер*\n\n"
        "Доступные команды:\n"
        "/add_income - добавить доход\n"
        "/add_expense - добавить расход\n"
        "/stats - статистика\n"
        "/report - отчет за месяц",
        parse_mode="Markdown"
    )


def add_income(update: Update, context: CallbackContext):
    update.message.reply_text("Введите сумму дохода:")
    context.user_data['waiting_for'] = 'income_amount'


def add_expense(update: Update, context: CallbackContext):
    update.message.reply_text("Введите сумму расхода:")
    context.user_data['waiting_for'] = 'expense_amount'


def main():
    app = Application.builder().token(TG_TOKEN).build()
    handler = MessageHandler(filters.TEXT & ~filters.COMMAND, start)
    app.add_handler(handler)

    app.start_polling()


if __name__ == "__main__":
    main()
