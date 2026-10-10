import discord
from discord import app_commands
import os

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    print("❌ 環境変数 DISCORD_TOKEN が設定されていません")
    exit(1)
print(f"✅ トークン読み込み完了：{BOT_TOKEN[:10]}...")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ✅ 両方読み込む
import features.othello as othello
import features.othello_panel as othello_panel

@bot.event
async def on_ready():
    bot.add_view(othello_panel.OthelloPanelView())
    
    await othello.setup(tree)       # ← 戻す
    await othello_panel.setup(tree)

    GUILD_ID = 【ここにサーバーID】
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ 起動完了：{bot.user}")
    print("✅ コマンド同期完了")

bot.run(BOT_TOKEN)
