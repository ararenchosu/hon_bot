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
        if not is_owner(itx):  # ← .user 削除
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(
        label="💾 今すぐバックアップ",
        style=discord.ButtonStyle.primary,
        custom_id="backup:create"
    )
    async def backup_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        path = create_backup()
        await itx.response.send_message(
            f"✅ バックアップ作成完了\n📁 `{path}`", ephemeral=True
        )

    @discord.ui.button(
        label="📂 バックアップ一覧",
        style=discord.ButtonStyle.secondary,
        custom_id="backup:list"
    )
    async def list_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        backups = sorted(os.listdir(BACKUP_DIR), reverse=True)[:5]
        if not backups:
            await itx.response.send_message(
                "📋 バックアップはまだありません", ephemeral=True
            )
            return
        text = "📂 最新5件のバックアップ:\n"
        for name in backups:
            text += f"- `{name}`\n"
        await itx.response.send_message(text, ephemeral=True)

    @discord.ui.button(
        label="📥 最新を復元",
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
            f"⚠️ 次のバックアップから復元しますか？\n`{latest}`\n"
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
            "🔄 Botを再起動します...\n"
            "5秒後に自動的に復帰します ✅",
            ephemeral=True
        )
        import asyncio
        async def delayed_exit():
            await asyncio.sleep(1)
            await itx.client.close()
        await delayed_exit()

class RestoreConfirmView(discord.ui.View):
    def __init__(self, backup_name):
        super().__init__(timeout=None)
        self.backup_name = backup_name

    @discord.ui.button(
        label="✅ 復元を実行",
        style=discord.ButtonStyle.danger
    )
    async def do_restore(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):  # ← .user 削除
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
        if not is_owner(itx):  # ← .user 削除
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="📦 データバックアップ・管理",
            description=(
                "💾 今すぐバックアップ → 現在のデータを保存\n"
                "📂 バックアップ一覧 → 過去の履歴を表示\n"
                "📥 最新を復元 → 最新のバックアップからデータを戻す\n"
                "🔄 Botを再起動 → Botを再起動（自動復帰）\n\n"
                "⚠️ 復元後は必ず再起動してください"
            ),
            color=0x2ECC71
        )
        latest = get_latest_backup()
        embed.add_field(
            name="📋 最新バックアップ",
            value=f"`{latest}`" if latest else "なし",
            inline=False
        )
        await itx.response.send_message(embed=embed, view=BackupPanelView())
