import discord
from discord import app_commands
from core.common import is_owner, CALL_CHANNEL_ID
from core.database import get_connection

# ========== 追加：パネル保存/読み込み ==========
def save_call_panel(channel_id: int, message_id: int, title: str, description: str, color: int):
    """パネル内容を保存（設置時・編集時に自動実行）"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO call_panel (channel_id, message_id, title, description, color)
        VALUES (?, ?, ?, ?, ?)
    """, (str(channel_id), str(message_id), title, description, color))
    conn.commit()
    conn.close()

def get_latest_call_panel():
    """一番新しい保存内容を取得（編集時の初期値に使用）"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT channel_id, message_id, title, description, color
        FROM call_panel
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

def get_call_message():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key='call_message'")
    r = cur.fetchone()
    conn.close()
    return r[0] if r else "$caller$さんが $target$さんを呼んでいます。"

def set_call_message(text):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("REPLACE INTO config VALUES ('call_message', ?)", (text,))
    conn.commit()
    conn.close()

class CallPanelView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="📢 メンバーを呼ぶ", style=discord.ButtonStyle.primary, custom_id="call:do")
    async def do_call(self, itx: discord.Interaction, btn: discord.ui.Button):
        class UserSelView(discord.ui.View):
            def __init__(self, bot):
                super().__init__()
                self.bot = bot
                self.add_item(discord.ui.UserSelect(placeholder="呼び出すユーザーを選択", max_values=1))
            async def interaction_check(self, inter: discord.Interaction) -> bool:
                target = self.children[0].values[0]
                msg = get_call_message().replace("$caller$", inter.user.mention).replace("$target$", target.mention)
                ch = self.bot.get_channel(CALL_CHANNEL_ID)
                if ch:
                    await ch.send(msg)
                    await inter.response.send_message(f"✅ {target.mention} を呼び出しました！", ephemeral=True)
                else:
                    await inter.response.send_message("❌ 通知チャンネルが見つかりません", ephemeral=True)
                return True
        await itx.response.send_message("呼び出すユーザーを選択：", view=UserSelView(self.bot), ephemeral=True)

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="call:edit")
    async def edit_panel(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        # ✅ 最新の内容を初期値に表示
        latest = get_latest_call_panel()
        default_title = latest["title"] if latest else "📢 メンバー呼び出し"
        default_desc = latest["description"] if latest else "ボタンからメンバーを選んで呼び出せます。"

        class EditModal(discord.ui.Modal, title="呼び出しパネル編集"):
            title_in = discord.ui.TextInput(label="タイトル", default=default_title)
            desc_in = discord.ui.TextInput(label="説明", style=discord.TextStyle.long, default=default_desc)
            async def on_submit(self, inter: discord.Interaction):
                embed = discord.Embed(
                    title=str(self.title_in),
                    description=str(self.desc_in),
                    color=0xe67e22
                )
                await inter.response.edit_message(embed=embed, view=CallPanelView(self.bot))
                # ✅ 編集したら自動保存
                save_call_panel(
                    inter.channel_id,
                    inter.message.id,
                    str(self.title_in),
                    str(self.desc_in),
                    0xe67e22
                )
                await inter.followup.send("✅ 更新・保存完了", ephemeral=True)
        await itx.response.send_modal(EditModal())

    @discord.ui.button(label="💬 メッセージ文変更", style=discord.ButtonStyle.secondary, custom_id="call:msg")
    async def edit_msg(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        class MsgModal(discord.ui.Modal, title="呼び出しメッセージ編集"):
            msg_in = discord.ui.TextInput(label="文（$caller$/$target$ 置換）", default=get_call_message(), style=discord.TextStyle.long)
            async def on_submit(self, inter: discord.Interaction):
                set_call_message(str(self.msg_in))
                await inter.response.send_message(f"✅ 更新：\n{self.msg_in}", ephemeral=True)
        await itx.response.send_modal(MsgModal())

async def setup(tree, bot):
    @tree.command(name="呼び出しパネル設置", description="呼び出しパネル設置（オーナー専用）")
    async def cmd_call_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        embed = discord.Embed(
            title="📢 メンバー呼び出し",
            description="ボタンからメンバーを選択して呼び出せます。\n通知は専用チャンネルに送信されます。",
            color=0xe67e22
        )
        await itx.response.send_message(embed=embed, view=CallPanelView(bot))
        # ✅ 新規設置時に自動保存
        msg = await itx.original_response()
        save_call_panel(
            itx.channel_id,
            msg.id,
            embed.title,
            embed.description,
            embed.color.value
        )
