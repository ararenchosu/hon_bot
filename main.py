import discord
from discord import app_commands
import asyncio
import os
from datetime import datetime, timedelta, timezone
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
import features.command_list_panel as command_list_panel
import features.command_restrict_panel as command_restrict_panel
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave
import features.voice_channel_panel as voice_panel
import features.ranking_panel as ranking_panel

JST = timezone(timedelta(hours=9))
STATUS_LOG_CHANNEL_ID = 1559119439981449256
REASON_FILE = ".last_stop_reason"

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

def get_jst_now():
    return datetime.now(JST)

async def send_status_embed(title: str, description: str, color: int):
    if not STATUS_LOG_CHANNEL_ID:
        return
    try:
        channel = bot.get_channel(STATUS_LOG_CHANNEL_ID)
        if not channel:
            print(f"⚠️ チャンネルが見つかりません")
            return
        now_jst = get_jst_now()
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(
            text=f"時刻：{now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}"
        )
        await channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ 通知送信エラー: {e}")

def clear_reason_file():
    if os.path.exists(REASON_FILE):
        try:
            os.remove(REASON_FILE)
        except:
            pass

def set_reason(reason: str):
    with open(REASON_FILE, "w", encoding="utf-8") as f:
        f.write(reason)

def get_and_clear_reason():
    if os.path.exists(REASON_FILE):
        with open(REASON_FILE, "r", encoding="utf-8") as f:
            reason = f.read().strip()
        clear_reason_file()
        return reason
    return None

@bot.event
async def on_message(message):
    if message.guild and not message.author.bot:
        await security_panel.check_forbidden_words(message)
        await security_panel.check_link_restriction(message)

# ✅ チェック関数（どこからでも呼び出せるように）
async def check_restriction(itx: discord.Interaction):
    from features.command_restrict_panel import check_command_allowed
    return await check_command_allowed(itx)

@bot.event
async def on_ready():
    print(f"\n✅ ログイン：{bot.user}")
    
    last_reason = get_and_clear_reason()
    
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
        from features.command_list_panel import CommandListView
        from features.command_restrict_panel import CommandRestrictMainView
        
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
        
        clv = CommandListView()
        clv.tree = tree
        bot.add_view(clv)
        
        crmv = CommandRestrictMainView()
        crmv.all_cmds = sorted([c.name for c in tree.get_commands()])
        bot.add_view(crmv)
        
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
    
    # ✅ 登録後に個別callbackをラップする方式（clear_commands不使用）
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
    print("  ✅ invite_link")
    await backup_panel.setup(tree)
    print("  ✅ backup_panel")
    await command_list_panel.setup(tree)
    print("  ✅ command_list_panel コマンド一覧")
    await command_restrict_panel.setup(tree)
    print("  ✅ command_restrict_panel コマンド制限管理")
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await welcome_leave.setup(bot)
    print("  ✅ welcome_leave 入退室ログ")
    await voice_panel.setup(tree)
    print("  ✅ voice_channel_panel")
    await ranking_panel.setup(tree)
    print("  ✅ ranking_panel")
    
    # ✅ 登録済みコマンドを1個ずつ上書き登録
    original_commands = tree.get_commands()
    
    for cmd in original_commands:
        original_callback = cmd.callback
        
        # チェックを挟んだ新しいcallback
        async def wrapped_callback(itx, *args, _cb=original_callback, **kwargs):
            if not await check_restriction(itx):
                return
            await _cb(itx, *args, **kwargs)
        
        # コマンドを再登録（上書き）
        @tree.command(name=cmd.name, description=cmd.description)
        async def new_command(itx, *args, _wrap=wrapped_callback, **kwargs):
            await _wrap(itx, *args, **kwargs)
    
    print("✅ 全コマンド制限チェック 自動設定完了")
    
    print("✅ 全コマンド登録完了")
    print("\n📋 コマンド一覧：")
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
    
    if last_reason == "restart_button":
        await send_status_embed(
            title="✅ 再起動完了",
            description="ボタン操作により再起動されました。\n入退室ログを監視中…",
            color=0xF39C12
        )
    else:
        await send_status_embed(
            title="🔄 機能追加又は.py更新により再起動",
            description="機能追加又は.py更新により再起動が実行されました。\n入退室ログを監視中…",
            color=0x9B59B6
        )
    print("✅ 起動通知送信完了")
    print("\n✅ 起動完了\n")

@bot.event
async def on_close():
    if os.path.exists(REASON_FILE):
        return
    set_reason("update")

bot.run(BOT_TOKEN)
