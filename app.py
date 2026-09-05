import sqlite3
from flask import Flask
from threading import Thread
import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# ==================================================
# ⚙️ إعدادات البوت (تقرأ من المتغيرات البيئية)
# ==================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8805134453:AAFPTagbbngBRj3nKSMy7VD1Uw0Jmo2oabE")
OPERATOR_GROUP_ID = int(os.environ.get("OPERATOR_GROUP_ID", -1003845654719))
DATABASE = "support.db"

# ==================================================
# 🗄️ قاعدة البيانات
# ==================================================

def init_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            topic_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            topic_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            first_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    print("🗄️ قاعدة البيانات جاهزة")

def get_user_topic(user_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT topic_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_user_topic(user_id, topic_id, first_name):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, topic_id, first_name) VALUES (?, ?, ?)", (user_id, topic_id, first_name))
    cursor.execute("INSERT OR REPLACE INTO topics (topic_id, user_id, first_name) VALUES (?, ?, ?)", (topic_id, user_id, first_name))
    conn.commit()
    conn.close()

def get_user_from_topic(topic_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM topics WHERE topic_id = ?", (topic_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

# ==================================================
# 👋 أوامر البوت
# ==================================================

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 مرحباً بك في صفور، {user.first_name}!\n\nأرسل رسالتك وسيتم تحويلها إلى فريق الدعم."
    )

async def handle_message(update: Update, context: CallbackContext):
    user = update.effective_user
    text = update.message.text
    if not text:
        return
    user_id = user.id
    first_name = user.first_name or "مستخدم"
    try:
        topic_id = get_user_topic(user_id)
        if not topic_id:
            topic_name = f"تذكرة من {first_name} (ID: {user_id})"
            topic = await context.bot.create_forum_topic(chat_id=OPERATOR_GROUP_ID, name=topic_name)
            topic_id = topic.message_thread_id
            save_user_topic(user_id, topic_id, first_name)
            await context.bot.send_message(chat_id=OPERATOR_GROUP_ID, message_thread_id=topic_id,
                text=f"📩 <b>تذكرة دعم جديدة</b>\n\n👤 الاسم: {first_name}\n🆔 ID: <code>{user_id}</code>\n\n📝 الرسالة:\n{text}",
                parse_mode="HTML")
        else:
            try:
                await context.bot.reopen_forum_topic(chat_id=OPERATOR_GROUP_ID, message_thread_id=topic_id)
            except Exception:
                pass
            await context.bot.send_message(chat_id=OPERATOR_GROUP_ID, message_thread_id=topic_id,
                text=f"👤 <b>{first_name}</b>\n🆔 <code>{user_id}</code>\n\n📝 {text}",
                parse_mode="HTML")
        await update.message.reply_text("✅ تم إرسال رسالتك إلى فريق الدعم.\n\nسنرد عليك قريباً.")
    except Exception as e:
        print(f"❌ خطأ في handle_message: {e}")
        await update.message.reply_text("⚠️ حدث خطأ في إرسال رسالتك.\nيرجى المحاولة لاحقاً.")

async def handle_group_reply(update: Update, context: CallbackContext):
    message = update.message
    if not message:
        return
    if update.effective_chat.id != OPERATOR_GROUP_ID:
        return
    topic_id = message.message_thread_id
    if not topic_id:
        return
    user_id = get_user_from_topic(topic_id)
    if not user_id:
        print(f"⚠️ لم يتم العثور على مستخدم للـTopic {topic_id}")
        return
    reply_text = message.text
    if not reply_text:
        return
    try:
        await context.bot.send_message(chat_id=user_id,
            text=f"📩 <b>رد من فريق الدعم</b>\n\n{reply_text}",
            parse_mode="HTML")
        print(f"✅ رد Topic {topic_id} → المستخدم {user_id}")
    except Exception as e:
        print(f"❌ خطأ في إرسال الرد: {e}")

# ==================================================
# 🚀 تشغيل البوت في main thread
# ==================================================

async def run_bot():
    init_database()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(OPERATOR_GROUP_ID), handle_group_reply))
    print("🤖 البوت يعمل...")
    # تجنب استخدام إشارات الخروج التي تسبب خطأ في Railway
    await app.run_polling(stop_signals=None)

# ==================================================
# 🌐 خادم Flask (لإبقاء البوت مستيقظاً)
# ==================================================

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "🤖 البوت يعمل 24/7"

@app_flask.route('/health')
def health():
    return "OK"

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# ==================================================
# ▶️ تشغيل الكل
# ==================================================

if __name__ == '__main__':
    # تشغيل Flask في Thread منفصل
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # تشغيل البوت في الخيط الرئيسي باستخدام asyncio
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("🛑 إيقاف البوت...")