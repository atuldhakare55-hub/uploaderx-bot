import os
import asyncio
import threading
from flask import Flask
from hydrogram import Client, filters
from hydrogram.types import ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# ================= CONFIGURATION =================
API_ID = 37940634
API_HASH = "6c9bf207b1eba747bb4ae29d8b8fa8e8"
BOT_TOKEN = "9222539598:AAFW3n-K_FYVyzwgpb8ApMYDVRdH1Er8oJM"
DUMP_CHANNEL = -1004474620195

# ================= FLASK KEEP-ALIVE SERVER =================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Server is Online 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# ================= SYSTEM STORAGE =================
# Pehli baar jo /setowner command chalayega, wo permanent OWNER ban jayega
OWNER_ID = None

# Premium Users List
PREMIUM_USERS = set()

# Caption Se Hatane Wale Words
REMOVE_WORDS = [
    "Downloaded by UV",
    "Downloaded by uv",
    "Download by UV",
    "Download by uv",
    "@old_channel",
    "Join our group",
    "https://t.me/"
]

# Batches: { "101": {"title": "Maths Special", "start_id": 1, "end_id": 10} }
BATCH_DB = {
    "101": {
        "title": "Batch 01 Demo",
        "start_id": 1,
        "end_id": 10
    }
}

app = Client("batch_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_states = {}


def clean_caption_text(caption: str, user_name: str, batch_title: str) -> str:
    text = caption or ""
    for word in REMOVE_WORDS:
        text = text.replace(word, "")
    text = text.strip()
    watermark = f"\n\n━━━━━━━━━━━━━━━━━━━━\n📥 **Downloaded by:** {user_name}\n📚 **Batch:** {batch_title}"
    return text + watermark


# ================= 1. OWNER ONLY COMMANDS =================

@app.on_message(filters.command("setowner") & filters.private)
async def set_owner_cmd(client, message):
    global OWNER_ID
    if OWNER_ID is None:
        OWNER_ID = message.from_user.id
        PREMIUM_USERS.add(OWNER_ID)
        await message.reply_text(f"👑 **Congratulations!** Aap is bot ke **OWNER** set ho gaye hain.\nOwner ID: `{OWNER_ID}`")
    elif message.from_user.id == OWNER_ID:
        await message.reply_text("Aap pehle se hi Owner hain!")
    else:
        await message.reply_text("❌ Owner pehle se set ho chuka hai.")


@app.on_message(filters.command("addpremium") & filters.private)
async def add_prem_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Sirf Owner hi premium users add kar sakta hai.")
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Format: `/addpremium <user_id>`")
    try:
        uid = int(parts[1])
        PREMIUM_USERS.add(uid)
        await message.reply_text(f"✅ User `{uid}` ab **Premium Member** hai!")
    except ValueError:
        await message.reply_text("❌ Invalid ID!")


@app.on_message(filters.command("delpremium") & filters.private)
async def del_prem_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Format: `/delpremium <user_id>`")
    try:
        uid = int(parts[1])
        PREMIUM_USERS.discard(uid)
        await message.reply_text(f"🚫 User `{uid}` ka premium access hata diya gaya.")
    except ValueError:
        await message.reply_text("❌ Invalid ID!")


@app.on_message(filters.command("addword") & filters.private)
async def add_word_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return
    word = message.text.replace("/addword", "").strip()
    if not word:
        return await message.reply_text("Format: `/addword <word_to_remove>`")
    REMOVE_WORDS.append(word)
    await message.reply_text(f"✅ Word blacklist me add ho gaya: `{word}`")


@app.on_message(filters.command("createbatch") & filters.private)
async def create_batch_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return
    # Format: /createbatch 102 Science Batch 1 50
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply_text("Format: `/createbatch <code e.g. 102> <title> <start_id> <end_id>`")
    
    code = parts[1]
    try:
        start_id = int(parts[-2])
        end_id = int(parts[-1])
        title = " ".join(parts[2:-2])
        BATCH_DB[code] = {
            "title": title,
            "start_id": start_id,
            "end_id": end_id
        }
        await message.reply_text(f"✅ **Batch Created!**\nCode: `{code}`\nTitle: `{title}`\nRange: `{start_id}` to `{end_id}`")
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}")


