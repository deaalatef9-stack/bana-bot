import os
import telebot
from telebot import types
from flask import Flask
import threading
import sqlite3

# ==========================================
# 1. الإعدادات الأساسية
# ==========================================
# ⚠️ ضع التوكن الخاص بك مكان النص التالي بالضبط:
BOT_TOKEN = '8661550066:AAE8aQZlI9Bvooa-hoW0yGexS_vTfEHTNok'

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 2. إعداد قاعدة البيانات
# ==========================================
def init_db():
    conn = sqlite3.connect('bana_game.db')
    cursor = conn.cursor()
    # جدول اللاعبين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 100
        )
    ''')
    # جدول الجولات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            max_num INTEGER,
            min_num INTEGER,
            result_num INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_player(user_id, username):
    conn = sqlite3.connect('bana_game.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = cursor.fetchone()
    if not player:
        cursor.execute('INSERT INTO players (user_id, username) VALUES (?, ?)', (user_id, username))
        conn.commit()
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        player = cursor.fetchone()
    conn.close()
    return player

def add_round(user_id, max_num, min_num, result_num):
    conn = sqlite3.connect('bana_game.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO rounds (user_id, max_num, min_num, result_num) VALUES (?, ?, ?, ?)', 
                   (user_id, max_num, min_num, result_num))
    conn.commit()
    conn.close()

def delete_last_round(user_id):
    conn = sqlite3.connect('bana_game.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rounds WHERE id = (SELECT MAX(id) FROM rounds WHERE user_id = ?)', (user_id,))
    conn.commit()
    conn.close()

def get_player_stats(user_id):
    conn = sqlite3.connect('bana_game.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), MAX(result_num), MIN(result_num) FROM rounds WHERE user_id = ?', (user_id,))
    stats = cursor.fetchone()
    conn.close()
    return stats

# ==========================================
# 3. الأزرار الرئيسية
# ==========================================
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("➕ تسجيل جولة", callback_data="add_round")
    btn_stats = types.InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
    btn_delete = types.InlineKeyboardButton("🗑️ حذف آخر جولة", callback_data="delete_last")
    btn_help = types.InlineKeyboardButton("❓ مساعدة", callback_data="help")
    markup.add(btn_add, btn_stats, btn_delete, btn_help)
    return markup

# ==========================================
# 4. أوامر البوت
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "لاعب"
    get_player(user_id, username)
    bot.send_message(message.chat.id, f"أهلاً بك يا {username} في مساعد لعبة بلانت! 🎮\nاختر من القائمة:", reply_markup=main_menu())

@bot.message_handler(commands=['menu'])
def show_menu(message):
    bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=main_menu())

# ==========================================
# 5. معالجة الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    username = call.from_user.username or "لاعب"
    get_player(user_id, username)

    if call.data == "add_round":
        msg = bot.send_message(call.message.chat.id, "📝 أرسل بيانات الجولة بهذا الشكل:\n`الحد الأعلى, الحد الأدنى, الرقم الفائز`\nمثال: `10, 1, 5`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_round_input)

    elif call.data == "stats":
        stats = get_player_stats(user_id)
        text = f"📊 **إحصائياتك:**\n\n"
        text += f"عدد الجولات: {stats[0]}\n"
        text += f"أعلى رقم فائز: {stats[1] if stats[1] else 'لا يوجد'}\n"
        text += f"أدنى رقم فائز: {stats[2] if stats[2] else 'لا يوجد'}"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "delete_last":
        delete_last_round(user_id)
        bot.answer_callback_query(call.id, "✅ تم حذف آخر جولة بنجاح!")
        bot.send_message(call.message.chat.id, "تم الحذف. اختر من القائمة:", reply_markup=main_menu())

    elif call.data == "help":
        text = "❓ **كيفية الاستخدام:**\n"
        text += "1. اضغط على 'تسجيل جولة'.\n"
        text += "2. أدخل الأرقام بالشكل: `الحد الأعلى, الحد الأدنى, الرقم الفائز`.\n"
        text += "3. يمكنك حذف آخر جولة إذا أخطأت.\n"
        text += "4. تابع إحصائياتك لتعرف أفضل الأرقام."
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

# ==========================================
# 6. معالجة إدخال الجولة
# ==========================================
def process_round_input(message):
    try:
        # تقسيم النص المدخل
        parts = message.text.split(',')
        if len(parts) != 3:
            raise ValueError("الرجاء إدخال 3 أرقام مفصولة بفواصل.")
        
        max_num = int(parts[0].strip())
        min_num = int(parts[1].strip())
        result_num = int(parts[2].strip())
        
        add_round(message.from_user.id, max_num, min_num, result_num)
        bot.reply_to(message, f"✅ تم تسجيل الجولة بنجاح!\nالحد الأعلى: {max_num}\nالحد الأدنى: {min_num}\nالرقم الفائز: {result_num}", reply_markup=main_menu())
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {e}\nالرجاء المحاولة مرة أخرى باستخدام الأزرار.", reply_markup=main_menu())

# ==========================================
# 7. سيرفر Flask
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 8. التشغيل
# ==========================================
if __name__ == "__main__":
    init_db()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    print("Bot is starting...")
    bot.infinity_polling()
