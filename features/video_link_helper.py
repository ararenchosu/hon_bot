import discord
from discord import app_commands
import re

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# 動画リンクと判断するパターン
VIDEO_PATTERNS = [
    r"\.mp4",
    r"discord\.com/channels/\d+/\d+/\d+",
    r"discord-attachments\.com",
]

def is_video_link(text: str):
    text = text.lower()
    for pat in VIDEO_PATTERNS:
        if re.search(pat, text):
            return True
    return False

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()
    
    # リンクが含まれる場合
    if is_video_link(content):
        await message.add_reaction("✅")
        
        # ここで「新しい形」に整形して返す
        # （必要に応じてフォーマットを変更してOK）
        reply = (
            "🎬 動画リンクを受信しました！\n"
            f"🔗 元のリンク：{content}\n"
            f"✨ コピー用リンク：`{content}`\n\n"
            "💡 上記をコピーしてお使いください！"
        )
        await message.channel.send(reply)

@bot.event
async def on_ready():
    print(f"✅ 動画リンク整理Bot 起動：{bot.user}")
