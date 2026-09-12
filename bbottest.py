import os
import telebot
import re
from datetime import datetime
import logging
from flask import Flask, request

# ===== ТОКЕН =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

# ===== СЕКРЕТНЫЙ КОД ДЛЯ ВЕБХУКА =====
# Придумай любой набор букв/цифр. Он будет в URL.
WEBHOOK_SECRET = "kofemofe_secret_2026"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# ===== ХРАНИЛИЩЕ =====
user_data = {}

# ===== ТЕКСТЫ =====
WELCOME = ("👋 Привет! Я бот для анализа отчетов.\n\n"
           "📝 Отправляйте мне сообщения с пополнениями и изъятиями.\n"
           "Когда закончите, отправьте команду: буххх\n\n"
           "Я соберу все данные и выдам полный отчет!")

NEW_DAY = "📅 Начинаем новый день!\nОтправляйте сообщения. Для отчета: буххх"
MESSAGE_SAVED = "✅ Сообщение сохранено!"
UNKNOWN = "❌ Не удалось распознать сообщение."
NO_DATA = "❌ Нет данных для отчета. Отправьте сначала пополнения и изъятия."
TRY_AGAIN = "\n\n📤 Отправьте буххх для нового отчета."

# ===== РАЗБИВКА ДЛИННЫХ СООБЩЕНИЙ =====
def split_message(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    parts, current = [], ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > max_length:
            parts.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        parts.append(current)
    return parts

def send_long_message(chat_id, text):
    parts = split_message(text)
    for i, part in enumerate(parts):
        if i == 0:
            bot.send_message(chat_id, part)
        else:
            bot.send_message(chat_id, f"📄 Продолжение {i+1}/{len(parts)}:\n\n{part}")

# ===== ПАРСИНГ =====
def parse_message(text):
    text_lower = text.lower()
    
    if 'итоговый остаток' in text_lower or 'остаток наличных' in text_lower:
        m = re.search(r'составляет\s*:?\s*([\d.,]+)', text)
        if m:
            return {'type': 'balance', 'amount': float(m.group(1).replace('.', '').replace(',', '')), 'raw': text}
    
    if 'приступил с кассой' in text_lower or 'приступил' in text_lower:
        return {'type': 'start', 'amount': 0, 'raw': text}
    
    if '✅' in text or 'пополнение' in text_lower:
        m = re.search(r'сумм[уе]?\s*:?\s*([\d.,]+)', text)
        if not m:
            m = re.search(r':\s*([\d.,]+)', text)
        if m:
            return {'type': 'income', 'amount': float(m.group(1).replace('.', '').replace(',', '')), 'raw': text}
    
    if '❌' in text or 'изъяти' in text_lower or 'выдано' in text_lower or 'запрос на изъятия' in text_lower:
        m = re.search(r'размер[еа]?\s*:?\s*([\d.,]+)', text)
        if not m:
            m = re.search(r':\s*([\d.,]+)', text)
        if m:
            return {'type': 'expense', 'amount': float(m.group(1).replace('.', '').replace(',', '')), 'raw': text}
    
    if 'закрытие смены' in text_lower or 'закрытие' in text_lower:
        return {'type': 'end', 'amount': 0, 'raw': text}
    
    return None

# ===== ГЕНЕРАЦИЯ ОТЧЕТА =====
def generate_report(user_id):
    if user_id not in user_data or not user_data[user_id]['messages']:
        return NO_DATA
    
    messages = user_data[user_id]['messages']
    income_messages, expense_messages = [], []
    start_message, end_message = None, None
    income_total, expense_total = 0, 0
    
    for msg in messages:
        msg = msg.replace('@Fuad_Nasrullayev', '').replace('@fuad_nasrullayev', '')
        parsed = parse_message(msg)
        if parsed:
            if parsed['type'] == 'income':
                income_messages.append(msg)
                income_total += parsed['amount']
            elif parsed['type'] == 'expense':
                expense_messages.append(msg)
                expense_total += parsed['amount']
            elif parsed['type'] == 'start':
                start_message = msg
            elif parsed['type'] == 'end':
                end_message = msg
    
    report_date = datetime.now().strftime('%d.%m.%Y')
    if start_message:
        d = re.search(r'(\d{2}\.\d{2}\.\d{4})', start_message)
        if d:
            report_date = d.group(1)
    
    report = ""
    
    # Начало
    if start_message:
        report += start_message + "\n\n"
    else:
        report += f"{report_date} - Приступил с кассой в сейфе\nНаличные - 0 сум\nКарта - 0\nВсего - 0 сум\n\n"
    
    # Пополнения
    report += f"Общая пополнение в сейфе наличных на сумму - {income_total:,.0f} сум\n"
    report += f"Общая пополнение карты на сумму - {income_total:,.0f} сум\n"
    report += f"Общая пополнение в сейфа в долларах - 0 $\n\n"
    for msg in income_messages:
        report += msg + "\n"
    
    # Изъятия
    report += f"\nОбщая изъятия денег из сейфа на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия наличных на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия из карты на сумму - 0\n"
    report += f"Общая изъятия из сейфа в долларах - 0 $\n\n"
    for msg in expense_messages:
        report += msg + "\n"
    
    # Конец
    if end_message:
        report += "\n" + end_message
    else:
        report += f"\n{report_date} - Приступил с кассой в сейфе\nНаличные - 0 сум\nКарта - 0\nВсего - 0 сум"
    
    report += TRY_AGAIN
    return report

# ===== ОБРАБОТЧИКИ =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_data[message.chat.id] = {'messages': []}
    bot.send_message(message.chat.id, WELCOME)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    text = message.text
    
    if user_id not in user_data:
        user_data[user_id] = {'messages': []}
    
    if text.lower().strip() == "буххх":
        send_long_message(user_id, generate_report(user_id))
        return
    
    if text.lower().strip() in ["новый день", "очистить"]:
        user_data[user_id] = {'messages': []}
        bot.reply_to(message, NEW_DAY)
        return
    
    parsed = parse_message(text)
    if parsed:
        user_data[user_id]['messages'].append(text)
        bot.reply_to(message, MESSAGE_SAVED)
    else:
        if ('общая пополнение' in text.lower() or 'общая изъятия' in text.lower() or
            'приступил с кассой' in text.lower() or 'закрытие смены' in text.lower()):
            user_data[user_id]['messages'].append(text)
            bot.reply_to(message, MESSAGE_SAVED)
        else:
            bot.reply_to(message, UNKNOWN)

# ===== ВЕБХУК =====
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Forbidden", 403

@app.route('/')
def index():
    return "Bot is running!", 200

# ===== ЗАПУСК =====
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
