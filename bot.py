import os
import re
import asyncio
import threading
from flask import Flask
from hydrogram import Client, filters
from hydrogram.types import ForceReply
from hydrogram.errors import FloodWait

# ================= CONFIGURATION =================
API_ID = 37940634
API_HASH = "6c9bf207b1eba747bb4ae29d8b8fa8e8"
BOT_TOKEN = "9222539598:AAFW3n-K_FYVyzwgpb8ApMYDVRdH1Er8oJM"
DUMP_CHANNEL = -1004474620195

OWNER_ID = None
PREMIUM_USERS = set()
BATCH_DB = {}
batch_counter = 101

user_states = {}
owner_batch_states = {}

# Telegram Bot Client
app = Client("batch_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ================= FLASK KEEP-ALIVE SERVER =================
web_app = Flask(__name__)

@web_app.route('/')
@web_app.route('/health')
def home():
    return "Bot Server is Online 24/7!", 200

# ================= HELPER FUNCTIONS =================
def parse_public_link(link: str):
    link = link.strip()
    pub_match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if pub_match and not link.startswith("https://t.me/c/"):
        return pub_match.group(1), int(pub_match.group(2))
    return None, None

# ================= OWNER COMMANDS =================
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
        return await message.reply_text("❌ Sirf Owner premium add kar sakta hai.")
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

# ================= BATCH DUMP WORKFLOW (/uploaddbbatch) =================
@app.on_message(filters.command("uploaddbbatch") & filters.private)
async def upload_db_batch_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Sirf Owner batch dump me upload kar sakta hai.")

    owner_batch_states[message.chat.id] = {}
    await message.reply_text(
        "🔗 **Public Channel ki Pehli (First) Post ka Link bhejo:**\n\n"
        "*(Example: `https://t.me/mychannel/10`)*",
        reply_markup=ForceReply(True)
    )

# ================= USER WORKFLOW =================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    if uid == OWNER_ID:
        return await message.reply_text(
            "👑 **Owner Control Panel:**\n\n"
            "• `/uploaddbbatch` - Public Channel se Dump me batch upload karein\n"
            "• `/addpremium <id>` - Buyer ko access dein\n"
            "• `/delpremium <id>` - Access hatayein\n"
            "• `/batches` - Current active batch codes dekhein\n"
            "• `/upload` - Batch transfer karein"
        )
    is_prem = "✅ Premium Access Active" if uid in PREMIUM_USERS else "🔒 Access Denied"
    await message.reply_text(
        f"👋 **Namaste!**\n\n"
        f"🆔 **Your User ID:** `{uid}`\n"
        f"⭐ **Status:** {is_prem}\n\n"
        f"Batch transfer karne ke liye `/upload` command dein."
    )

@app.on_message(filters.command("batches") & filters.private)
async def list_batches_cmd(client, message):
    if not BATCH_DB:
        return await message.reply_text("ℹ️ Filhal koi batch available nahi hai.")
    txt = "📋 **Available Batches:**\n\n"
    for code, data in BATCH_DB.items():
        txt += f"👉 Code: `{code}` | Title: **{data['title']}** (Dump IDs: {data['start_id']} to {data['end_id']})\n"
    await message.reply_text(txt)

@app.on_message(filters.command("upload") & filters.private)
async def upload_cmd(client, message):
    uid = message.from_user.id
    if uid not in PREMIUM_USERS and uid != OWNER_ID:
        return await message.reply_text(
            "🔒 **Aapke paas access nahi hai!**\n\n"
            f"Access lene ke liye Admin ko apna User ID bhejein:\n👉 `{uid}`"
        )

    if not BATCH_DB:
        return await message.reply_text("❌ Filhal koi batch upload nahi hua hai.")

    user_states[uid] = {}
    batches = "\n".join([f"👉 `{k}` : {v['title']}" for k, v in BATCH_DB.items()])
    await message.reply_text(
        f"📋 **Available Batches:**\n{batches}\n\n**Batch Code bhejo:**",
        reply_markup=ForceReply(True)
    )

# ================= CENTRAL REPLY CONVERSATION HANDLER =================
@app.on_message(filters.private & filters.reply)
async def reply_conversation_handler(client, message):
    uid = message.chat.id
    text = message.text.strip()

    # 1. OWNER DUMP BATCH HANDLER
    if uid in owner_batch_states and uid == OWNER_ID:
        state = owner_batch_states[uid]

        # First Link
        if "first_link" not in state:
            chat_user, msg_id = parse_public_link(text)
            if not chat_user:
                return await message.reply_text("❌ Public link bhejo (format: `https://t.me/channel/10`):", reply_markup=ForceReply(True))
            state["source_chat"] = chat_user
            state["start_id"] = msg_id
            state["first_link"] = text
            await message.reply_text("🔗 **Aakhri (Last) Post ka Link bhejo:**", reply_markup=ForceReply(True))
            return

        # Last Link
        if "last_link" not in state:
            chat_user, msg_id = parse_public_link(text)
            if not chat_user or chat_user != state["source_chat"]:
                return await message.reply_text("❌ Same public channel ka last post link bhejo:", reply_markup=ForceReply(True))
            if msg_id < state["start_id"]:
                return await message.reply_text("❌ Last post ID pehli post se badi honi chahiye. Dobara bhejo:", reply_markup=ForceReply(True))
            state["end_id"] = msg_id
            state["last_link"] = text
            await message.reply_text(
                "✏️ **Batch ka Title/Name bhejo (e.g. Physics Batch):**",
                reply_markup=ForceReply(True)
            )
            return

        # Title
        if "batch_title" not in state:
            state["batch_title"] = text
            await message.reply_text(
                "🔄 **Caption Replacement Word bhejo:**\n\n"
                "Format: `Old Word -> New Word`\n"
                "*(Agar koi word replace nahi karna toh `skip` likhein)*",
                reply_markup=ForceReply(True)
            )
            return

        # Dump Process Execution
        if "replace_done" not in state:
            old_word, new_word = "", ""
            if text.lower() != "skip":
                if "->" in text:
                    parts = text.split("->")
                    old_word = parts[0].strip()
                    new_word = parts[1].strip()
                else:
                    old_word = text.strip()
                    new_word = ""

            source_chat = state["source_chat"]
            start_id = state["start_id"]
            end_id = state["end_id"]
            batch_title = state["batch_title"]

            progress_msg = await message.reply_text("⏳ **Batch Dump Channel me upload hona shuru ho gaya hai...**")
            
            dump_first_id = None
            dump_last_id = None
            uploaded_count = 0

            for m_id in range(start_id, end_id + 1):
                try:
                    src_msg = await client.get_messages(source_chat, m_id)
                    if not src_msg or src_msg.empty:
                        continue

                    caption = src_msg.caption or ""
                    if old_word and old_word in caption:
                        caption = caption.replace(old_word, new_word)

                    copied = await client.copy_message(
                        chat_id=DUMP_CHANNEL,
                        from_chat_id=source_chat,
                        message_id=m_id,
                        caption=caption
                    )

                    if dump_first_id is None:
                        dump_first_id = copied.id
                    dump_last_id = copied.id
                    uploaded_count += 1

                    await asyncio.sleep(2)

                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    continue

            global batch_counter
            batch_code = f"batch_{batch_counter}"
            batch_counter += 1

            if dump_first_id and dump_last_id:
                BATCH_DB[batch_code] = {
                    "title": batch_title,
                    "start_id": dump_first_id,
                    "end_id": dump_last_id
                }
                await progress_msg.edit_text(
                    f"🎉 **Batch Successfully Dump Me Store Ho Gaya!**\n\n"
                    f"📦 **Batch Title:** `{batch_title}`\n"
                    f"🔑 **Batch Code:** `{batch_code}`\n"
                    f"📊 **Total Files Uploaded:** `{uploaded_count}`\n"
                    f"📍 **Dump IDs:** `{dump_first_id}` to `{dump_last_id}`"
                )
            else:
                await progress_msg.edit_text("❌ Koi message transfer nahi ho paya. Channel check karein.")

            owner_batch_states.pop(uid, None)
            return

    # 2. USER UPLOAD FLOW
    if uid in user_states:
        state = user_states[uid]

        if "batch" not in state:
            if text not in BATCH_DB:
                return await message.reply_text("❌ Galat batch code! Sahi code bhejo:", reply_markup=ForceReply(True))
            state["batch"] = text
            await message.reply_text(
                "✅ **Target Channel/Group ID bhejo:**\n\n"
                "⚠️ Bot ko target channel/group me **Admin** banayein with 'Post Messages' rights.\n"
                "ID `-100...` format me bhejein:",
                reply_markup=ForceReply(True)
            )
            return

        if "target_chat" not in state:
            try:
                target_id = int(text)
                chat = await client.get_chat(target_id)
                bot_member = await client.get_chat_member(target_id, "me")

                if not bot_member.privileges or not bot_member.privileges.can_post_messages:
                    return await message.reply_text(
                        "❌ Bot Admin nahi hai ya Post permission nahi hai! Admin banakar dobara ID bhejo:",
                        reply_markup=ForceReply(True)
                    )
                state["target_chat"] = target_id
            except Exception:
                return await message.reply_text("❌ Invalid ID ya bot wahan Admin nahi hai. Sahi ID bhejo:", reply_markup=ForceReply(True))

            await message.reply_text(
                "✅ Target Channel verify ho gaya!\n\n"
                "Caption me **'Downloaded by'** ke aage kya naam/username lagana hai, wo bhejo:",
                reply_markup=ForceReply(True)
            )
            return

        if "user_name" not in state:
            state["user_name"] = text
            batch_key = state["batch"]
            target_chat = state["target_chat"]
            user_name = state["user_name"]

            batch_info = BATCH_DB[batch_key]
            status_msg = await message.reply_text("🚀 **Batch target channel me transfer ho raha hai...**")

            start_id = batch_info["start_id"]
            end_id = batch_info["end_id"]
            batch_title = batch_info["title"]

            for msg_id in range(start_id, end_id + 1):
                try:
                    orig = await client.get_messages(DUMP_CHANNEL, msg_id)
                    if not orig or orig.empty:
                        continue

                    caption = orig.caption or ""
                    clean_cap = caption + f"\n\n━━━━━━━━━━━━━━━━━━━━\n📥 **Downloaded by:** {user_name}\n📚 **Batch:** {batch_title}"

                    await client.copy_message(
                        chat_id=target_chat,
                        from_chat_id=DUMP_CHANNEL,
                        message_id=msg_id,
                        caption=clean_cap
                    )
                    await asyncio.sleep(2.5)

                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    await client.copy_message(
                        chat_id=target_chat,
                        from_chat_id=DUMP_CHANNEL,
                        message_id=msg_id,
                        caption=clean_cap
                    )
                except Exception:
                    continue

            await status_msg.edit_text("🎉 **Batch transfer complete ho gaya!**")
            user_states.pop(uid, None)


# ================= RUNNER =================
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Starting Telegram Bot on Main Thread...")
    app.run()
