import json
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

app = Flask(__name__)

TOKEN = os.getenv("BOT_TOKEN")8661550066:AAF7yv80It90Ei69X5i-WGezbyvGqmEqVdY
DATA_FILE = "results.json"

def load_results():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_results(results):
    with open(DATA_FILE, "w") as f:
        json.dump(results, f)

def get_stats(results):
    if not results:
        return "لا توجد نتائج مسجلة بعد."
    count = len(results)
    avg = sum(results) / count
    max_val = max(results)
    min_val = min(results)
    current_high = 0
    current_low = 0
    max_high_streak = 0
    max_low_streak = 0
    for val in results:
        if val >= 2.0:
            current_high += 1
            current_low = 0
            max_high_streak = max(max_high_streak, current_high)
        else:
            current_low += 1
            current_high = 0
            max_low_streak = max(max_low_streak, current_low)
    high_count = sum(1 for v in results if v >= 2.0)
    low_count = count - high_count
    high_percent = (high_count / count) * 100
    low_percent = (low_count / count) * 100
    return (
        f"📊 **الإحصائيات الشاملة:**\n"
        f"🔢 عدد المشاهدات: {count}\n"
        f"📉 المتوسط: {avg:.2f}x\n"
        f"⬆️ أعلى قيمة: {max_val:.2f}x\n"
        f"⬇️ أقل قيمة: {min_val:.2f}x\n"
        f"🔥 أطول سلسلة عالية: {max_high_streak}\n"
        f"❄️ أطول سلسلة منخفضة: {max_low_streak}\n"
        f"📈 نسبة العالية: {high_percent:.1f}%\n"
        f"📉 نسبة المنخفضة: {low_percent:.1f}%"
    )

def calculate_prediction(results):
    if len(results) < 5:
        return "⚠️ أحتاج إلى 5 نتائج على الأقل لتحليل النمط."
    last_5 = results[-5:]
    avg = sum(last_5) / len(last_5)
    last_value = results[-1]
    streak_high = 0
    streak_low = 0
    for val in reversed(results):
        if val >= 2.0:
            streak_high += 1
            streak_low = 0
        else:
            streak_low += 1
            streak_high = 0
        if streak_high > 0 or streak_low > 0:
            break
    reversal_signal = ""
    if last_value >= 3.0:
        reversal_signal = "آخر قيمة مرتفعة جداً."
    elif last_value < 1.5:
        reversal_signal = "آخر قيمة منخفضة جداً."
    confidence = 50
    if streak_high >= 3:
        confidence += 20
    if streak_low >= 3:
        confidence += 20
    if avg > 2.5:
        confidence += 10
    if avg < 1.8:
        confidence += 10
    confidence = min(confidence, 95)
    if streak_high >= 3:
        pred = "ديكور قوي (بعد سلسلة مرتفعة)"
        confidence = min(confidence + 15, 95)
    elif streak_low >= 3:
        pred = "مستوى منخفض قوي (بعد السلسلة)"
        confidence = min(confidence + 15, 95)
    elif avg > 2.2:
        pred = "التوقعات المتوقعة (المتوسط)"
    else:
        pred = "التوقعات العالية (المتوسط المنخفض)"
    return (
        f"🎯 **تحليل آخر 5 جولات:**\n"
        f"المتوسط: {avg:.2f}x\n"
        f"آخر قيمة: {last_value:.2f}x\n"
        f"{reversal_signal}\n\n"
        f"🔮 **توقعي للجولة القادمة:**\n{pred}\n"
        f"🎯 **نسبة الثقة:** {confidence}%"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("📈 آخر النتائج", callback_data="last")],
        [InlineKeyboardButton("➕ إضافة جولة", callback_data="add")],
        [InlineKeyboardButton("🔮 القادمة المتوقعة", callback_data="predict")],
        [InlineKeyboardButton("🗑️ حذف آخر جولة", callback_data="undo")],
        [InlineKeyboardButton("🔬 تحليل شامل", callback_data="analyze")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر من القائمة:", reply_markup=reply_markup)

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    results = load_results()

    if query.data == "stats":
        await query.edit_message_text(get_stats(results))
    elif query.data == "last":
        if not results:
            await query.edit_message_text("لا توجد نتائج مسجلة بعد.")
        else:
            last_5 = results[-5:]
            await query.edit_message_text(f"📈 آخر 5 نتائج:\n{last_5}")
    elif query.data == "add":
        context.user_data["waiting_for_multiplier"] = True
        await query.edit_message_text("✏️ أرسل المضاعف الآن:")
    elif query.data == "predict":
        prediction_text = calculate_prediction(results)
        await query.edit_message_text(prediction_text)
    elif query.data == "undo":
        if not results:
            await query.edit_message_text("لا توجد نتائج لحذفها.")
        else:
            results.pop()
            save_results(results)
            await query.edit_message_text("✅ تم حذف آخر جولة.")
    elif query.data == "analyze":
        if len(results) < 5:
            await query.edit_message_text("⚠️ أحتاج إلى 5 نتائج على الأقل.")
        else:
            analysis = get_stats(results) + "\n\n" + calculate_prediction(results)
            await query.edit_message_text(analysis)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for_multiplier"):
        try:
            multiplier = float(update.message.text)
            if multiplier <= 0:
                await update.message.reply_text("❌ أدخل رقم أكبر من صفر.")
                return
            results = load_results()
            results.append(multiplier)
            save_results(results)
            context.user_data["waiting_for_multiplier"] = False
            await update.message.reply_text(f"✅ تم تسجيل {multiplier}x")
            if len(results) >= 5:
                prediction_text = calculate_prediction(results)
                await update.message.reply_text(prediction_text)
        except ValueError:
            await update.message.reply_text("❌ أرسل رقم صحيح.")

async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = load_results()
    if not results:
        await update.message.reply_text("لا توجد نتائج لحذفها.")
        return
    results.pop()
    save_results(results)
    await update.message.reply_text("✅ تم حذف آخر جولة.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_results([])
    await update.message.reply_text("✅ تم الحذف والبدء من جديد.")

def run_bot():
    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("undo", undo_command))
    app_bot.add_handler(CommandHandler("clear", clear_command))
    app_bot.add_handler(CallbackQueryHandler(buttons))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_bot.run_polling()

@app.route("/")
def home():
    return "Bot is running!"

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
