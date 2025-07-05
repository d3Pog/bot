from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes, CallbackContext, JobQueue
)
import datetime

# Этапы
(MAIN_MENU, COUNTRY, MARKA, DRIVE, FUEL, YEAR, MILEAGE, DAMAGE, BUDGET, CITY,
 CONTACT, PHONE_REQUEST, CONFIRM, EDIT_SELECT) = range(14)

# Чаты
MANAGER_JAPAN_CHINA_ID = 1054391474
MANAGER_KOREA_UAE_ID = 569926688
GROUP_CHAT_ID = -4985828342

step_names = {
    COUNTRY: "Страна",
    MARKA: "Марка",
    DRIVE: "Привод",
    FUEL: "Топливо",
    YEAR: "Год",
    MILEAGE: "Пробег",
    DAMAGE: "Состояние",
    BUDGET: "Бюджет",
    CITY: "Город",
    CONTACT: "Связь",
    PHONE_REQUEST: "Номер телефона"
}

step_prompts = {
    COUNTRY: ("🌍 Из какой страны вы хотите авто?", ["🇰🇷 Южная Корея", "🇯🇵 Япония", "🇨🇳 Китай", "🇦🇪 ОАЭ"]),
    MARKA: ("1️⃣ Какая марка и модель интересует? (например, Toyota Prius)", []),
    DRIVE: ("2️⃣ Привод?", ["🚙 2WD", "🛞 4WD"]),
    FUEL: ("3️⃣ Топливо?", ["⛽ Бензин", "🛢️ Дизель", "🔋 Гибрид", "⚡ Электро"]),
    YEAR: ("4️⃣ Год выпуска от (например, 2021)", []),
    MILEAGE: ("5️⃣ Пробег (например, до 100000 км)", []),
    DAMAGE: ("6️⃣ Состояние:", ["✅ Без ДТП", "🛠 Незначительные повреждения", "🤷 Не важно"]),
    BUDGET: ("7️⃣ Бюджет под ключ (Какой у вас бюджет?)", []),
    CITY: ("8️⃣ Город доставки:", []),
    CONTACT: ("9️⃣ Как связаться с вами?", ["💬 Telegram", "📱 WhatsApp", "📞 Звонок"]),
    PHONE_REQUEST: ("📞 Пожалуйста, нажмите кнопку ниже, чтобы отправить номер телефона:", [])
}

def make_keyboard(options, include_back=True):
    buttons = [[opt] for opt in options]
    if include_back:
        buttons.append(["⬅️ Назад"])
    buttons.append(["🏠 Главное меню"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

def phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Отправить номер телефона", request_contact=True)], ["🏠 Главное меню"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        ["📝 Оставить заявку"],
        ["ℹ️ О компании", "📞 Контакты"]
    ], resize_keyboard=True, one_time_keyboard=True)

async def remind_incomplete(context: CallbackContext):
    chat_id = context.job.chat_id
    user_data = context.application.user_data.get(chat_id, {})
    if not user_data.get("completed"):
        await context.bot.send_message(
            chat_id=chat_id,
            text="👋 Вы начали заполнять заявку, но не закончили. Хотите продолжить?",
            reply_markup=make_keyboard(["✅ Продолжить"], include_back=False)
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["started_at"] = datetime.datetime.now()
    context.user_data["completed"] = False

    context.job_queue.run_once(
        remind_incomplete,
        when=86400,
        chat_id=update.effective_chat.id,
        name=f"reminder_{update.effective_chat.id}"
    )

    await update.message.reply_text(
        "Добро пожаловать в DemMax 🚗\nВыберите действие:",
        reply_markup=main_menu_keyboard()
    )
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📝 Оставить заявку":
        return await ask_question(update, context, COUNTRY)
    elif text == "✅ Продолжить":
        incomplete_steps = [s for s in step_names if step_names[s] not in context.user_data]
        return await ask_question(update, context, incomplete_steps[0]) if incomplete_steps else await review_application(update, context)
    elif text == "ℹ️ О компании":
        await update.message.reply_text("DemMax — доставка авто из Японии, Кореи, Китая и ОАЭ.")
        return MAIN_MENU
    elif text == "📞 Контакты":
        await update.message.reply_text("📞 +7 924 836-20-30\n🌐 https://dem-max.ru")
        return MAIN_MENU
    elif text == "🏠 Главное меню":
        return await start(update, context)
    else:
        return await start(update, context)

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE, step):
    prompt, options = step_prompts.get(step, ("Введите значение:", []))
    include_back = step != COUNTRY
    if step == PHONE_REQUEST:
        await update.message.reply_text(prompt, reply_markup=phone_keyboard())
    else:
        await update.message.reply_text(prompt, reply_markup=make_keyboard(options, include_back))
    return step

