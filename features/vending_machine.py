import discord
from discord import app_commands
import json
import os
from datetime import datetime, timedelta, timezone
from core.common import is_owner

JST = timezone(timedelta(hours=9))
VENDING_DATA_FILE = "vending_products.json"
ORDERS_FILE = "vending_orders.json"
VENDING_LOG_CHANNEL_ID = 1559602193647271936

# ✅ パネル最新情報を保存（更新ボタン用）
_active_panel = {"channel_id": None, "message_id": None}

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

# ===== 商品管理用パネル（管理者専用） =====
class VendingAdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ 商品追加", style=discord.ButtonStyle.primary, custom_id="vending_admin_add")
    async def add_product_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddProductModal())

    @discord.ui.button(label="➖ 商品削除", style=discord.ButtonStyle.danger, custom_id="vending_admin_remove")
    async def remove_product_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = ProductRemoveSelectView()
        await interaction.response.send_message("削除する商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="🔄 パネル更新", style=discord.ButtonStyle.success, custom_id="vending_admin_refresh")
    async def refresh_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """✅ パネルを最新の内容に更新"""
        if not _active_panel["message_id"]:
            await interaction.response.send_message(
                "⚠️ まだ自販機パネルが設置されていません。\n先に「パネル設置」を押してください。",
                ephemeral=True
            )
            return
        products = load_products()
        if not products:
            await interaction.response.send_message(
                "⚠️ 商品が登録されていません。\n先に商品を追加してください。",
                ephemeral=True
            )
            return
        # 保存されたチャンネル・メッセージを取得して上書き編集
        channel = interaction.guild.get_channel(_active_panel["channel_id"])
        if not channel:
            await interaction.response.send_message("❌ チャンネルが見つかりません", ephemeral=True)
            return
        try:
            message = await channel.fetch_message(_active_panel["message_id"])
        except:
            await interaction.response.send_message(
                "❌ パネルが見つかりません。\n「パネル設置」からやり直してください。",
                ephemeral=True
            )
            return
        # 最新内容に入れ替え
        embed = discord.Embed(
            title="🛒 自動販売機",
            description="下のボタンから商品を選んでください。\n支払いはPayPay送金リンク式です。",
            color=0x3498DB
        )
        await message.edit(embed=embed, view=VendingMachineView())
        await interaction.response.send_message("✅ パネルを最新の内容に更新しました！", ephemeral=True)

    @discord.ui.button(label="📤 パネル設置", style=discord.ButtonStyle.secondary, custom_id="vending_admin_place")
    async def place_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """✅ 新規パネルを設置して位置を記憶"""
        products = load_products()
        if not products:
            await interaction.response.send_message(
                "⚠️ 商品が登録されていません。\n先に「➕ 商品追加」から登録してください。",
                ephemeral=True
            )
            return
        embed = discord.Embed(
            title="🛒 自動販売機",
            description="下のボタンから商品を選んでください。\n支払いはPayPay送金リンク式です。",
            color=0x3498DB
        )
        msg = await interaction.channel.send(embed=embed, view=VendingMachineView())
        # 位置を記憶 → 更新ボタンでここを編集する
        _active_panel["channel_id"] = interaction.channel_id
        _active_panel["message_id"] = msg.id
        await interaction.response.send_message("✅ 自販機パネルを設置しました！\n以降は「🔄 パネル更新」で内容を反映できます。", ephemeral=True)

class AddProductModal(discord.ui.Modal, title="商品追加"):
    name = discord.ui.TextInput(label="商品名", required=True)
    price = discord.ui.TextInput(label="金額（円）", required=True)
    description = discord.ui.TextInput(label="説明（任意）", required=False, style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.price.value.isdigit():
            await interaction.response.send_message("❌ 金額は数字で入力してください", ephemeral=True)
            return
        price = int(self.price.value)
        products = load_products()
        pid = f"prod_{len(products)+1:03d}"
        products[pid] = {
            "name": self.name.value,
            "price": price,
            "desc": self.description.value or ""
        }
        save_products(products)
        await interaction.response.send_message(
            f"✅ 追加完了！\nID: `{pid}`\n商品名: {self.name.value}\n金額: ￥{price}\n\n👉 「🔄 パネル更新」を押すと表示に反映されます",
            ephemeral=True
        )

class ProductRemoveSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        products = load_products()
        for pid, prod in products.items():
            self.add_item(discord.ui.Button(
                label=f"{prod['name']} ￥{prod['price']}",
                custom_id=f"remove_{pid}",
                style=discord.ButtonStyle.danger
            ))

    async def interaction_check(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    async def on_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id", "")
        if custom_id.startswith("remove_"):
            pid = custom_id.replace("remove_", "")
            products = load_products()
            if pid not in products:
                await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
                return
            del products[pid]
            save_products(products)
            await interaction.response.send_message(
                f"✅ 削除完了！\nID: `{pid}`\n👉 「🔄 パネル更新」を押すと表示から消えます",
                ephemeral=True
            )
            await interaction.message.delete()

# ===== ユーザー用 自販機パネル =====
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
            view = PayPayLinkPromptView(pid, prod["name"], prod["price"])
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

class PayPayLinkPromptView(discord.ui.View):
    def __init__(self, pid, name, price):
        super().__init__(timeout=300)
        self.pid = pid
        self.prod_name = name
        self.price = price

    @discord.ui.button(label="📋 リンクを貼り付けて送信", style=discord.ButtonStyle.success)
    async def prompt_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PayPayLinkModal(self.pid, self.prod_name, self.price)
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

# ✅ 永続対応
class OrderConfirmView(discord.ui.View):
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="✅ 確認・引き渡し完了",
        style=discord.ButtonStyle.success,
        custom_id="vending_confirm"
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = self.ticket_id
        if not ticket_id:
            try:
                if interaction.message and interaction.message.embeds:
                    embed = interaction.message.embeds[0]
                    for field in embed.fields:
                        if "チケットID" in field.name:
                            ticket_id = field.value.replace("`", "").strip()
                            break
            except:
                pass
        if not ticket_id:
            await interaction.response.send_message("❌ チケットIDが取得できません。手動で確認してください", ephemeral=True)
            return

        orders = load_orders()
        if ticket_id not in orders:
            await interaction.response.send_message("❌ 存在しない注文です", ephemeral=True)
            return
        orders[ticket_id]["status"] = "completed"
        save_orders(orders)
        await interaction.response.send_message(f"✅ `{ticket_id}` を完了にしました", ephemeral=True)
        embed = discord.Embed(title="✅ 引き渡し完了", color=0x2ECC71)
        await interaction.message.edit(embed=embed, view=None)

async def setup(tree: app_commands.CommandTree):
    # 管理パネル設置コマンド
    @tree.command(name="自動販売機管理パネル", description="商品追加・削除用管理パネルを表示")
    async def admin_panel_cmd(interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        embed = discord.Embed(
            title="⚙️ 自販機管理パネル",
            description="下のボタンから商品の追加・削除・更新ができます",
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed, view=VendingAdminPanelView())
