import discord
from discord import app_commands
import os
from core.database import init_db

from features.lottery_panel import setup as lottery_setup
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
        bot.add_view(LotteryPanelView())
        bot.add_view(PointCheckPanelView())
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
    print("  ✅ lottery_panel（くじ引き・ポイント確認）")
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await welcome_leave.setup(bot)
    print("✅ 全コマンド登録完了")

    # ✅ 登録済みコマンドを表示（これが本当の一覧です）
    print("\n📋 登録されているコマンド：")
    all_cmds = tree.get_commands()
    for cmd in all_cmds:
        print(f"   /{cmd.name} — {cmd.description}")
    print(f"✅ 合計 {len(all_cmds)} 件\n")

    # ✅ ギルド同期（IDは正しいものを使用）
    GUILD_ID = 1542788841465978880
    print(f"🔄 ギルド {GUILD_ID} に反映中...")
    
    # force=True で強制的に上書き
    synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
    
    # ✅ ギルド側の実際のコマンドを取得して表示
    guild = discord.Object(id=GUILD_ID)
    guild_cmds = await tree.fetch_commands(guild=guild)
    print(f"\n✅ サーバーに反映されたコマンド一覧（{len(guild_cmds)}件）：")
    if not guild_cmds:
        print("   ⚠️ まだ反映されていません。少し待ってから再度お試しください。")
    for cmd in guild_cmds:
        print(f"   /{cmd.name} — {cmd.description}")
    print()

    # ✅ パネル復元
    print("🔄 パネル復元中...")
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
    print("✅ パネル復元完了\n")


bot.run(BOT_TOKEN)
