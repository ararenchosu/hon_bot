import discord
from discord import app_commands
import asyncio
import os
from core.database import init_db
from features.lottery_panel import setup as lottery_setup
from features.login_bonus import setup as login_bonus_setup
from features.slots_panel import setup as slots_setup
from features.blackjack_panel import setup as blackjack_setup
from features.highlow_panel import setup as highlow_setup
from features.point_admin_panel import setup as point_admin_setup
import features.embed_sender as embed_sender
import features.clear_messages as clear_messages
import features.moderation_panel as moderation_panel
import features.security_panel as security_panel
import features.invite_link as invite_link
import features.backup_panel as backup_panel
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave
import features.voice_channel_panel as voice_panel
import features.ranking_panel as ranking_panel

# ✅ ここにメッセージを送るチャンネルIDを入れる
STATUS_LOG_CHANNEL_ID = 1559119439981449256  # ← 自分のチャンネルIDに書き換える

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

# ========== 共通：ステータス通知送信関数 ==========
async def send_status_embed(title: str, description: str, color: int):
    """ステータスメッセージを送信する共通処理"""
    if not STATUS_LOG_CHANNEL_ID or STATUS_LOG_CHANNEL_ID == 123456789012345678:
        return  # ID未設定時はスキップ
    try:
        channel = bot.get_channel(STATUS_LOG_CHANNEL_ID)
        if not channel:
            print(f"⚠️ チャンネルが見つかりません (ID: {STATUS_LOG_CHANNEL_ID})")
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.set_footer(
            text=f"時刻：{discord.utils.format_dt(discord.utils.utcnow(), 'F')}"
        )
        await channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ ステータス通知送信エラー: {e}")

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
        from features.invite_link import InvitePanelView, InviteDurationView
        from features.backup_panel import BackupPanelView

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
        bot.add_view(InvitePanelView())
        bot.add_view(InviteDurationView())
        bot.add_view(BackupPanelView())
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
    await blackjack_setup(tree)
    print("  ✅ blackjack_panel")
    await highlow_setup(tree)
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
    await invite_link.setup(tree)
    print("  ✅ invite_link → /招待リンクパネル")
    await backup_panel.setup(tree)
    print("  ✅ backup_panel → /バックアップパネル")
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

    # ✅ 起動完了メッセージ送信
    await send_status_embed(
        title="✅ 起動完了",
        description="Botが正常に起動しました。",
        color=0x2ECC71
    )
    print("✅ 起動通知送信完了")
    print("\n✅ 起動完了\n")

# ========== 停止時イベント ==========
@bot.event
async def on_close():
    """Botが閉じられる直前に実行"""
    await send_status_embed(
        title="🛑 停止/再起動",
        description="Botが停止されました。",
        color=0xE74C3C
    )

bot.run(BOT_TOKEN)
