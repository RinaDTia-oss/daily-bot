import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReactionTypeEmoji
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import json
import os
from datetime import datetime
from random import choice

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
import os
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
COMMENT_GROUP_ID = int(os.getenv("COMMENT_GROUP_ID"))
DATA_FILE = "daily_planner_data.json"
# ==================

# Загрузка данных
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "tasks": [],
        "plans": [],
        "reactions": ["ты молодец", "здорово", "отлично справилась", "прекрасно!", "восхитительно", "горжусь тобой"]
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
user_tasks = data.get("tasks", [])
plans = data.get("plans", [])
reactions = data.get("reactions", [])

def save():
    data["tasks"] = user_tasks
    data["plans"] = plans
    save_data(data)

# Смайлики
PRIORITIES = {
    "critical": "🔥",
    "high_month_year": "🐉",
    "high_week": "🦎",
    "high_day": "🐍",
    "low": "👽"
}
STATUSES = {
    "done": "💋",
    "partial": "😘",
    "bonus": "🥰",
    "failed_high": "🤦‍♀️",
    "failed_low": "🕸"
}

# Теги
TAGS = {
    "year": "#годичные_кольца",
    "month": "#вышел_месяц",
    "week": "#трусы_неделька"
}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я твой бот-ежедневник. Используй /plan, чтобы составить план, /add_a_task, чтобы добавить задачу, и /report, чтобы составить отчёт.")

# /add_a_task <задача>
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_text = ' '.join(context.args)
    if not task_text:
        await update.message.reply_text("Пожалуйста, укажи задачу. Пример: /add_a_task Попить воды")
        return
    if task_text in user_tasks:
        await update.message.reply_text("Такая задача уже есть в списке.")
    else:
        user_tasks.append(task_text)
        save()
        await update.message.reply_text(f"Задача добавлена: {task_text}")

