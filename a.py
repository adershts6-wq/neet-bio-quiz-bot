import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# ================= CONFIG =================
BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 123456789   # ← your Telegram numeric ID
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ================= DATA =================
QUESTIONS = [
    {
        "q": "Human heart has how many chambers?",
        "options": ["2", "3", "4", "5"],
        "answer": 2,
        "explanation": "Human heart has 4 chambers"
    },
    {
        "q": "Unit of heredity is?",
        "options": ["Cell", "Chromosome", "Gene", "DNA"],
        "answer": 2,
        "explanation": "Gene is the unit of heredity"
    },
    {
        "q": "Which hormone regulates blood sugar?",
        "options": ["Adrenaline", "Insulin", "Thyroxine", "Estrogen"],
        "answer": 1,
        "explanation": "Insulin regulates blood glucose level"
    }
]

user_state = {}     # {user_id: {"qno":0,"score":0}}
leaderboard = {}   # {user_id: score}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *NEET Quiz Bot*\n\n"
        "/quiz – Start quiz\n"
        "/score – Your score\n"
        "/leaderboard – Top scores",
        parse_mode="Markdown"
    )

# ================= QUIZ START =================
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_state[uid] = {"qno": 0, "score": 0}
    await send_question(update, context)

# ================= SEND QUESTION =================
async def send_question(update, context):
    uid = update.effective_user.id
    qno = user_state[uid]["qno"]

    if qno >= len(QUESTIONS):
        score = user_state[uid]["score"]
        leaderboard[uid] = score

        await update.effective_message.reply_text(
            f"✅ *Quiz Completed*\n\n"
            f"🎯 Score: *{score}*\n\n"
            f"/leaderboard",
            parse_mode="Markdown"
        )
        return

    q = QUESTIONS[qno]
    buttons = []

    for i, opt in enumerate(q["options"]):
        buttons.append(
            [InlineKeyboardButton(opt, callback_data=str(i))]
        )

    await update.effective_message.reply_text(
        f"Q{qno+1}. {q['q']}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ================= ANSWER HANDLER =================
async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    selected = int(query.data)

    qno = user_state[uid]["qno"]
    correct = QUESTIONS[qno]["answer"]

    if selected == correct:
        user_state[uid]["score"] += 4
        reply = "✅ Correct  (+4)"
    else:
        user_state[uid]["score"] -= 1
        reply = (
            "❌ Wrong  (-1)\n"
            f"✔ Correct answer: {QUESTIONS[qno]['options'][correct]}"
        )

    user_state[uid]["qno"] += 1

    await query.edit_message_text(
        reply + "\n\n📘 " + QUESTIONS[qno]["explanation"]
    )

    await send_question(query, context)

# ================= SCORE =================
async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sc = user_state.get(uid, {}).get("score", 0)
    await update.message.reply_text(f"🎯 Your Score: {sc}")

# ================= LEADERBOARD =================
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("No attempts yet")
        return

    text = "🏆 *Leaderboard*\n\n"
    sorted_lb = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)

    for i, (uid, sc) in enumerate(sorted_lb[:10], start=1):
        text += f"{i}. User {uid} — {sc}\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ================= BROADCAST (ADMIN) =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /broadcast message")
        return

    sent = 0
    for uid in user_state:
        try:
            await context.bot.send_message(uid, msg)
            sent += 1
        except:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent} users")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(answer))

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()