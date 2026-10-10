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
    # View登録（永続ボタン）
    try:
        bot.add_view(othello_panel.OthelloPanelView())
        # 各パネルのViewも同様に登録
        # bot.add_view(auth_panel.AuthPanelView())
        # bot.add_view(role_panel.RoleGivePanelView())
        # bot.add_view(revoke_panel.RoleRemovePanelView())
        # bot.add_view(call_panel.CallPanelView())
    except Exception as e:
        print(f"⚠️ View登録スキップ: {e}")

    # 各機能のコマンド登録
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree)
    await welcome_leave.setup(bot)  # 入退出通知

    # ✅ ギルド同期（即時反映）
    GUILD_ID = 1542788841465978880
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    
    print(f"✅ 起動完了：{bot.user}")
    print("✅ 全コマンド同期完了")

bot.run(BOT_TOKEN)
