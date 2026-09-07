import telebot
from telebot import types
import re
from datetime import datetime
import logging

BOT_TOKEN = "8968271583:AAE8x6CdtvoaHnHEN7ezD7ebk8JWbMXDvNo"
bot = telebot.TeleBot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

user_data = {}
user_language = {}

TEXTS = {
    'ru': {
        'choose_lang': "🌐 Выберите язык:",
        'lang_changed': "✅ Язык изменен на русский.",
        'welcome': "👋 Привет! Я бот для анализа отчетов.\n\n"
                   "📝 Отправляйте мне сообщения с пополнениями и изъятиями.\n"
                   "Когда закончите, отправьте одну из команд:\n"
                   "`кофемофебух` или `кофемоефус` или `буххх`\n\n"
                   "Я соберу все данные и выдам полный отчет!",
        'new_day': "📅 Начинаем новый день!\n"
                   "Отправляйте мне сообщения с пополнениями и изъятиями.\n"
                   "Для отчета отправьте: кофемофебух",
        'message_saved': "✅ Сообщение сохранено!",
        'unknown': "❌ Не удалось распознать сообщение.\n"
                   "Примеры:\n"
                   "✅ Пополнение сейфа из филиала НТД на сумму : 530.000 сум\n"
                   "❌ Изъятие 25.000 сум на дорожные расходы",
        'no_data': "❌ Нет данных для отчета.\n"
                   "Отправьте сначала пополнения и изъятия.",
        'try_again': "\n\n📤 Отправьте буххх для нового отчета.\n"
                     "Или новый день для очистки данных."
    },
    'uz': {
        'choose_lang': "🌐 Tilni tanlang:",
        'lang_changed': "✅ Til o'zbek tiliga o'zgartirildi.",
        'welcome': "👋 Salom! Men hisobotlarni tahlil qilish uchun botman.\n\n"
                   "📝 Menga tushum va chiqimlar haqida xabarlar yuboring.\n"
                   "Tugatganingizda, buyruqlardan birini yuboring:\n"
                   "`кофемофебух` yoki `кофемоефус` yoki `буххх`\n\n"
                   "Men barcha ma'lumotlarni yig'ib, to'liq hisobot beraman!",
        'new_day': "📅 Yangi kun boshlaymiz!\n"
                   "Menga tushum va chiqimlar haqida xabarlar yuboring.\n"
                   "Hisobot uchun: кофемофебух",
        'message_saved': "✅ Xabar saqlandi!",
        'unknown': "❌ Xabarni taniy olmadim.\n"
                   "Misollar:\n"
                   "✅ Пополнение сейфа из филиала НТД на сумму : 530.000 сум\n"
                   "❌ Изъятие 25.000 сум на дорожные расходы",
        'no_data': "❌ Hisobot uchun ma'lumot yo'q.\n"
                   "Avval tushum va chiqimlarni yuboring.",
        'try_again': "\n\n📤 Yangi hisobot uchun буххх yuboring.\n"
                     "Yoki ma'lumotlarni tozalash uchun новый день."
    }
}

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

