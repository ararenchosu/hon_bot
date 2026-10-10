import discord
from othello_board import OthelloBoard, BLACK, WHITE

class OthelloView(discord.ui.View):
    def __init__(self, game, player_black, player_white):
        super().__init__(timeout=None)
        self.game = game
        self.player_black = player_black
        self.player_white = player_white
        self.board = game.board

    async def build_embed(self):
        b, w = self.board.count()
        turn = "⚫ 黒の番です" if self.board.current == BLACK else "⚪ 白の番です"
        embed = discord.Embed(title="🔳 オセロ", description=self.board.render(), color=0x222222)
        embed.add_field(name="状況", value=f"黒：{b}　白：{w}\n{turn}", inline=False)
        return embed

    def check_turn(self, interaction):
        if self.board.current == BLACK and interaction.user.id != self.player_black.id:
            return False
        if self.board.current == WHITE and interaction.user.id != self.player_white.id:
            return False
        return True

    @discord.ui.button(label="ａ", style=discord.ButtonStyle.secondary, row=1)
    async def col_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 0)

    @discord.ui.button(label="ｂ", style=discord.ButtonStyle.secondary, row=1)
    async def col_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 1)

    @discord.ui.button(label="ｃ", style=discord.ButtonStyle.secondary, row=1)
    async def col_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 2)

    @discord.ui.button(label="ｄ", style=discord.ButtonStyle.secondary, row=1)
    async def col_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 3)

    @discord.ui.button(label="ｅ", style=discord.ButtonStyle.secondary, row=1)
    async def col_e(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 4)

    @discord.ui.button(label="ｆ", style=discord.ButtonStyle.secondary, row=1)
    async def col_f(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 5)

    @discord.ui.button(label="ｇ", style=discord.ButtonStyle.secondary, row=1)
    async def col_g(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 6)

    @discord.ui.button(label="ｈ", style=discord.ButtonStyle.secondary, row=1)
    async def col_h(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 7)

    async def handle_move(self, interaction, col):
        if not self.check_turn(interaction):
            await interaction.response.send_message("自分の番ではありません", ephemeral=True)
            return
        # どの行に置くか選んでもらう
        class RowSelect(discord.ui.View):
            def __init__(self, parent, col):
                super().__init__(timeout=30)
                self.parent = parent
                self.col = col
                for r in range(8):
                    self.add_item(discord.ui.Button(
                        label=str(r+1), style=discord.ButtonStyle.secondary,
                        custom_id=f"row_{r}"
                    ))
            async def callback(self, interaction: discord.Interaction):
                row = int(interaction.data["custom_id"].split("_")[1])
                if not self.parent.check_turn(interaction):
                    await interaction.response.send_message("自分の番ではありません", ephemeral=True)
                    return
                if not self.parent.board.put(row, self.col):
                    await interaction.response.send_message("そこには置けません", ephemeral=True)
                    return
                # 次の人が置けない場合
                next_color = WHITE if self.parent.board.current == BLACK else BLACK
                if not self.parent.board.can_put(next_color) and not self.parent.board.is_game_over():
                    self.parent.board.current = next_color
                embed = await self.parent.build_embed()
                if self.parent.board.is_game_over():
                    b, w = self.parent.board.count()
                    if b > w:
                        result = "⚫ 黒の勝ち！"
                    elif w > b:
                        result = "⚪ 白の勝ち！"
                    else:
                        result = "引き分け"
                    embed.set_field_at(0, name="結果", value=f"黒：{b}　白：{w}\n{result}", inline=False)
                    self.parent.disable_all_items()
                    await interaction.response.edit_message(embed=embed, view=self.parent)
                else:
                    await interaction.response.edit_message(embed=embed, view=self.parent)
        await interaction.response.send_message("行を選んでください：", view=RowSelect(self, col), ephemeral=True)

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
