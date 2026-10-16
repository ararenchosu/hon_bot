import discord
from discord import app_commands
import random
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
DATA_FILE = "kn_points_data.json"
GEM = "💎"
BOMB = "💣"
EMPTY = "⬜"
active_games = {}

# ========== ✅ くじ引き基準の読み書きに統一 ==========
def load_all_data():
    if not os.path.exists(DATA_FILE):
        return {}, {}, {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # ユーザーポイントと管理キーを分離
        points = {}
        last_draw = data.get("last_lottery_draw", {})
        last_bonus = data.get("last_bonus_receive", {})
        for k, v in data.items():
            if k not in ["last_lottery_draw", "last_bonus_receive"]:
                points[k] = v
        return points, last_draw, last_bonus
    except Exception as e:
        print(f"⚠️ データ読み込みエラー: {e}")
        return {}, {}, {}

def save_all_data(points, last_draw, last_bonus):
    output = dict(points)
    output["last_lottery_draw"] = last_draw
    output["last_bonus_receive"] = last_bonus
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def get_points(user_id: int):
    pts, _, _ = load_all_data()
    return pts.get(str(user_id), 0)

def add_points(user_id: int, amount: int):
    pts, last_draw, last_bonus = load_all_data()
    uid = str(user_id)
    pts[uid] = pts.get(uid, 0) + amount
    save_all_data(pts, last_draw, last_bonus)
    return pts[uid]

# ========== 難易度選択パネル ==========
class MinesSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 かんたん", style=discord.ButtonStyle.success, custom_id="mines:easy")
    async def easy_btn(self, itx: discord.Interaction, btn):
        await itx.response.send_modal(BetModal(size=5, bombs=3, multiplier_rate=1.12))

    @discord.ui.button(label="🟡 ふつう", style=discord.ButtonStyle.primary, custom_id="mines:normal")
    async def normal_btn(self, itx: discord.Interaction, btn):
        await itx.response.send_modal(BetModal(size=5, bombs=6, multiplier_rate=1.18))

    @discord.ui.button(label="🔴 むずかしい", style=discord.ButtonStyle.danger, custom_id="mines:hard")
    async def hard_btn(self, itx: discord.Interaction, btn):
        await itx.response.send_modal(BetModal(size=6, bombs=12, multiplier_rate=1.25))

    @discord.ui.button(
        label="📊 所持ポイント確認",
        style=discord.ButtonStyle.secondary,
        row=1,
        custom_id="mines:check_points"
    )
    async def check_points_btn(self, itx: discord.Interaction, btn):
        pts = get_points(itx.user.id)
        await itx.response.send_message(
            f"👤 {itx.user.mention} の所持ポイント\n**{pts:,}** pt",
            ephemeral=True
        )

# ========== ポイント入力モーダル ==========
class BetModal(discord.ui.Modal, title="💵 賭けるポイントを入力"):
    bet_amount = discord.ui.TextInput(
        label="賭けるポイント",
        placeholder="例: 100",
        required=True
    )

    def __init__(self, size: int, bombs: int, multiplier_rate: float):
        super().__init__()
        self.size = size
        self.bombs = bombs
        self.multiplier_rate = multiplier_rate

    async def on_submit(self, itx: discord.Interaction):
        await itx.response.defer(ephemeral=True)
        try:
            amount = int(self.bet_amount.value)
            if amount <= 0:
                raise ValueError
        except:
            await itx.followup.send("❌ 正しい数値を入力してください", ephemeral=True)
            return

        current_points = get_points(itx.user.id)
        if current_points < amount:
            await itx.followup.send(
                f"❌ ポイントが足りません！\n現在：{current_points:,} pt\n必要：{amount:,} pt",
                ephemeral=True
            )
            return

        add_points(itx.user.id, -amount)
        after_bet = get_points(itx.user.id)
        view = MinesGameView(itx.user.id, self.size, self.bombs, amount, self.multiplier_rate)
        active_games[itx.user.id] = view

        embed = discord.Embed(
            title=f"💎 マインスゲーム開始！",
            description=(
                f"サイズ：{self.size}×{self.size}\n"
                f"爆弾：{self.bombs}個\n"
                f"賭け：**{amount:,} pt**\n"
                f"所持：{after_bet:,} pt\n\n"
                f"💎 を集めて倍率UP！いつでも💰受け取れます✨"
            ),
            color=0x3498DB
        )
        await itx.followup.send(embed=embed, view=view)

# ========== ゲーム本体 ==========
class MinesGameView(discord.ui.View):
    def __init__(self, user_id: int, size: int, bombs: int, bet: int, multiplier_rate: float):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.size = size
        self.bombs = bombs
        self.bet = bet
        self.multiplier = 1.0
        self.multiplier_rate = multiplier_rate
        self.grid = [[False]*size for _ in range(size)]
        self.revealed = [[False]*size for _ in range(size)]
        self.game_over = False

        all_pos = [(r,c) for r in range(size) for c in range(size)]
        for r,c in random.sample(all_pos, bombs):
            self.grid[r][c] = True

        for r in range(size):
            for c in range(size):
                b = discord.ui.Button(
                    label=EMPTY,
                    style=discord.ButtonStyle.secondary,
                    row=r,
                    custom_id=f"mines_cell:{user_id}:{r}:{c}"
                )
                b.callback = self.make_callback(r,c)
                self.add_item(b)

        self.cashout_btn = discord.ui.Button(
            label="💰 受け取る",
            style=discord.ButtonStyle.success,
            row=size,
            custom_id=f"mines_cashout:{user_id}"
        )
        self.cashout_btn.callback = self.cashout
        self.add_item(self.cashout_btn)

        self.quit_btn = discord.ui.Button(
            label="❌ キャンセル（返金）",
            style=discord.ButtonStyle.secondary,
            row=size,
            custom_id=f"mines_quit:{user_id}"
        )
        self.quit_btn.callback = self.quit
        self.add_item(self.quit_btn)

        self.check_btn = discord.ui.Button(
            label="📊 ポイント確認",
            style=discord.ButtonStyle.secondary,
            row=size+1,
            custom_id=f"mines_check:{user_id}"
        )
        self.check_btn.callback = self.check_points
        self.add_item(self.check_btn)

    async def check_points(self, itx: discord.Interaction):
        if itx.user.id != self.user_id:
            await itx.response.send_message("❌ あなたのゲームではありません", ephemeral=True)
            return
        pts = get_points(self.user_id)
        await itx.response.send_message(
            f"📊 現在の所持ポイント：**{pts:,}** pt",
            ephemeral=True
        )

    def make_callback(self, row, col):
        async def callback(itx: discord.Interaction):
            if itx.user.id != self.user_id:
                await itx.response.send_message("❌ あなたのゲームではありません", ephemeral=True)
                return
            if self.game_over or self.revealed[row][col]:
                await itx.response.defer()
                return

            self.revealed[row][col] = True

            if self.grid[row][col]:
                self.game_over = True
                for i, b in enumerate(self.children):
                    if hasattr(b, 'row') and isinstance(b.row, int) and b.row < self.size:
                        r = b.row
                        c = i % self.size
                        b.disabled = True
                        if self.grid[r][c]:
                            b.label = BOMB
                            b.style = discord.ButtonStyle.danger
                        elif self.revealed[r][c]:
                            b.label = GEM
                            b.style = discord.ButtonStyle.success

                self.cashout_btn.disabled = True
                self.quit_btn.disabled = True
                self.check_btn.disabled = True

                embed = discord.Embed(
                    title="💥 ゲームオーバー",
                    description=(
                        f"爆弾を踏んでしまいました…\n"
                        f"賭け **{self.bet:,} pt** は没収されました\n\n"
                        f"次回の挑戦をお待ちしてます✨"
                    ),
                    color=0xE74C3C
                )
                await itx.response.edit_message(embed=embed, view=self)
                if self.user_id in active_games:
                    del active_games[self.user_id]

            else:
                self.multiplier *= self.multiplier_rate
                opened = sum(sum(r) for r in self.revealed)
                safe_total = self.size * self.size - self.bombs

                for b in self.children:
                    if getattr(b, 'custom_id', '').endswith(f":{row}:{col}"):
                        b.label = GEM
                        b.style = discord.ButtonStyle.success
                        b.disabled = True
                        break

                if opened >= safe_total:
                    self.game_over = True
                    reward = int(self.bet * self.multiplier)
                    add_points(self.user_id, reward)
                    final_pts = get_points(self.user_id)
                    for b in self.children:
                        b.disabled = True

                    embed = discord.Embed(
                        title="🎉 コンプリート！",
                        description=(
                            f"全マス開けました✨\n"
                            f"配当：**{reward:,} pt**（{self.multiplier:.2f}倍）\n"
                            f"利益：+{reward - self.bet:,} pt\n"
                            f"現在：{final_pts:,} pt"
                        ),
                        color=0x2ECC71
                    )
                    await itx.response.edit_message(embed=embed, view=self)
                    if self.user_id in active_games:
                        del active_games[self.user_id]
                else:
                    current_reward = int(self.bet * self.multiplier)
                    embed = discord.Embed(
                        title="💎 マインスゲーム",
                        description=(
                            f"開けた：{opened}/{safe_total}\n"
                            f"現在の倍率：**{self.multiplier:.2f}倍**\n"
                            f"受け取り時：**{current_reward:,} pt**"
                        ),
                        color=0x3498DB
                    )
                    await itx.response.edit_message(embed=embed, view=self)
        return callback

    async def cashout(self, itx: discord.Interaction):
        if itx.user.id != self.user_id or self.game_over:
            await itx.response.defer()
            return

        self.game_over = True
        reward = int(self.bet * self.multiplier)
        add_points(self.user_id, reward)
        final_pts = get_points(self.user_id)

        for b in self.children:
            b.disabled = True

        embed = discord.Embed(
            title="💰 配当を受け取りました",
            description=(
                f"獲得：**{reward:,} pt**\n"
                f"倍率：{self.multiplier:.2f}倍\n"
                f"利益：+{reward - self.bet:,} pt\n"
                f"現在：{final_pts:,} pt"
            ),
            color=0xF1C40F
        )
        await itx.response.edit_message(embed=embed, view=self)
        if self.user_id in active_games:
            del active_games[self.user_id]

    async def quit(self, itx: discord.Interaction):
        if itx.user.id != self.user_id:
            await itx.response.defer()
            return

        self.game_over = True
        add_points(self.user_id, self.bet)
        final_pts = get_points(self.user_id)
        del active_games[self.user_id]

        await itx.response.edit_message(
            embed=discord.Embed(
                title="✅ キャンセル完了",
                description=f"**{self.bet:,} pt** を返金しました\n現在：{final_pts:,} pt",
                color=0x95A5A6
            ),
            view=None
        )

# ========== セットアップ ==========
async def setup(tree: app_commands.CommandTree, bot=None):
    if bot is not None and not hasattr(bot, "_mines_registered"):
        bot.add_view(MinesSetupView())
        bot._mines_registered = True
        print("✅ mines_panel 永続View登録完了")

    @tree.command(name="minesパネル", description="💎 マインスゲームパネルを表示")
    async def cmd_mines_panel(itx: discord.Interaction):
        await itx.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="💎 マインスゲーム",
            description=(
                "下のボタンから難易度を選んでください✨\n\n"
                "🟢 かんたん ：5×5  爆弾3個  倍率+12%/1マス\n"
                "🟡 ふつう   ：5×5  爆弾6個  倍率+18%/1マス\n"
                "🔴 むずかしい：6×6  爆弾12個  倍率+25%/1マス\n\n"
                "💰 いつでも受け取り可 ｜ 💣 踏むと没収\n"
                "📊 いつでもポイント確認OK"
            ),
            color=0x3498DB
        )
        await itx.followup.send(embed=embed, view=MinesSetupView())
