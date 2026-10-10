import discord
from discord import app_commands
from discord.ext import commands  # ← 追加
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

from core.common import OWNER_ID, CALL_CHANNEL_ID, WELCOME_LEAVE_CHANNEL_ID, JST
from core.database import init_db

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Botクラスに変更
bot = commands.Bot(intents=intents)
tree = bot.tree  # ← こう書いてもOK

# 機能インポート
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave
import features.embed_tool as embed_tool
import features.othello as othello

@bot.event
async def on_ready():
    init_db()

    # View登録
    bot.add_view(auth_panel.AuthPanelView())
    bot.add_view(role_panel.RoleSelectPanelView())
    bot.add_view(revoke_panel.RoleRevokePanelView())
    bot.add_view(call_panel.CallPanelView(bot))

    # 各機能のセットアップ
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await embed_tool.setup(tree)
    await othello.setup(bot)  # ← オセロは bot を渡す

    # イベント
    @bot.event
    async def on_member_join(member):
        await welcome_leave.on_member_join(member)

    @bot.event
    async def on_member_remove(member):
        await welcome_leave.on_member_remove(member)

    await tree.sync()
    print(f"✅ 起動完了: {bot.user}")

bot.run(BOT_TOKEN)
