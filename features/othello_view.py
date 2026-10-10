import discord
from .othello_board import OthelloBoard

BLACK = "black"
WHITE = "white"

class OthelloView(discord.ui.View):
    def __init__(self, game, player_black, player_white):
        super().__init__(timeout=None)
        self.game = game
        self.player_black = player_black
        self.player_white = player_white
        self.board = game.board
        self.message = None

    async def build_embed(self):
        b, w = self.board.count()
        turn_text = "⚫ 黒の番です" if self.board.current == BLACK else "⚪ 白の番です"
        embed = discord.Embed(title="🔳 オセロ", description=self.board.render(), color=0x222222)
        embed.add_field(
            name="状況",
            value=f"黒：{b}　白：{w}\n{turn_text}",
            inline=False
        )
        embed.add_field(
            name="プレイヤー",
            value=f"{self.player_black.mention} 黒\n{self.player_white.mention} 白",
            inline=False
        )
        return embed

    def check_turn(self, interaction):
        if self.board.current == BLACK and interaction.user.id != self.player_black.id:
            return False
        if self.board.current == WHITE and interaction.user.id != self.player_white.id:
            return False
        return True

    # ===== 列ボタン =====
    @discord.ui.button(label="ａ", style=discord.ButtonStyle.secondary, row=0)
    async def col_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 0)
    @discord.ui.button(label="ｂ", style=discord.ButtonStyle.secondary, row=0)
    async def col_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 1)
    @discord.ui.button(label="ｃ", style=discord.ButtonStyle.secondary, row=0)
    async def col_c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 2)
    @discord.ui.button(label="ｄ", style=discord.ButtonStyle.secondary, row=0)
    async def col_d(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 3)
    @discord.ui.button(label="ｅ", style=discord.ButtonStyle.secondary, row=0)
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

        # ===== 行選択用View =====
        class RowSelectView(discord.ui.View):
            def __init__(self, parent_view, col_idx):
                super().__init__(timeout=30)
                self.parent = parent_view
                self.col = col_idx

                # 1行目：1～5
                for r in range(5):
                    self.add_item(discord.ui.Button(
                        label=str(r+1),
                        style=discord.ButtonStyle.secondary,
                        custom_id=f"rowsel_{r}"
                    ))
                # 2行目：6～8
                for r in range(5, 8):
                    self.add_item(discord.ui.Button(
                        label=str(r+1),
                        style=discord.ButtonStyle.secondary,
                        custom_id=f"rowsel_{r}",
                        row=1
                    ))

            async def callback(self, interaction: discord.Interaction):
                row = int(interaction.data["custom_id"].split("_")[1])

                if not self.parent.check_turn(interaction):
                    await interaction.response.send_message("自分の番ではありません", ephemeral=True)
                    return

                if not self.parent.board.put(row, self.col):
                    await interaction.response.send_message("❌ そこには置けません", ephemeral=True)
                    return

                # パス処理
                next_color = WHITE if self.parent.board.current == BLACK else BLACK
                if not self.parent.board.can_put(next_color) and not self.parent.board.is_game_over():
                    self.parent.board.current = next_color

                embed = await self.parent.build_embed()

                if self.parent.board.is_game_over():
                    b, w = self.parent.board.count()
                    if b > w:
                        result = f"⚫ {self.parent.player_black.mention} の勝ち！"
                    elif w > b:
                        result = f"⚪ {self.parent.player_white.mention} の勝ち！"
                    else:
                        result = "🤝 引き分け！"
                    embed.set_field_at(
                        0,
                        name="🏆 対戦結果",
                        value=f"黒：{b}　白：{w}\n{result}",
                        inline=False
                    )
                    self.parent.disable_all_items()
                    await interaction.response.edit_message(embed=embed, view=self.parent)
                else:
                    await interaction.response.edit_message(embed=embed, view=self.parent)

        # 行選択を表示
        row_view = RowSelectView(self, col)
        await interaction.response.send_message(
            "👇 行番号を選んでください：",
            view=row_view,
            ephemeral=True
        )

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
