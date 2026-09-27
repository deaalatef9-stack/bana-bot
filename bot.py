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
    # جدول الجولات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rounds (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            multiplier REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # جدول التنبيهات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            user_id BIGINT PRIMARY KEY,
            threshold REAL
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
    # التحقق من التنبيهات
    check_alert(user_id, multiplier)

def delete_last_round(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM rounds WHERE id = (SELECT MAX(id) FROM rounds WHERE user_id = %s)', (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_history(user_id, limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT multiplier, timestamp FROM rounds WHERE user_id = %s ORDER BY id DESC LIMIT %s', (user_id, limit))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_full_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT multiplier FROM rounds WHERE user_id = %s', (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not rows:
        return None
    
    multipliers = [row[0] for row in rows]
    total = len(multipliers)
    avg = sum(multipliers) / total
    max_val = max(multipliers)
    min_val = min(multipliers)
    
    high_2x = sum(1 for x in multipliers if x >= 2.0)
    high_5x = sum(1 for x in multipliers if x >= 5.0)
    high_10x = sum(1 for x in multipliers if x >= 10.0)
    
    prob_2x = (high_2x / total) * 100
    prob_5x = (high_5x / total) * 100
    prob_10x = (high_10x / total) * 100
    
    return {
        'total': total, 'avg': avg, 'max': max_val, 'min': min_val,
        'prob_2x': prob_2x, 'prob_5x': prob_5x, 'prob_10x': prob_10x
    }

