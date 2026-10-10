import discord
from discord import app_commands
import os
from core.database import init_db  # ← 追加

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

# ✅ DB初期化：起動時に必ず実行
init_db()

# ===== 全機能読み込み =====
import features.othello as othello
import features.othello_panel as othello_panel
import features.auth_panel as auth_panel
import features.role_panel as role_panel
import features.revoke_panel as revoke_panel
import features.call_panel as call_panel
import features.welcome_leave as welcome_leave

# ========== 復元共通処理 ==========
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
        print(f"⚠️ 復元失敗（再設置推奨）ch={channel_id}, msg={message_id}: {e}")
        return False

@bot.event
async def on_ready():
    # ✅ 永続View登録
    try:
        bot.add_view(othello_panel.OthelloPanelView())
        bot.add_view(call_panel.CallPanelView(bot))
        bot.add_view(auth_panel.AuthPanelView())
        bot.add_view(role_panel.RoleSelectPanelView())
        bot.add_view(revoke_panel.RoleRevokePanelView())
        print("✅ 全View登録完了")
    except Exception as e:
        print(f"⚠️ View登録エラー: {e}")

    # ✅ 保存済みパネルを自動復元
    print("🔄 パネル復元中...")
    # 呼び出しパネル
    call_saved = call_panel.get_latest_call_panel()
    if call_saved:
        await restore_panel(call_saved["channel_id"], call_saved["message_id"],
                            call_panel.CallPanelView, bot)
    # 認証パネル
    auth_saved = auth_panel.get_latest_auth_panel()
    if auth_saved:
        await restore_panel(auth_saved["channel_id"], auth_saved["message_id"],
                            auth_panel.AuthPanelView)
    # ロール付与パネル
    role_give_saved = role_panel.get_latest_role_give_panel()
    if role_give_saved:
        await restore_panel(role_give_saved["channel_id"], role_give_saved["message_id"],
                            role_panel.RoleSelectPanelView)
    # ロール剥奪パネル
    role_revoke_saved = revoke_panel.get_latest_role_revoke_panel()
    if role_revoke_saved:
        await restore_panel(role_revoke_saved["channel_id"], role_revoke_saved["message_id"],
                            revoke_panel.RoleRevokePanelView)

    # ✅ コマンド登録
    await othello.setup(tree)
    await othello_panel.setup(tree)
    await auth_panel.setup(tree)
    await role_panel.setup(tree)
    await revoke_panel.setup(tree)
    await call_panel.setup(tree, bot)
    await welcome_leave.setup(bot)

    # ✅ ギルド同期
    GUILD_ID = 1542788841465978880
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    
    print(f"✅ 起動完了：{bot.user}")
    print("✅ 全コマンド同期完了")

bot.run(BOT_TOKEN)
