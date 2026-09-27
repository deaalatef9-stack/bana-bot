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
# 2. إعداد قاعدة البيانات (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            coins INTEGER DEFAULT 100
        )
    ''')
    conn.commit()
    conn.close()

def get_player(user_id, username):
    conn = sqlite3.connect('game_data.db')
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

def update_player(user_id, level, xp, coins):
    conn = sqlite3.connect('game_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE players SET level = ?, xp = ?, coins = ? WHERE user_id = ?', (level, xp, coins, user_id))
    conn.commit()
    conn.close()

# ==========================================
# 3. أوامر البوت
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or "لاعب"
    get_player(user_id, username)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_profile = types.InlineKeyboardButton("👤 ملفي", callback_data="profile")
    btn_work = types.InlineKeyboardButton("⛏️ اعمل (جمع نقاط)", callback_data="work")
    btn_shop = types.InlineKeyboardButton("🛒 المتجر", callback_data="shop")
    markup.add(btn_profile, btn_work, btn_shop)
    
    bot.send_message(message.chat.id, f"أهلاً بك يا {username} في بوت لعبة بلانت! 🎮\nاختر من القائمة:", reply_markup=markup)

@bot.message_handler(commands=['profile'])
def show_profile(message):
    user_id = message.from_user.id
    username = message.from_user.username or "لاعب"
    player = get_player(user_id, username)
    
    text = f"👤 **ملفك الشخصي:**\n\n"
    text += f"الاسم: {player[1]}\n"
    text += f"المستوى: {player[2]}\n"
    text += f"نقاط الخبرة: {player[3]}\n"
    text += f"العملات: {player[4]} 💰"
    bot.reply_to(message, text, parse_mode='Markdown')

# ==========================================
# 4. معالجة الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    username = call.from_user.username or "لاعب"
    player = get_player(user_id, username)
    
    if call.data == "profile":
        text = f"👤 **ملفك الشخصي:**\n\nالمستوى: {player[2]}\nالخبرة: {player[3]}\nالعملات: {player[4]} 💰"
        bot.answer_callback_query(call.id)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, parse_mode='Markdown')
        
    elif call.data == "work":
        new_xp = player[3] + 10
        new_coins = player[4] + 5
        new_level = player[2]
        
        if new_xp >= 100:
            new_level += 1
            new_xp = 0
            bot.answer_callback_query(call.id, "🎉 مبروك! لقد ارتفعت لمستوى جديد!")
        else:
            bot.answer_callback_query(call.id, "لقد عملت وحصلت على 10 خبرة و 5 عملات!")
            
        update_player(user_id, new_level, new_xp, new_coins)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="profile"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"لقد انتهيت من العمل! 💪\nمستواك الحالي: {new_level}\nخبرتك: {new_xp}/100", reply_markup=markup)
        
    elif call.data == "shop":
        bot.answer_callback_query(call.id, "المتجر قيد التطوير... 🛠️")

# ==========================================
# 5. سيرفر Flask
# ==========================================
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 6. تشغيل البوت والسيرفر
# ==========================================
if __name__ == "__main__":
    init_db()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    print("Bot is starting...")
    bot.infinity_polling()
