import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# إعداد قاعدة البيانات
def init_db():
    conn = sqlite3.connect('rounds.db')
    c = conn.cursor()
    # جدول لتخزين الجولات
    c.execute('''CREATE TABLE IF NOT EXISTS rounds
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  chat_id INTEGER,
                  message_text TEXT,
                  user_id INTEGER,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

# إعداد التسجيل
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN")

# دالة تسجيل الرسائل المتعلقة بالجولات
async def log_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    # كلمات مفتاحية لمعرفة أن هذه الرسالة تتعلق باللعبة
    keywords = ["الجولة", "فاز", "خسر", "النقاط"]
    
    if any(keyword in text for keyword in keywords):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = update.effective_user
        
        # حفظ في قاعدة البيانات
        conn = sqlite3.connect('rounds.db')
        c = conn.cursor()
        c.execute("INSERT INTO rounds (chat_id, message_text, user_id, timestamp) VALUES (?, ?, ?, ?)",
                  (update.effective_chat.id, text, user.id, timestamp))
        conn.commit()
        conn.close()
        
        # اختياري: تأكيد التسجيل (يمكن حذفه إذا كان مزعجاً)
        # await update.message.reply_text("تم تسجيل الجولة ✅")

if __name__ == '__main__':
    init_db() # إنشاء قاعدة البيانات عند بدء التشغيل
    app = ApplicationBuilder().token(TOKEN).build()
    # الاستماع لكل الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, log_round))
    print("Bot is running and logging rounds...")
    app.run_polling()
