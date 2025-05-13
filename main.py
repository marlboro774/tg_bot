import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from av import TG_TOKEN

conn = sqlite3.connect('finance.db', check_same_thread=False)
cursor = conn.cursor()

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

AMOUNT, CATEGORY = range(2)

# Категории для выбора
FOOD = ['Еда']
TRANSP = ['Транспорт']
RAZVL = ['Развлечения']
ZARPLATA = ['Зарплата']
MORE = ['Другое']

# Функция для создания клавиатуры с командами
def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

# Функция для создания основной клавиатуры с командами
def create_main_keyboard():
    button_list = [
        KeyboardButton('/add_income'),
        KeyboardButton('/add_expense'),
        KeyboardButton('/stats'),
        KeyboardButton('/report'),
        KeyboardButton('/reset')
    ]
    reply_markup = ReplyKeyboardMarkup(build_menu(button_list, n_cols=2), resize_keyboard=True) # resize_keyboard=True для лучшего отображения
    return reply_markup

async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

    # Отправляем клавиатуру сразу после старта
    reply_markup = create_main_keyboard()

    await update.message.reply_text(
        f"""Привет, {username}! Я бот для учёта финансов. Выберите команду:""",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def add_income(update: Update, context: CallbackContext):
    context.user_data['type'] = 'income'
    await update.message.reply_text("Введите сумму дохода:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True))
    return AMOUNT

async def add_expense(update: Update, context: CallbackContext):
    context.user_data['type'] = 'expense'
    await update.message.reply_text("Введите сумму расхода:", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True))
    return AMOUNT

async def handle_amount(update: Update, context: CallbackContext):
    if update.message.text == "Отмена":
        await update.message.reply_text("Действие отменено.", reply_markup=create_main_keyboard())
        return ConversationHandler.END
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        keyboard = [FOOD, TRANSP, RAZVL, ZARPLATA, MORE]
        reply_markup = ReplyKeyboardMarkup(build_menu([KeyboardButton(cat[0]) for cat in keyboard], n_cols=3), one_time_keyboard=True)
        await update.message.reply_text("Выберите категорию с помощью кнопок или напишите свою:", reply_markup=reply_markup)
        return CATEGORY

    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True))
        return AMOUNT

async def handle_category(update: Update, context: CallbackContext):
    category = update.message.text
    user_id = update.effective_user.id
    transaction_type = context.user_data['type']
    amount = context.user_data['amount']

    cursor.execute(
        "INSERT INTO transactions (user_id, amount, category, type, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, transaction_type, datetime.now().strftime('%d/%m/%y'))
    )
    conn.commit()
    await update.message.reply_text(f"{transaction_type.capitalize()} добавлен!", reply_markup=create_main_keyboard())
    return ConversationHandler.END

async def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income'", (user_id,))
    total_income = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense'", (user_id,))
    total_expense = cursor.fetchone()[0] or 0
    await update.message.reply_text(f"Ваши финансы:\nДоходы: {total_income}\nРасходы: {total_expense}", reply_markup=create_main_keyboard())

async def report(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("SELECT amount, category, type, date FROM transactions WHERE user_id = ?", (user_id,))
    transactions = cursor.fetchall()
    if not transactions:
        await update.message.reply_text("Нет транзакций.", reply_markup=create_main_keyboard())
        return
    report_message = "Ваш отчет:\n"
    for amount, category, type, date in transactions:
        report_message += f"{type.capitalize()}: {amount} (Категория: {category}, Дата: {date})\n"
    await update.message.reply_text(report_message, reply_markup=create_main_keyboard())

async def reset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
    conn.commit()
    await update.message.reply_text("Ваши данные о финансах были сброшены.", reply_markup=create_main_keyboard())

def main():
    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reset", reset))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_income', add_income),
                      CommandHandler('add_expense', add_expense)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()