import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone
from core.common import is_owner
from core.database import get_connection
import asyncio  # ✅ 追加

JST = timezone(timedelta(hours=9))
MOD_LOG_CHANNEL_ID = None  # ← ログ用チャンネルIDを入れてください
MUTE_ROLE_NAME = "ミュート"

# ========== データベース初期化 ==========
def init_security_tables():
    conn = get_connection()
    cur = conn.cursor()
    # 禁止ワード
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forbidden_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            match_type TEXT DEFAULT 'partial',
            level TEXT DEFAULT 'warning'
        )
    """)
    # 監視対象チャンネル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS monitored_channels (
            channel_id TEXT PRIMARY KEY,
            channel_name TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    """)
    # 自動監視設定
    cur.execute("""
        CREATE TABLE IF NOT EXISTS security_settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT 'off'
        )
    """)
    for key in ['spam_monitor', 'link_monitor', 'word_monitor']:
        cur.execute("INSERT OR IGNORE INTO security_settings VALUES (?, 'off')", (key,))
    # ミュート管理
    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_mutes (
            user_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            end_time TEXT NOT NULL,
            reason TEXT,
            mute_type TEXT DEFAULT 'timed'
        )
    """)
    # 期限付きBAN管理
    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_tempbans (
            user_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            end_time TEXT NOT NULL,
            reason TEXT
        )
    """)
    # 管理履歴
    cur.execute("""
        CREATE TABLE IF NOT EXISTS security_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL,
            operator_id TEXT,
            operator_name TEXT
        )
    """)
    # 注意文テンプレート
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notice_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    cur.execute("SELECT COUNT(*) FROM notice_templates")
    if cur.fetchone()[0] == 0:
        defaults = [
            ("注意", "迷惑行為を控えてください。ルールを守ってご利用ください。"),
            ("厳重注意", "繰り返し迷惑行為が見られます。今後同様の行為があった場合、ミュートまたはBANとなります。"),
            ("最終警告", "これ以上の違反は即時BANとなります。今一度行動を改めてください。")
        ]
        for t, c in defaults:
            cur.execute("INSERT INTO notice_templates (title, content) VALUES (?, ?)", (t, c))
    conn.commit()
    conn.close()

# ========== 共通：設定取得・更新 ==========
def get_setting(key):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM security_settings WHERE key=?", (key,))
    r = cur.fetchone()
    conn.close()
    return r[0] if r else 'off'

