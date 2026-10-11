import discord
from discord import app_commands
import os
from core.database import init_db

from features.lottery_panel import setup as lottery_setup
from features.login_bonus import setup as login_bonus_setup  # ✅ 追加
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave

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


@bot.event
async def on_ready():
    print(f"\n✅ ログイン：{bot.user}")

    # ✅ View登録
    try:
        from features.lottery_panel import LotteryPanelView, PointCheckPanelView
        from features.login_bonus import LoginBonusPanelView  # ✅ 追加
        bot.add_view(LotteryPanelView())
        bot.add_view(PointCheckPanelView())
        bot.add_view(LoginBonusPanelView())  # ✅ 追加
        bot.add_view(othello_panel.OthelloPanelView())
        bot.add_view(call_panel.CallPanelView(bot))
        bot.add_view(auth_panel.AuthPanelView())
        bot.add_view(role_panel.RoleSelectPanelView())
        bot.add_view(revoke_panel.RoleRevokePanelView())
        print("✅ 全View登録完了")
    except Exception as e:
        print(f"⚠️ View登録エラー: {e}")

    # ✅ コマンド登録
    print("\n🔄 コマンド登録中...")
    await lottery_setup(tree)
    print("  ✅ lottery_panel → /くじ引きパネル設置 / /ポイント確認パネル設置")
    await login_bonus_setup(tree)  # ✅ 追加
    print("  ✅ login_bonus → /ログインボーナスパネル設置")
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await welcome_leave.setup(bot)
    print("✅ 全コマンド登録完了")

    # ✅ 登録確認
    print("\n📋 登録済みコマンド一覧：")
    for cmd in tree.get_commands():
        print(f"   /{cmd.name}")

    # ✅ グローバル同期
    print("\n🔄 グローバル同期中...")
    synced = await tree.sync()
    print(f"✅ 同期完了！合計 {len(synced)} 件")
    for cmd in synced:
        print(f"   /{cmd.name}")

    # ✅ パネル復元
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
