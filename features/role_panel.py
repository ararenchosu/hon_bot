import discord
from discord import app_commands
from core.common import is_owner
from core.database import get_connection

# ========== 追加：パネル保存/読み込み ==========
def save_role_give_panel(channel_id: int, message_id: int, title: str, description: str, color: int):
    """ロール付与パネル内容を保存（設置時・編集時に自動実行）"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO role_give_panel (channel_id, message_id, title, description, color)
        VALUES (?, ?, ?, ?, ?)
    """, (str(channel_id), str(message_id), title, description, color))
    conn.commit()
    conn.close()

def get_latest_role_give_panel():
    """一番新しい保存内容を取得（編集時の初期値に使用）"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT channel_id, message_id, title, description, color
        FROM role_give_panel
        ORDER BY updated_at DESC
        LIMIT 1
    """)
    r = cur.fetchone()
    conn.close()
    if r:
        return {
            "channel_id": int(r[0]),
            "message_id": int(r[1]),
            "title": r[2],
            "description": r[3],
            "color": int(r[4])
        }
    return None
# ===========================================

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
        # ✅ 最新の内容を初期値に表示
        latest = get_latest_role_give_panel()
        default_title = latest["title"] if latest else "🎖️ ロール選択"
        default_desc = latest["description"] if latest else "ボタンから必要なロールを選択して取得してください。"

        class EditModal(discord.ui.Modal, title="ロールパネル編集"):
            title_in = discord.ui.TextInput(label="タイトル", default=default_title)
            desc_in = discord.ui.TextInput(
                label="説明", style=discord.TextStyle.long,
                default=default_desc
            )
            async def on_submit(self, inter: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in), description=str(self.desc_in), color=0x3498db
                )
                await inter.response.edit_message(embed=embed, view=RoleSelectPanelView())
                # ✅ 編集したら自動保存
                save_role_give_panel(
                    inter.channel_id,
                    inter.message.id,
                    str(self.title_in),
                    str(self.desc_in),
                    0x3498db
                )
                await inter.followup.send("✅ 更新・保存完了", ephemeral=True)
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
            description="⬇️のボタンを押して、必要なロールを選択して取得してください。\n誤ったロールを付けた際はロール剥奪でロールを外すことができます。",
            color=0x3498db
        )
        await itx.response.send_message(embed=embed, view=RoleSelectPanelView())
        # ✅ 新規設置時に自動保存
        msg = await itx.original_response()
        save_role_give_panel(
            itx.channel_id,
            msg.id,
            embed.title,
            embed.description,
            embed.color.value
        )
