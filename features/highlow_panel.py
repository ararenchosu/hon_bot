import discord
from discord import app_commands
import random
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"
HL_RESULT_CHANNEL_ID = 1558772472881488004

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
CARD_VALUES = {r: i+2 for i, r in enumerate(RANKS)}
SUITS = ["♠", "♥", "♦", "♣"]

def create_deck():
    deck = [(s, r) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(rank):
    return CARD_VALUES[rank]

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"points": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"points": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_points(user_id):
    return load_data().get("points", {}).get(str(user_id), 0)

def add_points(user_id, amount):
    data = load_data()
    uid = str(user_id)
    data["points"][uid] = data["points"].get(uid, 0) + amount
    save_data(data)
    return data["points"][uid]

def get_multiplier(streak):
    """連続回数に応じた倍率：1回目1.0 → +0.3ずつ無限にUP"""
    return 1.0 + (streak - 1) * 0.3

async def send_result_embed(client, user, first_card, next_card, choice, result_text, change, bet, total, streak, is_free=False, is_cashout=False):
    channel = client.get_channel(HL_RESULT_CHANNEL_ID)
    if not channel:
        print(f"⚠️ 結果チャンネルが見つかりません: {HL_RESULT_CHANNEL_ID}")
        return
    
    title = "📈 ハイ＆ロー確定" if is_cashout else ("📈 ハイ＆ロー結果（お試し）" if is_free else "📈 ハイ＆ロー結果")
    color = 0x999999 if is_free else (0x2ECC71 if change >= 0 else 0xE74C3C)
    
    embed = discord.Embed(
        title=title,
        description=f"{user.mention} がプレイしました！",
        color=color,
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="1枚目", value=f"{first_card[0]}{first_card[1]} （{card_value(first_card[1])}）", inline=True)
    if next_card:
        embed.add_field(name="選択", value="📈 ハイ" if choice == "high" else "📉 ロー", inline=True)
        embed.add_field(name="2枚目", value=f"{next_card[0]}{next_card[1]} （{card_value(next_card[1])}）", inline=True)
    embed.add_field(name="結果", value=result_text, inline=False)
    if streak > 0:
        embed.add_field(name="連続当選", value=f"{streak}回目\n×{get_multiplier(streak):.1f}倍", inline=True)
    if not is_free:
        embed.add_field(name="賭けP", value=f"{bet}P", inline=True)
        embed.add_field(name="変動", value=f"{change:+d}P", inline=True)
        embed.add_field(name="合計P", value=f"{total}P", inline=True)
    else:
        embed.add_field(name="備考", value="お試しモード\nポイントの増減なし", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await channel.send(embed=embed)

games = {}

class HighLowGameView(discord.ui.View):
    def __init__(self, user_id, bet, is_free=False):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bet = bet
        self.is_free = is_free
        self.deck = create_deck()
        self.first_card = self.deck.pop()
        self.streak = 0
        games[user_id] = self

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    async def show_choice_ui(self, itx):
        """ハイ・ロー・終了 選択画面表示"""
        mode_text = "🍀 お試しモード" if self.is_free else f"賭け：{self.bet}P"
        if self.streak > 0:
            mode_text += f"\n🔥 連続当選：{self.streak}回目 ×{get_multiplier(self.streak):.1f}倍"
        
        embed = discord.Embed(
            title="📈 ハイ＆ロー",
            description=mode_text,
            color=0x999999 if self.is_free else 0x3498DB
        )
        embed.add_field(name="現在のカード", value=f"**{self.first_card[0]}{self.first_card[1]}** （{card_value(self.first_card[1])}）", inline=False)
        embed.add_field(name="次はどうする？", value="ボタンを選んでください", inline=False)
        
        await itx.response.edit_message(embed=embed, view=self)

    async def process_result(self, itx, choice, next_card):
        val1 = card_value(self.first_card[1])
        val2 = card_value(next_card[1])
        
        if choice == "high":
            won = val2 > val1
        else:
            won = val2 < val1
        
        if val2 == val1:
            # 同じ値 → 引き分け・継続
            result_text = "⚖️ 引き分け！同じ値です。続行中"
            await send_result_embed(
                itx.client, itx.user,
                self.first_card, next_card, choice,
                result_text, 0, self.bet,
                get_points(self.user_id) if not self.is_free else 0,
                self.streak, is_free=self.is_free
            )
            self.first_card = next_card
            await self.show_choice_ui(itx)
            return
        
        if won:
            self.streak += 1
            mult = get_multiplier(self.streak)
            result_text = f"🎉 当たり！ 次の倍率：×{mult:.1f}"
            await send_result_embed(
                itx.client, itx.user,
                self.first_card, next_card, choice,
                result_text, 0, self.bet,
                get_points(self.user_id) if not self.is_free else 0,
                self.streak, is_free=self.is_free
            )
            self.first_card = next_card
            await self.show_choice_ui(itx)
        else:
            # 負け → 終了
            self.streak = 0
            change = -self.bet if not self.is_free else 0
            new_total = 0 if self.is_free else add_points(self.user_id, change)
            result_text = "💔 ハズレ… 没収"
            self.disable_all_items()
            embed = discord.Embed(
                title="📈 ハイ＆ロー",
                description=("🍀 お試しモード" if self.is_free else f"賭け：{self.bet}P"),
                color=0x999999 if self.is_free else 0xE74C3C
            )
            embed.add_field(name="1枚目", value=f"{self.first_card[0]}{self.first_card[1]} （{val1}）", inline=True)
            embed.add_field(name="2枚目", value=f"{next_card[0]}{next_card[1]} （{val2}）", inline=True)
            embed.add_field(name="結果", value=result_text, inline=False)
            if not self.is_free:
                embed.add_field(name="変動", value=f"{change:+d}P", inline=True)
                embed.add_field(name="所持P", value=f"{new_total}P", inline=True)
            await itx.response.edit_message(embed=embed, view=self)
            await send_result_embed(
                itx.client, itx.user,
                self.first_card, next_card, choice,
                result_text, change, self.bet, new_total,
                0, is_free=self.is_free
            )
            del games[self.user_id]

    @discord.ui.button(label="📈 ハイ", style=discord.ButtonStyle.primary, row=0)
    async def high_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        next_card = self.deck.pop()
        await self.process_result(itx, "high", next_card)

    @discord.ui.button(label="📉 ロー", style=discord.ButtonStyle.danger, row=0)
    async def low_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        next_card = self.deck.pop()
        await self.process_result(itx, "low", next_card)

    @discord.ui.button(label="💰 終了して確定", style=discord.ButtonStyle.success, row=1)
    async def cashout_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        if self.streak == 0:
            await itx.response.send_message("❌ まだ何も当たっていません", ephemeral=True)
            return
        
        mult = get_multiplier(self.streak)
        win_amount = int(self.bet * mult)
        change = win_amount if not self.is_free else 0
        new_total = 0 if self.is_free else add_points(self.user_id, change)
        
        self.disable_all_items()
        result_text = f"✅ {self.streak}回連続！ ×{mult:.1f}倍 → {win_amount}P 確定"
        
        embed = discord.Embed(
            title="📈 ハイ＆ロー 配当確定！",
            description=("🍀 お試しモード" if self.is_free else f"賭け：{self.bet}P"),
            color=0x999999 if self.is_free else 0xF1C40F
        )
        embed.add_field(name="最終倍率", value=f"×{mult:.1f}", inline=True)
        embed.add_field(name="連続回数", value=f"{self.streak}回", inline=True)
        embed.add_field(name="確定額", value=f"+{win_amount}P", inline=True)
        if not self.is_free:
            embed.add_field(name="変動", value=f"+{win_amount}P", inline=True)
            embed.add_field(name="所持P", value=f"{new_total}P", inline=True)
        
        await itx.response.edit_message(embed=embed, view=self)
        await send_result_embed(
            itx.client, itx.user,
            self.first_card, None, "cashout",
            result_text, change, self.bet, new_total,
            self.streak, is_free=self.is_free, is_cashout=True
        )
        del games[self.user_id]

class HighLowPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🍀 お試しプレイ", style=discord.ButtonStyle.secondary, custom_id="hl:free", row=0)
    async def free_play(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 0, is_free=True)

    @discord.ui.button(label="💳 1P ハイ＆ロー", style=discord.ButtonStyle.primary, custom_id="hl:1", row=1)
    async def hl1(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 1)

    @discord.ui.button(label="💳 10P ハイ＆ロー", style=discord.ButtonStyle.primary, custom_id="hl:10", row=1)
    async def hl10(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 10)

    @discord.ui.button(label="💳 50P ハイ＆ロー", style=discord.ButtonStyle.primary, custom_id="hl:50", row=2)
    async def hl50(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 50)

    @discord.ui.button(label="💳 100P ハイ＆ロー", style=discord.ButtonStyle.danger, custom_id="hl:100", row=2)
    async def hl100(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 100)

async def start_game(itx, bet, is_free=False):
    pts = get_points(itx.user.id)
    if itx.user.id in games:
        await itx.response.send_message("❌ ゲーム進行中です。終了までお待ちください", ephemeral=True)
        return
    if not is_free and pts < bet:
        await itx.response.send_message(f"❌ ポイントが足りません！（所持：{pts}P / 必要：{bet}P）", ephemeral=True)
        return

    view = HighLowGameView(itx.user.id, bet, is_free=is_free)
    
    mode_text = "🍀 お試しモード\nいくらでも練習可能" if is_free else (
        f"賭け：{bet}P\n\n"
        "📈 ハイ / 📉 ロー を選ぶ\n"
        "💰 終了して確定 → 連続分をGET\n"
        "🔥 連続するたび倍率UP！上限なし"
    )
    embed = discord.Embed(
        title="📈 ハイ＆ロー",
        description=mode_text,
        color=0x999999 if is_free else 0x3498DB
    )
    embed.add_field(name="最初のカード", value=f"**{view.first_card[0]}{view.first_card[1]}** （{card_value(view.first_card[1])}）", inline=False)
    embed.add_field(name="予想してください", value="下から選んでください", inline=False)
    
    await itx.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(tree: app_commands.CommandTree):
    @tree.command(name="ハイローパネル設置", description="ハイ＆ローパネル設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        embed = discord.Embed(
            title="📈 ハイ＆ロー",
            description=(
                "🍀 **お試し** → ポイント不要・無限プレイ\n"
                "💳 **1P/10P/50P/100P** → ポイントを賭けて\n"
                "📈 ハイ：次が大きい / 📉 ロー：次が小さい\n"
                "💰 終了して確定 → 連続分を受け取る\n"
                "🔥 連続するたび+0.3倍 UP！上限なし\n"
                "⚖️ 同じ値 → 引き分け・そのまま継続\n"
                "💔 負け → 賭け金没収・終了"
            ),
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=HighLowPanelView())
        await itx.followup.send("✅ ハイ＆ローパネル設置完了", ephemeral=True)
