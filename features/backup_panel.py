import discord
from discord import app_commands
import os
import shutil
import asyncio
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
STATUS_LOG_CHANNEL_ID = 1559119439981449256
REASON_FILE = ".last_stop_reason"
BACKUP_DIR = "data_backup"
DATA_DIR = "data"
DB_FILE = "kn_server.db"
POINT_FILE = "kn_points_data.json"

os.makedirs(BACKUP_DIR, exist_ok=True)

# ========== 自動バックアップ実行時間 ==========
BACKUP_HOURS = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24]

auto_backup_task = None

def set_reason(reason: str):
    with open(REASON_FILE, "w", encoding="utf-8") as f:
        f.write(reason)

def clear_reason_file():
    if os.path.exists(REASON_FILE):
        try:
            os.remove(REASON_FILE)
        except:
            pass

def get_jst_now():
    return datetime.now(JST)

async def send_status_embed(client, title: str, description: str, color: int):
    if not STATUS_LOG_CHANNEL_ID:
        return
    try:
        channel = client.get_channel(STATUS_LOG_CHANNEL_ID)
        if not channel:
            print(f"⚠️ チャンネルが見つかりません: {STATUS_LOG_CHANNEL_ID}")
            return
        now_jst = get_jst_now()
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(
            text=f"時刻：{now_jst.strftime('%Y-%m-%d %H:%M:%S JST')}"
        )
        await channel.send(embed=embed)
    except Exception as e:
        print(f"⚠️ 通知送信エラー: {e}")

def get_latest_backup():
    if not os.path.exists(BACKUP_DIR):
        return None
    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    return backups[0] if backups else None

def cleanup_old_backups():
    if not os.path.exists(BACKUP_DIR):
        return
    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    if len(backups) <= 1:
        return
    for old_name in backups[1:]:
        old_path = os.path.join(BACKUP_DIR, old_name)
        try:
            if os.path.isdir(old_path):
                shutil.rmtree(old_path)
            else:
                os.remove(old_path)
            print(f"🗑️ 古いバックアップ削除: {old_name}")
        except Exception as e:
            print(f"⚠️ 削除失敗 {old_name}: {e}")

def create_backup(note: str = ""):
    cleanup_old_backups()
    suffix = f"_{note}" if note else ""
    now = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{now}{suffix}")
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

async def auto_backup_scheduler(client):
    await client.wait_until_ready()
    last_executed_hour = None
    while not client.is_closed():
        now = get_jst_now()
        current_hour = now.hour
        effective_hour = 24 if current_hour == 0 else current_hour
        if effective_hour in BACKUP_HOURS and last_executed_hour != effective_hour:
            try:
                path = create_backup("定刻")
                print(f"✅ 定刻バックアップ実行: {now.strftime('%H時')} → {path}")
                await send_status_embed(
                    client,
                    title=f"⏰ 定刻バックアップ（{now.strftime('%H時')}）",
                    description=f"スケジュールされた時間にバックアップを実行しました。\n📁 `{path}`\n✅ 最新1件のみ保持中",
                    color=0x3498DB
                )
                last_executed_hour = effective_hour
            except Exception as e:
                print(f"⚠️ 定刻バックアップエラー: {e}")
        await asyncio.sleep(30)

def start_auto_backup(client):
    global auto_backup_task
    if auto_backup_task is None or auto_backup_task.done():
        auto_backup_task = asyncio.create_task(auto_backup_scheduler(client))
        schedule_str = ", ".join(f"{h}時" for h in BACKUP_HOURS)
        print(f"✅ 定刻バックアップ開始（毎日 {schedule_str}）")

