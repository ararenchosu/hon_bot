import discord
from discord import app_commands
from core.common import is_owner
from core.database import get_connection

# ========== 🔴 除外リスト：ここに「制限しないコマンド名」を書く ==========
EXCLUDE_COMMANDS = [
    "コマンド確認パネル",
    # 例："スロット", "ブラックジャック", "ハイアンドロー"
    # 遊びたいコマンドはここに追加するだけ！
]
# =========================================================================

# ========== データベース初期化 ==========
def init_restrict_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS restricted_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_name TEXT NOT NULL UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS restrict_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL UNIQUE
        )
    """)
    conn.commit()
    conn.close()

# ========== データ操作用：禁止コマンド ==========
def get_restricted_cmds():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT command_name FROM restricted_commands ORDER BY command_name")
    items = [row[0] for row in cur.fetchall()]
    conn.close()
    return items

def add_restricted_cmd(name: str):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO restricted_commands (command_name) VALUES (?)", (name,))
        conn.commit()
        ok = True
    except:
        ok = False
    conn.close()
    return ok

def remove_restricted_cmd(name: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM restricted_commands WHERE command_name = ?", (name,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0

# ========== データ操作用：制限チャンネル ==========
def get_restrict_channels():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT channel_id FROM restrict_channels")
    items = [row[0] for row in cur.fetchall()]
    conn.close()
    return items

def add_restrict_channel(channel_id: int):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO restrict_channels (channel_id) VALUES (?)", (channel_id,))
        conn.commit()
        ok = True
    except:
        ok = False
    conn.close()
    return ok

def remove_restrict_channel(channel_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM restrict_channels WHERE channel_id = ?", (channel_id,))
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0

# ========== 共通判定 ==========
def is_restricted_here(channel_id: int, cmd_name: str):
    if channel_id not in get_restrict_channels():
        return False
    return cmd_name in get_restricted_cmds()

# ========== 一括チェッカー（全コマンド自動判定） ==========
async def check_command_allowed(itx: discord.Interaction):
    """個別ファイル編集不要！自動的に全コマンドをチェック"""
    # 👑 オーナーは常に許可
    if is_owner(itx):
        return True
    # コマンド名取得
    cmd_name = itx.command.name if itx.command else ""
    # ✅ 除外リストにあるコマンドは無制限で許可
    if cmd_name in EXCLUDE_COMMANDS:
        return True
    # 🚫 制限判定
    if itx.guild and itx.channel:
        if is_restricted_here(itx.channel.id, cmd_name):
            await itx.response.send_message(
                f"🚫 このチャンネルでは `/{cmd_name}` を使用できません。",
                ephemeral=True
            )
            return False
    return True

# ========== メインパネル ==========
class CommandRestrictMainView(discord.ui.View):
    def __init__(self, all_cmds=None):
        super().__init__(timeout=None)
        self.all_cmds = all_cmds or []

    def make_embed(self):
        rc = get_restricted_cmds()
        chs = get_restrict_channels()
        ch_text = "\n".join(f"<#{cid}>" for cid in chs) if chs else "なし"
        rc_text = "\n".join(f"・`/{n}`" for n in rc) if rc else "なし"
        exclude_text = "\n".join(f"・`/{n}`" for n in EXCLUDE_COMMANDS) if EXCLUDE_COMMANDS else "なし"

        return discord.Embed(
            title="🔒 コマンド使用制限 管理パネル",
            description=(
                "📌 指定チャンネル＋指定コマンド → 一般メンバー使用不可\n"
                "👑 オーナーは常に使用可\n\n"
                f"📺 制限中のチャンネル:\n{ch_text}\n\n"
                f"🚫 禁止中のコマンド:\n{rc_text}\n\n"
                f"✅ 除外（どこでも使用可）:\n{exclude_text}"
            ),
            color=0x9B59B6
        )

    @discord.ui.button(label="📺 チャンネル設定", style=discord.ButtonStyle.primary, custom_id="restrict:ch_add", row=0)
    async def ch_add_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        await itx.response.send_message(
            "✅ 制限を追加するチャンネルを選択",
            view=ChannelAddSelectView(),
            ephemeral=True
        )

    @discord.ui.button(label="📺 チャンネル解除", style=discord.ButtonStyle.secondary, custom_id="restrict:ch_del", row=0)
    async def ch_del_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        chs = get_restrict_channels()
        if not chs:
            await itx.response.send_message("❌ 登録されたチャンネルがありません", ephemeral=True)
            return
        await itx.response.send_message(
            "✅ 制限を解除するチャンネルを選択",
            view=ChannelRemoveSelectView(chs),
            ephemeral=True
        )

    @discord.ui.button(label="🚫 禁止コマンド設定", style=discord.ButtonStyle.danger, custom_id="restrict:cmd_add", row=1)
    async def cmd_add_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        if not self.all_cmds:
            await itx.response.send_message(
                "⚠️ コマンド一覧が空です。\n先に「🔄 コマンド更新」を押してください。",
                ephemeral=True
            )
            return
        await itx.response.send_message(
            "✅ 禁止するコマンドを選択（複数可）",
            view=CommandAddSelectView(self.all_cmds),
            ephemeral=True
        )

    @discord.ui.button(label="✅ 禁止コマンド解除", style=discord.ButtonStyle.success, custom_id="restrict:cmd_del", row=1)
    async def cmd_del_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        rc = get_restricted_cmds()
        if not rc:
            await itx.response.send_message("❌ 禁止コマンドが登録されていません", ephemeral=True)
            return
        await itx.response.send_message(
            "✅ 禁止を解除するコマンドを選択",
            view=CommandRemoveSelectView(rc),
            ephemeral=True
        )

    @discord.ui.button(label="🔄 コマンド更新", style=discord.ButtonStyle.primary, custom_id="restrict:refresh", row=2)
    async def refresh_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if hasattr(itx, 'tree') and itx.tree:
            self.all_cmds = sorted([c.name for c in itx.tree.get_commands()])
        await itx.response.edit_message(embed=self.make_embed(), view=self)
        await itx.followup.send("✅ コマンド一覧を更新しました！", ephemeral=True)

# ========== チャンネル選択：追加 ==========
class ChannelAddSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(ChannelAddMenu())

class ChannelAddMenu(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="制限に追加するチャンネル選択",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=5
        )
    async def callback(self, itx: discord.Interaction):
        added = []
        for ch in self.values:
            if add_restrict_channel(ch.id):
                added.append(ch.mention)
        if added:
            await itx.response.send_message(
                f"✅ 追加: {', '.join(added)}",
                ephemeral=True
            )
        else:
            await itx.response.send_message(
                "⚠️ 選択したチャンネルはすでに登録されています",
                ephemeral=True
            )

# ========== チャンネル選択：解除 ==========
class ChannelRemoveSelectView(discord.ui.View):
    def __init__(self, ch_list):
        super().__init__(timeout=60)
        options = []
        for cid in ch_list[:25]:
            # 一時的にitxを使うのでcallback内で取得
            pass
        self.options_list = options

class ChannelRemoveMenu(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="制限から解除するチャンネル選択", options=options)
    async def callback(self, itx: discord.Interaction):
        cid = int(self.values[0])
        if remove_restrict_channel(cid):
            await itx.response.send_message(f"✅ 解除: <#{cid}>", ephemeral=True)
        else:
            await itx.response.send_message("❌ 解除に失敗", ephemeral=True)

# ========== 禁止コマンド選択：追加 ==========
class CommandAddSelectView(discord.ui.View):
    def __init__(self, all_cmds):
        super().__init__(timeout=120)
        rc = get_restricted_cmds()
        options = [
            discord.SelectOption(label=f"/{name}", value=name, default=(name in rc))
            for name in sorted(all_cmds)[:25]
        ]
        self.add_item(CommandAddMenu(options))

class CommandAddMenu(discord.ui.Select):
    def __init__(self, options):
        super().__init__(
            placeholder="禁止にするコマンド選択",
            options=options,
            min_values=1,
            max_values=min(25, len(options))
        )
    async def callback(self, itx: discord.Interaction):
        added = []
        for name in self.values:
            if add_restricted_cmd(name):
                added.append(f"`/{name}`")
        if added:
            await itx.response.send_message(
                f"✅ 禁止追加: {', '.join(added)}",
                ephemeral=True
            )
        else:
            await itx.response.send_message(
                "⚠️ 選択したコマンドはすでに禁止設定されています",
                ephemeral=True
            )

# ========== 禁止コマンド選択：解除 ==========
class CommandRemoveSelectView(discord.ui.View):
    def __init__(self, restricted_list):
        super().__init__(timeout=60)
        options = [discord.SelectOption(label=f"/{name}", value=name) for name in restricted_list[:25]]
        self.add_item(CommandRemoveMenu(options))

class CommandRemoveMenu(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="禁止を解除するコマンド選択", options=options)
    async def callback(self, itx: discord.Interaction):
        name = self.values[0]
        if remove_restricted_cmd(name):
            await itx.response.send_message(f"✅ 禁止解除: `/{name}`", ephemeral=True)
        else:
            await itx.response.send_message("❌ 解除に失敗", ephemeral=True)

# ========== セットアップ ==========
async def setup(tree: app_commands.CommandTree):
    init_restrict_tables()
    bot = tree.client
    all_names = sorted([c.name for c in tree.get_commands()])
    main_view = CommandRestrictMainView(all_names)
    bot.add_view(main_view)

    @tree.command(
        name="コマンド制限パネル設置",
        description="チャンネル別コマンド制限管理（オーナー専用）"
    )
    @app_commands.check(is_owner)
    async def restrict_panel_cmd(itx: discord.Interaction):
        latest_cmds = sorted([c.name for c in tree.get_commands()])
        view = CommandRestrictMainView(latest_cmds)
        await itx.response.send_message(embed=view.make_embed(), view=view)
