import json, random, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
QUESTIONS_FILE = "questions.json"
STATS_FILE = "stats.json"
# =========================================

# ---------- LOAD / SAVE ----------
def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file) as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

QUESTIONS = load_json(QUESTIONS_FILE, {"11": {}, "12": {}})
STATS = load_json(STATS_FILE, {"users": [], "attempts": {}})
user_state = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in STATS["users"]:
        STATS["users"].append(uid)
        save_json(STATS_FILE, STATS)

    kb = [
        [InlineKeyboardButton("Class 11 Biology", callback_data="class_11")],
        [InlineKeyboardButton("Class 12 Biology", callback_data="class_12")]
    ]
    await update.message.reply_text(
        "🧬 NEET Biology Quiz Bot",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= USERS COUNT =================
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(f"👥 Total users: {len(STATS['users'])}")

# ================= BROADCAST =================
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    user_state[update.effective_user.id] = {"mode": "broadcast"}
    await update.message.reply_text("📢 Send message to broadcast:")

# ================= BULK ADD =================
async def bulkadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    user_state[update.effective_user.id] = {"mode": "bulk"}
    await update.message.reply_text(
        "Paste bulk questions\n"
        "First line: Class | Chapter\n\n"
        "Q:\nA)\nB)\nC)\nD)\nANS:"
    )

# ================= TEXT ROUTER =================
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_state:
        return

    st = user_state[uid]
    text = update.message.text.strip()

    # ---------- BROADCAST ----------
    if st.get("mode") == "broadcast":
        sent = 0
        for u in STATS["users"]:
            try:
                await context.bot.send_message(u, text)
                sent += 1
            except:
                pass
        del user_state[uid]
        return await update.message.reply_text(f"✅ Message sent to {sent} users")

    # ---------- BULK ADD ----------
    if st.get("mode") == "bulk":
        lines = text.splitlines()
        cls, chapter = [x.strip() for x in lines[0].split("|")]
        QUESTIONS.setdefault(cls, {}).setdefault(chapter, [])

        i = 1
        count = 0
        while i < len(lines):
            if lines[i].startswith("Q:"):
                q = lines[i][2:].strip()
                opts = [
                    lines[i+1][3:].strip(),
                    lines[i+2][3:].strip(),
                    lines[i+3][3:].strip(),
                    lines[i+4][3:].strip()
                ]
                ans = {"A":0,"B":1,"C":2,"D":3}[lines[i+5].split(":")[1].strip()]
                QUESTIONS[cls][chapter].append({
                    "q": q,
                    "options": opts,
                    "answer": ans
                })
                count += 1
                i += 6
            else:
                i += 1

        save_json(QUESTIONS_FILE, QUESTIONS)
        del user_state[uid]
        return await update.message.reply_text(f"✅ {count} questions added")

    # ---------- REPORT AFTER EXAM ----------
    if st.get("reporting") is not None:
        idx = st["reporting"]
        qdata = st["qs"][idx]

        msg = (
            "🚨 Question Report\n\n"
            f"User ID: {uid}\n"
            f"Class: {st['class']}\n"
            f"Chapter: {st['chapter']}\n\n"
            f"Question:\n{qdata['q']}\n\n"
            f"Reason:\n{text}"
        )
        await context.bot.send_message(ADMIN_ID, msg)
        st["reporting"] = None
        return await update.message.reply_text("✅ Report sent to admin")

# ================= QUIZ FLOW =================
async def class_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    user_state[q.from_user.id] = {"class": q.data.split("_")[1]}
    kb = [[InlineKeyboardButton(c, callback_data=f"ch_{c}")]
          for c in QUESTIONS[user_state[q.from_user.id]["class"]]]
    await q.edit_message_text("Select Chapter:", reply_markup=InlineKeyboardMarkup(kb))

async def chapter_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    ch = q.data.replace("ch_","")
    cls = user_state[uid]["class"]

    total = len(QUESTIONS[cls][ch])
    user_state[uid]["chapter"] = ch

    btns = []
    for n in [10,20,30,40,50]:
        if n <= total:
            btns.append([InlineKeyboardButton(f"{n} Questions", callback_data=f"qcount_{n}")])

    await q.edit_message_text(
        f"📘 {ch}\nTotal questions: {total}\nSelect number:",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def qcount_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    user_state[uid]["q_limit"] = int(q.data.replace("qcount_",""))
    await q.edit_message_text(
        "▶️ Start test?",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Start", callback_data="start_test")]]
        )
    )

async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    cls = user_state[uid]["class"]
    ch = user_state[uid]["chapter"]
    limit = user_state[uid]["q_limit"]

    all_qs = QUESTIONS[cls][ch]
    user_state[uid].update({
        "qs": random.sample(all_qs, limit),
        "qno": 0,
        "score": 0,
        "answers": []
    })
    await send_q(q, uid)

async def send_q(q, uid):
    st = user_state[uid]
    if st["qno"] >= len(st["qs"]):
        st["review_index"] = 0
        return await show_review(q, uid)

    cur = st["qs"][st["qno"]]
    kb = [[InlineKeyboardButton(o, callback_data=f"a_{i}")]
          for i,o in enumerate(cur["options"])]
    await q.edit_message_text(cur["q"], reply_markup=InlineKeyboardMarkup(kb))

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    st = user_state[uid]

    selected = int(q.data.split("_")[1])
    correct = st["qs"][st["qno"]]["answer"]

    st["answers"].append(selected)
    st["score"] += 4 if selected == correct else -1
    st["qno"] += 1
    await send_q(q, uid)

# ================= ANSWER REVIEW =================
async def show_review(q, uid):
    st = user_state[uid]
    i = st["review_index"]

    if i >= len(st["qs"]):
        return await show_leaderboard(q, uid)

    qdata = st["qs"][i]
    ua = st["answers"][i]
    ca = qdata["answer"]

    text = (
        f"Q{i+1}. {qdata['q']}\n\n"
        f"Your answer: {qdata['options'][ua]} {'✅' if ua==ca else '❌'}\n"
        f"Correct answer: {qdata['options'][ca]} ✅"
    )

    kb = [
        [InlineKeyboardButton("🚩 Report", callback_data=f"report_{i}")],
        [InlineKeyboardButton("Next ▶️", callback_data="review_next")]
    ]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def review_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    user_state[uid]["review_index"] += 1
    await show_review(q, uid)

async def report_after_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    idx = int(q.data.replace("report_",""))
    user_state[uid]["reporting"] = idx
    await q.message.reply_text("✍️ Type the issue with this question:")

# ================= LEADERBOARD =================
async def show_leaderboard(q, uid):
    st = user_state[uid]
    key = f"{st['class']}|{st['chapter']}"

    STATS["attempts"].setdefault(key, []).append(
        {"uid": uid, "score": st["score"]}
    )
    save_json(STATS_FILE, STATS)

    scores = sorted(STATS["attempts"][key], key=lambda x: x["score"], reverse=True)
    rank = next(i+1 for i,v in enumerate(scores) if v["uid"] == uid)

    board = "\n".join([f"{i+1}. {v['score']}" for i,v in enumerate(scores[:5])])

    await q.edit_message_text(
        f"🏁 Test Completed\n\n"
        f"Score: {st['score']}\n"
        f"Students: {len(scores)}\n"
        f"Your Rank: {rank}\n\n"
        f"🏆 Leaderboard\n{board}"
    )

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("bulkadd", bulkadd))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_handler(CallbackQueryHandler(class_select, pattern="^class_"))
    app.add_handler(CallbackQueryHandler(chapter_select, pattern="^ch_"))
    app.add_handler(CallbackQueryHandler(qcount_select, pattern="^qcount_"))
    app.add_handler(CallbackQueryHandler(start_test, pattern="^start_test$"))
    app.add_handler(CallbackQueryHandler(answer, pattern="^a_"))
    app.add_handler(CallbackQueryHandler(review_next, pattern="^review_next$"))
    app.add_handler(CallbackQueryHandler(report_after_exam, pattern="^report_"))

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()