def parse_message(text):
    result = None
    text_lower = text.lower()
    
    if 'итоговый остаток' in text_lower or 'остаток наличных' in text_lower:
        amount_match = re.search(r'составляет\s*:?\s*([\d.,]+)', text)
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            result = {'type': 'balance', 'category': 'Остаток', 'amount': amount, 'raw': text}
            return result
    
    if '✅' in text or 'Пополнение' in text or 'пополнение' in text_lower:
        amount_match = re.search(r'(?:сумме?|сум)\s*:?\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r':\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r'(\d+[\.,]?\d*)\s*(?:сум|so\'m)', text)
        
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            
            category = 'Пополнение'
            if 'Микрорайон' in text or 'микрорайон' in text_lower:
                category = 'Микрорайон'
            elif 'НТД' in text or 'нтд' in text_lower:
                category = 'НТД'
            elif 'Оромгох' in text or 'оромгох' in text_lower:
                category = 'Оромгох'
            elif 'Учредител' in text or 'учредител' in text_lower:
                category = 'Учредители'
            elif 'Street' in text or 'street' in text_lower:
                category = 'Street 93'
            
            result = {'type': 'income', 'category': category, 'amount': amount, 'raw': text}
            return result
    
    if ('❌' in text or 
        'Изъяти' in text or 'изъяти' in text_lower or 
        'Выдано' in text or 'выдано' in text_lower or
        'Запрос на изъятия' in text_lower):
        
        amount_match = re.search(r'(?:размере|сумме|сум)\s*:?\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r':\s*([\d.,]+)', text)
        if not amount_match:
            amount_match = re.search(r'(\d+[\.,]?\d*)\s*(?:сум|so\'m)', text)
        
        if amount_match:
            amount_str = amount_match.group(1).replace('.', '').replace(',', '')
            amount = float(amount_str) if amount_str else 0
            
            category = 'Изъятие'
            if 'Фуад' in text or 'фуад' in text_lower:
                category = 'Фуад Насруллаев'
            elif 'Базаркому' in text or 'базаркому' in text_lower:
                category = 'Базаркому'
            elif 'Учредител' in text or 'учредител' in text_lower:
                category = 'Учредитель'
            elif 'зарплат' in text_lower or 'персонал' in text_lower:
                category = 'Зарплата'
            elif 'дорожн' in text_lower:
                category = 'Дорожные расходы'
            elif 'Bakery' in text or 'bakery' in text_lower:
                category = 'Bakery'
            elif 'Prime' in text or 'prime' in text_lower:
                category = 'Prime Kofe Mofe'
            
            result = {'type': 'expense', 'category': category, 'amount': amount, 'raw': text}
            return result
    
    return None

def extract_report_data(text):
    data = {'income': 0, 'expense': 0, 'balance': 0, 'date': None}
    
    date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    if date_match:
        data['date'] = date_match.group(1)
    
    income_match = re.search(r'Общая пополнение\s*[^:]*:\s*([\d.,]+)', text)
    if income_match:
        data['income'] = float(income_match.group(1).replace('.', '').replace(',', ''))
    
    expense_match = re.search(r'Общая изъятия\s*[^:]*:\s*([\d.,]+)', text)
    if expense_match:
        data['expense'] = float(expense_match.group(1).replace('.', '').replace(',', ''))
    
    balance_match = re.search(r'Закрытие смены.*?Наличные\s*[-–]\s*([\d.,]+)', text, re.DOTALL)
    if balance_match:
        data['balance'] = float(balance_match.group(1).replace('.', '').replace(',', ''))
    
    if data['balance'] == 0:
        balance_match2 = re.search(r'Всего\s*[-–]\s*([\d.,]+)', text)
        if balance_match2:
            data['balance'] = float(balance_match2.group(1).replace('.', '').replace(',', ''))
    
    return data

def generate_report(user_id, lang):
    if user_id not in user_data or not user_data[user_id]['messages']:
        return TEXTS[lang]['no_data']
    
    data = user_data[user_id]
    messages = data['messages']
    
    income_messages = []
    expense_messages = []
    start_messages = []
    end_messages = []
    other_messages = []
    
    income_total = 0
    expense_total = 0
    
    for msg in messages:
        # Убираем @Fuad_Nasrullayev из сообщений
        msg = msg.replace('@Fuad_Nasrullayev', '').replace('@fuad_nasrullayev', '')
        
        parsed = parse_message(msg)
        if parsed:
            if parsed['type'] == 'income':
                income_messages.append(msg)
                income_total += parsed['amount']
            elif parsed['type'] == 'expense':
                expense_messages.append(msg)
                expense_total += parsed['amount']
            elif parsed['type'] == 'balance':
                expense_messages.append(msg)
        else:
            if 'Приступил с кассой' in msg or 'Приступил' in msg:
                start_messages.append(msg)
            elif 'Закрытие смены' in msg or 'Закрытие' in msg:
                end_messages.append(msg)
            else:
                if 'Общая пополнение' in msg or 'Общая изъятия' in msg:
                    other_messages.append(msg)
    
    report_date = data.get('date', datetime.now().strftime('%d.%m.%Y'))
    
    report = f"📊 ОТЧЕТ ЗА {report_date}\n\n"
    
    if start_messages:
        for msg in start_messages:
            report += msg + "\n"
    else:
        report += f"{report_date} - Приступил с кассой в сейфе \n"
        report += f"Наличные - 0 сум\n"
        report += f"Карта - 0\n"
        report += f"Всего - 0 сум\n"
    
    report += f"\nОбщая пополнение в сейфе наличных на сумму - {income_total:,.0f} сум\n"
    report += f"Общая пополнение карты на сумму - 0\n"
    report += f"Общая пополнение в сейфа в долларах - 0$\n\n"
    
    for msg in income_messages:
        report += msg + "\n"
    
    report += f"\nОбщая изъятия денег из сейфа на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия наличных на сумму - {expense_total:,.0f} сум\n"
    report += f"Общая изъятия из карты на сумму - 0\n"
    report += f"Общая изъятия в долларах - 0$\n\n"
    
    for msg in expense_messages:
        report += msg + "\n"
    
    for msg in other_messages:
        report += msg + "\n"
    
    if end_messages:
        for msg in end_messages:
            report += msg + "\n"
    else:
        report += f"\nЗакрытие смены на {report_date} \n"
        report += f"Наличные - 0 сум\n"
        report += f"Карта - 0\n"
        report += f"Всего - 0 сум\n"
    
    report += TEXTS[lang]['try_again']
    
    return report

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    
    if user_id in user_data:
        user_data[user_id] = {'messages': [], 'date': None}
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    btn_uz = types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz")
    markup.add(btn_ru, btn_uz)
    
    bot.send_message(
        user_id,
        "🌐 Выберите язык / Tilni tanlang:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    
    if call.data == "lang_ru":
        user_language[user_id] = 'ru'
        text = TEXTS['ru']['lang_changed'] + "\n\n" + TEXTS['ru']['welcome']
    elif call.data == "lang_uz":
        user_language[user_id] = 'uz'
        text = TEXTS['uz']['lang_changed'] + "\n\n" + TEXTS['uz']['welcome']
    else:
        return
    
    if user_id not in user_data:
        user_data[user_id] = {'messages': [], 'date': None}
    
    bot.edit_message_text(
        text,
        chat_id=user_id,
        message_id=call.message.message_id
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    text = message.text
    
    if user_id not in user_language:
        bot.reply_to(
            message,
            "⚠️ Сначала выберите язык: /start\n\n⚠️ Avval tilni tanlang: /start"
        )
        return
    
    lang = user_language[user_id]
    
    if user_id not in user_data:
        user_data[user_id] = {'messages': [], 'date': None}
    
    trigger_words = [
        "кофемофебух",
        "кофемоефус",
        "кофемоефе",
        "буххх"
    ]
    
    if text.lower().strip() in trigger_words:
        report = generate_report(user_id, lang)
        send_long_message(user_id, report)
        return
    
    if text.lower().strip() in ["новый день", "очистить"]:
        user_data[user_id] = {'messages': [], 'date': None}
        bot.reply_to(message, TEXTS[lang]['new_day'])
        return
    
    parsed = parse_message(text)
    
    if parsed:
        user_data[user_id]['messages'].append(text)
        bot.reply_to(message, TEXTS[lang]['message_saved'])
        
        if 'итоговый остаток' in text.lower() or 'остаток наличных' in text.lower():
            if not user_data[user_id].get('date'):
                user_data[user_id]['date'] = datetime.now().strftime('%d.%m.%Y')
        
        if 'Приступил с кассой' in text or 'Закрытие смены' in text:
            report_data = extract_report_data(text)
            if report_data.get('date'):
                user_data[user_id]['date'] = report_data['date']
    else:
        if ('Приступил с кассой' in text or 
            'Закрытие смены' in text or 
            'Общая пополнение' in text or
            'Общая изъятия' in text):
            
            user_data[user_id]['messages'].append(text)
            report_data = extract_report_data(text)
            if report_data.get('date'):
                user_data[user_id]['date'] = report_data['date']
            bot.reply_to(message, TEXTS[lang]['message_saved'])
        else:
            bot.reply_to(message, TEXTS[lang]['unknown'])

if __name__ == '__main__':
    print("🤖 Бот запущен и готов к работе!")
    print("📊 Ожидает сообщения в личном чате")
    print("🔑 Триггеры: кофемофебух, кофемоефус, кофемоефе, буххх")
    bot.infinity_polling()