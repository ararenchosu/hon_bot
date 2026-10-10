import discord
from discord import app_commands
from core.common import is_owner, RESULT_CHANNEL_ID, OTHELLO_CATEGORY_ID
import asyncio
from .othello_view import OthelloView

active_games = set()

class OthelloPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 対戦開始", style=discord.ButtonStyle.primary, custom_id="othello_panel:challenge")
    async def challenge_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id in active_games:
            await itx.response.send_message("❌ あなたは既に対戦中です", ephemeral=True)
            return

        # 相手選択
        opponent_result = None
        proceed = asyncio.Event()

        class SelectOpponentView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(discord.ui.UserSelect(placeholder="対戦相手を選んでください", max_values=1))

            async def callback(self, inter: discord.Interaction):
                nonlocal opponent_result
                selected = self.children[0].values[0]

                if selected == inter.user:
                    await inter.response.send_message("❌ 自分自身とは対戦できません", ephemeral=True)
                    return
                if selected.bot:
                    await inter.response.send_message("❌ Botとは対戦できません", ephemeral=True)
                    return
                if selected.id in active_games:
                    await inter.response.send_message(f"❌ {selected.mention} は既に対戦中です", ephemeral=True)
                    return

                opponent_result = selected
                proceed.set()
                await inter.response.send_message(f"✅ {selected.mention} に対戦を申し込みました。チャンネルを作成します…", ephemeral=True)

        select_view = SelectOpponentView()
        await itx.response.send_message("対戦相手を選んでください：", view=select_view, ephemeral=True)

        try:
            await asyncio.wait_for(proceed.wait(), timeout=60)
        except asyncio.TimeoutError:
            await itx.followup.send("⏰ 60秒以内に相手が選択されませんでした。", ephemeral=True)
            return

        opponent = opponent_result
        guild = itx.guild

        # ===== 先にチャンネル作成 =====
        category = None
        if OTHELLO_CATEGORY_ID and OTHELLO_CATEGORY_ID != 0:
            category = guild.get_channel(OTHELLO_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            itx.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            opponent: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        for oid in [1256574550901133377, 1546348374922625065]:
            owner = guild.get_member(oid)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(view_channel=True)

        channel_name = f"オセロ-{itx.user.name}-vs-{opponent.name}"
        try:
            ticket_ch = await guild.create_text_channel(
                name=channel_name,
                topic=f"対戦申込：{itx.user.mention} → {opponent.mention}",
                category=category,
                overwrites=overwrites
            )
        except Exception as e:
            await itx.followup.send(f"❌ チャンネル作成エラー：{e}", ephemeral=True)
            return

        await itx.followup.send(f"✅ チャンネル作成完了！ → {ticket_ch.mention}", ephemeral=True)

        # ===== チャンネル内で承認/拒否 =====
        class ApproveRejectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.approved = None

            @discord.ui.button(label="✅ 承認", style=discord.ButtonStyle.success)
            async def approve_btn(self, btn_itx: discord.Interaction, b):
                if btn_itx.user.id != opponent.id:
                    await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                    return
                self.approved = True
                self.stop()
                await btn_itx.response.send_message("✅ 承認されたので開始します", ephemeral=False)

            @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger)
            async def reject_btn(self, btn_itx: discord.Interaction, b):
                if btn_itx.user.id != opponent.id:
                    await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                    return
                self.approved = False
                self.stop()
                await btn_itx.response.send_message("❌ 拒否されたのでチケット削除します", ephemeral=False)

        ar_view = ApproveRejectView()
        await ticket_ch.send(
            f"{opponent.mention}\n{itx.user.mention} がオセロの対戦を申し込んでいます！\n⏰ 2分以内に選択してください。",
            view=ar_view
        )

        timed_out = await ar_view.wait()
        if timed_out:
            await ticket_ch.send(f"⏰ 応答がないため、このチャンネルを削除します")
            await asyncio.sleep(3)
            await ticket_ch.delete()
            return

        if not ar_view.approved:
            # 拒否 → 削除
            await ticket_ch.send("5秒後にこのチャンネルを削除します")
            await asyncio.sleep(5)
            await ticket_ch.delete()
            return

        # 承認 → オセロ開始
        active_games.add(itx.user.id)
        active_games.add(opponent.id)

        view = OthelloView(itx.user, opponent)
        await ticket_ch.send(
            f"⚫ 先攻：{itx.user.mention}\n⚪ 後攻：{opponent.mention}\n先攻の番です！",
            view=view
        )

        # 対戦終了待ち
        while not view.game_over:
            await asyncio.sleep(2)

        b, w = view.board.count()
        if b > w:
            result_text = f"🏆 {itx.user.mention} の勝ち！ ⚫ {b} 対 {w} ⚪"
        elif w > b:
            result_text = f"🏆 {opponent.mention} の勝ち！ ⚪ {w} 対 {b} ⚫"
        else:
            result_text = "🤝 引き分け！"

        # 結果送信
        result_ch = guild.get_channel(RESULT_CHANNEL_ID)
        if result_ch:
            embed = discord.Embed(title="🎮 オセロ対戦結果", color=0x2ecc71)
            embed.add_field(name="対戦者", value=f"⚫ 先攻：{itx.user.mention}\n⚪ 後攻：{opponent.mention}", inline=False)
            embed.add_field(name="スコア", value=f"⚫ {b} ： {w} ⚪", inline=False)
            embed.add_field(name="結果", value=result_text, inline=False)
            await result_ch.send(embed=embed)

        await ticket_ch.send(f"対戦終了！\n{result_text}\n5秒後にこのチャンネルを削除します")
        await asyncio.sleep(5)
        await ticket_ch.delete()

        active_games.discard(itx.user.id)
        active_games.discard(opponent.id)

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="othello_panel:edit")
    async def edit_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return

        class EditModal(discord.ui.Modal, title="パネル編集"):
            title_in = discord.ui.TextInput(label="タイトル", default="🎮 オセロで対戦しよう！")
            desc_in = discord.ui.TextInput(label="説明文", style=discord.TextStyle.long,
                default="下のボタンを押して対戦相手を選んでください。\n承諾されると専用チャンネルが自動作成されます。")

            async def on_submit(self, modal_itx: discord.Interaction):
                embed = discord.Embed(title=str(self.title_in), description=str(self.desc_in), color=0x2ecc71)
                await modal_itx.response.edit_message(embed=embed, view=OthelloPanelView())
                await modal_itx.followup.send("✅ パネルを更新しました", ephemeral=True)

        await itx.response.send_modal(EditModal())


async def setup(tree):
    @tree.command(name="オセロパネル設置", description="オセロ対戦パネルを設置（オーナー専用）")
    async def cmd_othello_panel(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用コマンドです", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎮 オセロで対戦しよう！",
            description="下のボタンを押して対戦相手を選んでください。\n承諾されると専用チャンネルが自動作成されます。",
            color=0x2ecc71
        )
        await itx.response.send_message(embed=embed, view=OthelloPanelView())
