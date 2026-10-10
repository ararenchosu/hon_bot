import discord
from discord import app_commands
import os
from dotenv import load_dotenv

# ========== 外部設定読み込み ==========
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ .env に BOT_TOKEN を設定してください")

# ========== 共通設定・DB ==========
from core.common import OWNER_ID, CALL_CHANNEL_ID, WELCOME_LEAVE_CHANNEL_ID, JST
from core.database import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ========== 各機能モジュール読み込み ==========
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave
import features.embed_tool as embed_tool

# オセロは後で追加するので、まだコメントアウト
# import features.othello as othello

# ========== 起動時処理 ==========
@bot.event
async def on_ready():
    # DB初期化（ファイル保存なので再起動してもデータ保持）
    init_db()

    # Viewを登録（再起動後もボタン動作するように）
    bot.add_view(auth_panel.AuthPanelView())
    bot.add_view(role_panel.RoleSelectPanelView())
    bot.add_view(revoke_panel.RoleRevokePanelView())
    bot.add_view(call_panel.CallPanelView(bot))

    # 各機能のコマンド登録
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await embed_tool.setup(tree)
    # await othello.setup(tree)  ← 後で有効化

    # イベントハンドラ登録
    @bot.event
    async def on_member_join(member):
        await welcome_leave.on_member_join(member)

    @bot.event
    async def on_member_remove(member):
        await welcome_leave.on_member_remove(member)

    # コマンドをDiscordに同期
    await tree.sync()

    print(f"✅ 起動完了: {bot.user}")
    print(f"   入退出通知先: {WELCOME_LEAVE_CHANNEL_ID}")
    print(f"   呼び出し通知先: {CALL_CHANNEL_ID}")
    print(f"   💾 データは data/kn_server.db に永続保存中")

# ========== 起動 ==========
bot.run(BOT_TOKEN)
