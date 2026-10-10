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

        # ===== 相手選択メニュー =====
        class OpponentSelect(discord.ui.UserSelect):
            def __init__(self):
                super().__init__(
                    placeholder="対戦相手を選んでください",
                    min_values=1,
                    max_values=1
                )
            async def callback(self, inter: discord.Interaction):
                selected = self.values[0]
                await handle_opponent_selected(inter, selected)

        class SelectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(OpponentSelect())

        view = SelectView()
        await itx.response.send_message(
            "👇 対戦相手を下から選んでください",
            view=view,
            ephemeral=True
        )

        # タイムアウト時の処理
        try:
            await view.wait()
        except asyncio.TimeoutError:
            await itx.followup.send(
                "⏰ 60秒以内に相手が選択されませんでした。もう一度お試しください。",
                ephemeral=True
            )
            return

        if not hasattr(itx, '_opponent'):
            await itx.followup.send("❌ 選択が完了しませんでした。", ephemeral=True)
        return

async def handle_opponent_selected(inter, selected):
    # バリデーション
    if selected == inter.user:
        await inter.response.send_message("❌ 自分自身とは対戦できません", ephemeral=True)
        return
    if selected.bot:
        await inter.response.send_message("❌ Botとは対戦できません", ephemeral=True)
        return
    if selected.id in active_games:
        await inter.response.send_message(f"❌ {selected.mention} は既に対戦中です", ephemeral=True)
        return

    opponent = selected
    challenger = inter.user
    guild = inter.guild

    await inter.response.send_message(
        f"✅ {opponent.mention} に対戦を申し込みました。チャンネルを作成します…",
        ephemeral=True
    )

    # ===== チャンネル作成 =====
    category = None
    if OTHELLO_CATEGORY_ID and OTHELLO_CATEGORY_ID != 0:
        category = guild.get_channel(OTHELLO_CATEGORY_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        challenger: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        opponent: discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    for oid in [1256574550901133377, 1546348374922625065]:
        owner = guild.get_member(oid)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=True)

    channel_name = f"オセロ-{challenger.name}-vs-{opponent.name}"
    try:
        ticket_ch = await guild.create_text_channel(
            name=channel_name,
            topic=f"対戦申込：{challenger.mention} → {opponent.mention}",
            category=category,
            overwrites=overwrites
        )
    except Exception as e:
        await inter.followup.send(f"❌ チャンネル作成エラー：{e}", ephemeral=True)
        return

    await inter.followup.send(
        f"✅ チャンネル作成完了！ → {ticket_ch.mention}",
        ephemeral=True
    )

    # ===== 承認/拒否ボタン =====
    class ApproveRejectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.decision = None

        @discord.ui.button(label="✅ 承認", style=discord.ButtonStyle.success)
        async def approve(self, btn_itx: discord.Interaction, btn):
            if btn_itx.user.id != opponent.id:
                await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                return
            self.decision = "approve"
            self.stop()
            await btn_itx.response.send_message("✅ 承認されたので開始します", ephemeral=False)

        @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger)
        async def reject(self, btn_itx: discord.Interaction, btn):
            if btn_itx.user.id != opponent.id:
                await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                return
            self.decision = "reject"
            self.stop()
            await btn_itx.response.send_message("❌ 拒否されたのでチケット削除します", ephemeral=False)

    ar_view = ApproveRejectView()
    await ticket_ch.send(
        f"{opponent.mention}\n{challenger.mention} がオセロの対戦を申し込んでいます！\n⏰ 2分以内に「✅ 承認」または「❌ 拒否」を押してください。",
        view=ar_view
    )

    await ar_view.wait()

    if ar_view.decision is None:
        await ticket_ch.send("⏰ 応答がないため、このチャンネルを削除します")
        await asyncio.sleep(3)
        await ticket_ch.delete()
        return

    if ar_view.decision == "reject":
        await ticket_ch.send("5秒後にこのチャンネルを削除します")
        await asyncio.sleep(5)
        await ticket_ch.delete()
        return

    # ===== 承認 → オセロ開始 =====
    active_games.add(challenger.id)
    active_games.add(opponent.id)

    game_view = OthelloView(challenger, opponent)
    await ticket_ch.send(
        f"⚫ 先攻：{challenger.mention}\n⚪ 後攻：{opponent.mention}\n先攻の番です！",
        view=game_view
    )

    # 対戦終了待ち
    while not game_view.game_over:
        await asyncio.sleep(2)

    b, w = game_view.board.count()
    if b > w:
        result_text = f"🏆 {challenger.mention} の勝ち！ ⚫ {b} 対 {w} ⚪"
    elif w > b:
        result_text = f"🏆 {opponent.mention} の勝ち！ ⚪ {w} 対 {b} ⚫"
    else:
        result_text = "🤝 引き分け！"

    # 結果送信
    result_ch = guild.get_channel(RESULT_CHANNEL_ID)
    if result_ch:
        embed = discord.Embed(title="🎮 オセロ対戦結果", color=0x2ecc71)
        embed.add_field(name="対戦者", value=f"⚫ 先攻：{challenger.mention}\n⚪ 後攻：{opponent.mention}", inline=False)
        embed.add_field(name="スコア", value=f"⚫ {b} ： {w} ⚪", inline=False)
        embed.add_field(name="結果", value=result_text, inline=False)
        await result_ch.send(embed=embed)

    await ticket_ch.send(f"対戦終了！\n{result_text}\n5秒後にこのチャンネルを削除します")
    await asyncio.sleep(5)
    await ticket_ch.delete()

    active_games.discard(challenger.id)
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
