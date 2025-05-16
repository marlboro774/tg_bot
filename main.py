import os
import matplotlib.pyplot as plt
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler
from av import TG_TOKEN
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, func
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Инициализация SQLAlchemy
Base = declarative_base()
engine = create_engine('sqlite:///finance.db', echo=False)
Session = sessionmaker(bind=engine)
session = Session()


# Модели данных
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
    date = Column(String)
    user = relationship("User", back_populates="transactions")


# Создание таблиц
Base.metadata.create_all(engine)

AMOUNT, CATEGORY = range(2)

# Категории для выбора
FOOD = ['Еда']
TRANSP = ['Транспорт']
RAZVL = ['Развлечения']
ZARPLATA = ['Зарплата']
MORE = ['Другое']


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu


def create_main_keyboard():
    button_list = [
        KeyboardButton('добавить доход'),
        KeyboardButton('добавить расход'),
        KeyboardButton('статистика'),
        KeyboardButton('отчёт'),
        KeyboardButton('сброс')
    ]
    return ReplyKeyboardMarkup(build_menu(button_list, n_cols=2), resize_keyboard=True)


async def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Проверяем существование пользователя
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        user = User(user_id=user_id, username=username)
        session.add(user)
        session.commit()

    await update.message.reply_text(
        f"Привет, {username}! Я бот для учёта финансов. Выберите команду:",
        reply_markup=create_main_keyboard()
    )
    return ConversationHandler.END


async def add_income(update: Update, context: CallbackContext):
    context.user_data['type'] = 'доход'
    await update.message.reply_text("Введите сумму дохода:",
                                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]],
                                                                     resize_keyboard=True))
    return AMOUNT


async def add_expense(update: Update, context: CallbackContext):
    context.user_data['type'] = 'расход'
    await update.message.reply_text("Введите сумму расхода:",
                                    reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]],
                                                                     resize_keyboard=True))
    return AMOUNT


async def handle_amount(update: Update, context: CallbackContext):
    if update.message.text == "Отмена":
        await update.message.reply_text("Действие отменено.", reply_markup=create_main_keyboard())
        return ConversationHandler.END

    try:
        amount = float(update.message.text)
        context.user_data['amount'] = amount
        keyboard = [FOOD, TRANSP, RAZVL, ZARPLATA, MORE]
        reply_markup = ReplyKeyboardMarkup(
            build_menu([KeyboardButton(cat[0]) for cat in keyboard], n_cols=3),
            one_time_keyboard=True
        )
        await update.message.reply_text(
            "Выберите категорию с помощью кнопок или напишите свою:",
            reply_markup=reply_markup
        )
        return CATEGORY
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите число.",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Отмена")]], resize_keyboard=True)
        )
        return AMOUNT


async def handle_category(update: Update, context: CallbackContext):
    category = update.message.text
    user_id = update.effective_user.id
    transaction_type = context.user_data['type']
    amount = context.user_data['amount']

    # Находим пользователя
    user = session.query(User).filter_by(user_id=user_id).first()
    if not user:
        await update.message.reply_text("Ошибка: пользователь не найден.", reply_markup=create_main_keyboard())
        return ConversationHandler.END

    # Создаем транзакцию
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        category=category,
        type=transaction_type,
        date=datetime.now().strftime('%d/%m/%y')
    )

    session.add(transaction)
    session.commit()

    await update.message.reply_text(
        f"{transaction_type.capitalize()} добавлен!",
        reply_markup=create_main_keyboard()
    )
    return ConversationHandler.END


async def stats(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    total_income = session.query(
        func.sum(Transaction.amount)
    ).filter_by(
        user_id=user_id,
        type='доход'
    ).scalar() or 0

    total_expense = session.query(
        func.sum(Transaction.amount)
    ).filter_by(
        user_id=user_id,
        type='расход'
    ).scalar() or 0

    await update.message.reply_text(
        f"Ваши финансы:\nДоходы: {total_income}\nРасходы: {total_expense}",
        reply_markup=create_main_keyboard()
    )


async def report(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    transactions = session.query(Transaction).filter_by(user_id=user_id).all()

    if not transactions:
        await update.message.reply_text("Нет транзакций.", reply_markup=create_main_keyboard())
        return

    categories = {}
    for t in transactions:
        if t.type.strip().lower() == 'расход':
            categories[t.category] = categories.get(t.category, 0) + abs(t.amount)

    if not categories:
        await update.message.reply_text("Нет расходов для отчёта.", reply_markup=create_main_keyboard())
        return

    # Настройка шрифтов
    plt.rcParams.update({'font.size': 14})
    plt.figure(figsize=(14, 8))

    # Создание гистограммы (подписи значений убраны)
    plt.barh(
        list(categories.keys()),
        list(categories.values()),
        color='skyblue',
        height=0.7
    )

    # Оформление
    plt.xlabel('Сумма', fontsize=16)
    plt.ylabel('Категории', fontsize=16)
    plt.title('Распределение расходов по категориям', fontsize=18, pad=20)
    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.tight_layout()

    # Сохранение и отправка
    filename = f"report_{user_id}.png"
    plt.savefig(filename, bbox_inches='tight')
    plt.close()

    await update.message.reply_photo(
        photo=open(filename, 'rb'),
        caption="Ваш отчёт:",
        reply_markup=create_main_keyboard()
    )

    os.remove(filename)


async def reset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    session.query(Transaction).filter_by(user_id=user_id).delete()
    session.commit()

    await update.message.reply_text(
        "Ваши данные о финансах были сброшены.",
        reply_markup=create_main_keyboard()
    )


def main():
    app = Application.builder().token(TG_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Обработчики кнопок внутри ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Text(["добавить доход"]), add_income),
            MessageHandler(filters.Text(["добавить расход"]), add_expense)
        ],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )
    app.add_handler(conv_handler)

    # Обработчики остальных кнопок
    app.add_handler(MessageHandler(filters.Text(["статистика"]), stats))
    app.add_handler(MessageHandler(filters.Text(["отчёт"]), report))
    app.add_handler(MessageHandler(filters.Text(["сброс"]), reset))

    app.run_polling()


if __name__ == "__main__":
    main()