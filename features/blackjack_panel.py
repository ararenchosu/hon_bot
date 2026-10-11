import discord
from discord import app_commands
import random
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

# ===== 統計用共通モジュール読み込み =====
from core.game_stats import increment

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"
BJ_RESULT_CHANNEL_ID = 1558770503261491311  # チャンネルID

# ===== カード定義 =====
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def create_deck():
    deck = [(s, r) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_value(rank):
    if rank in ["J", "Q", "K"]:
        return 10
    if rank == "A":
        return 11
    return int(rank)

def hand_total(cards):
    total = sum(card_value(r) for _, r in cards)
    aces = sum(1 for _, r in cards if r == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total

def is_blackjack(cards):
    return len(cards) == 2 and hand_total(cards) == 21

# ===== ポイント読み書き =====
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

# ===== 結果通知送信 =====
async def send_result_embed(client, user, dealer_cards, player_cards, result_text, change, bet, total, is_free=False):
    channel = client.get_channel(BJ_RESULT_CHANNEL_ID)
    if not channel:
        print(f"⚠️ 結果チャンネルが見つかりません: {BJ_RESULT_CHANNEL_ID}")
        return

    dealer_str = " ".join(f"{s}{r}" for s, r in dealer_cards)
    player_str = " ".join(f"{s}{r}" for s, r in player_cards)
    title = "🃏 ブラックジャック結果（お試し）" if is_free else "🃏 ブラックジャック結果"
    
    embed = discord.Embed(
        title=title,
        description=f"{user.mention} が対戦しました！",
        color=0x999999 if is_free else (0x2ECC71 if change > 0 else (0x999999 if change == 0 else 0xE74C3C)),
        timestamp=datetime.now(JST)
    )
    embed.add_field(name="ディーラー", value=f"{dealer_str}\n合計: {hand_total(dealer_cards)}", inline=True)
    embed.add_field(name="あなた", value=f"{player_str}\n合計: {hand_total(player_cards)}", inline=True)
    embed.add_field(name="結果", value=result_text, inline=False)
    if not is_free:
        embed.add_field(name="賭けP", value=f"{bet}P", inline=True)
        embed.add_field(name="変動", value=f"{change:+d}P", inline=True)
        embed.add_field(name="合計P", value=f"{total}P", inline=True)
    else:
        embed.add_field(name="備考", value="お試しモード\nポイントの増減なし", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await channel.send(embed=embed)

    # ===== チャンネル名更新 =====
    count = increment("blackjack")
    await channel.edit(name=f"🃏・ブラックジャック・{count}回", reason="プレイ回数更新")


# ===== ゲーム状態管理 =====
games = {}

class BlackjackGameView(discord.ui.View):
    def __init__(self, user_id, bet, is_free=False):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bet = bet
        self.is_free = is_free
        deck = create_deck()
        self.deck = deck
        self.dealer_hand = [deck.pop(), deck.pop()]
        self.player_hand = [deck.pop(), deck.pop()]
        self.doubled = False
        games[user_id] = self
        if is_blackjack(self.player_hand):
            self.disable_all_items()

    def disable_all_items(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def hand_str(self, cards, hide_one=False):
        if hide_one:
            return f"{cards[0][0]}{cards[0][1]} ?"
        return " ".join(f"{s}{r}" for s, r in cards)

    async def update_display(self, itx=None):
        player_total = hand_total(self.player_hand)
        dealer_hidden = len(self.player_hand) == 2 and not self.doubled
        dealer_total = hand_total(self.dealer_hand) if not dealer_hidden else "?"
        mode_text = "🍀 お試しモード" if self.is_free else f"賭け：{self.bet}P"
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=mode_text,
            color=0x959595 if self.is_free else 0x1ABC9C
        )
        embed.add_field(name="ディーラー", value=f"{self.hand_str(self.dealer_hand, dealer_hidden)}\n合計: {dealer_total}", inline=False)
        embed.add_field(name="あなた", value=f"{self.hand_str(self.player_hand)}\n合計: {player_total}", inline=False)
        if itx:
            await itx.response.edit_message(embed=embed, view=self)

    async def finish_game(self, itx, result_text, change):
        self.disable_all_items()
        new_total = 0 if self.is_free else add_points(self.user_id, change)
        player_total = hand_total(self.player_hand)
        dealer_total = hand_total(self.dealer_hand)
        mode_text = "🍀 お試しモード" if self.is_free else f"賭け：{self.bet}P → {result_text}"
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=mode_text,
            color=0x999999 if self.is_free else (0x2ECC71 if change > 0 else (0x999999 if change == 0 else 0xE74C3C))
        )
        embed.add_field(name="ディーラー", value=f"{self.hand_str(self.dealer_hand)}\n合計: {dealer_total}", inline=True)
        embed.add_field(name="あなた", value=f"{self.hand_str(self.player_hand)}\n合計: {player_total}", inline=True)
        embed.add_field(name="結果", value=result_text, inline=False)
        if not self.is_free:
            embed.add_field(name="変動", value=f"{change:+d}P", inline=True)
            embed.add_field(name="所持P", value=f"{new_total}P", inline=True)
        await itx.response.edit_message(embed=embed, view=self)
        await send_result_embed(
            itx.client, itx.user,
            self.dealer_hand, self.player_hand,
            result_text, change, self.bet, new_total,
            is_free=self.is_free
        )
        del games[self.user_id]

    @discord.ui.button(label="ヒット", style=discord.ButtonStyle.primary)
    async def hit(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        if self.doubled:
            await itx.response.send_message("❌ ダブル後は追加できません", ephemeral=True)
            return
        self.player_hand.append(self.deck.pop())
        total = hand_total(self.player_hand)
        if total > 21:
            await self.finish_game(itx, "バースト！負け", -self.bet if not self.is_free else 0)
        elif total == 21:
            await self.stand(itx, None)
        else:
            await self.update_display(itx)

    @discord.ui.button(label="スタンド", style=discord.ButtonStyle.success)
    async def stand(self, itx: discord.Interaction, btn: discord.ui.Button):
        if itx and itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        while hand_total(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        p_total = hand_total(self.player_hand)
        d_total = hand_total(self.dealer_hand)
        if d_total > 21 or p_total > d_total:
            if is_blackjack(self.player_hand):
                result_text = "🎉 ブラックジャック！勝ち"
                change = int(self.bet * 1.5) if not self.is_free else 0
            else:
                result_text = "🎉 勝ち"
                change = self.bet if not self.is_free else 0
        elif p_total < d_total:
            result_text = "💔 負け"
            change = -self.bet if not self.is_free else 0
        else:
            result_text = "引き分け"
            change = 0
        if itx:
            await self.finish_game(itx, result_text, change)

    @discord.ui.button(label="ダブル", style=discord.ButtonStyle.danger)
    async def double(self, itx: discord.Interaction, btn: discord.ui.Button):
        if self.is_free:
            await itx.response.send_message("❌ お試しモードではダブルできません", ephemeral=True)
            return
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ 自分のゲームではありません", ephemeral=True)
            return
        if len(self.player_hand) != 2:
            await itx.response.send_message("❌ 初回のみダブル可能です", ephemeral=True)
            return
        pts = get_points(self.user_id)
        if pts < self.bet:
            await itx.response.send_message("❌ ポイントが足りません", ephemeral=True)
            return
        self.bet *= 2
        self.doubled = True
        self.player_hand.append(self.deck.pop())
        total = hand_total(self.player_hand)
        if total > 21:
            await self.finish_game(itx, "バースト！負け", -self.bet)
        else:
            await self.stand(itx, None)


class BlackjackPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🍀 お試しプレイ", style=discord.ButtonStyle.secondary, custom_id="bj:free", row=0)
    async def free_play(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 0, is_free=True)

    @discord.ui.button(label="💳 10P ブラックジャック", style=discord.ButtonStyle.primary, custom_id="bj:10", row=1)
    async def bj10(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 10)

    @discord.ui.button(label="💳 50P ブラックジャック", style=discord.ButtonStyle.primary, custom_id="bj:50", row=1)
    async def bj50(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 50)

    @discord.ui.button(label="💳 100P ブラックジャック", style=discord.ButtonStyle.danger, custom_id="bj:100", row=2)
    async def bj100(self, itx: discord.Interaction, btn: discord.ui.Button):
        await start_game(itx, 100)


async def start_game(itx, bet, is_free=False):
    pts = get_points(itx.user.id)
    if itx.user.id in games:
        await itx.response.send_message("❌ ゲーム進行中です。終了までお待ちください", ephemeral=True)
        return
    if not is_free and pts < bet:
        await itx.response.send_message(f"❌ ポイントが足りません！（所持：{pts}P / 必要：{bet}P）", ephemeral=True)
        return
    view = BlackjackGameView(itx.user.id, bet, is_free=is_free)
    
    if is_blackjack(view.player_hand):
        change = int(bet * 1.5) if not is_free else 0
        new_total = 0 if is_free else add_points(itx.user.id, change)
        mode_text = "🍀 お試しモード" if is_free else f"賭け：{bet}P"
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=mode_text,
            color=0x999999 if is_free else 0xFFD700
        )
        embed.add_field(name="ディーラー", value=view.hand_str(view.dealer_hand) + f"\n合計: {hand_total(view.dealer_hand)}", inline=True)
        embed.add_field(name="あなた", value=view.hand_str(view.player_hand) + "\n🃏 ブラックジャック！", inline=True)
        result_text = "🎉 ブラックジャック！" if is_free else f"🎉 ブラックジャック！+{change}P"
        embed.add_field(name="結果", value=result_text, inline=False)
        if not is_free:
            embed.add_field(name="所持P", value=f"{new_total}P", inline=True)
        view.disable_all_items()
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)
        await send_result_embed(
            itx.client, itx.user, view.dealer_hand, view.player_hand,
            "ブラックジャック", change, bet, new_total, is_free=is_free
        )
        del games[itx.user.id]
        return
    
    mode_text = "🍀 お試しモード\nポイントの増減なし" if is_free else (
        f"賭け：{bet}P\n\n"
        "ヒット：もう1枚引く\n"
        "スタンド：そのまま勝負\n"
        "ダブル：賭け倍増＋1枚のみ"
    )
    embed = discord.Embed(
        title="🃏 ブラックジャック",
        description=mode_text,
        color=0x999999 if is_free else 0x1ABC9C
    )
    hide_dealer = not is_free
    embed.add_field(name="ディーラー", value=view.hand_str(view.dealer_hand, hide_dealer) + "\n合計: ?" if hide_dealer else f"\n合計: {hand_total(view.dealer_hand)}", inline=False)
    embed.add_field(name="あなた", value=view.hand_str(view.player_hand) + f"\n合計: {hand_total(view.player_hand)}", inline=False)
    await itx.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(tree: app_commands.CommandTree):
    @tree.command(name="ブラックジャックパネル設置", description="ブラックジャックパネル設置（オーナー専用）")
    async def cmd(itx: discord.Interaction):
        if not is_owner(itx):
            await itx.response.send_message("❌ オーナー専用です", ephemeral=True)
            return
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=(
                "🍀 **お試し** → ポイントを使わず対戦\n"
                "💳 **10P/50P/100P** → ポイントを賭けて対戦\n"
                "🃏 ブラックジャック：1.5倍払い出し\n"
                "✅ ヒット：カードを引く / ❌ スタンド：そのまま\n"
                "⚡ ダブル：賭け倍増＋1枚（お試し不可）"
            ),
            color=0x1ABC9C
        )
        await itx.response.send_message(embed=embed, view=BlackjackPanelView())
        await itx.followup.send("✅ ブラックジャックパネル設置完了", ephemeral=True)
