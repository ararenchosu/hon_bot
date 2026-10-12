import discord
from discord import app_commands
import asyncio
import os
from core.database import init_db
from features.lottery_panel import setup as lottery_setup
from features.login_bonus import setup as login_bonus_setup
from features.slots_panel import setup as slots_setup
from features.blackjack_panel import setup as bj_setup
from features.highlow_panel import setup as hl_setup
from features.point_admin_panel import setup as point_admin_setup
import features.embed_sender as embed_sender
import features.clear_messages as clear_messages
import features.moderation_panel as moderation_panel
import features.security_panel as security_panel
import features.invite_link as invite_link  # ✅ 招待リンク
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave
import features.voice_channel_panel as voice_panel
import features.ranking_panel as ranking_panel

BOT_TOKEN = os.getenv("DISCORD_TOKEN")
if not BOT_TOKEN:
    print("❌ 環境変数 DISCORD_TOKEN が設定されていません")
    exit(1)
print(f"✅ トークン読み込み完了：{BOT_TOKEN[:10]}...")

init_db()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

async def restore_panel(channel_id, message_id, ViewClass, *view_args):
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"⚠️ チャンネルが見つかりません: {channel_id}")
            return False
        msg = await channel.fetch_message(message_id)
        await msg.edit(view=ViewClass(*view_args))
        return True
    except Exception as e:
        print(f"⚠️ 復元失敗: {e}")
        return False

# ========== 監視イベント ==========
@bot.event
async def on_message(message):
    if message.guild and not message.author.bot:
        await security_panel.check_forbidden_words(message)
        await security_panel.check_link_restriction(message)

# ========== 起動処理 ==========
@bot.event
async def on_ready():
    print(f"\n✅ ログイン：{bot.user}")
    
    try:
        from features.lottery_panel import LotteryPanelView, PointCheckPanelView
        from features.login_bonus import LoginBonusPanelView
        from features.slots_panel import SlotPanelView
        from features.blackjack_panel import BlackjackPanelView
        from features.highlow_panel import HighLowPanelView
        from features.point_admin_panel import PointAdminView
        from features.moderation_panel import ModerationPanelView
        from features.security_panel import (
            SecurityMainView, ForbiddenWordView,
            LockChannelView, UnlockChannelView,
            EmergencyLockView, EmergencyUnlockView
        )
        from features.invite_link import InvitePanelView, InviteDurationView  # ✅ 招待リンク
        
        bot.add_view(LotteryPanelView())
        bot.add_view(PointCheckPanelView())
        bot.add_view(LoginBonusPanelView())
        bot.add_view(SlotPanelView())
        bot.add_view(BlackjackPanelView())
        bot.add_view(HighLowPanelView())
        bot.add_view(PointAdminView())
        bot.add_view(ModerationPanelView())
        bot.add_view(SecurityMainView())
        bot.add_view(ForbiddenWordView())
        bot.add_view(LockChannelView())
        bot.add_view(UnlockChannelView())
        bot.add_view(EmergencyLockView())
        bot.add_view(EmergencyUnlockView())
        bot.add_view(InvitePanelView())       # ✅ 招待リンク
        bot.add_view(InviteDurationView())    # ✅ 招待リンク
        bot.add_view(othello_panel.OthelloPanelView())
        bot.add_view(call_panel.CallPanelView(bot))
        bot.add_view(auth_panel.AuthPanelView())
        bot.add_view(role_panel.RoleSelectPanelView())
        bot.add_view(revoke_panel.RoleRevokePanelView())
        bot.add_view(voice_panel.VoiceCreatePanelView())
        bot.add_view(ranking_panel.RankingPanelView())
        print("✅ 全View登録完了")
    except Exception as e:
        print(f"⚠️ View登録エラー: {e}")
    
    print("\n🔄 コマンド登録中...")
    await lottery_setup(tree)
    print("  ✅ lottery_panel")
    await login_bonus_setup(tree)
    print("  ✅ login_bonus")
    await slots_setup(tree)
    print("  ✅ slots_panel")
    await bj_setup(tree)
    print("  ✅ blackjack_panel")
    await hl_setup(tree)
    print("  ✅ highlow_panel")
    await point_admin_setup(tree)
    print("  ✅ point_admin_panel")
    await embed_sender.setup(tree)
    print("  ✅ embed_sender")
    await clear_messages.setup(tree)
    print("  ✅ clear_messages")
    await moderation_panel.setup(tree)
    print("  ✅ moderation_panel")
    await security_panel.setup(tree)
    print("  ✅ security_panel")
    await invite_link.setup(tree)  # ✅ 招待リンク
    print("  ✅ invite_link → /招待リンクパネル")
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await welcome_leave.setup(bot)
    await voice_panel.setup(tree)
    print("  ✅ voice_channel_panel")
    await ranking_panel.setup(tree)
    print("  ✅ ranking_panel")
    print("✅ 全コマンド登録完了")
    
    print("\n📋 登録済みコマンド一覧：")
    for cmd in tree.get_commands():
        print(f"   /{cmd.name}")
    
    print("\n🔄 グローバル同期中...")
    synced = await tree.sync()
    print(f"✅ 同期完了！合計 {len(synced)} 件")
    for cmd in synced:
        print(f"   /{cmd.name}")
    
    print("\n🔄 自動更新タスク起動中...")
    asyncio.create_task(ranking_panel.auto_update_task(bot))
    print("✅ ランキング自動更新タスク起動完了")
    
    print("\n🔄 パネル復元中...")
    call_saved = call_panel.get_latest_call_panel()
    if call_saved:
        await restore_panel(call_saved["channel_id"], call_saved["message_id"], call_panel.CallPanelView, bot)
    auth_saved = auth_panel.get_latest_auth_panel()
    if auth_saved:
        await restore_panel(auth_saved["channel_id"], auth_saved["message_id"], auth_panel.AuthPanelView)
    role_give_saved = role_panel.get_latest_role_give_panel()
    if role_give_saved:
        await restore_panel(role_give_saved["channel_id"], role_give_saved["message_id"], role_panel.RoleSelectPanelView)
    role_revoke_saved = revoke_panel.get_latest_role_revoke_panel()
    if role_revoke_saved:
        await restore_panel(role_revoke_saved["channel_id"], role_revoke_saved["message_id"], revoke_panel.RoleRevokePanelView)
    print("✅ 起動完了\n")

bot.run(BOT_TOKEN)