def set_alert(user_id, threshold):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (user_id, threshold) VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET threshold = EXCLUDED.threshold
    ''', (user_id, threshold))
    conn.commit()
    cursor.close()
    conn.close()

def get_alert(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT threshold FROM alerts WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None

def check_alert(user_id, multiplier):
    threshold = get_alert(user_id)
    if threshold and multiplier >= threshold:
        bot.send_message(user_id, f"🚨 **تنبيه!** 🚨\n\nلقد وصل المعامل إلى **{multiplier}x**، وهو أكبر من الحد الذي حددته ({threshold}x)!\n\nاستعد للجولة القادمة! 🔥", parse_mode='Markdown')

# ==========================================
# 3. الأزرار
# ==========================================
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_add = types.InlineKeyboardButton("➕ تسجيل جولة", callback_data="add_round")
    btn_stats = types.InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")
    btn_history = types.InlineKeyboardButton("📜 سجل الجولات", callback_data="history")
    btn_predict = types.InlineKeyboardButton("🔮 توقع الجولة القادمة", callback_data="predict")
    btn_alert = types.InlineKeyboardButton("🔔 ضبط التنبيه", callback_data="set_alert")
    btn_share = types.InlineKeyboardButton("📤 مشاركة إحصائياتي", callback_data="share")
    btn_delete = types.InlineKeyboardButton("🗑️ حذف آخر جولة", callback_data="delete_last")
    markup.add(btn_add, btn_stats, btn_history, btn_predict, btn_alert, btn_share, btn_delete)
    return markup

# ==========================================
# 4. أوامر البوت
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    bot.send_message(message.chat.id, "أهلاً بك في مساعد لعبة Aviator (Blant)! ✈️\nاختر من القائمة:", reply_markup=main_menu())

# ==========================================
# 5. معالجة الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "add_round":
        msg = bot.send_message(chat_id, "📝 أرسل رقم المعامل (المضاعف) فقط:\nمثال: `1.42` أو `5.94`", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_round_input)

    elif call.data == "stats":
        stats = get_full_stats(user_id)
        if not stats:
            bot.answer_callback_query(call.id, "لا توجد جولات مسجلة بعد!")
            return
        
        text = f"📊 **إحصائياتك الكاملة:**\n\n"
        text += f"🔢 عدد الجولات: {stats['total']}\n"
        text += f"📈 المتوسط: {stats['avg']:.2f}x\n"
        text += f"🔺 أعلى معامل: {stats['max']}x\n"
        text += f"🔻 أدنى معامل: {stats['min']}x\n\n"
        text += f"🎯 **الاحتمالات:**\n"
        text += f"   • فرصة ظهور 2x+: {stats['prob_2x']:.1f}%\n"
        text += f"   • فرصة ظهور 5x+: {stats['prob_5x']:.1f}%\n"
        text += f"   • فرصة ظهور 10x+: {stats['prob_10x']:.1f}%\n"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "history":
        history = get_history(user_id)
        if not history:
            bot.answer_callback_query(call.id, "لا توجد جولات مسجلة بعد!")
            return
        
        text = "📜 **آخر 10 جولات:**\n\n"
        for i, (mult, ts) in enumerate(history, 1):
            text += f"{i}. {mult}x\n"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "predict":
        stats = get_full_stats(user_id)
        if not stats or stats['total'] < 10:
            bot.answer_callback_query(call.id, "يجب تسجيل 10 جولات على الأقل للتوقع!")
            return
        
        avg = stats['avg']
        if avg > 3.0:
            prediction = "🔥 التوقع: معامل عالي (أكبر من 2.0x)"
        elif avg < 1.5:
            prediction = "❄️ التوقع: معامل منخفض (أقل من 2.0x)"
        else:
            prediction = "⚖️ التوقع: معامل متوسط (بين 1.5x و 2.5x)"
            
        text = f"🔮 **تحليل الجولة القادمة:**\n\n"
        text += f"متوسط كل الجولات: {avg:.2f}x\n"
        text += f"عدد الجولات: {stats['total']}\n"
        text += f"**{prediction}**"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=main_menu())

    elif call.data == "set_alert":
        msg = bot.send_message(chat_id, "🔔 أرسل الحد الأدنى للتنبيه (مثلاً: 5.0):\nسأرسل لك رسالة عندما يصل المعامل لهذا الرقم.", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_alert_input)

    elif call.data == "share":
        stats = get_full_stats(user_id)
        if not stats:
            bot.answer_callback_query(call.id, "لا توجد إحصائيات لمشاركتها!")
            return
        
        share_text = f"📊 **إحصائياتي في لعبة Aviator:**\n\n"
        share_text += f"🔢 عدد الجولات: {stats['total']}\n"
        share_text += f"📈 المتوسط: {stats['avg']:.2f}x\n"
        share_text += f"🔺 أعلى معامل: {stats['max']}x\n"
        share_text += f"🎯 فرصة 2x+: {stats['prob_2x']:.1f}%\n"
        bot.answer_callback_query(call.id)
        bot.send_message(chat_id, f"انسخ هذه الرسالة وشاركها مع أصدقائك:\n\n{share_text}", parse_mode='Markdown')

    elif call.data == "delete_last":
        delete_last_round(user_id)
        bot.answer_callback_query(call.id, "✅ تم حذف آخر جولة بنجاح!")
        bot.send_message(chat_id, "تم الحذف. اختر من القائمة:", reply_markup=main_menu())

# ==========================================
# 6. معالجة الإدخال
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

def process_alert_input(message):
    try:
        threshold = float(message.text.strip())
        if threshold <= 1.0:
            raise ValueError("الحد يجب أن يكون أكبر من 1.0")
        set_alert(message.from_user.id, threshold)
        bot.reply_to(message, f"✅ تم ضبط التنبيه على: {threshold}x\nسأرسل لك رسالة عندما يصل المعامل لهذا الرقم.", reply_markup=main_menu())
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}\nالرجاء إدخال رقم صحيح (مثل 5.0)", reply_markup=main_menu())

# ==========================================
# 7. معالج الرسائل النصية العامة (لإظهار القائمة تلقائياً)
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    # إذا كانت الرسالة تبدأ بـ / (أمر)، نتجاهلها لأن لها معالجاً خاصاً
    if message.text and message.text.startswith('/'):
        return
    # إرسال القائمة الرئيسية تلقائياً
    bot.reply_to(message, "تفضل، اختر من القائمة:", reply_markup=main_menu())

# ==========================================
# 8. سيرفر Flask
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 9. التشغيل
# ==========================================
if __name__ == "__main__":
    init_db()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    print("Bot is starting...")
    bot.infinity_polling()
