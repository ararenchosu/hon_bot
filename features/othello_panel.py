import discord
from discord import app_commands
from core.common import is_owner, RESULT_CHANNEL_ID, OTHELLO_CATEGORY_ID
import asyncio
from .othello_view import OthelloView
from .othello_board import OthelloBoard

active_games = set()


class OthelloPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎮 対戦開始", style=discord.ButtonStyle.primary, custom_id="othello_panel:challenge")
    async def challenge_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id in active_games:
            await itx.response.send_message("❌ あなたは既に対戦中です", ephemeral=True)
            return

        selected_opponent = None
        selection_done = asyncio.Event()

        class OpponentSelect(discord.ui.UserSelect):
            def __init__(self):
                super().__init__(
                    placeholder="対戦相手を選んでください",
                    min_values=1,
                    max_values=1
                )

            async def callback(self, inter: discord.Interaction):
                nonlocal selected_opponent
                selected_opponent = self.values[0]
                selection_done.set()

                if selected_opponent == inter.user:
                    await inter.response.send_message("❌ 自分自身とは対戦できません", ephemeral=True)
                    return
                if selected_opponent.bot:
                    await inter.response.send_message("❌ Botとは対戦できません", ephemeral=True)
                    return
                if selected_opponent.id in active_games:
                    await inter.response.send_message(f"❌ {selected_opponent.mention} は既に対戦中です", ephemeral=True)
                    return

                await inter.response.send_message(
                    f"✅ {selected_opponent.mention} に対戦を申し込みました。チャンネルを作成します…",
                    ephemeral=True
                )

        class SelectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(OpponentSelect())

        select_view = SelectView()
        await itx.response.send_message(
            "👇 対戦相手を下から選んでください",
            view=select_view,
            ephemeral=True
        )

        try:
            await asyncio.wait_for(selection_done.wait(), timeout=60)
        except asyncio.TimeoutError:
            await itx.followup.send(
                "⏰ 60秒以内に相手が選択されませんでした。もう一度お試しください。",
                ephemeral=True
            )
            return

        opponent = selected_opponent
        challenger = itx.user
        guild = itx.guild

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
            await itx.followup.send(f"❌ チャンネル作成エラー：{e}", ephemeral=True)
            return

        await itx.followup.send(
            f"✅ チャンネル作成完了！ → {ticket_ch.mention}",
            ephemeral=True
        )

        # ===== 承認/拒否ボタン =====
        class ApproveRejectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.final_decision = None

            @discord.ui.button(label="✅ 承認", style=discord.ButtonStyle.success)
            async def approve_btn(self, btn_itx: discord.Interaction, btn):
                if btn_itx.user.id != opponent.id:
                    await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                    return
                self.final_decision = "approve"
                self.stop()

                # ===== 盤面表示ボタン =====
                class StartBoardView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)

                    @discord.ui.button(label="🎮 盤面表示", style=discord.ButtonStyle.primary)
                    async def show_board_btn(self, board_itx: discord.Interaction, btn):
                        await board_itx.response.defer()

                        active_games.add(challenger.id)
                        active_games.add(opponent.id)

                        game = type('Game', (), {'board': OthelloBoard()})()

                        game_view = OthelloView(
                            game=game,
                            player_black=challenger,
                            player_white=opponent,
                            result_channel_id=RESULT_CHANNEL_ID,
                            ticket_channel=ticket_ch
                        )

                        # ✅ 対戦終了時にIDを削除する処理
                        async def cleanup_and_close():
                            active_games.discard(challenger.id)
                            active_games.discard(opponent.id)
                            await ticket_ch.send("✅ 対戦終了！5秒後にこのチャンネルを削除します")
                            await asyncio.sleep(5)
                            try:
                                await ticket_ch.delete()
                            except:
                                pass

                        # ✅ 変数名を統一：cleanup_callback に設定
                        game_view.cleanup_callback = cleanup_and_close

                        embed = await game_view.build_embed()
                        game_view.main_message = await ticket_ch.send(
                            embed=embed,
                            view=game_view
                        )

                await btn_itx.response.send_message(
                    "✅ 承認されました。⬇️の盤面表示ボタンを押して開始しましょう",
                    view=StartBoardView(),
                    ephemeral=False
                )

            @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger)
            async def reject_btn(self, btn_itx: discord.Interaction, btn):
                if btn_itx.user.id != opponent.id:
                    await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                    return
                self.final_decision = "reject"
                self.stop()
                await btn_itx.response.send_message("❌ 拒否されたのでチケット削除します", ephemeral=False)
                await ticket_ch.send("5秒後にこのチャンネルを削除します")
                await asyncio.sleep(5)
                await ticket_ch.delete()

        ar_view = ApproveRejectView()
        await ticket_ch.send(
            f"{opponent.mention}\n{challenger.mention} がオセロの対戦を申し込んでいます！\n⏰ 2分以内に「✅ 承認」または「❌ 拒否」を押してください。",
            view=ar_view
        )
        await ar_view.wait()

        if ar_view.final_decision is None:
            await ticket_ch.send("⏰ 応答がないため、このチャンネルを削除します")
            await asyncio.sleep(3)
            await ticket_ch.delete()
            return

    # ==== パネル編集ボタン ====
    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="othello_panel:edit")
    async def edit_btn(self, itx: discord.Interaction, btn):
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
            title="🔳 オセロで対戦しよう！",
            description="⬇️のボタンを押して対戦相手を選んでください。\n承諾されると専用チャンネルが自動作成されます。",
            color=0x222222
        )
        await itx.response.send_message(embed=embed, view=OthelloPanelView())
