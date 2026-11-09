import os
import asyncio
import threading
from flask import Flask
from hydrogram import Client, filters
from hydrogram.types import ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# Credentials
API_ID = 37940634
API_HASH = "6c9bf207b1eba747bb4ae29d8b8fa8e8"
BOT_TOKEN = "9222539598:AAFW3n-K_FYVyzwgpb8ApMYDVRdH1Er8oJM"
DUMP_CHANNEL = -1004474620195

# Render Free Port Binding
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Caption se hatane wale words
REMOVE_WORDS = [
    "Downloaded by UV",
    "Downloaded by uv",
    "Download by UV",
    "Download by uv",
    "@old_channel",
    "Join our group",
    "https://t.me/"
]

# Batch Mapping
BATCH_DB = {
    "101": {
        "title": "Batch 01 Demo",
        "subjects": {
            "Subject 1": (1, 10),
            "Subject 2": (11, 20)
        }
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


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply_text(
        "👋 **Welcome!**\n\nBatch upload karne ke liye `/upload` command use karein."
    )


@app.on_message(filters.command("upload") & filters.private)
async def upload_cmd(client, message):
    user_states[message.chat.id] = {}
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

    # Step 1: Batch Code
    if "batch" not in state:
        if text not in BATCH_DB:
            await message.reply_text("❌ Galat batch code! Sahi code bhejo:", reply_markup=ForceReply(True))
            return
        state["batch"] = text
        await message.reply_text(
            "✅ Batch Select ho gaya!\n\nTarget **Channel/Group ID** bhejo (`-100...` format me):\n*(Dhyan rahe bot wahan Admin ho)*",
            reply_markup=ForceReply(True)
        )
        return

    # Step 2: Target ID Verification
    if "target_chat" not in state:
        try:
            target_id = int(text)
            chat = await client.get_chat(target_id)
            bot_member = await client.get_chat_member(target_id, "me")

            if not bot_member.privileges or not bot_member.privileges.can_post_messages:
                await message.reply_text("❌ Bot ke paas Admin/Post permission nahi hai. Rights dekar dobara ID bhejo:")
                return

            state["target_chat"] = target_id
            state["is_forum"] = getattr(chat, "is_forum", False)
            state["chat_username"] = chat.username

        except Exception:
            await message.reply_text("❌ Invalid ID ya bot wahan Admin nahi hai. Sahi ID bhejo:", reply_markup=ForceReply(True))
            return

        await message.reply_text(
            "✅ Target chat verify ho gaya!\n\nCaption me lagane ke liye apna **Name ya Username** bhejo:",
            reply_markup=ForceReply(True)
        )
        return

    # Step 3: Name & Upload Loop
    if "user_name" not in state:
        state["user_name"] = text
        batch_key = state["batch"]
        target_chat = state["target_chat"]
        user_name = state["user_name"]
        is_forum = state["is_forum"]
        chat_username = state["chat_username"]

        batch_info = BATCH_DB[batch_key]
        status_msg = await message.reply_text("🚀 Upload process shuru ho raha hai...")

        index_buttons = []

        for sub_name, (start_id, end_id) in batch_info["subjects"].items():
            thread_id = None

            # Forum/Topics group ho toh Topic banayega
            if is_forum:
                try:
                    topic = await client.create_forum_topic(chat_id=target_chat, title=f"📚 {sub_name}")
                    thread_id = topic.id
                except Exception:
                    thread_id = None

            # Normal Channel/Group me Header Message
            if not thread_id:
                header = await client.send_message(
                    chat_id=target_chat,
                    text=f"━━━━━━━━━━━━━━━━━━━━\n📚 **SUBJECT: {sub_name.upper()}**\n━━━━━━━━━━━━━━━━━━━━"
                )
                if chat_username:
                    jump_url = f"https://t.me/{chat_username}/{header.id}"
                else:
                    clean_cid = str(target_chat).replace("-100", "")
                    jump_url = f"https://t.me/c/{clean_cid}/{header.id}"
                index_buttons.append([InlineKeyboardButton(f"📂 {sub_name}", url=jump_url)])

            # Transfer loop
            for msg_id in range(start_id, end_id + 1):
                try:
                    orig = await client.get_messages(DUMP_CHANNEL, msg_id)
                    if not orig or orig.empty:
                        continue

                    new_caption = clean_caption_text(orig.caption, user_name, batch_info["title"])

                    await client.copy_message(
                        chat_id=target_chat,
                        from_chat_id=DUMP_CHANNEL,
                        message_id=msg_id,
                        caption=new_caption,
                        message_thread_id=thread_id
                    )
                    await asyncio.sleep(2.5)

                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    await client.copy_message(
                        chat_id=target_chat,
                        from_chat_id=DUMP_CHANNEL,
                        message_id=msg_id,
                        caption=new_caption,
                        message_thread_id=thread_id
                    )
                except Exception:
                    continue

        # Normal chat me Index Card pin karna
        if not is_forum and index_buttons:
            try:
                idx_msg = await client.send_message(
                    chat_id=target_chat,
                    text=(
                        f"📌 **BATCH NAVIGATION INDEX**\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎓 **Batch:** `{batch_info['title']}`\n"
                        f"👤 **Access:** {user_name}\n\n"
                        f"Niche button par click karke direct subject par jump karein:"
                    ),
                    reply_markup=InlineKeyboardMarkup(index_buttons)
                )
                await client.pin_chat_message(target_chat, idx_msg.id)
            except Exception:
                pass

        await status_msg.edit_text("🎉 **Batch transfer complete ho gaya!**")
        user_states.pop(uid, None)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
