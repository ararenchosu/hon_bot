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

# ===== 全機能読み込み =====
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave

@bot.event
async def on_ready():
    # ✅ 永続View登録
    try:
        bot.add_view(othello_panel.OthelloPanelView())
        bot.add_view(call_panel.CallPanelView(bot))  # ← bot渡す
    except Exception as e:
        print(f"⚠️ View登録: {e}")

    # ✅ コマンド登録（引数の形に注意）
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)  # ← tree, bot の順で2つ渡す
    await welcome_leave.setup(bot)

    # ✅ ギルド同期
    GUILD_ID = 1542788841465978880
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    
    print(f"✅ 起動完了：{bot.user}")
    print("✅ 全コマンド同期完了")

bot.run(BOT_TOKEN)
