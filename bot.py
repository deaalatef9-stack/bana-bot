import os
import telebot
from telebot import types
from flask import Flask
import threading
import psycopg2

# ==========================================
# 1. الإعدادات الأساسية
# ==========================================
# ⚠️ ضع التوكن الخاص بك مكان النص التالي بالضبط:
BOT_TOKEN = '8661550066:AAE8aQZlI9Bvooa-hoW0yGexS_vTfEHTNok'

# ✅ قراءة رابط قاعدة البيانات من Environment Variables في Render
DATABASE_URL = os.environ.get('DATABASE_URL')

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 2. إعداد قاعدة البيانات (PostgreSQL)
# ==========================================
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            multiplier REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

def add_round(user_id, multiplier):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO rounds (user_id, multiplier) VALUES (%s, %s)', (user_id, multiplier))
    conn.commit()
    cursor.close()
    conn.close()

def delete_last_round(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rounds WHERE id = (SELECT MAX(id) FROM rounds WHERE user_id = %s)', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_player_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT multiplier FROM rounds WHERE user_id = %s ORDER BY id DESC LIMIT 10', (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        return None
    
    multipliers = [row[0] for row in rows]
    return multipliers

# ==========================================
# 3. الأزرار الرئيسية
# ==========================================
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("➕ تسجيل جولة", callback_data="add_round")
    btn_stats = types.InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
    btn_predict = types.InlineKeyboardButton("🔮 توقع الجولة القادمة", callback_data="predict")
    btn_delete = types.InlineKeyboardButton("🗑️ حذف آخر جولة", callback_data="delete_last")
    markup.add(btn_add, btn_stats, btn_predict, btn_delete)
    return markup

# ==========================================
# 4. أوامر البوت
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "أهلاً بك في مساعد لعبة Aviator (Blant)! ✈️\nاختر من القائمة:", reply_markup=main_menu())

@bot.message_handler(commands=['menu'])
def show_menu(message):
    bot.send_message(message.chat.id, "القائمة الرئيسية:", reply_markup=main_menu())

# ==========================================
# 5. معالجة الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id

    if call.data == "add_round":
        msg = bot.send_message(call.message.chat.id, "📝 أرسل رقم المعامل (المضاعف) فقط:\nمثال: `1.42` أو `5.94`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_round_input)

    elif call.data == "stats":
        multipliers = get_player_stats(user_id)
        if not multipliers:
            bot.answer_callback_query(call.id, "لا توجد جولات مسجلة بعد!")
            return
        
        avg = sum(multipliers) / len(multipliers)
        max_val = max(multipliers)
        min_val = min(multipliers)
        
        text = f"📊 **إحصائياتك (آخر {len(multipliers)} جولات):**\n\n"
        text += f"📈 المتوسط: {avg:.2f}x\n"
        text += f"🔺 أعلى معامل: {max_val}x\n"
        text += f"🔻 أدنى معامل: {min_val}x\n"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "predict":
        multipliers = get_player_stats(user_id)
        if not multipliers:
            bot.answer_callback_query(call.id, "يجب تسجيل 10 جولات على الأقل للتوقع!")
            return
        
        avg = sum(multipliers) / len(multipliers)
        high_count = sum(1 for x in multipliers if x >= 2.0)
        
        if avg > 3.0:
            prediction = "🔥 التوقع: معامل عالي (أكبر من 2.0x)"
        elif avg < 1.5:
            prediction = "❄️ التوقع: معامل منخفض (أقل من 2.0x)"
        else:
            prediction = "⚖️ التوقع: معامل متوسط (بين 1.5x و 2.5x)"
            
        text = f"🔮 **تحليل الجولة القادمة:**\n\n"
        text += f"متوسط آخر 10 جولات: {avg:.2f}x\n"
        text += f"عدد الجولات العالية (2x+): {high_count}\n"
        text += f"**{prediction}**"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "delete_last":
        delete_last_round(user_id)
        bot.answer_callback_query(call.id, "✅ تم حذف آخر جولة بنجاح!")
        bot.send_message(call.message.chat.id, "تم الحذف. اختر من القائمة:", reply_markup=main_menu())

# ==========================================
# 6. معالجة إدخال الجولة
# ==========================================
def process_round_input(message):
    try:
        multiplier = float(message.text.strip())
        if multiplier <= 1.0:
            raise ValueError("المعامل يجب أن يكون أكبر من 1.0")
        
        add_round(message.from_user.id, multiplier)
        bot.reply_to(message, f"✅ تم تسجيل المعامل: {multiplier}x", reply_markup=main_menu())
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}\nالرجاء إدخال رقم صحيح (مثل 1.42)", reply_markup=main_menu())

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