# ========== パネル埋め込み内容を生成する共通関数 ==========
def get_panel_embed():
    """最新情報を反映した埋め込みを返す"""
    latest = get_latest_backup()
    schedule_str = " / ".join(f"{h}時" for h in BACKUP_HOURS)
    embed = discord.Embed(
        title="📦 データバックアップ・管理",
        description=(
            f"⏰ 自動: 毎日 {schedule_str} に実行\n"
            "💾 最新を永久保存 → 手動保存（古いものは自動削除）\n"
            "🔄 情報を更新 → 最新ファイル名を再取得\n"
            "📂 保存状況を確認 → 詳細を表示\n"
            "📥 保存分を復元 → 最新の状態に戻す\n"
            "🔄 Botを再起動 → 停止→待機→再起動"
        ),
        color=0x2ECC71
    )
    embed.add_field(
        name="📋 最新（1件保持）",
        value=f"`{latest}`" if latest else "なし",
        inline=False
    )
    return embed

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
        path = create_backup("手動")
        # ✅ パネル自体を更新 → ファイル名が即時反映
        await itx.response.edit_message(
            embed=get_panel_embed(),
            view=self
        )
        await itx.followup.send(
            f"✅ バックアップを保存\n📁 `{path}`\n✅ 古いバックアップは削除済み",
            ephemeral=True
        )
        await send_status_embed(
            itx.client,
            title="💾 手動バックアップ実行",
            description=f"オーナーによりバックアップが保存されました。\n`{path}`\n✅ 最新1件のみ保持中",
            color=0x3498DB
        )

    # ✅ 新規追加：情報更新ボタン
    @discord.ui.button(
        label="🔄 情報を更新",
        style=discord.ButtonStyle.secondary,
        custom_id="backup:refresh"
    )
    async def refresh_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not await self.check_owner(itx):
            return
        # 最新のファイル名に更新
        await itx.response.edit_message(
            embed=get_panel_embed(),
            view=self
        )
        await itx.followup.send(
            "✅ 情報を更新しました",
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
        schedule_str = " / ".join(f"{h}時" for h in BACKUP_HOURS)
        if not latest:
            await itx.response.send_message(
                f"📋 まだバックアップが保存されていません\n⏰ 実行予定：{schedule_str}",
                ephemeral=True
            )
            return
        await itx.response.send_message(
            f"📂 現在保存されているバックアップ:\n- `{latest}`\n✅ 最新1件のみ保持中\n⏰ 実行予定：{schedule_str}",
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
            f"⚠️ バックアップから復元しますか？\n`{latest}`\n"
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
            "🔄 Botを再起動します…\n停止→5秒経過→再起動開始→完了",
            ephemeral=True
        )
        set_reason("restart_button")
        
        await send_status_embed(
            itx.client,
            title="🔄 再起動実行",
            description="オーナーにより再起動が実行されました。\nBotを停止しています…",
            color=0xF39C12
        )
        await asyncio.sleep(0.5)
        await send_status_embed(
            itx.client,
            title="⏹️ Bot停止",
            description="自動再起動のためBotを停止しました。\n5秒後に再起動を開始します。",
            color=0xE74C3C
        )
        await asyncio.sleep(5)
        await send_status_embed(
            itx.client,
            title="⏳ 再起動開始",
            description="5秒が経過しました。\n再起動を開始します…",
            color=0x9B59B6
        )
        async def delayed_exit():
            await asyncio.sleep(0.5)
            await itx.client.close()
        await delayed_exit()

class RestoreConfirmView(discord.ui.View):
    def __init__(self, backup_name):
        super().__init__(timeout=None)
        self.backup_name = backup_name

    @discord.ui.button(
        label="✅ 復元を実行",
        style=discord.ButtonStyle.danger,
        custom_id="backup:restore_confirm"
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
            await send_status_embed(
                itx.client,
                title="📥 復元実行",
                description=f"オーナーによりバックアップから復元されました。\n`{self.backup_name}`",
                color=0x9B59B6
            )
        else:
            await itx.response.edit_message(
                content=f"❌ 失敗：{msg}", view=None
            )

    @discord.ui.button(
        label="❌ キャンセル",
        style=discord.ButtonStyle.secondary,
        custom_id="backup:restore_cancel"
    )
    async def cancel(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.edit_message(content="✅ キャンセルしました", view=None)

async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    
    if not hasattr(bot, "_backup_panel_registered"):
        bot.add_view(BackupPanelView())
        bot.add_view(RestoreConfirmView(""))
        bot._backup_panel_registered = True
    
    start_auto_backup(bot)

    @tree.command(name="バックアップパネル", description="バックアップ管理パネルを表示")
    async def backup_panel_cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message(
                "❌ オーナーのみ実行可能です", ephemeral=True
            )
            return
        await itx.response.send_message(
            embed=get_panel_embed(),
            view=BackupPanelView()
        )
