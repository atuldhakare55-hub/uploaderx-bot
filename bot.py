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

# ================= FLASK KEEP-ALIVE SERVER =================
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Server is Online 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, use_reloader=False)

# ================= SYSTEM STORAGE =================
OWNER_ID = None
PREMIUM_USERS = set()

# Batches: { "batch_1": {"title": "Maths", "start_id": 10, "end_id": 25} }
BATCH_DB = {}
batch_counter = 101

app = Client("batch_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# States
user_states = {}
owner_batch_states = {}


def parse_telegram_link(link: str):
    """
    Link formats supported:
    1. Public: https://t.me/channel_username/123
    2. Private: https://t.me/c/1234567890/123
    """
    link = link.strip()
    c_match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if c_match:
        chat_id = int("-100" + c_match.group(1))
        msg_id = int(c_match.group(2))
        return chat_id, msg_id

    pub_match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if pub_match:
        chat_id = pub_match.group(1)
        msg_id = int(pub_match.group(2))
        return chat_id, msg_id

    return None, None


# ================= 1. OWNER MANAGEMENT =================

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


# ================= 2. OWNER DUMP BATCH WORKFLOW (/uploaddbbatch) =================

@app.on_message(filters.command("uploaddbbatch") & filters.private)
async def upload_db_batch_cmd(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("❌ Sirf Owner batch dump me upload kar sakta hai.")

    owner_batch_states[message.chat.id] = {}
    await message.reply_text(
        "🔗 **Pehli (First) Post ka Link bhejo:**\n\n"
        "• Public link: `https://t.me/channel/10`\n"
        "• Private link: `https://t.me/c/xxxxxx/10` *(Dhyan rahe private me bot Admin ho)*",
        reply_markup=ForceReply(True)
    )


# ================= 3. USER BATCH TRANSFER WORKFLOW (/upload) =================

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    uid = message.from_user.id
    if uid == OWNER_ID:
        return await message.reply_text(
            "👑 **Owner Control Panel:**\n\n"
            "• `/uploaddbbatch` - Channel se Dump me batch upload karein\n"
            "• `/addpremium <id>` - Buyer ko access dein\n"
            "• `/delpremium <id>` - Access hatayein\n"
            "• `/batches` - Current active batch codes dekhein\n"
            "• `/upload` - Batch transfer test karein"
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


# ================= 4. CENTRAL REPLY CONVERSATION HANDLER =================

@app.on_message(filters.private & filters.reply)
async def reply_conversation_handler(client, message):
    uid = message.chat.id
    text = message.text.strip()

    # --- OWNER DB BATCH UPLOAD HANDLER ---
    if uid in owner_batch_states and uid == OWNER_ID:
        state = owner_batch_states[uid]

        # Step 1: First Link
        if "first_link" not in state:
            chat_id, msg_id = parse_telegram_link(text)
            if not chat_id:
                return await message.reply_text("❌ Galat link format. Sahi link bhejo:", reply_markup=ForceReply(True))
            state["source_chat"] = chat_id
            state["start_id"] = msg_id
            state["first_link"] = text
            await message.reply_text("🔗 **Aakhri (Last) Post ka Link bhejo:**", reply_markup=ForceReply(True))
            return

        # Step 2: Last Link
        if "last_link" not in state:
            chat_id, msg_id = parse_telegram_link(text)
            if not chat_id or chat_id != state["source_chat"]:
                return await message.reply_text("❌ Link galat hai ya channel match nahi hua. Same channel ki last post link bhejo:", reply_markup=ForceReply(True))
            if msg_id < state["start_id"]:
                return await message.reply_text("❌ Last post ID pehli post se badi honi chahiye. Dobara bhejo:", reply_markup=ForceReply(True))
            state["end_id"] = msg_id
            state["last_link"] = text
            await message.reply_text(
                "✏️ **Batch ka Title/Name bhejo (e.g. Physics Crash Course):**",
                reply_markup=ForceReply(True)
            )
            return

        # Step 3: Batch Title
        if "batch_title" not in state:
            state["batch_title"] = text
            await message.reply_text(
                "🔄 **Caption Replacement Word bhejo:**\n\n"
                "Format: `Old Word -> New Word`\n"
                "*(Agar sirf word hatana hai to likho: `Downloaded by uv -> `)*\n"
                "*(Agar koi word replace nahi karna toh `skip` likh do)*",
                reply_markup=ForceReply(True)
            )
            return

        # Step 4: Word Replacement & Auto-Upload to Dump
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

                    # Caption replacement
                    caption = src_msg.caption or ""
                    if old_word and old_word in caption:
                        caption = caption.replace(old_word, new_word)

                    # Dump me copy
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
                    f"🔑 **Batch Code (User ko dene ke liye):** `{batch_code}`\n"
                    f"📊 **Total Files Uploaded:** `{uploaded_count}`\n"
                    f"📍 **Dump IDs:** `{dump_first_id}` to `{dump_last_id}`\n\n"
                    f"Ab koi bhi user `/upload` command dekar ye code `{batch_code}` dalega to ye batch transfer ho jayega!"
                )
            else:
                await progress_msg.edit_text("❌ Koi bhi message transfer nahi ho paya. Channel permissions check karein.")

            owner_batch_states.pop(uid, None)
            return

    # --- USER BATCH TRANSFER HANDLER ---
    if uid in user_states:
        state = user_states[uid]

        # Step 1: Batch Code
        if "batch" not in state:
            if text not in BATCH_DB:
                return await message.reply_text("❌ Galat batch code! Sahi code bhejo:", reply_markup=ForceReply(True))
            state["batch"] = text
            await message.reply_text(
                "✅ **Target Channel/Group ID bhejo:**\n\n"
                "⚠️ **Zaroori:** Bot ko pehle target channel/group me **Admin** banayein with 'Post Messages' rights.\n\n"
                "ID `-100...` format me bhejein:",
                reply_markup=ForceReply(True)
            )
            return

        # Step 2: Target Verification
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

        # Step 3: Name & Transfer to Target
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
if __name__ == "__main__":
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    app.run()
