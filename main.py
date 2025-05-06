from datetime import datetime
import locale
import matplotlib.pyplot as plt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from av import TG_TOKEN
from telebot import types
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, filters, CallbackContext, \
    Application
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, extract, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from calendar import month_name
import io

# Инициализация SQLAlchemy
Base = declarative_base()
engine = create_engine('sqlite:///finance.db')
Session = sessionmaker(bind=engine)
session = Session()
locale.setlocale(locale.LC_TIME, 'ru_RU')


# Определение моделей
class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    transactions = relationship("Transaction", back_populates="user")


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    amount = Column(Float)
    category = Column(String)
    type = Column(String)  # 'income' или 'expense'
    date = Column(Date)
    description = Column(String, nullable=True)

    user = relationship("User", back_populates="transactions")


# Создание таблиц
Base.metadata.create_all(engine)


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Добавляем пользователя в БД, если его нет
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id, username=username)
        session.add(user)
        session.commit()

    keyboard = [
        [InlineKeyboardButton("Добавить доход", callback_data='add_income')],
        [InlineKeyboardButton("Добавить расход", callback_data='add_expense')],
        [InlineKeyboardButton("Статистика", callback_data='stats')],
        [InlineKeyboardButton("Отчет за месяц", callback_data='report')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"""💰 *Финансовый трекер*

Привет, {username}! Я помогу тебе управлять финансами.

Выбери действие:""",
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == 'add_income':
        await add_income(update, context)
    elif query.data == 'add_expense':
        await add_expense(update, context)
    elif query.data == 'stats':
        await stats(update, context)
    elif query.data == 'report':
        await report(update, context)


async def add_income(update: Update, context: CallbackContext):
    context.user_data['transaction_type'] = 'income'
    await context.bot.send_message(update.callback_query.message.chat.id, "Введите сумму дохода:")
    context.user_data['waiting_for'] = 'amount'


async def add_expense(update: Update, context: CallbackContext):
    context.user_data['transaction_type'] = 'expense'
    await context.bot.send_message(update.callback_query.message.chat.id, "Введите сумму расхода:")
    context.user_data['waiting_for'] = 'amount'


async def handle_amount(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text

    try:
        amount = float(text)
        context.user_data['amount'] = amount
        await update.message.reply_text("Укажите категорию:")
        context.user_data['waiting_for'] = 'category'
    except ValueError:
        await update.message.reply_text("Ошибка! Введите число.")


async def handle_category(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    category = update.message.text
    amount = context.user_data['amount']
    transaction_type = context.user_data['transaction_type']

    # Сохраняем транзакцию
    user = session.query(User).filter_by(user_id=user_id).first()
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        category=category,
        type=transaction_type,
        date=datetime.now().date(),
        description=None
    )
    session.add(transaction)
    session.commit()

    await update.message.reply_text(
        f"✅ {'Доход' if transaction_type == 'income' else 'Расход'} на сумму {amount} руб. в категории '{category}' успешно добавлен!"
    )
    context.user_data.clear()


async def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    today = datetime.now().date()

    # Получаем статистику
    total_income = session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'income',
        extract('month', Transaction.date) == today.month
    ).scalar() or 0

    total_expenses = session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        extract('month', Transaction.date) == today.month
    ).scalar() or 0

    balance = total_income - total_expenses

    await context.bot.send_message(update.callback_query.message.chat.id, f"""📊 *Статистика за {month_name[today.month]}*

        Доходы: {total_income:.2f} руб.
        Расходы: {total_expenses:.2f} руб.
        Баланс: {balance:.2f} руб.""")


async def report(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    today = datetime.now().date()

    # Получаем данные для графика
    expenses = session.query(
        Transaction.category,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        extract('month', Transaction.date) == today.month
    ).group_by(Transaction.category).all()

    if not expenses:
        await update.message.reply_text("Нет данных о расходах за этот месяц.")
        return

    # Создаем график
    categories = [e[0] for e in expenses]
    amounts = [e[1] for e in expenses]

    plt.figure(figsize=(10, 6))
    plt.pie(amounts, labels=categories, autopct='%1.1f%%')
    plt.title(f"Расходы за {month_name[today.month]}")

    # Сохраняем график в буфер
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    # Отправляем график
    await context.bot.send_photo(update.callback_query.message.chat.id, photo=buf,
                                 caption=f"📈 Отчет по расходам за {month_name[today.month]}")


async def handle_message(update: Update, context: CallbackContext):
    if context.user_data.get('waiting_for') == 'amount':
        await handle_amount(update, context)
    elif context.user_data.get('waiting_for') == 'category':
        await handle_category(update, context)
    else:
        await start(update, context)


def main():
    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_income", add_income))
    app.add_handler(CommandHandler("add_expense", add_expense))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
