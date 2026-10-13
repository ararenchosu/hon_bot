import discord
from discord import app_commands
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
VENDING_DATA_FILE = "vending_products.json"
ORDERS_FILE = "vending_orders.json"
VENDING_LOG_CHANNEL_ID = 1559119439981449256  # ログ送信先

# ===== 商品データ管理 =====
def load_products():
    if not os.path.exists(VENDING_DATA_FILE):
        return {}
    with open(VENDING_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(data):
    with open(VENDING_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return {}
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_ticket_id():
    return f"V-{datetime.now(JST).strftime('%Y%m%d')}-{os.urandom(2).hex().upper()}"

# ===== View定義 =====
class VendingMachineView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        products = load_products()
        if not products:
            self.add_item(discord.ui.Button(
                label="商品登録待ち",
                disabled=True,
                style=discord.ButtonStyle.secondary,
                custom_id="vending_empty"
            ))
            return
        for pid, prod in products.items():
            self.add_item(discord.ui.Button(
                label=f"{prod['name']} ￥{prod['price']}",
                custom_id=f"vending_buy_{pid}",
                style=discord.ButtonStyle.primary
            ))

    async def interaction_check(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id", "") if interaction.data else ""
        if custom_id.startswith("vending_buy_"):
            pid = custom_id.replace("vending_buy_", "")
            products = load_products()
            if pid not in products:
                await interaction.response.send_message("❌ この商品は現在利用できません", ephemeral=True)
                return False
            prod = products[pid]
            view = PayPayLinkInputView(pid)
            await interaction.response.send_message(
                f"🛒 **{prod['name']}**\n"
                f"💴 金額：**￥{prod['price']}**\n\n"
                f"【手順】\n"
                f"1. PayPayアプリを開く\n"
                f"2. 送金 → 金額 `{prod['price']}円` を入力\n"
                f"3. 「リンクを発行」を選択してコピー\n"
                f"4. 下のボタンからリンクを貼り付け",
                view=view,
                ephemeral=True
            )
            return False
        return True

class PayPayLinkInputView(discord.ui.View):
    def __init__(self, product_id):
        super().__init__(timeout=None)
        self.pid = product_id

    @discord.ui.button(label="📋 リンクを貼り付けて送信", style=discord.ButtonStyle.success, custom_id="vending_link_input")
    async def prompt_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        prod = products[self.pid]
        modal = PayPayLinkModal(self.pid, prod["name"], prod["price"])
        await interaction.response.send_modal(modal)

class PayPayLinkModal(discord.ui.Modal, title="PayPay送金リンク送信"):
    link = discord.ui.TextInput(
        label="PayPay送金リンクを貼り付け",
        placeholder="https://paypay.ne.jp/...",
        required=True,
        style=discord.TextStyle.short
    )

    def __init__(self, pid, name, price):
        super().__init__()
        self.pid = pid
        self.prod_name = name
        self.price = price

    async def on_submit(self, interaction: discord.Interaction):
        if "paypay.ne.jp" not in self.link.value:
            await interaction.response.send_message("❌ PayPayのリンクを貼り付けてください", ephemeral=True)
            return
        ticket_id = generate_ticket_id()
        orders = load_orders()
        orders[ticket_id] = {
            "user_id": str(interaction.user.id),
            "user_name": interaction.user.name,
            "product_id": self.pid,
            "product_name": self.prod_name,
            "price": self.price,
            "paypay_link": self.link.value,
            "status": "pending",
            "created_at": datetime.now(JST).isoformat()
        }
        save_orders(orders)

        await interaction.response.send_message(
            f"✅ 受付完了！\n"
            f"🎫 チケットID：`{ticket_id}`\n"
            f"📦 商品：{self.prod_name}\n"
            f"💴 金額：￥{self.price}\n\n"
            f"運営が確認次第お渡しします。このIDを控えておいてください。",
            ephemeral=True
        )

        if VENDING_LOG_CHANNEL_ID:
            log_ch = interaction.client.get_channel(VENDING_LOG_CHANNEL_ID)
            if log_ch:
                embed = discord.Embed(title="🛒 新規注文", color=0xF1C40F)
                embed.add_field(name="ユーザー", value=f"{interaction.user.mention}\n{interaction.user.id}", inline=False)
                embed.add_field(name="商品", value=f"{self.prod_name}\n￥{self.price}", inline=False)
                embed.add_field(name="チケットID", value=f"`{ticket_id}`", inline=False)
                embed.add_field(name="PayPayリンク", value=f"🔗 {self.link.value}", inline=False)
                embed.set_footer(text=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"))
                await log_ch.send(embed=embed, view=OrderConfirmView(ticket_id))

class OrderConfirmView(discord.ui.View):
    def __init__(self, ticket_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="✅ 確認・引き渡し完了", style=discord.ButtonStyle.success, custom_id="vending_complete")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        orders = load_orders()
        if self.ticket_id not in orders:
            await interaction.response.send_message("❌ 存在しない注文です", ephemeral=True)
            return
        orders[self.ticket_id]["status"] = "completed"
        save_orders(orders)
        await interaction.response.send_message(f"✅ `{self.ticket_id}` を完了にしました", ephemeral=True)
        embed = discord.Embed(title="✅ 引き渡し完了", color=0x2ECC71)
        await interaction.message.edit(embed=embed, view=None)

# ===== セットアップ（サブBot用）=====
async def setup(tree: app_commands.CommandTree):
    @tree.command(name="vending-add", description="自販機に商品を追加")
    @app_commands.describe(name="商品名", price="金額", description="商品の説明")
    async def vending_add(interaction: discord.Interaction, name: str, price: int, description: str = ""):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        products = load_products()
        pid = f"prod_{len(products)+1:03d}"
        products[pid] = {"name": name, "price": price, "desc": description}
        save_products(products)
        await interaction.response.send_message(
            f"✅ 追加：{name} ￥{price}\n"
            f"→ パネルを再設置すると反映されます",
            ephemeral=True
        )

    @tree.command(name="vending-remove", description="自販機から商品を削除")
    @app_commands.describe(product_id="削除する商品ID")
    async def vending_remove(interaction: discord.Interaction, product_id: str):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        products = load_products()
        if product_id not in products:
            await interaction.response.send_message("❌ 存在しないIDです", ephemeral=True)
            return
        del products[product_id]
        save_products(products)
        await interaction.response.send_message(f"✅ 削除しました", ephemeral=True)

    @tree.command(name="vending-setup", description="自販機パネルを設置（メインBotで実行）")
    async def vending_setup_cmd(interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        products = load_products()
        if not products:
            await interaction.response.send_message(
                "⚠️ 商品が登録されていません。\n"
                "先に `/vending-add` で商品を追加してください。",
                ephemeral=True
            )
            return
        embed = discord.Embed(
            title="🛒 自動販売機",
            description="下のボタンから商品を選んでください。\n支払いはPayPay送金リンク式です。",
            color=0x3498DB
        )
        await interaction.response.send_message(embed=embed, view=VendingMachineView())
