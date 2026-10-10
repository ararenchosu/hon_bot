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

        class SelectOpponentView(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.add_item(discord.ui.UserSelect(placeholder="対戦相手を選んでください", max_values=1))

            async def interaction_check(self, inter: discord.Interaction) -> bool:
                opponent = self.children[0].values[0]
                if opponent == inter.user:
                    await inter.response.send_message("❌ 自分自身とは対戦できません", ephemeral=True)
                    return False
                if opponent.bot:
                    await inter.response.send_message("❌ Botとは対戦できません", ephemeral=True)
                    return False
                if opponent.id in active_games:
                    await inter.response.send_message(f"❌ {opponent.mention} は既に対戦中です", ephemeral=True)
                    return False
                return True

            async def callback(self, inter: discord.Interaction):
                opponent = self.children[0].values[0]

                class RequestView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=120)
                        self.accepted = None

                    @discord.ui.button(label="✅ 承諾", style=discord.ButtonStyle.success)
                    async def accept(self, btn_itx: discord.Interaction, b):
                        if btn_itx.user.id != opponent.id:
                            await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                            return
                        self.accepted = True
                        self.stop()
                        await btn_itx.response.send_message("✅ 承諾されました！チャンネルを作成中…", ephemeral=True)

                    @discord.ui.button(label="❌ 拒否", style=discord.ButtonStyle.danger)
                    async def reject(self, btn_itx: discord.Interaction, b):
                        if btn_itx.user.id != opponent.id:
                            await btn_itx.response.send_message("❌ 招待された人だけが押せます", ephemeral=True)
                            return
                        self.accepted = False
                        self.stop()
                        await btn_itx.response.send_message("❌ 対戦を拒否しました", ephemeral=True)

                req_view = RequestView()
                await inter.response.send_message(
                    f"{opponent.mention}\n{inter.user.mention} がオセロの対戦を申し込んでいます！\n⏰ 2分以内に「✅ 承諾」または「❌ 拒否」を押してください。",
                    view=req_view
                )

                timed_out = await req_view.wait()
                if timed_out:
                    await inter.followup.send(
                        f"⏰ {opponent.mention} から応答がありませんでした。\n相手に確認してみてください。",
                        ephemeral=True
                    )
                    return
                if not req_view.accepted:
                    await inter.followup.send(f"❌ {opponent.mention} が対戦を拒否しました", ephemeral=True)
                    return

                # --- ここからチャンネル作成 ---
                guild = inter.guild
                category = None
                if OTHELLO_CATEGORY_ID and OTHELLO_CATEGORY_ID != 0:
                    category = guild.get_channel(OTHELLO_CATEGORY_ID)
                    if not category:
                        await inter.followup.send("⚠️ カテゴリが見つかりません。トップレベルに作成します。", ephemeral=True)

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    inter.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                    opponent: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                }
                for oid in [1256574550901133377, 1546348374922625065]:
                    owner = guild.get_member(oid)
                    if owner:
                        overwrites[owner] = discord.PermissionOverwrite(view_channel=True)

                channel_name = f"オセロ-{inter.user.name}-vs-{opponent.name}"
                try:
                    ticket_ch = await guild.create_text_channel(
                        name=channel_name,
                        topic=f"対戦：{inter.user.mention} VS {opponent.mention}",
                        category=category,
                        overwrites=overwrites
                    )
                except Exception as e:
                    await inter.followup.send(f"❌ チャンネル作成エラー：{e}", ephemeral=True)
                    return

                active_games.add(inter.user.id)
                active_games.add(opponent.id)

                view = OthelloView(inter.user, opponent)
                await ticket_ch.send(
                    f"⚫ 先攻：{inter.user.mention}\n⚪ 後攻：{opponent.mention}\n先攻の番です！",
                    view=view
                )

                await inter.followup.send(f"✅ チャンネル作成完了！ → {ticket_ch.mention}", ephemeral=True)

                while not view.game_over:
                    await asyncio.sleep(2)

                b, w = view.board.count()
                if b > w:
                    result_text = f"🏆 {inter.user.mention} の勝ち！ ⚫ {b} 対 {w} ⚪"
                elif w > b:
                    result_text = f"🏆 {opponent.mention} の勝ち！ ⚪ {w} 対 {b} ⚫"
                else:
                    result_text = "🤝 引き分け！"

                result_ch = guild.get_channel(RESULT_CHANNEL_ID)
                if result_ch:
                    embed = discord.Embed(title="🎮 オセロ対戦結果", color=0x2ecc71)
                    embed.add_field(name="対戦者", value=f"⚫ 先攻：{inter.user.mention}\n⚪ 後攻：{opponent.mention}", inline=False)
                    embed.add_field(name="スコア", value=f"⚫ {b} ： {w} ⚪", inline=False)
                    embed.add_field(name="結果", value=result_text, inline=False)
                    await result_ch.send(embed=embed)

                await ticket_ch.send(f"対戦終了！\n{result_text}\n5秒後にこのチャンネルを削除します")
                await asyncio.sleep(5)
                await ticket_ch.delete()

                active_games.discard(inter.user.id)
                active_games.discard(opponent.id)

        await itx.response.send_message("対戦相手を選んでください：", view=SelectOpponentView(), ephemeral=True)

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
