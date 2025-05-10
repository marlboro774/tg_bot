import sqlite3
from datetime import datetime
from telegram import Update
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
TRANSACTION_TYPE = range(1)


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    await update.message.reply_text(
        """Привет, {}! Я бот для учёта финансов.
Чтобы добавить доход, используйте /add_income.
Чтобы добавить расход, используйте /add_expense.
Для просмотра статистики используйте /stats.
Для получения отчёта используйте /report.""".format(username)

    )
    return ConversationHandler.END


async def add_income(update: Update, context: CallbackContext):
    context.user_data['type'] = 'income'
    await update.message.reply_text("Введите сумму дохода:")
    return AMOUNT


async def add_expense(update: Update, context: CallbackContext):
    context.user_data['type'] = 'expense'
    await update.message.reply_text("Введите сумму расхода:")
    return AMOUNT


async def handle_amount(update: Update, context: CallbackContext):
    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        await update.message.reply_text("Укажите категорию:")
        return CATEGORY
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return AMOUNT

async def handle_category(update: Update, context: CallbackContext):
    category = update.message.text
    user_id = update.effective_user.id
    transaction_type = context.user_data['type']
    cursor.execute(
        "INSERT INTO transactions (user_id, amount, category, type, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, context.user_data['amount'], category, transaction_type, datetime.now().isoformat())

    )

    conn.commit()
    await update.message.reply_text(f"{transaction_type.capitalize()} добавлен!")
    return ConversationHandler.END


async def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'income'", (user_id,))
    total_income = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE user_id = ? AND type = 'expense'", (user_id,))
    total_expense = cursor.fetchone()[0] or 0
    await update.message.reply_text(f"Ваши финансы:\nДоходы: {total_income}\nРасходы: {total_expense}")


async def report(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    cursor.execute("SELECT amount, category, type, date FROM transactions WHERE user_id = ?", (user_id,))
    transactions = cursor.fetchall()
    if not transactions:
        await update.message.reply_text("Нет транзакций.")
        return
    report_message = "Ваш отчет:\n"
    for amount, category, type, date in transactions:
        report_message += f"{type.capitalize()}: {amount} (Категория: {category}, Дата: {'%d/%m/%y'})\n"
    await update.message.reply_text(report_message)


def main():
    app = Application.builder().token(TG_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_income', add_income),
                      CommandHandler('add_expense', add_expense)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