def set_setting(key, value):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("REPLACE INTO security_settings VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# ========== 監視チャンネル管理 ==========
def get_monitored_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT channel_id, channel_name FROM monitored_channels")
    result = cur.fetchall()
    conn.close()
    return result

def add_monitored_channel(channel_id, channel_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO monitored_channels VALUES (?, ?, ?)",
        (str(channel_id), channel_name, datetime.now(JST).isoformat())
    )
    conn.commit()
    conn.close()

def remove_monitored_channel(channel_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM monitored_channels WHERE channel_id=?", (str(channel_id),))
    conn.commit()
    conn.close()

def is_monitored_channel(channel_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM monitored_channels WHERE channel_id=?", (str(channel_id),))
    r = cur.fetchone()
    conn.close()
    return r is not None

# ========== 禁止ワード管理 ==========
def get_forbidden_words():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, word, match_type, level FROM forbidden_words")
    result = cur.fetchall()
    conn.close()
    return result

def add_forbidden_word(word, match_type='partial', level='warning'):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO forbidden_words (word, match_type, level) VALUES (?, ?, ?)",
        (word, match_type, level)
    )
    conn.commit()
    conn.close()

def remove_forbidden_word(word_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM forbidden_words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()

# ========== ミュート管理 ==========
def add_mute(user_id, user_name, end_time_str, reason, mute_type='timed'):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO active_mutes VALUES (?, ?, ?, ?, ?)",
        (str(user_id), user_name, end_time_str, reason, mute_type)
    )
    conn.commit()
    conn.close()

def remove_mute(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM active_mutes WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()

def get_expired_mutes():
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now(JST).isoformat()
    cur.execute("SELECT user_id, user_name FROM active_mutes WHERE end_time < ?", (now,))
    result = cur.fetchall()
    conn.close()
    return result

# ========== 期限付きBAN管理 ==========
def add_tempban(user_id, user_name, end_time_str, reason):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "REPLACE INTO active_tempbans VALUES (?, ?, ?, ?)",
        (str(user_id), user_name, end_time_str, reason)
    )
    conn.commit()
    conn.close()

def remove_tempban(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM active_tempbans WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()

def get_expired_tempbans():
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now(JST).isoformat()
    cur.execute("SELECT user_id, user_name FROM active_tempbans WHERE end_time < ?", (now,))
    result = cur.fetchall()
    conn.close()
    return result

# ========== 履歴記録 ==========
def add_security_log(user_id, user_name, action, reason, op_id=None, op_name=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO security_log VALUES (NULL, ?, ?, ?, ?, ?, ?)",
        (str(user_id), user_name, action, reason, datetime.now(JST).isoformat(),
         str(op_id) if op_id else None, op_name)
    )
    conn.commit()
    conn.close()

def get_security_stats(days=7):
    conn = get_connection()
    cur = conn.cursor()
    since = (datetime.now(JST) - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT action, COUNT(*) FROM security_log
        WHERE timestamp >= ? GROUP BY action
    """, (since,))
    result = dict(cur.fetchall())
    conn.close()
    return result

# ========== 注意文テンプレート ==========
def get_templates():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content FROM notice_templates")
    result = cur.fetchall()
    conn.close()
    return result

# ========== ログ送信 ==========
async def send_security_log(guild, title, desc, color=0x3498DB):
    if not MOD_LOG_CHANNEL_ID:
        return
    ch = guild.get_channel(MOD_LOG_CHANNEL_ID)
    if not ch:
        return
    embed = discord.Embed(title=title, description=desc, color=color, timestamp=datetime.now(JST))
    await ch.send(embed=embed)

# ========== 共通モーダル ==========
class ConfirmModal(discord.ui.Modal):
    def __init__(self, title, callback):
        super().__init__(title=title)
        self.callback = callback
        self.reason_in = discord.ui.TextInput(label="理由", required=True, max_length=100)
        self.add_item(self.reason_in)
    async def on_submit(self, itx):
        await self.callback(itx, self.reason_in.value)

# ========== ① チャンネルロック ==========
class LockChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="🔒 ロック実行", style=discord.ButtonStyle.danger)
    async def lock_btn(self, itx: discord.Interaction, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        async def _lock(itx, reason):
            perms = itx.channel.overwrites_for(itx.guild.default_role)
            perms.send_messages = False
            await itx.channel.set_permissions(itx.guild.default_role, overwrite=perms, reason=reason)
            add_security_log(itx.user.id, str(itx.user), "チャンネルロック", reason, itx.user.id, str(itx.user))
            await send_security_log(itx.guild, "🔒 チャンネルロック",
                f"チャンネル：{itx.channel.mention}\n実行者：{itx.user.mention}\n理由：{reason}", 0xF1C40F)
            await itx.response.edit_message(
                content=f"✅ {itx.channel.mention} をロックしました\n理由：{reason}",
                view=UnlockChannelView()
            )
        await itx.response.send_modal(ConfirmModal("チャンネルロック", _lock))
    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, itx, btn):
        await itx.response.edit_message(content="キャンセルしました", view=None)

class UnlockChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="🔓 解除", style=discord.ButtonStyle.success, custom_id="sec:unlock")
    async def unlock_btn(self, itx: discord.Interaction, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        async def _unlock(itx, reason):
            perms = itx.channel.overwrites_for(itx.guild.default_role)
            perms.send_messages = None
            await itx.channel.set_permissions(itx.guild.default_role, overwrite=perms, reason=reason)
            add_security_log(itx.user.id, str(itx.user), "チャンネル解除", reason, itx.user.id, str(itx.user))
            await send_security_log(itx.guild, "🔓 チャンネル解除",
                f"チャンネル：{itx.channel.mention}\n実行者：{itx.user.mention}\n理由：{reason}", 0x2ECC71)
            await itx.response.edit_message(content=f"✅ {itx.channel.mention} を解除しました", view=None)
        await itx.response.send_modal(ConfirmModal("チャンネル解除", _unlock))

# ========== ② 時間指定ミュート ==========
class MuteUserSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(discord.ui.UserSelect(placeholder="対象ユーザーを選択"))
    async def interaction_check(self, itx):
        target = self.children[0].values[0]
        view = MuteDurationView(target)
        await itx.response.send_message(
            f"対象：{target.mention}\n時間を選択してください",
            view=view, ephemeral=True
        )
        return True

class MuteDurationView(discord.ui.View):
    def __init__(self, target):
        super().__init__(timeout=120)
        self.target = target
    @discord.ui.button(label="1時間", style=discord.ButtonStyle.primary)
    async def h1(self, itx, btn): await self._mute(itx, 1)
    @discord.ui.button(label="6時間", style=discord.ButtonStyle.primary)
    async def h6(self, itx, btn): await self._mute(itx, 6)
    @discord.ui.button(label="24時間", style=discord.ButtonStyle.primary)
    async def h24(self, itx, btn): await self._mute(itx, 24)
    @discord.ui.button(label="7日", style=discord.ButtonStyle.primary)
    async def d7(self, itx, btn): await self._mute(itx, 24*7)
    @discord.ui.button(label="無期限", style=discord.ButtonStyle.danger)
    async def perm(self, itx, btn): await self._mute(itx, None)
    async def _mute(self, itx, hours):
        end_time = (datetime.now(JST) + timedelta(hours=hours)).isoformat() if hours else None
        async def _confirm(itx, reason):
            role = discord.utils.get(itx.guild.roles, name=MUTE_ROLE_NAME)
            if not role:
                await itx.response.send_message(f"❌ 「{MUTE_ROLE_NAME}」ロールを先に作成してください", ephemeral=True)
                return
            await self.target.add_roles(role, reason=reason)
            if end_time:
                add_mute(self.target.id, str(self.target), end_time, reason)
            add_security_log(self.target.id, str(self.target), "ミュート", reason, itx.user.id, str(itx.user))
            try:
                await self.target.send(
                    f"🔇 サーバーにてミュートされました\n"
                    f"理由：{reason}\n"
                    f"期間：{f'{hours}時間' if hours else '無期限'}"
                )
            except: pass
            await send_security_log(itx.guild, "🔇 ミュート実行",
                f"対象：{self.target.mention}\n実行者：{itx.user.mention}\n理由：{reason}\n期間：{f'{hours}時間' if hours else '無期限'}", 0xF79E1B)
            await itx.response.edit_message(content=f"✅ {self.target.mention} をミュートしました", view=None)
        await itx.response.send_modal(ConfirmModal("ミュート実行", _confirm))

# ========== ③ 期限付きBAN ==========
class TempBanSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(discord.ui.UserSelect(placeholder="対象ユーザーを選択"))
    async def interaction_check(self, itx):
        target = self.children[0].values[0]
        view = TempBanDurationView(target)
        await itx.response.send_message(
            f"対象：{target.mention}\n期間を選択してください",
            view=view, ephemeral=True
        )
        return True

class TempBanDurationView(discord.ui.View):
    def __init__(self, target):
        super().__init__(timeout=120)
        self.target = target
    @discord.ui.button(label="3日", style=discord.ButtonStyle.primary)
    async def d3(self, itx, btn): await self._ban(itx, 3)
    @discord.ui.button(label="7日", style=discord.ButtonStyle.primary)
    async def d7(self, itx, btn): await self._ban(itx, 7)
    @discord.ui.button(label="30日", style=discord.ButtonStyle.primary)
    async def d30(self, itx, btn): await self._ban(itx, 30)
    @discord.ui.button(label="無期限", style=discord.ButtonStyle.danger)
    async def perm(self, itx, btn): await self._ban(itx, None)
    async def _ban(self, itx, days):
        end_time = (datetime.now(JST) + timedelta(days=days)).isoformat() if days else None
        async def _confirm(itx, reason):
            try:
                await itx.guild.ban(self.target, reason=reason, delete_message_days=0)
            except Exception as e:
                await itx.response.send_message(f"❌ BAN失敗：{e}", ephemeral=True)
                return
            if end_time:
                add_tempban(self.target.id, str(self.target), end_time, reason)
            add_security_log(self.target.id, str(self.target), "期限付きBAN", reason, itx.user.id, str(itx.user))
            try:
                await self.target.send(
                    f"🚫 サーバーからBANされました\n"
                    f"理由：{reason}\n"
                    f"期間：{f'{days}日' if days else '無期限'}"
                )
            except: pass
            await send_security_log(itx.guild, "🚫 BAN実行",
                f"対象：{self.target.mention}\n実行者：{itx.user.mention}\n理由：{reason}\n期間：{f'{days}日' if days else '無期限'}", 0xE74C3C)
            await itx.response.edit_message(content=f"✅ {self.target.mention} をBANしました", view=None)
        await itx.response.send_modal(ConfirmModal("期限付きBAN", _confirm))

# ========== ④ スパム一括削除 ==========
class SpamDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(discord.ui.UserSelect(placeholder="対象ユーザーを選択"))
    async def interaction_check(self, itx):
        target = self.children[0].values[0]
        view = SpamDeleteCountView(target)
        await itx.response.send_message(
            f"対象：{target.mention}\n削除する件数を選択",
            view=view, ephemeral=True
        )
        return True

class SpamDeleteCountView(discord.ui.View):
    def __init__(self, target):
        super().__init__(timeout=120)
        self.target = target
    @discord.ui.button(label="直近10件", style=discord.ButtonStyle.primary)
    async def c10(self, itx, btn): await self._delete(itx, 10)
    @discord.ui.button(label="直近30件", style=discord.ButtonStyle.primary)
    async def c30(self, itx, btn): await self._delete(itx, 30)
    @discord.ui.button(label="直近50件", style=discord.ButtonStyle.primary)
    async def c50(self, itx, btn): await self._delete(itx, 50)
    async def _delete(self, itx, limit):
        deleted = 0
        async for msg in itx.channel.history(limit=200):
            if deleted >= limit: break
            if msg.author.id == self.target.id:
                try:
                    await msg.delete()
                    deleted += 1
                except: pass
        add_security_log(self.target.id, str(self.target), "スパム削除", f"{deleted}件", itx.user.id, str(itx.user))
        await send_security_log(itx.guild, "🧹 スパム一括削除",
            f"対象：{self.target.mention}\n実行者：{itx.user.mention}\n削除件数：{deleted}件", 0x9B59B6)
        await itx.response.edit_message(content=f"✅ {deleted}件削除しました", view=None)

# ========== ⑤ 緊急サーバー封鎖 ==========
class EmergencyLockView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="🚨 封鎖実行", style=discord.ButtonStyle.danger)
    async def lock_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        async def _lock(itx, reason):
            perms = itx.guild.default_role.permissions
            perms.send_messages = False
            perms.create_instant_invite = False
            await itx.guild.edit(default_role_permissions=perms, reason=reason)
            add_security_log(itx.user.id, str(itx.user), "緊急封鎖", reason, itx.user.id, str(itx.user))
            await send_security_log(itx.guild, "🚨 緊急サーバー封鎖",
                f"実行者：{itx.user.mention}\n理由：{reason}", 0xE74C3C)
            await itx.response.edit_message(
                content=f"✅ サーバーを封鎖しました\n理由：{reason}",
                view=EmergencyUnlockView()
            )
        await itx.response.send_modal(ConfirmModal("緊急封鎖", _lock))

class EmergencyUnlockView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="✅ 封鎖解除", style=discord.ButtonStyle.success, custom_id="sec:emergency_unlock")
    async def unlock_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        async def _unlock(itx, reason):
            perms = itx.guild.default_role.permissions
            perms.send_messages = True
            perms.create_instant_invite = True
            await itx.guild.edit(default_role_permissions=perms, reason=reason)
            add_security_log(itx.user.id, str(itx.user), "緊急封鎖解除", reason, itx.user.id, str(itx.user))
            await send_security_log(itx.guild, "✅ 緊急封鎖解除",
                f"実行者：{itx.user.mention}\n理由：{reason}", 0x2ECC71)
            await itx.response.edit_message(content="✅ 通常運用に戻しました", view=None)
        await itx.response.send_modal(ConfirmModal("封鎖解除", _unlock))

# ========== ⑥ 監視チャンネル設定 ==========
class MonitoredChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="➕ 追加", style=discord.ButtonStyle.success)
    async def add_btn(self, itx, btn):
        class AddView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.ChannelSelect(placeholder="追加するチャンネル", channel_types=[discord.ChannelType.text]))
            async def interaction_check(self, itx):
                ch = self.children[0].values[0]
                add_monitored_channel(ch.id, ch.name)
                await itx.response.send_message(f"✅ {ch.mention} を監視対象に追加しました", ephemeral=True)
                return True
        await itx.response.send_message("追加するチャンネルを選択", view=AddView(), ephemeral=True)
    @discord.ui.button(label="➖ 除外", style=discord.ButtonStyle.danger)
    async def remove_btn(self, itx, btn):
        ch_list = get_monitored_channels()
        if not ch_list:
            await itx.response.send_message("❌ 登録されていません", ephemeral=True)
            return
        class RemoveView(discord.ui.View):
            def __init__(self):
                super().__init__()
                opts = [discord.SelectOption(label=name, value=cid) for cid, name in ch_list]
                self.add_item(discord.ui.Select(placeholder="除外するチャンネル", options=opts))
            async def callback(self, itx):
                cid = self.children[0].values[0]
                remove_monitored_channel(cid)
                await itx.response.send_message(f"✅ 除外しました", ephemeral=True)
        await itx.response.send_message("除外するチャンネルを選択", view=RemoveView(), ephemeral=True)
    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary)
    async def back_btn(self, itx, btn):
        embed = await build_security_embed()
        await itx.response.edit_message(embed=embed, view=SecurityMainView())

# ========== ⑦ 禁止ワード管理画面 ==========
class ForbiddenWordView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    async def build_embed(self):
        words = get_forbidden_words()
        if words:
            word_list = "\n".join([f" [{wid}] `{word}`" for wid, word, _, _ in words])
        else:
            word_list = "⚠️ 登録された禁止ワードはありません"
        status = get_setting('word_monitor')
        embed = discord.Embed(
            title="🔍 禁止ワード管理",
            description=word_list,
            color=0x3498DB
        )
        embed.set_footer(text=f"現在の状態：{'✅ 検知有効' if status=='on' else '❌ 検知無効'}")
        return embed

    @discord.ui.button(label="➕ 新規登録", style=discord.ButtonStyle.success, row=0)
    async def add_btn(self, itx, btn):
        class AddModal(discord.ui.Modal, title="禁止ワード新規登録"):
            word = discord.ui.TextInput(label="禁止する言葉", required=True, max_length=100)
            async def on_submit(self, itx):
                add_forbidden_word(self.word.value)
                await itx.response.send_message(f"✅ 「{self.word.value}」を登録しました", ephemeral=True)
        await itx.response.send_modal(AddModal())
        await asyncio.sleep(0.4)
        embed = await self.build_embed()
        await itx.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="➖ 登録解除", style=discord.ButtonStyle.danger, row=0)
    async def remove_btn(self, itx, btn):
        words = get_forbidden_words()
        if not words:
            await itx.response.send_message("❌ 登録されていません", ephemeral=True)
            return
        class RemoveView(discord.ui.View):
            def __init__(self, parent_view):
                super().__init__(timeout=120)
                self.parent = parent_view
                opts = [discord.SelectOption(label=f"{word[:25]}", value=str(wid)) for wid, word, _, _ in words]
                self.add_item(discord.ui.Select(placeholder="解除するワードを選択", options=opts))
            async def callback(self, itx):
                wid = int(self.children[0].values[0])
                remove_forbidden_word(wid)
                await itx.response.send_message("✅ 登録を解除しました", ephemeral=True)
                await asyncio.sleep(0.4)
                embed = await self.parent.build_embed()
                await itx.edit_original_response(embed=embed, view=self.parent)
        await itx.response.send_message("解除するワードを選択してください", view=RemoveView(self), ephemeral=True)

    @discord.ui.button(label="❌ 状態読込中...", style=discord.ButtonStyle.secondary, row=1, custom_id="fw:toggle")
    async def toggle_btn(self, itx, btn):
        new_val = 'on' if get_setting('word_monitor') == 'off' else 'off'
        set_setting('word_monitor', new_val)
        # ボタンのラベルを更新
        if new_val == 'on':
            btn.label = '✅ 検知中 → OFFにする'
            btn.style = discord.ButtonStyle.success
        else:
            btn.label = '❌ 停止中 → ONにする'
            btn.style = discord.ButtonStyle.secondary
        embed = await self.build_embed()
        await itx.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔙 メインに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back_btn(self, itx, btn):
        embed = await build_security_embed()
        await itx.response.edit_message(embed=embed, view=SecurityMainView())

# ========== ⑧ 注意文テンプレート送信 ==========
class SendNoticeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(discord.ui.UserSelect(placeholder="対象ユーザーを選択"))
    async def interaction_check(self, itx):
        target = self.children[0].values[0]
        templates = get_templates()
        class SelectView(discord.ui.View):
            def __init__(self):
                super().__init__()
                opts = [discord.SelectOption(label=title, value=str(tid)) for tid, title, _ in templates]
                self.add_item(discord.ui.Select(placeholder="送信する文面", options=opts))
            async def callback(self, itx):
                tid = int(self.children[0].values[0])
                for t in templates:
                    if t[0] == tid:
                        _, title, content = t
                        break
                try:
                    await target.send(f"⚠️ {title}\n\n{content}")
                except:
                    pass
                add_security_log(target.id, str(target), f"注意送信:{title}", content, itx.user.id, str(itx.user))
                await send_security_log(itx.guild, f"✍️ {title}",
                    f"対象：{target.mention}\n実行者：{itx.user.mention}\n内容：{content}", 0x3498DB)
                await itx.response.send_message(f"✅ {target.mention} に送信しました", ephemeral=True)
        await itx.response.send_message("送信する文面を選択", view=SelectView(), ephemeral=True)
        return True

# ========== ⑨ 状況サマリー ==========
async def build_stats_embed():
    stats = get_security_stats(7)
    embed = discord.Embed(title="📊 治安状況サマリー（過去7日間）", color=0x3498DB)
    embed.add_field(name="🔇 ミュート", value=str(stats.get("ミュート", 0)), inline=True)
    embed.add_field(name="🚫 BAN", value=str(stats.get("期限付きBAN", 0)), inline=True)
    embed.add_field(name="🧹 削除", value=str(stats.get("スパム削除", 0)), inline=True)
    embed.add_field(name="⚠️ 注意", value=str(sum(v for k, v in stats.items() if k.startswith("注意送信"))), inline=True)
    return embed

# ========== 埋め込み作成 ==========
async def build_security_embed():
    ch_list = get_monitored_channels()
    ch_text = "\n".join([f"• <#{cid}> {name}" for cid, name in ch_list]) if ch_list else "⚠️ 登録なし（全チャンネル未監視）"
    embed = discord.Embed(title="🛡️ 治安管理パネル", color=0x992D22)
    embed.add_field(name="📺 監視チャンネル", value=ch_text, inline=False)
    embed.add_field(name="⚡ 高速投稿監視", value=f"✅ {get_setting('spam_monitor')}" if get_setting('spam_monitor')=='on' else f"❌ {get_setting('spam_monitor')}", inline=True)
    embed.add_field(name="🔗 リンク制限", value=f"✅ {get_setting('link_monitor')}" if get_setting('link_monitor')=='on' else f"❌ {get_setting('link_monitor')}", inline=True)
    embed.add_field(name="🔍 禁止ワード", value=f"✅ {get_setting('word_monitor')}" if get_setting('word_monitor')=='on' else f"❌ {get_setting('word_monitor')}", inline=True)
    return embed

# ========== メインパネル ==========
class SecurityMainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        init_security_tables()

    # ===== 1行目 =====
    @discord.ui.button(label="🔒 チャンネルロック", style=discord.ButtonStyle.secondary, row=0)
    async def lock_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(f"チャンネル：{itx.channel.mention}\n理由を入力してロック実行", view=LockChannelView(), ephemeral=True)

    @discord.ui.button(label="🔇 時間指定ミュート", style=discord.ButtonStyle.primary, row=0)
    async def mute_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message("対象ユーザーを選択してください", view=MuteUserSelectView(), ephemeral=True)

    @discord.ui.button(label="⏰ 期限付きBAN", style=discord.ButtonStyle.danger, row=0)
    async def ban_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message("対象ユーザーを選択してください", view=TempBanSelectView(), ephemeral=True)

    # ===== 2行目 =====
    @discord.ui.button(label="🧹 スパム削除", style=discord.ButtonStyle.primary, row=1)
    async def spamdel_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message("対象ユーザーを選択してください", view=SpamDeleteView(), ephemeral=True)

    @discord.ui.button(label="🚨 緊急封鎖", style=discord.ButtonStyle.danger, row=1)
    async def emergency_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message("⚠️ サーバー全体を一時停止します\n理由を入力して実行", view=EmergencyLockView(), ephemeral=True)

    @discord.ui.button(label="📺 監視チャンネル", style=discord.ButtonStyle.primary, row=1)
    async def ch_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        ch_list = get_monitored_channels()
        ch_text = "\n".join([f"• <#{cid}> {name}" for cid, name in ch_list]) if ch_list else "⚠️ 登録なし"
        embed = discord.Embed(title="📺 監視チャンネル設定", description=ch_text, color=0x3498DB)
        await itx.response.send_message(embed=embed, view=MonitoredChannelView(), ephemeral=True)

    # ===== 3行目 =====
    @discord.ui.button(label="⚡ 高速投稿", style=discord.ButtonStyle.success, row=2)
    async def spam_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        new_val = 'on' if get_setting('spam_monitor') == 'off' else 'off'
        set_setting('spam_monitor', new_val)
        embed = await build_security_embed()
        await itx.response.edit_message(embed=embed, view=SecurityMainView())

    @discord.ui.button(label="🔗 リンク制限", style=discord.ButtonStyle.success, row=2)
    async def link_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        new_val = 'on' if get_setting('link_monitor') == 'off' else 'off'
        set_setting('link_monitor', new_val)
        embed = await build_security_embed()
        await itx.response.edit_message(embed=embed, view=SecurityMainView())

    @discord.ui.button(label="🔍 禁止ワード管理", style=discord.ButtonStyle.primary, row=2)
    async def wordmanage_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        view = ForbiddenWordView()
        embed = await view.build_embed()
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    # ===== 4行目 =====
    @discord.ui.button(label="✍️ 注意文送信", style=discord.ButtonStyle.secondary, row=3)
    async def notice_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message("対象ユーザーを選択してください", view=SendNoticeView(), ephemeral=True)

    @discord.ui.button(label="📊 状況サマリー", style=discord.ButtonStyle.secondary, row=3)
    async def stats_btn(self, itx, btn):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        embed = await build_stats_embed()
        await itx.response.send_message(embed=embed, ephemeral=True)

async def setup(tree: app_commands.CommandTree):
    init_security_tables()

    @tree.command(name="治安パネル設置", description="治安管理パネル（オーナー専用）")
    @app_commands.check(is_owner)
    async def cmd(itx: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ 治安管理パネル",
            description="""🔒 チャンネルロック → 発言一時停止
🔇 時間指定ミュート → 期間を指定して発言制限
⏰ 期限付きBAN → 自動解除されるBAN
🧹 スパム削除 → 対象者のメッセージ一括削除
🚨 緊急封鎖 → サーバー全体を一時停止
📺 監視チャンネル → 自動検知の対象を選択

⚡ 高速投稿 / 🔗 リンク制限 → ON/OFF
🔍 禁止ワード管理 → 一覧・登録・解除・ON/OFF
✍️ 注意文送信 → 定型文をDM送信
📊 状況サマリー → 集計表示

※ 監視対象登録チャンネルでのみ自動検知が動作します
※ 全操作はオーナー専用です""",
            color=0x992D22
        )
        await itx.response.send_message(embed=embed, view=SecurityMainView())
        await itx.followup.send("✅ 治安パネル設置完了", ephemeral=True)
# ===== 一括登録用（1回実行したら削除してOK） =====
async def register_default_channels():
    from core.database import get_connection
    conn = get_connection()
    cur = conn.cursor()
    # 登録するチャンネル
    ch_id = "1558099501305176095"
    cur.execute("SELECT 1 FROM monitored_channels WHERE channel_id=?", (ch_id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO monitored_channels VALUES (?, ?, ?)",
            (ch_id, "指定チャンネル", "2026-10-11T23:18:00+09:00")
        )
        print(f"✅ チャンネル {ch_id} を登録しました")
    else:
        print(f"ℹ️ 既に登録済み：{ch_id}")
    conn.commit()
    conn.close()

# 起動時に実行
import discord
original_on_ready = getattr(discord.Client, '_original_on_ready', None)
async def patched_on_ready(self):
    await register_default_channels()
    if original_on_ready:
        await original_on_ready(self)
discord.Client._original_on_ready = getattr(discord.Client, 'on_ready', None)
discord.Client.on_ready = patched_on_ready