# ================= 2. DUMP CHANNEL ME SIRF OWNER VIDEO DAALEGA =================
@app.on_message((filters.video | filters.document | filters.photo) & filters.private)
async def owner_dump_uploader(client, message):
    # Sirf Owner upload kar sakta hai Dump me
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Sirf Owner Dump channel me video bhej sakta hai.")

    msg = await message.reply_text("⏳ Dump channel me save ho raha hai...")
    try:
        copied = await message.copy(chat_id=DUMP_CHANNEL)
        await msg.edit_text(
            f"✅ **Dump Channel Me Upload Ho Gaya!**\n\n"
            f"🆔 **Dump Message ID:** `{copied.id}`\n\n"
            f"💡 Naya batch banane ke liye use karein:\n"
            f"`/createbatch <batch_code> <title> {copied.id} {copied.id}`"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Dump Upload Error: `{str(e)}`")


# ================= 3. USER UPLOAD FLOW =================

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    if uid == OWNER_ID:
        return await message.reply_text(
            "👑 **Owner Control Panel:**\n\n"
            "• Video bhej kar Dump me daalein (ID mil jayegi)\n"
            "• `/addpremium <id>` - Buyer ko access dein\n"
            "• `/delpremium <id>` - Access hatayein\n"
            "• `/addword <word>` - Caption clean word add karein\n"
            "• `/createbatch <code> <title> <start> <end>` - Batch banayein\n"
            "• `/upload` - Testing ke liye upload shuru karein"
        )
    
    is_prem = "✅ Premium Access Active" if uid in PREMIUM_USERS else "🔒 Access Denied (Contact Owner)"
    await message.reply_text(
        f"👋 **Namaste!**\n\n"
        f"🆔 **Your User ID:** `{uid}`\n"
        f"⭐ **Status:** {is_prem}\n\n"
        f"Batch transfer karne ke liye `/upload` command use karein."
    )


@app.on_message(filters.command("upload") & filters.private)
async def upload_cmd(client, message):
    uid = message.from_user.id
    if uid not in PREMIUM_USERS and uid != OWNER_ID:
        return await message.reply_text(
            "🔒 **Aapke paas access nahi hai!**\n\n"
            f"Access lene ke liye Admin ko apna User ID bhejein:\n👉 `{uid}`"
        )

    user_states[uid] = {}
    batches = "\n".join([f"👉 `{k}` : {v['title']}" for k, v in BATCH_DB.items()])
    await message.reply_text(
        f"📋 **Available Batches:**\n{batches}\n\n**Batch Code bhejo (e.g. 101):**",
        reply_markup=ForceReply(True)
    )


@app.on_message(filters.private & filters.reply)
async def conversation_handler(client, message):
    uid = message.chat.id
    if uid not in user_states:
        return

    state = user_states[uid]
    text = message.text.strip()

    # Step 1: Batch Code Select
    if "batch" not in state:
        if text not in BATCH_DB:
            await message.reply_text("❌ Galat batch code! Sahi code bhejo:", reply_markup=ForceReply(True))
            return
        state["batch"] = text
        await message.reply_text(
            "✅ **Target Channel/Group ID bhejo:**\n\n"
            "⚠️ **Dhyan rahe:** Pehle mujhe (is bot ko) apne target channel/group me **Admin** banayein aur **Post Messages** permission dein.\n\n"
            "Channel ID `-100...` format me bhejein:",
            reply_markup=ForceReply(True)
        )
        return

    # Step 2: Target ID aur Bot Admin Verify
    if "target_chat" not in state:
        try:
            target_id = int(text)
            chat = await client.get_chat(target_id)
            bot_member = await client.get_chat_member(target_id, "me")

            if not bot_member.privileges or not bot_member.privileges.can_post_messages:
                await message.reply_text(
                    "❌ **Bot Admin nahi hai!**\nTarget channel me bot ko Admin banakar 'Post Messages' permission dein aur dobara ID bhejein:",
                    reply_markup=ForceReply(True)
                )
                return

            state["target_chat"] = target_id
            state["is_forum"] = getattr(chat, "is_forum", False)
            state["chat_username"] = chat.username

        except Exception:
            await message.reply_text(
                "❌ **Invalid ID ya bot Admin nahi hai!**\nSahi `-100...` ID bhejein aur bot ko Admin banayein:",
                reply_markup=ForceReply(True)
            )
            return

        await message.reply_text(
            "✅ Target Channel verify ho gaya!\n\n"
            "Caption me **'Downloaded by'** ke aage kya naam/username daalna hai, wo likhkar bhejo:",
            reply_markup=ForceReply(True)
        )
        return

    # Step 3: Name / Username & File Transfer
    if "user_name" not in state:
        state["user_name"] = text
        batch_key = state["batch"]
        target_chat = state["target_chat"]
        user_name = state["user_name"]
        is_forum = state["is_forum"]
        chat_username = state["chat_username"]

        batch_info = BATCH_DB[batch_key]
        status_msg = await message.reply_text("🚀 **Batch transfer shuru ho raha hai...**")

        start_id = batch_info["start_id"]
        end_id = batch_info["end_id"]
        batch_title = batch_info["title"]

        # Channel me Header Message
        try:
            header = await client.send_message(
                chat_id=target_chat,
                text=f"━━━━━━━━━━━━━━━━━━━━\n📚 **BATCH: {batch_title.upper()}**\n━━━━━━━━━━━━━━━━━━━━"
            )
        except Exception:
            pass

        # Loop transfer
        for msg_id in range(start_id, end_id + 1):
            try:
                orig = await client.get_messages(DUMP_CHANNEL, msg_id)
                if not orig or orig.empty:
                    continue

                new_caption = clean_caption_text(orig.caption, user_name, batch_title)

                await client.copy_message(
                    chat_id=target_chat,
                    from_chat_id=DUMP_CHANNEL,
                    message_id=msg_id,
                    caption=new_caption
                )
                await asyncio.sleep(2.5)

            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                await client.copy_message(
                    chat_id=target_chat,
                    from_chat_id=DUMP_CHANNEL,
                    message_id=msg_id,
                    caption=new_caption
                )
            except Exception:
                continue

        await status_msg.edit_text("🎉 **Batch transfer poora ho gaya!**")
        user_states.pop(uid, None)


# ================= RUNNER =================
if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    app.run()