async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE, step):
    text = update.message.text
    if text == "⬅️ Назад":
        prev_step = step - 1
        return await ask_question(update, context, prev_step)
    elif text == "🏠 Главное меню":
        return await start(update, context)

    context.user_data[step_names[step]] = text

    if step == CONTACT:
        return await ask_question(update, context, PHONE_REQUEST)

    if step == PHONE_REQUEST:
        return await review_application(update, context)

    if context.user_data.get("_editing"):
        context.user_data.pop("_editing")
        return await review_application(update, context)

    return await ask_question(update, context, step + 1)

async def phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.effective_message.contact
    if contact and contact.phone_number:
        context.user_data["Номер телефона"] = contact.phone_number
    else:
        await update.message.reply_text("Пожалуйста, нажмите кнопку для отправки номера.")
        return PHONE_REQUEST

    if context.user_data.get("_editing"):
        context.user_data.pop("_editing")
    return await review_application(update, context)

async def review_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = "\n".join([
        f"📍 {step_names[s]}: {context.user_data.get(step_names[s])}"
        for s in step_names
        if step_names[s] in context.user_data
    ])
    await update.message.reply_text(
        f"🧾 Проверь, всё верно:\n\n{summary}",
        reply_markup=make_keyboard(["✅ Отправить заявку", "🔄 Изменить"])
    )
    return CONFIRM

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "🔄 Изменить":
        await update.message.reply_text(
            "Что вы хотите изменить?",
            reply_markup=make_keyboard(list(step_names.values()), include_back=False)
        )
        return EDIT_SELECT
    elif choice == "✅ Отправить заявку":
        context.user_data["completed"] = True
        user = update.effective_user
        context.user_data["Telegram"] = f"@{user.username}" if user.username else f"ID: {user.id}"

        full_text = f"🕒 Время: {context.user_data.get('started_at')}\n"
        full_text += "\n".join([
            f"📍 {step_names[s]}: {context.user_data.get(step_names[s])}"
            for s in step_names
            if step_names[s] in context.user_data
        ])
        full_text += f"\n📨 Telegram: {context.user_data['Telegram']}"

        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"📩 Новая заявка:\n{full_text}")
        if context.user_data["Страна"] in ["🇯🇵 Япония", "🇨🇳 Китай"]:
            await context.bot.send_message(chat_id=MANAGER_JAPAN_CHINA_ID, text=f"📩 Новая заявка:\n{full_text}")
        else:
            await context.bot.send_message(chat_id=MANAGER_KOREA_UAE_ID, text=f"📩 Новая заявка:\n{full_text}")

        await update.message.reply_text("🔥 Заявка принята! Мы свяжемся с вами в ближайшее время.", reply_markup=main_menu_keyboard())
        return MAIN_MENU
    return CONFIRM

async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field_name = update.message.text
    for step, name in step_names.items():
        if name == field_name:
            context.user_data.pop(name, None)
            context.user_data["_editing"] = True
            return await ask_question(update, context, step)
    await update.message.reply_text("Поле не найдено.")
    return EDIT_SELECT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return MAIN_MENU

def main():
    app = Application.builder().token("7879339836:AAG7qEivcsB3DzzO6MvapdRfmY8ryFWRUFM").build()
    app.job_queue.set_application(app)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, COUNTRY))],
            MARKA: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, MARKA))],
            DRIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, DRIVE))],
            FUEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, FUEL))],
            YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, YEAR))],
            MILEAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, MILEAGE))],
            DAMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, DAMAGE))],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, BUDGET))],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, CITY))],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_step(u, c, CONTACT))],
            PHONE_REQUEST: [MessageHandler(filters.CONTACT, phone_input)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
            EDIT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_select)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
