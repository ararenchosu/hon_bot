import discord
from discord import app_commands
import os
import shutil
from datetime import datetime
from core.common import is_owner

BACKUP_DIR = "data_backup"
DATA_DIR = "data"
DB_FILE = "kn_server.db"
POINT_FILE = "kn_points_data.json"

os.makedirs(BACKUP_DIR, exist_ok=True)

def get_latest_backup():
    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    return backups[0] if backups else None

def create_backup():
    # 古いバックアップを削除
    for old_name in os.listdir(BACKUP_DIR):
        old_path = os.path.join(BACKUP_DIR, old_name)
        try:
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            else:
                os.remove(old_path)
        except Exception as e:
            print(f"⚠️ 古いバックアップ削除: {e}")
    
    # 新しいバックアップを作成
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{now}")
    os.makedirs(backup_path, exist_ok=True)
    
    if os.path.exists(os.path.join(DATA_DIR, DB_FILE)):
        shutil.copy2(os.path.join(DATA_DIR, DB_FILE), backup_path)
    if os.path.exists(os.path.join(DATA_DIR, POINT_FILE)):
        shutil.copy2(os.path.join(DATA_DIR, POINT_FILE), backup_path)
    
    return backup_path

def restore_backup(backup_name: str):
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return False, "バックアップが見つかりません"
    try:
        if os.path.exists(os.path.join(backup_path, DB_FILE)):
            shutil.copy2(os.path.join(backup_path, DB_FILE),
                         os.path.join(DATA_DIR, DB_FILE))
        if os.path.exists(os.path.join(backup_path, POINT_FILE)):
            shutil.copy2(os.path.join(backup_path, POINT_FILE),
                         os.path.join(DATA_DIR, POINT_FILE))
        return True, "復元完了"
    except Exception as e:
        return False, str(e)

class BackupPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_owner(self, itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="💾 最新を永久保存",
        style=discord.ButtonStyle.primary,
        custom_id="backup:create"
    )
    async def backup_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        path = create_backup()
        await itx.response.send_message(
            f"✅ 最新バックアップを保存（前回分は上書き）\n📁 `{path}`", 
            ephemeral=True
        )

    @discord.ui.button(
        label="📂 保存状況を確認",
        style=discord.ButtonStyle.secondary,
        custom_id="backup:list"
    )
    async def list_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        latest = get_latest_backup()
        if not latest:
            await itx.response.send_message(
                "📋 まだバックアップが保存されていません", ephemeral=True
            )
            return
        await itx.response.send_message(
            f"📂 現在保存されているバックアップ:\n- `{latest}`\n✅ 最新1件が永久保存中",
            ephemeral=True
        )

    @discord.ui.button(
        label="📥 保存分を復元",
        style=discord.ButtonStyle.danger,
        custom_id="backup:restore"
    )
    async def restore_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        latest = get_latest_backup()
        if not latest:
            await itx.response.send_message(
                "❌ 復元可能なバックアップがありません", ephemeral=True
            )
            return
        confirm_view = RestoreConfirmView(latest)
        await itx.response.send_message(
            f"⚠️ 保存中のバックアップから復元しますか？\n`{latest}`\n"
            "※ 現在のデータは上書きされます",
            view=confirm_view,
            ephemeral=True
        )

    @discord.ui.button(
        label="🔄 Botを再起動",
        style=discord.ButtonStyle.success,
        custom_id="backup:restart"
    )
    async def restart_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        await itx.response.send_message(
            "🔄 Botを再起動します...\n5秒後に自動的に復帰します ✅",
            ephemeral=True
        )
        import asyncio
        async def delayed_exit():
            await asyncio.sleep(1)
            await itx.client.close()
        await delayed_exit()

    @discord.ui.button(
        label="🛑 Botを停止",
        style=discord.ButtonStyle.danger,
        custom_id="backup:shutdown",
        row=1  # 下段に表示
    )
    async def shutdown_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        confirm_view = ShutdownConfirmView()
        await itx.response.send_message(
            "⚠️ 本当にBotを停止しますか？\n"
            "※ 再起動するには手動で起動し直す必要があります",
            view=confirm_view,
            ephemeral=True
        )

class ShutdownConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ 停止を実行",
        style=discord.ButtonStyle.danger
    )
    async def do_shutdown(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return
        await itx.response.edit_message(
            content="🛑 Botを停止しました\nお疲れ様でした ✨",
            view=None
        )
        import asyncio
        async def delayed_shutdown():
            await asyncio.sleep(1)
            await itx.client.close()
        await delayed_shutdown()

    @discord.ui.button(
        label="❌ キャンセル",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.edit_message(content="✅ 停止をキャンセルしました", view=None)

class RestoreConfirmView(discord.ui.View):
    def __init__(self, backup_name):
        super().__init__(timeout=None)
        self.backup_name = backup_name

    @discord.ui.button(
        label="✅ 復元を実行",
        style=discord.ButtonStyle.danger
    )
    async def do_restore(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return
        ok, msg = restore_backup(self.backup_name)
        if ok:
            await itx.response.edit_message(
                content=f"✅ {msg}\n🔄 続けて「Botを再起動」ボタンを押してください",
                view=None
            )
        else:
            await itx.response.edit_message(
                content=f"❌ 失敗：{msg}", view=None
            )

    @discord.ui.button(
        label="❌ キャンセル",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.edit_message(content="✅ キャンセルしました", view=None)

async def setup(tree: app_commands.CommandTree):
    @tree.command(name="バックアップパネル", description="バックアップ管理パネルを表示")
    async def backup_panel_cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="📦 データバックアップ・管理",
            description=(
                "💾 最新を永久保存 → 最新の状態を1件保存（前回分は上書き）\n"
                "📂 保存状況を確認 → 現在保存されているデータを表示\n"
                "📥 保存分を復元 → 保存した最新の状態に戻す\n"
                "🔄 Botを再起動 → 自動復帰\n"
                "🛑 Botを停止 → 完全に停止（手動再起動必要）"
            ),
            color=0x2ECC71
        )
        latest = get_latest_backup()
        embed.add_field(
            name="📋 保存中",
            value=f"`{latest}`\n✅ 最新1件が保持中" if latest else "なし",
            inline=False
        )
        await itx.response.send_message(embed=embed, view=BackupPanelView())
