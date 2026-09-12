import os
import telebot
from telebot import types
import re
from datetime import datetime
import logging
from flask import Flask
import threading

# ===== ТОКЕН ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

bot = telebot.TeleBot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# ===== ХРАНИЛИЩЕ =====
user_data = {}

# ===== ТЕКСТЫ =====
WELCOME = ("👋 Привет! Я бот для анализа отчетов.\n\n"
           "📝 Отправляйте мне сообщения с пополнениями и изъятиями.\n"
           "Когда закончите, отправьте команду:\n"
           "`буххх`\n\n"
           "Я соберу все данные и выдам полный отчет!")

NEW_DAY = ("📅 Начинаем новый день!\n"
           "Отправляйте мне сообщения с пополнениями и изъятиями.\n"
           "Для отчета отправьте: буххх")

MESSAGE_SAVED = "✅ Сообщение сохранено!"

UNKNOWN = ("❌ Не удалось распознать сообщение.\n"
           "Примеры:\n"
           "✅ Пополнение сейфа из филиала НТД на сумму : 530.000 сум\n"
           "❌ Изъятие 25.000 сум на дорожные расходы")

NO_DATA = ("❌ Нет данных для отчета.\n"
           "Отправьте сначала пополнения и изъятия.")

TRY_AGAIN = ("\n\n📤 Отправьте буххх для нового отчета.\n"
             "Или новый день для очистки данных.")

# ===== ФУНКЦИЯ РАЗБИВКИ ДЛИННОГО СООБЩЕНИЯ =====
def split_message(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    
    parts = []
    lines = text.split('\n')
    current_part = ""
    
    for line in lines:
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line + "\n"
        else:
            current_part += line + "\n"
    
    if current_part:
        parts.append(current_part)
    
    return parts

def send_long_message(chat_id, text):
    parts = split_message(text)
    for i, part in enumerate(parts):
        if i == 0:
            bot.send_message(chat_id, part)
        else:
            bot.send_message(chat_id, f"📄 Продолжение {i+1}/{len(parts)}:\n\n{part}")

# ===== ФУНКЦИЯ ПАРСИНГА =====
def parse_message(text):
    result = None
    text_lower = text.lower()
    
    # Итоговый остаток
    if 'итоговый остаток' in text_lower or 'остаток наличных' in text_lower:
        amount_match = re.search(r'составляет\s*:?\s*([\d.,]+)', text)
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            result = {'type': 'balance', 'category': 'Остаток', 'amount': amount, 'raw': text}
            return result
    
    # Приступил с кассой
    if 'приступил с кассой' in text_lower or 'приступил' in text_lower:
        result = {'type': 'start', 'category': 'Начало', 'amount': 0, 'raw': text}
        return result
    
    # Пополнение
    if '✅' in text or 'пополнение' in text_lower or 'Пополнение' in text:
        amount_match = re.search(r'сумм[уе]?\s*:?\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r':\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r'([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:сум|so\'m)', text)
        
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            
            result = {'type': 'income', 'category': 'Пополнение', 'amount': amount, 'raw': text}
            return result
    
    # Изъятие
    if ('❌' in text or 
        'изъяти' in text_lower or
        'выдано' in text_lower or
        'запрос на изъятия' in text_lower):
        
        amount_match = re.search(r'размер[еа]?\s*:?\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r':\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r'([\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:сум|so\'m)', text)
        
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            
            result = {'type': 'expense', 'category': 'Изъятие', 'amount': amount, 'raw': text}
            return result
    
    # Закрытие смены
    if 'закрытие смены' in text_lower or 'закрытие' in text_lower:
        result = {'type': 'end', 'category': 'Конец', 'amount': 0, 'raw': text}
        return result
    
    return None

# ===== ФУНКЦИЯ ГЕНЕРАЦИИ ОТЧЕТА =====
def generate_report(user_id):
    if user_id not in user_data or not user_data[user_id]['messages']:
        return NO_DATA
    
    data = user_data[user_id]
    messages = data['messages']
    
    income_messages = []
    expense_messages = []
    start_message = None
    end_message = None
    
    income_total = 0
    expense_total = 0
    
    for msg in messages:
        # Убираем @Fuad_Nasrullayev
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
    
    # Определяем дату
    report_date = datetime.now().strftime('%d.%m.%Y')
    if start_message:
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', start_message)
        if date_match:
            report_date = date_match.group(1)
    
    # ===== ФОРМИРУЕМ ОТЧЕТ =====
    report = ""
    
    # 1. Начало смены
    if start_message:
        report += start_message + "\n\n"
    else:
        report += f"{report_date} - Приступил с кассой в сейфе\n"
        report += f"Наличные - 0 сум\n"
        report += f"Карта - 0\n"
        report += f"Всего - 0 сум\n\n"
    
    # 2. Общая пополнение
    report += f"Общая пополнение в сейфе наличных на сумму - {income_total:,.0f} сум\n"
    report += f"Общая пополнение карты на сумму - {income_total:,.0f} сум\n"
    report += f"Общая пополнение в сейфа в долларах - 0 $\n\n"
    
    # 3. Все пополнения
    for msg in income_messages:
        report += msg + "\n"
    
    # 4. Общая изъятия
    report += f"\nОбщая изъятия денег из сейфа на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия наличных на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия из карты на сумму - 0\n"
    report += f"Общая изъятия из сейфа в долларах - 0 $\n\n"
    
    # 5. Все изъятия
    for msg in expense_messages:
        report += msg + "\n"
    
    # 6. Закрытие смены
    if end_message:
        report += "\n" + end_message
    else:
        report += f"\n{report_date} - Приступил с кассой в сейфе\n"
        report += f"Наличные - 0 сум\n"
        report += f"Карта - 0\n"
        report += f"Всего - 0 сум"
    
    report += TRY_AGAIN
    
    return report

# ===== КОМАНДА /START =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    
    if user_id in user_data:
        user_data[user_id] = {'messages': []}
    else:
        user_data[user_id] = {'messages': []}
    
    bot.send_message(user_id, WELCOME)

# ===== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ =====
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    text = message.text
    
    if user_id not in user_data:
        user_data[user_id] = {'messages': []}
    
    # ===== ТРИГГЕР =====
    if text.lower().strip() == "буххх":
        report = generate_report(user_id)
        send_long_message(user_id, report)
        return
    
    # ===== НОВЫЙ ДЕНЬ =====
    if text.lower().strip() in ["новый день", "очистить"]:
        user_data[user_id] = {'messages': []}
        bot.reply_to(message, NEW_DAY)
        return
    
    # ===== СОХРАНЯЕМ =====
    parsed = parse_message(text)
    
    if parsed:
        user_data[user_id]['messages'].append(text)
        bot.reply_to(message, MESSAGE_SAVED)
    else:
        # Проверяем на общие итоги
        if ('общая пополнение' in text.lower() or 
            'общая изъятия' in text.lower() or
            'приступил с кассой' in text.lower() or
            'закрытие смены' in text.lower()):
            user_data[user_id]['messages'].append(text)
            bot.reply_to(message, MESSAGE_SAVED)
        else:
            bot.reply_to(message, UNKNOWN)

# ===== FLASK ВЕБ-СЕРВЕР ДЛЯ RENDER =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_bot_polling():
    print("Starting bot polling...")
    bot.infinity_polling()

# ===== ЗАПУСК =====
if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot_polling)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)
