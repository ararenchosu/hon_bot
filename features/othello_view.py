import discord
from .othello_board import OthelloBoard

BLACK = "black"
WHITE = "white"

class OthelloView(discord.ui.View):
    def __init__(self, game, player_black, player_white, result_channel_id=None, ticket_channel=None):
        super().__init__(timeout=None)
        self.game = game
        self.player_black = player_black
        self.player_white = player_white
        self.board = game.board
        self.message = None
        self.result_channel_id = result_channel_id   # 結果送信用
        self.ticket_channel = ticket_channel           # チケット削除用
        self.force_ended = False

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
        if self.force_ended:
            return False
        if self.board.current == BLACK and interaction.user.id != self.player_black.id:
            return False
        if self.board.current == WHITE and interaction.user.id != self.player_white.id:
            return False
        return True

    # ===== 1行目：a～e =====
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

    # ===== 2行目：f～h ＋ 強制終了 =====
    @discord.ui.button(label="ｆ", style=discord.ButtonStyle.secondary, row=1)
    async def col_f(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 5)
    @discord.ui.button(label="ｇ", style=discord.ButtonStyle.secondary, row=1)
    async def col_g(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 6)
    @discord.ui.button(label="ｈ", style=discord.ButtonStyle.secondary, row=1)
    async def col_h(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, 7)
    
    # ✅ 強制終了ボタン
    @discord.ui.button(label="⚠️ 強制終了", style=discord.ButtonStyle.danger, row=1)
    async def force_end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.force_ended:
            await interaction.response.send_message("❌ 既に終了しています", ephemeral=True)
            return
        # どちらのプレイヤーでも押せる
        if interaction.user.id not in (self.player_black.id, self.player_white.id):
            await interaction.response.send_message("❌ 対戦者のみ実行できます", ephemeral=True)
            return
        
        self.force_ended = True
        self.disable_all_items()
        
        b, w = self.board.count()
        if b > w:
            result_text = f"⚫ {self.player_black.mention} の勝ち！"
        elif w > b:
            result_text = f"⚪ {self.player_white.mention} の勝ち！"
        else:
            result_text = "🤝 引き分け！"
        
        # 結果を表示
        embed = discord.Embed(title="🔳 オセロ【強制終了】", description=self.board.render(), color=0xff4444)
        embed.add_field(name="途中終了 状況", value=f"黒：{b}　白：{w}\n{result_text}", inline=False)
        embed.add_field(name="プレイヤー", value=f"{self.player_black.mention} 黒\n{self.player_white.mention} 白", inline=False)
        
        await interaction.response.edit_message(embed=embed, view=self)
        
        # チケットチャンネルに通知
        if self.ticket_channel:
            await self.ticket_channel.send(f"⚠️ {interaction.user.mention} により対戦が強制終了されました。\n5秒後にこのチャンネルを削除します…")
        
        # 結果を専用チャンネルに送信
        if self.result_channel_id and self.ticket_channel:
            guild = self.ticket_channel.guild
            result_ch = guild.get_channel(self.result_channel_id)
            if result_ch:
                res_embed = discord.Embed(title="⚠️ オセロ対戦【途中終了】", color=0xff4444)
                res_embed.add_field(name="対戦者", value=f"⚫ {self.player_black.mention}\n⚪ {self.player_white.mention}", inline=False)
                res_embed.add_field(name="最終スコア", value=f"黒：{b}　白：{w}", inline=False)
                res_embed.add_field(name="結果", value=result_text, inline=False)
                res_embed.set_footer(text=f"終了者：{interaction.user}")
                await result_ch.send(embed=res_embed)
        
        # 3秒後にチャンネル削除
        import asyncio
        await asyncio.sleep(3)
        if self.ticket_channel:
            try:
                await self.ticket_channel.delete()
            except:
                pass

    async def handle_move(self, interaction, col):
        if self.force_ended:
            await interaction.response.send_message("❌ 対戦は終了しています", ephemeral=True)
            return
        if not self.check_turn(interaction):
            await interaction.response.send_message("自分の番ではありません", ephemeral=True)
            return

        class RowSelectView(discord.ui.View):
            def __init__(self, parent_view, col_idx):
                super().__init__(timeout=30)
                self.parent = parent_view
                self.col = col_idx
                for r in range(5):
                    self.add_item(discord.ui.Button(
                        label=str(r+1),
                        style=discord.ButtonStyle.secondary,
                        custom_id=f"rowsel_{r}"
                    ))
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
                    embed.set_field_at(0, name="🏆 対戦結果", value=f"黒：{b}　白：{w}\n{result}", inline=False)
                    self.parent.disable_all_items()
                    
                    # 通常終了時も結果送信＆チャンネル削除
                    if self.parent.result_channel_id and self.parent.ticket_channel:
                        guild = self.parent.ticket_channel.guild
                        result_ch = guild.get_channel(self.parent.result_channel_id)
                        if result_ch:
                            res_embed = discord.Embed(title="🎮 オセロ対戦結果", color=0x2ecc71)
                            res_embed.add_field(name="対戦者", value=f"⚫ {self.parent.player_black.mention}\n⚪ {self.parent.player_white.mention}", inline=False)
                            res_embed.add_field(name="最終スコア", value=f"黒：{b}　白：{w}", inline=False)
                            res_embed.add_field(name="結果", value=result, inline=False)
                            await result_ch.send(embed=res_embed)
                    
                    await interaction.response.edit_message(embed=embed, view=self.parent)
                    
                    if self.parent.ticket_channel:
                        await self.parent.ticket_channel.send("✅ 対戦終了！5秒後にこのチャンネルを削除します")
                        import asyncio
                        await asyncio.sleep(5)
                        try:
                            await self.parent.ticket_channel.delete()
                        except:
                            pass
                else:
                    await interaction.response.edit_message(embed=embed, view=self.parent)

        await interaction.response.send_message("👇 行番号を選んでください：", view=RowSelectView(self, col), ephemeral=True)

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
