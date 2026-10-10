import discord
from discord import app_commands
from core.common import is_owner
from core.database import get_connection


def get_selectable_roles(guild_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT role_id, role_name FROM select_roles WHERE guild_id=?", (str(guild_id),))
    result = cur.fetchall()
    conn.close()
    return result


def add_selectable_role(guild_id, role_id, role_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO select_roles VALUES (NULL, ?, ?, ?)",
        (str(guild_id), str(role_id), role_name)
    )
    conn.commit()
    conn.close()


class RoleSelectPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎖️ ロールを選択して取得", style=discord.ButtonStyle.primary, custom_id="rpanel:select")
    async def select_role(self, itx: discord.Interaction, btn: discord.ui.Button):
        roles = get_selectable_roles(itx.guild_id)
        if not roles:
            await itx.response.send_message(
                "❌ 付与するロールが設定されていません。オーナーが追加してください。",
                ephemeral=True
            )
            return

        class RoleSelectView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.Select(
                    placeholder="取得するロールを選択",
                    max_values=len(roles),
                    options=[discord.SelectOption(label=name, value=rid) for rid, name in roles]
                ))

            async def interaction_check(self, inter: discord.Interaction) -> bool:
                selected = self.children[0].values
                added = []
                for rid in selected:
                    r = inter.guild.get_role(int(rid))
                    if r and r not in inter.user.roles:
                        await inter.user.add_roles(r)
                        added.append(r.name)
                if added:
                    await inter.response.send_message(
                        f"✅ ロールを付与：{', '.join(added)}", ephemeral=True
                    )
                else:
                    await inter.response.send_message(
                        "✅ 選択されたロールは既に付与されています", ephemeral=True
                    )
                return True

        await itx.response.send_message(
            "取得するロールを選択してください：", view=RoleSelectView(), ephemeral=True
        )

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="rpanel:edit")
    async def edit_panel(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class EditModal(discord.ui.Modal, title="ロールパネル編集"):
            title_in = discord.ui.TextInput(label="タイトル", default="🎖️ ロール選択")
            desc_in = discord.ui.TextInput(
                label="説明", style=discord.TextStyle.long,
                default="ボタンから必要なロールを選択して取得してください。"
            )

            async def on_submit(self, inter: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in), description=str(self.desc_in), color=0x3498db
                )
                await inter.response.edit_message(embed=embed, view=RoleSelectPanelView())
                await inter.followup.send("✅ 更新しました", ephemeral=True)

        await itx.response.send_modal(EditModal())

    @discord.ui.button(label="➕ 付与ロール追加", style=discord.ButtonStyle.success, custom_id="rpanel:add")
    async def add_role_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class RolePickerView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.RoleSelect(placeholder="追加するロールを選択"))

            async def interaction_check(self, inter: discord.Interaction) -> bool:
                role = self.children[0].values[0]
                add_selectable_role(inter.guild_id, role.id, role.name)
                await inter.response.send_message(
                    f"✅ 「{role.name}」を選択候補に追加しました！", ephemeral=True
                )
                return True

        await itx.response.send_message(
            "追加するロールを選択してください：", view=RolePickerView(), ephemeral=True
        )


async def setup(tree):
    @tree.command(name="ロール付与パネル設置", description="選択式ロールパネル設置（オーナー専用）")
    async def cmd_role_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎖️ ロール選択",
            description="下のボタンを押して、必要なロールを選択して取得してください。",
            color=0x3498db
        )
        await itx.response.send_message(embed=embed, view=RoleSelectPanelView())
