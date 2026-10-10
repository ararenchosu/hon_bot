import discord
from discord.ext import commands
from othello_board import OthelloBoard
from othello_view import OthelloView

class OthelloGame:
    def __init__(self, player_black, player_white):
        self.board = OthelloBoard()
        self.player_black = player_black
        self.player_white = player_white

async def setup(bot: commands.Bot):
    @bot.tree.command(name="オセロ", description="オセロで対戦します")
    async def othello(interaction: discord.Interaction, 相手: discord.Member):
        if interaction.user == 相手:
            await interaction.response.send_message("自分自身とは対戦できません", ephemeral=True)
            return
        if 相手.bot:
            await interaction.response.send_message("Botとは対戦できません", ephemeral=True)
            return
        game = OthelloGame(interaction.user, 相手)
        view = OthelloView(game, interaction.user, 相手)
        embed = await view.build_embed()
        await interaction.response.send_message(
            f"{interaction.user.mention} VS {相手.mention} のオセロを開始します！\n⚫ 黒：{interaction.user.mention}\n⚪ 白：{相手.mention}",
            embed=embed, view=view
        )
