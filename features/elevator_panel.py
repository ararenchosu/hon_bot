import discord
from discord import app_commands
from core.common import is_owner
# ========== 🔧 設定 ==========
# 常に表示される共通カテゴリ（0階：誰でも最初から見える）
ALWAYS_VISIBLE_CATEGORY_IDS = [
    1542788842078216295,  # 固定表示
    1558092186602704947,  # ✅ 💬 雑談 → 0階へ移動
]
# 「鯖メン」ロール名
MEMBER_ROLE_NAME = "鯖メン"
FLOOR_CONFIG = {
    "0階": {
        "role_name": None,
        "role_id": None,
        "category_ids": [
            1542788842078216295,  # 固定表示
            1558092186602704947,  # ✅ 💬 雑談
        ]
    },
    "1階": {
        "role_name": "1階入出許可証",
        "role_id": None,
        "category_ids": [
            1558099663922405376,  # ✅ 📞 通話作成 → 1階に残す
            1558697840031568032,  # 1日1回限定
            1558088654147166219,  # ロール付与＆剥奪
            1558080162367545375,  # メンバー呼び出し
        ]
    },
    "2階": {
        "role_name": "2階入出許可証",
        "role_id": None,
        "category_ids": [
            1558766861859037234,  # カジノ機能
            1558467161146663023,  # オセロ機能
        ]
    },
}
PANEL_EMBED = {
    "title": "🏢 エレベーター",
    "description": (
        "下のメニューから行き先の階を選択してください。\n"
        "📌 **0階**：固定カテゴリ＋💬雑談（常時表示）\n"
        "🔹 **1階**：📞通話作成・くじ引き・ロール管理等\n"
        "🔹 **2階**：カジノ・オセロ\n"
        "🔄 設定変更後は「パネル更新」を押してください"
    ),
    "color": 0x3498DB
}
# ===============================================================
def build_floor_options():
    options = []
    for floor_name, info in FLOOR_CONFIG.items():
        if floor_name == "0階":
            desc = "固定＋雑談が常時表示"
        else:
            desc = f"{len(info['category_ids'])}個のカテゴリを表示"
        options.append(discord.SelectOption(
            label=floor_name, description=desc, emoji="🏢"
        ))
    return options
def make_embed():
    return discord.Embed(
        title=PANEL_EMBED["title"],
        description=PANEL_EMBED["description"],
        color=PANEL_EMBED["color"]
    )
