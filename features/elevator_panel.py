import discord
from discord import app_commands
from core.common import is_owner

# ========== 設定 ==========
# 常に表示される共通カテゴリ（どの階にいても見える）
ALWAYS_VISIBLE_CATEGORY_IDS = [
    1542788842078216295,  # 固定表示カテゴリ
]

FLOOR_CONFIG = {
    "1階": {
        "role_name": "1階入出許可証",
        "role_id": None,  # ← 実際のロールIDがあれば記入
        "category_ids": [
            1558099663922405376,  # 通話作成
            1558092186602704947,  # 雑談
            1558697840031568032,  # 1日1回限定
            1558088654147166219,  # ロール付与＆剥奪
            1558080162367545375,  # メンバー呼び出し
        ]
    },
    "2階": {
        "role_name": "2階入出許可証",
        "role_id": None,  # ← 実際のロールIDがあれば記入
        "category_ids": [
            1558766861859037234,  # カジノ機能
            1558467161146663023,  # オセロ機能
        ]
    }
}
# ==========================

class ElevatorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="🏢 行き先の階を選択してください",
        options=[
            discord.SelectOption(
                label=floor_name,
                description=f"{len(info['category_ids'])}個 + 共通カテゴリが表示",
                emoji="🏢"
            )
            for floor_name, info in FLOOR_CONFIG.items()
        ],
        custom_id="elevator:select_floor"
    )
    async def select_floor(self, itx: discord.Interaction, selected_values):
        target_floor = selected_values[0]
        guild = itx.guild
        user = itx.user

        # 全階のロールをいったん削除
        for info in FLOOR_CONFIG.values():
            role = None
            if info["role_id"]:
                role = guild.get_role(info["role_id"])
            if not role:
                role = discord.utils.get(guild.roles, name=info["role_name"])
            if role and role in user.roles:
                await user.remove_roles(role)

        # 選択された階のロールを付与
        target_info = FLOOR_CONFIG[target_floor]
        target_role = None
        if target_info["role_id"]:
            target_role = guild.get_role(target_info["role_id"])
        if not target_role:
            target_role = discord.utils.get(guild.roles, name=target_info["role_name"])

        if not target_role:
            await itx.response.send_message(
                f"❌ 「{target_info['role_name']}」ロールが見つかりません。",
                ephemeral=True
            )
            return

        await user.add_roles(target_role)

        # 表示カテゴリ一覧を作成
        common_list = []
        for cid in ALWAYS_VISIBLE_CATEGORY_IDS:
            cat = guild.get_channel(cid)
            common_list.append(f"✅ {cat.name if cat else f'ID:{cid}'}")

        floor_list = []
        for cid in target_info["category_ids"]:
            cat = guild.get_channel(cid)
            floor_list.append(f"✅ {cat.name if cat else f'ID:{cid}'}")

        await itx.response.send_message(
            f"✅ {target_floor} に移動しました！\n"
            f"付与ロール：`{target_role.name}`\n\n"
            f"📌 常に表示：\n" + "\n".join(common_list) + "\n\n"
            f"📂 {target_floor}のカテゴリ：\n" + "\n".join(floor_list),
            ephemeral=True
        )

    @discord.ui.button(
        label="❌ 階を閉じる（共通はそのまま）",
        style=discord.ButtonStyle.secondary,
        custom_id="elevator:clear"
    )
    async def clear_btn(self, itx: discord.Interaction, btn):
        guild = itx.guild
        user = itx.user
        removed_list = []

        for info in FLOOR_CONFIG.values():
            role = None
            if info["role_id"]:
                role = guild.get_role(info["role_id"])
            if not role:
                role = discord.utils.get(guild.roles, name=info["role_name"])
            if role and role in user.roles:
                await user.remove_roles(role)
                removed_list.append(f"`{role.name}`")

        if removed_list:
            await itx.response.send_message(
                f"✅ 以下のロールを削除しました。\n"
                f"共通カテゴリはそのまま表示されています。\n\n"
                f"削除：{', '.join(removed_list)}",
                ephemeral=True
            )
        else:
            await itx.response.send_message(
                "ℹ️ 現在どの階にも入っていません。\n"
                "共通カテゴリは表示されたままです。",
                ephemeral=True
            )

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
        embed = discord.Embed(
            title="🏢 エレベーター",
            description=(
                "下のメニューから行き先の階を選択してください。\n"
                f"📌 カテゴリID:`{ALWAYS_VISIBLE_CATEGORY_IDS[0]}` は常に表示されます。\n\n"
                "🔹 **1階**：通話作成・雑談・くじ引き等\n"
                "🔹 **2階**：カジノ・オセロ\n"
                "❌ 「階を閉じる」→ 共通カテゴリ以外を非表示"
            ),
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=ElevatorView())
        await itx.followup.send("✅ エレベーターパネル設置完了", ephemeral=True)