# /plan
async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Год", callback_data="plan_year")],
        [InlineKeyboardButton("Месяц", callback_data="plan_month")],
        [InlineKeyboardButton("Неделя", callback_data="plan_week")],
        [InlineKeyboardButton("День", callback_data="plan_day")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("На какой период составить план?", reply_markup=reply_markup)

# Выбор периода
async def plan_choose_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    period = query.data.split("_")[1]
    context.user_data['plan_period'] = period
    context.user_data['plan_tasks'] = []
    context.user_data['current_task_index'] = 0
    await show_add_task_menu(query, context)

# Меню добавления задач
async def show_add_task_menu(destination, context: ContextTypes.DEFAULT_TYPE):
    period = context.user_data['plan_period']
    tasks = context.user_data['plan_tasks']
    keyboard = []

    for task in tasks:
        keyboard.append([InlineKeyboardButton(f"📋 {task['text']}", callback_data="noop")])

    if period == "day":
        for i, task in enumerate(user_tasks):
            if task not in [t['text'] for t in tasks]:
                keyboard.append([InlineKeyboardButton(f"✅ {task}", callback_data=f"select_task_{i}")])

    keyboard.append([InlineKeyboardButton("➕ Добавить свою", callback_data="manual_task")])
    if tasks:
        keyboard.append([InlineKeyboardButton("✅ Готово", callback_data="finish_selecting_tasks")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Добавь задачи. Когда закончишь — нажми «Готово»."
    if hasattr(destination, 'edit_message_text'):
        await destination.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await destination.reply_text(text=text, reply_markup=reply_markup)

# Выбор задачи из списка (для дня)
async def select_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task_idx = int(query.data.split("_")[2])
    task_text = user_tasks[task_idx]
    if task_text not in [t['text'] for t in context.user_data['plan_tasks']]:
        context.user_data['plan_tasks'].append({"text": task_text, "priority": None, "deadline": None})
    await show_add_task_menu(query, context)

# Ручной ввод задачи
async def manual_task_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Напиши задачу:")
    context.user_data['awaiting_task'] = True

# Получение вручную введённой задачи
async def receive_manual_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_task'):
        return
    task_text = update.message.text.strip()
    if task_text:
        context.user_data['plan_tasks'].append({"text": task_text, "priority": None, "deadline": None})
    context.user_data['awaiting_task'] = False
    await show_add_task_menu(update.message, context)

# Завершить выбор задач → перейти к приоритетам
async def finish_selecting_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data['plan_tasks']:
        await query.edit_message_text("Ты не добавил ни одной задачи.")
        return
    context.user_data['current_task_index'] = 0
    await show_priority_menu(query, context)

# Показать меню приоритетов
async def show_priority_menu(destination, context: ContextTypes.DEFAULT_TYPE):
    tasks = context.user_data['plan_tasks']
    idx = context.user_data['current_task_index']
    if idx >= len(tasks):
        await finalize_plan(destination, context)
        return

    task = tasks[idx]
    period = context.user_data['plan_period']
    keyboard = []

    if period == "day":
        keyboard.append([InlineKeyboardButton("🔥 Горящий", callback_data="pri_critical")])
        keyboard.append([InlineKeyboardButton("🐍 Высокий", callback_data="pri_high")])
        keyboard.append([InlineKeyboardButton("👽 Низкий", callback_data="pri_low")])
    elif period == "week":
        keyboard.append([InlineKeyboardButton("🔥 Горящий", callback_data="pri_critical")])
        keyboard.append([InlineKeyboardButton("🦎 Высокий", callback_data="pri_high")])
        keyboard.append([InlineKeyboardButton("👽 Низкий", callback_data="pri_low")])
    else:
        keyboard.append([InlineKeyboardButton("🔥 Горящий", callback_data="pri_critical")])
        keyboard.append([InlineKeyboardButton("🐉 Высокий", callback_data="pri_high")])
        keyboard.append([InlineKeyboardButton("👽 Низкий", callback_data="pri_low")])

    keyboard.append([InlineKeyboardButton("Пропустить", callback_data="pri_skip")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Задача {idx + 1} из {len(tasks)}:\n\n{task['text']}\n\nВыбери приоритет:"
    if hasattr(destination, 'edit_message_text'):
        await destination.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await destination.reply_text(text=text, reply_markup=reply_markup)

# Установка приоритета
async def set_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pri = query.data.split("_")[1]
    idx = context.user_data['current_task_index']
    task = context.user_data['plan_tasks'][idx]
    period = context.user_data['plan_period']

    task["priority"] = "low"
    task["icon"] = PRIORITIES["low"]

    if pri == "critical":
        task["priority"] = "critical"
        task["icon"] = PRIORITIES["critical"]
        if period == "day":
            await query.edit_message_text("До какого времени дедлайн? Напиши, например: 15:00")
        else:
            await query.edit_message_text("В какой день недели дедлайн? Напиши: Понедельник, Вторник и т.д.")
        context.user_data['awaiting_deadline'] = True
        return
    elif pri == "high":
        task["priority"] = "high"
        if period == "day":
            task["icon"] = PRIORITIES["high_day"]
        elif period == "week":
            task["icon"] = PRIORITIES["high_week"]
        else:
            task["icon"] = PRIORITIES["high_month_year"]
    elif pri == "skip":
        pass  # уже по умолчанию low

    context.user_data['current_task_index'] += 1
    await show_priority_menu(query, context)

# Получение дедлайна
async def receive_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_deadline'):
        return
    deadline = update.message.text.strip()
    idx = context.user_data['current_task_index']
    task = context.user_data['plan_tasks'][idx]
    task["deadline"] = deadline
    context.user_data['current_task_index'] += 1
    context.user_data['awaiting_deadline'] = False
    await show_priority_menu(update.message, context)

# Финализация плана
async def finalize_plan(destination, context: ContextTypes.DEFAULT_TYPE):
    period = context.user_data['plan_period']
    tasks = context.user_data['plan_tasks']
    tag = TAGS.get(period, "")
    header = f"📅 План на {period}"
    if tag:
        header += f" {tag}"
    body = []
    for task in tasks:
        line = f"{task['icon']} {task['text']}"
        if task.get("deadline"):
            line += f" ⏰ {task['deadline']}"
        body.append(line)
    full_text = header + "\n\n" + "\n".join(body)

    try:
        sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=full_text)
        plan_id = sent.message_id
        plans.append({
            "id": plan_id,
            "period": period,
            "tasks": tasks,
            "date": datetime.now().isoformat(),
            "type": "plan"
        })
        save()
        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text("✅ План опубликован в канале!")
        else:
            await destination.reply_text("✅ План опубликован в канале!")
    except Exception as e:
        logger.error(e)
        await destination.edit_message_text("❌ Не удалось опубликовать в канал.")

# /report
async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    available = [p for p in plans if p["type"] == "plan"]
    if not available:
        await update.message.reply_text("Нет планов для отчёта.")
        return

    keyboard = []
    periods = ["year", "month", "week", "day"]
    for period in periods:
        latest = next((p for p in reversed(available) if p["period"] == period), None)
        if latest:
            date_str = datetime.fromisoformat(latest["date"]).strftime("%d.%m.%Y")
            keyboard.append([InlineKeyboardButton(f"{period.capitalize()} ({date_str})", callback_data=f"report_{latest['id']}")])

    if not keyboard:
        await update.message.reply_text("Нет доступных планов.")
        return

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери план для отчёта:", reply_markup=reply_markup)

# Начало отчёта
async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[1])
    plan = next((p for p in plans if p["id"] == plan_id), None)
    if not plan:
        await query.edit_message_text("План не найден.")
        return

    context.user_data['report_plan'] = plan
    context.user_data['report_results'] = {}
    context.user_data['bonus_tasks'] = []
    context.user_data['report_task_index'] = 0
    await show_report_task(query, context)

# Показать задачу для отчёта
async def show_report_task(destination, context: ContextTypes.DEFAULT_TYPE):
    plan = context.user_data['report_plan']
    idx = context.user_data['report_task_index']
    tasks = plan['tasks']

    if idx >= len(tasks):
        keyboard = [
            [InlineKeyboardButton("➕ Добавить достижение", callback_data="add_bonus")],
            [InlineKeyboardButton("📤 Отправить отчёт", callback_data="send_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Все задачи оценены! 🎉\n\nХочешь добавить, что сделала сверх плана?"
        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text(text=text, reply_markup=reply_markup)
        else:
            await destination.reply_text(text=text, reply_markup=reply_markup)
        return

    task = tasks[idx]
    keyboard = [
        [InlineKeyboardButton("💋 Выполнена", callback_data="status_done")],
        [InlineKeyboardButton("😘 Частично", callback_data="status_partial")],
        [InlineKeyboardButton("🤦‍♀️ Не сделана (высокий)", callback_data="status_failed_high")],
        [InlineKeyboardButton("🕸 Не сделана (низкий)", callback_data="status_failed_low")],
        [InlineKeyboardButton("Пропустить", callback_data="status_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Задача {idx + 1} из {len(tasks)}:\n\n{task['text']}\n\nКак прошла?"
    if hasattr(destination, 'edit_message_text'):
        await destination.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await destination.reply_text(text=text, reply_markup=reply_markup)

# Установка статуса
async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    status = query.data.split("_")[1]
    idx = context.user_data['report_task_index']
    plan = context.user_data['report_plan']
    task = plan['tasks'][idx]

    result = {"task": task, "status": status}
    context.user_data['report_results'][idx] = result
    context.user_data['report_task_index'] += 1
    await show_report_task(query, context)

# Добавить бонус
async def add_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Напиши, что сделала крутое, чего не было в плане:")
    context.user_data['awaiting_bonus'] = True

# Получение бонусной задачи
async def receive_bonus_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_bonus'):
        return
    task_text = update.message.text.strip()
    if task_text:
        bonus_task = {"text": task_text, "icon": "🥰", "priority": "bonus"}
        context.user_data['bonus_tasks'].append({"task": bonus_task, "status": "bonus"})
    context.user_data['awaiting_bonus'] = False

    keyboard = [
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="add_bonus")],
        [InlineKeyboardButton("📤 Отправить отчёт", callback_data="send_report")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Отлично! Что-то ещё?", reply_markup=reply_markup)

# Отправить отчёт
async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await finalize_report(query, context)

# Финализация отчёта
async def finalize_report(destination, context: ContextTypes.DEFAULT_TYPE):
    plan = context.user_data['report_plan']
    results = context.user_data['report_results']
    bonus_tasks = context.user_data['bonus_tasks']
    period = plan['period']
    header = f"📊 Отчёт по плану на {period}"

    body = ["📋 Задачи из плана:"]
    stats = {"done": 0, "partial": 0, "failed": 0}

    for i, task in enumerate(plan['tasks']):
        res = results.get(i)
        if res is None:
            priority = task.get("priority", "low")
            if priority in ["critical", "high"]:
                icon = "🤦‍♀️"
                stats["failed"] += 1
            else:
                icon = "🕸"
                stats["failed"] += 1
            line = f"{icon} {task['text']}"
        else:
            status = res['status']
            if status == "done":
                line = f"💋 {task['text']}"
                stats["done"] += 1
            elif status == "partial":
                line = f"😘 {task['text']}"
                stats["partial"] += 1
            elif status == "failed_high":
                line = f"🤦‍♀️ {task['text']}"
                stats["failed"] += 1
            elif status == "failed_low":
                line = f"🕸 {task['text']}"
                stats["failed"] += 1
            else:
                priority = task.get("priority", "low")
                icon = "🤦‍♀️" if priority in ["critical", "high"] else "🕸"
                line = f"{icon} {task['text']}"
                stats["failed"] += 1
        body.append(line)

    if bonus_tasks:
        body.append("\n🎁 Дополнительно:")
        for b in bonus_tasks:
            if isinstance(b.get('task'), dict):
                body.append(f"🥰 {b['task']['text']}")

    total = stats["done"] + stats["partial"] + stats["failed"]
    success_rate = (stats["done"] + stats["partial"]) / total * 100 if total > 0 else 0

    encouragements = [
        "Ты молодец! Так держать! 🌟",
        "Отличная работа! Я тобой горжусь! 💖",
        "Вау, как здорово! Продолжай в том же духе! 🚀",
        "Ты справилась лучше всех! 💪",
        "Ты — суперзвезда! ✨"
    ]
    encouragement = choice(encouragements)

    full_text = f"{header}\n\n" + "\n".join(body)
    full_text += f"\n\n✅ Выполнено: {stats['done']}\n🔄 Частично: {stats['partial']}\n❌ Не сделано: {stats['failed']}\n\nУспехов: {success_rate:.1f}%\n\n{encouragement}"

    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=full_text)
        plans.append({
            "id": "report_" + str(len(plans)),
            "period": period,
            "date": datetime.now().isoformat(),
            "type": "report",
            "content": full_text
        })
        save()
        if hasattr(destination, 'edit_message_text'):
            await destination.edit_message_text("✅ Отчёт отправлен в канал!")
        else:
            await destination.reply_text("✅ Отчёт отправлен в канал!")
    except Exception as e:
        logger.error(e)
        await destination.edit_message_text("❌ Не удалось отправить отчёт.")

# Обработка постов в группе с "хвалюсь"
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    
    # Логируем ВСЕ доступные данные о сообщении
    logger.info("=== НОВОЕ СООБЩЕНИЕ ===")
    logger.info(f"message.text: {message.text}")
    logger.info(f"message.caption: {message.caption}")
    logger.info(f"message.photo: {message.photo}")
    logger.info(f"message.media_group_id: {message.media_group_id}")
    
    # Проверяем, есть ли фото и подпись
    has_photo = bool(message.photo)
    has_caption = bool(message.caption)
    
    logger.info(f"Содержит фото: {has_photo}")
    logger.info(f"Содержит подпись: {has_caption}")
    
    # Собираем текст из всех возможных источников
    text = ""
    if message.text:
        text = message.text.lower()
        logger.info("Используем message.text")
    elif message.caption:
        text = message.caption.lower()
        logger.info("Используем message.caption")
    else:
        logger.info("Текст не найден ни в одном источнике")
    
    # Проверяем наличие слова "хвалюсь"
    has_boast = "хвалюсь" in text if text else False
    logger.info(f"Содержит 'хвалюсь': {has_boast}")
    
    # Если нашли слово "хвалюсь" — ставим реакцию
    if has_boast:
        try:
            await context.bot.set_message_reaction(
                chat_id=message.chat_id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(emoji="👍")]
            )
            await message.reply_text(choice(reactions))
            logger.info("✅ Реакция и комментарий добавлены успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка при реакции: {e}")
    else:
        logger.info("❌ Слово 'хвалюсь' не найдено")

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_a_task", add_task))
    application.add_handler(CommandHandler("plan", plan_start))
    application.add_handler(CommandHandler("report", report_start))

    application.add_handler(CallbackQueryHandler(plan_choose_period, pattern=r"^plan_"))
    application.add_handler(CallbackQueryHandler(select_task, pattern=r"^select_task_"))
    application.add_handler(CallbackQueryHandler(manual_task_prompt, pattern=r"^manual_task$"))
    application.add_handler(CallbackQueryHandler(finish_selecting_tasks, pattern=r"^finish_selecting_tasks$"))
    application.add_handler(CallbackQueryHandler(set_priority, pattern=r"^pri_"))
    application.add_handler(CallbackQueryHandler(start_report, pattern=r"^report_"))
    application.add_handler(CallbackQueryHandler(set_status, pattern=r"^status_"))
    application.add_handler(CallbackQueryHandler(add_bonus, pattern=r"^add_bonus$"))
    application.add_handler(CallbackQueryHandler(send_report, pattern=r"^send_report$"))

    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, receive_manual_task), group=0)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, receive_deadline), group=1)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, receive_bonus_task), group=3)

    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(chat_id=COMMENT_GROUP_ID), handle_group_message))

    application.run_polling()

if __name__ == '__main__':
    main()
