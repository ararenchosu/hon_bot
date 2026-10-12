import discord
from discord import app_commands
from core.common import is_owner
import os
import shutil
from datetime import datetime

BACKUP_DIR = "/data/backups"
DB_PATH = "/data/kn_server.db"

os.makedirs(BACKUP_DIR, exist_ok=True)


class BackupPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💾 データをバックアップ",
        style=discord.ButtonStyle.primary,
        custom_id="backup:create"
    )
    async def backup_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        # ✅ オーナー以外は拒否
        if not is_owner(itx):
            await itx.response.send_message("❌ このボタンはオーナー専用です", ephemeral=True)
            return

        await itx.response.defer(ephemeral=True)

        try:
            # 古いバックアップを全削除
            for f in os.listdir(BACKUP_DIR):
                if f.endswith(".db"):
                    os.remove(os.path.join(BACKUP_DIR, f))

            # 最新1件だけ保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_PATH, backup_file)
            size_kb = os.path.getsize(backup_file) / 1024

            # ✅ バックアップファイルをDMに送信
            file_for_dm = discord.File(backup_file, filename=f"backup_{timestamp}.db")
            dm_success = False
            try:
                await itx.user.send(
                    f"✅ バックアップファイル\n"
                    f"📂 ファイル名：`backup_{timestamp}.db`\n"
                    f"📊 サイズ：{size_kb:.1f} KB\n"
                    f"🕒 作成日時：{timestamp}",
                    file=file_for_dm
                )
                dm_success = True
            except Exception as e:
                print(f"DM送信エラー: {e}")

            embed = discord.Embed(
                title="✅ バックアップ完了",
                description=f"ファイル名：`backup_{timestamp}.db`\n"
                            f"サイズ：{size_kb:.1f} KB\n"
                            f"古いバックアップは削除しました（最新1件を保持）\n"
                            f"{'✅ DMにファイルを送信しました' if dm_success else '⚠️ DM送信に失敗しましたがサーバーに保存済み'}",
                color=0x2ECC71
            )
            await itx.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await itx.followup.send(f"❌ バックアップ失敗：{e}", ephemeral=True)

    @discord.ui.button(
        label="📂 最新バックアップ確認",
        style=discord.ButtonStyle.secondary,
        custom_id="backup:check"
    )
    async def check_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ このボタンはオーナー専用です", ephemeral=True)
            return

        files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
        if not files:
            await itx.response.send_message("⚠️ バックアップが存在しません", ephemeral=True)
            return

        latest = sorted(files, reverse=True)[0]
        size = os.path.getsize(os.path.join(BACKUP_DIR, latest)) / 1024
        embed = discord.Embed(
            title="📂 最新バックアップ",
            description=f"ファイル名：`{latest}`\nサイズ：{size:.1f} KB",
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🔄 最新を復元",
        style=discord.ButtonStyle.danger,
        custom_id="backup:restore_latest"
    )
    async def restore_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ このボタンはオーナー専用です", ephemeral=True)
            return

        files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")]
        if not files:
            await itx.response.send_message("⚠️ 復元するバックアップが存在しません", ephemeral=True)
            return

        latest_file = sorted(files, reverse=True)[0]
        backup_path = os.path.join(BACKUP_DIR, latest_file)

        confirm_embed = discord.Embed(
            title="⚠️ 復元確認",
            description=f"最新のバックアップ：`{latest_file}` を復元します\n"
                        "現在のデータは上書きされます。よろしいですか？",
            color=0xE74C3C
        )
        await itx.response.send_message(embed=confirm_embed, view=RestoreConfirmView(latest_file, backup_path), ephemeral=True)


class RestoreConfirmView(discord.ui.View):
    def __init__(self, filename, backup_path):
        super().__init__(timeout=120)
        self.filename = filename
        self.backup_path = backup_path

    @discord.ui.button(
        label="✅ 復元を実行",
        style=discord.ButtonStyle.danger
    )
    async def do_restore(self, itx: discord.Interaction, btn: discord.ui.Button):
        # ✅ 復元実行時もオーナー確認
        if not is_owner(itx):
            await itx.response.send_message("❌ この操作はオーナー専用です", ephemeral=True)
            return

        try:
            # 現在のデータを一時退避
            shutil.copy2(DB_PATH, DB_PATH + ".current_backup")
            # 最新バックアップから復元
            shutil.copy2(self.backup_path, DB_PATH)

            await itx.response.send_message(
                f"✅ 復元完了！\n"
                f"📂 復元元：`{self.filename}`\n"
                f"💾 変更前のデータは `.current_backup` に退避済み\n"
                "⚠️ Botを再起動して反映してください",
                ephemeral=True
            )
        except Exception as e:
            await itx.response.send_message(f"❌ 復元失敗：{e}", ephemeral=True)

    @discord.ui.button(
        label="❌ キャンセル",
        style=discord.ButtonStyle.secondary
    )
    async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.edit_message(content="❌ キャンセルしました", embed=None, view=None)


async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    bot.add_view(BackupPanelView())

    @tree.command(
        name="バックアップパネル",
        description="データのバックアップ・復元パネル（オーナー専用）"
    )
    @app_commands.check(is_owner)
    async def backup_panel_cmd(itx: discord.Interaction):
        embed = discord.Embed(
            title="💾 データバックアップパネル",
            description="""
🔒 全てのボタンはオーナーのみ操作可能

💾 バックアップ → 最新を保存 & ファイルをDM送信
📂 確認 → 保存されている最新ファイルを表示
🔄 最新を復元 → 最新を一発で復元

⚠️ 復元後はBot再起動が必要
⚠️ 最新1件のみ自動保持（古いものは自動削除）
            """,
            color=0xF39C12
        )
        await itx.response.send_message(embed=embed, view=BackupPanelView())
        await itx.followup.send("✅ パネルを表示しました", ephemeral=True)