class EditEmbedModal(discord.ui.Modal, title="✏️ パネル内容変更"):
    def __init__(self, current_title, current_desc):
        super().__init__(timeout=None)
        self.title_input = discord.ui.TextInput(
            label="タイトル",
            default=current_title,
            max_length=100,
            required=True
        )
        self.desc_input = discord.ui.TextInput(
            label="説明文",
            default=current_desc,
            style=discord.TextStyle.long,
            max_length=2000,
            required=True
        )
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
    async def on_submit(self, itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        PANEL_EMBED["title"] = self.title_input.value
        PANEL_EMBED["description"] = self.desc_input.value
        await itx.response.edit_message(embed=make_embed(), view=ElevatorView())
        await itx.followup.send("✅ 更新完了", ephemeral=True)
class ElevatorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self._floor_select.options = build_floor_options()
    @discord.ui.select(
        placeholder="🏢 行き先の階を選択してください",
        custom_id="elevator:select_floor"
    )
    async def _floor_select(self, itx: discord.Interaction, select: discord.ui.Select):
        target_floor = select.values[0]
        guild = itx.guild
        user = itx.user
        # オーナー以外 → 選択中のロールを削除
        if not is_owner(itx):
            for floor_name, info in FLOOR_CONFIG.items():
                if floor_name == "0階":
                    continue
                role = None
                if info["role_id"]:
                    role = guild.get_role(info["role_id"])
                if not role and info["role_name"]:
                    role = discord.utils.get(guild.roles, name=info["role_name"])
                if role and role in user.roles:
                    await user.remove_roles(role)
        # 0階選択
        if target_floor == "0階":
            common_list = []
            for cid in FLOOR_CONFIG["0階"]["category_ids"]:
                cat = guild.get_channel(cid)
                common_list.append(f"✅ {cat.name if cat else f'ID:{cid}'}")
            await itx.response.send_message(
                "✅ 0階に移動しました！\n"
                "固定カテゴリ＋雑談が表示されます。\n\n"
                "📌 表示カテゴリ：\n" + "\n".join(common_list),
                ephemeral=True
            )
            return
        # 1階・2階…
        target_info = FLOOR_CONFIG[target_floor]
        if not is_owner(itx):
            target_role = None
            if target_info["role_id"]:
                target_role = guild.get_role(target_info["role_id"])
            if not target_role and target_info["role_name"]:
                target_role = discord.utils.get(guild.roles, name=target_info["role_name"])
            if not target_role:
                await itx.response.send_message(
                    f"❌ 「{target_info['role_name']}」ロールが見つかりません。",
                    ephemeral=True
                )
                return
            await user.add_roles(target_role)
            role_note = f"付与ロール：`{target_role.name}`"
        else:
            role_note = "👑 オーナー：全カテゴリ表示中"
        common_list = []
        for cid in ALWAYS_VISIBLE_CATEGORY_IDS:
            cat = guild.get_channel(cid)
            common_list.append(f"✅ {cat.name if cat else f'ID:{cid}'}")
        floor_list = []
        for cid in target_info["category_ids"]:
            cat = guild.get_channel(cid)
            floor_list.append(f"✅ {cat.name if cat else f'ID:{cid}'}")
        await itx.response.send_message(
            f"✅ {target_floor} に移動しました！\n{role_note}\n\n"
            f"📌 常に表示：\n" + "\n".join(common_list) + "\n\n"
            f"📂 {target_floor}のカテゴリ：\n" + "\n".join(floor_list),
            ephemeral=True
        )
    @discord.ui.button(
        label="✏️ 内容変更",
        style=discord.ButtonStyle.secondary,
        custom_id="elevator:edit_embed",
        row=1
    )
    async def _edit_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用", ephemeral=True)
            return
        # ✅ 現在メッセージに表示されている内容を取得
        embed = itx.message.embeds[0] if itx.message.embeds else None
        if embed:
            current_title = embed.title or ""
            current_desc = embed.description or ""
        else:
            current_title = PANEL_EMBED["title"]
            current_desc = PANEL_EMBED["description"]
        # 現在の内容を初期値にしてモーダルを開く
        await itx.response.send_modal(EditEmbedModal(current_title, current_desc))
    @discord.ui.button(
        label="🔄 パネル更新",
        style=discord.ButtonStyle.primary,
        custom_id="elevator:refresh",
        row=1
    )
    async def _refresh_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        await itx.response.edit_message(embed=make_embed(), view=ElevatorView())
        await itx.followup.send("✅ パネルを更新しました！", ephemeral=True)
    @discord.ui.button(
        label="❌ 全階を閉じる",
        style=discord.ButtonStyle.danger,
        custom_id="elevator:clear",
        row=2
    )
    async def _clear_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if is_owner(itx):
            await itx.response.send_message("👑 オーナー：常に全カテゴリ表示中", ephemeral=True)
            return
        guild = itx.guild
        user = itx.user
        removed_list = []
        for floor_name, info in FLOOR_CONFIG.items():
            if floor_name == "0階":
                continue
            role = None
            if info["role_id"]:
                role = guild.get_role(info["role_id"])
            if not role and info["role_name"]:
                role = discord.utils.get(guild.roles, name=info["role_name"])
            if role and role in user.roles:
                await user.remove_roles(role)
                removed_list.append(f"`{role.name}`")
        if removed_list:
            await itx.response.send_message(
                "✅ 全ての階を閉じました。\n"
                "📌 0階の状態に戻ります。",
                ephemeral=True
            )
        else:
            await itx.response.send_message("ℹ️ 既に0階です", ephemeral=True)
async def setup(tree: app_commands.CommandTree, bot=None):
    if bot is not None and not hasattr(bot, "_elevator_view_registered"):
        bot.add_view(ElevatorView())
        bot._elevator_view_registered = True
        print("✅ elevator_panel 永続View登録完了")
    @tree.command(
        name="エレベーター設置",
        description="🏢 階層別カテゴリ切り替えパネル"
    )
    @app_commands.check(is_owner)
    async def cmd(itx: discord.Interaction):
        await itx.response.send_message(embed=make_embed(), view=ElevatorView())
        await itx.followup.send("✅ 設置完了", ephemeral=True)
