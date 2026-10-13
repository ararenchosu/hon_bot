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
PANEL_COLOR = 0x2ECC71  # 緑色で統一

# パネル最新情報を保存
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

# 商品一覧埋め込み作成
def build_vending_embed():
    products = load_products()
    desc = "商品を選択して購入手続きへ進んでください。\n"
    desc += "────────────────────────────\n"
    for pid, prod in products.items():
        desc += f"**{prod['name']}**\n"
        if prod.get("desc"):
            desc += f"{prod['desc']}\n"
        stock = prod.get("stock")
        if stock is None:
            stock_text = "無限"
        else:
            stock_text = f"{stock}個（手動仕入れ）"
        desc += f"価格: {prod['price']}円 | 在庫: {stock_text}\n"
        desc += "────────────────────────────\n"
    return discord.Embed(
        title="🛒 商品一覧",
        description=desc,
        color=PANEL_COLOR
    )

# ===== 管理パネル =====
class VendingAdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="➕ 商品追加", style=discord.ButtonStyle.secondary, custom_id="vending_admin_add", row=0)
    async def add_product_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddProductModal())

    @discord.ui.button(label="➖ 商品削除", style=discord.ButtonStyle.secondary, custom_id="vending_admin_remove", row=0)
    async def remove_product_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = ProductRemoveSelectView()
        await interaction.response.send_message("削除する商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="📥 仕入れ", style=discord.ButtonStyle.secondary, custom_id="vending_admin_restock", row=0)
    async def restock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = RestockSelectView()
        await interaction.response.send_message("仕入れる商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="🔄 パネル更新", style=discord.ButtonStyle.secondary, custom_id="vending_admin_refresh", row=1)
    async def refresh_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _active_panel["message_id"]:
            await interaction.response.send_message(
                "⚠️ まだ自販機パネルが設置されていません。\n一度管理パネルを送信し直してください。",
                ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(_active_panel["channel_id"])
        if not channel:
            await interaction.response.send_message("❌ チャンネルが見つかりません", ephemeral=True)
            return
        try:
            message = await channel.fetch_message(_active_panel["message_id"])
        except:
            await interaction.response.send_message(
                "❌ パネルが見つかりません。\n管理パネルを送信し直してください。",
                ephemeral=True
            )
            return
        embed = build_vending_embed()
        await message.edit(embed=embed, view=VendingMachineView())
        await interaction.response.send_message("✅ パネルを最新の内容に更新しました！", ephemeral=True)

# 仕入れ用選択View
class RestockSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        products = load_products()
        for pid, prod in products.items():
            stock = prod.get("stock")
            if stock is None:
                stock_text = "無限"
            else:
                stock_text = f"{stock}個"
            self.add_item(discord.ui.Button(
                label=f"{prod['name']}（現在: {stock_text}）",
                custom_id=f"restock_{pid}",
                style=discord.ButtonStyle.secondary
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
        if custom_id.startswith("restock_"):
            pid = custom_id.replace("restock_", "")
            products = load_products()
            if pid not in products:
                await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
                return
            await interaction.response.send_modal(RestockModal(pid))
            await interaction.message.delete()

class RestockModal(discord.ui.Modal, title="商品仕入れ"):
    amount = discord.ui.TextInput(label="追加する個数", required=True)

    def __init__(self, pid):
        super().__init__()
        self.pid = pid

    async def on_submit(self, interaction: discord.Interaction):
        if not self.amount.value.isdigit():
            await interaction.response.send_message("❌ 数字で入力してください", ephemeral=True)
            return
        add = int(self.amount.value)
        products = load_products()
        if self.pid not in products:
            await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
            return
        stock = products[self.pid].get("stock")
        if stock is None:
            await interaction.response.send_message("⚠️ この商品は在庫無限設定のため仕入れ不要です", ephemeral=True)
            return
        products[self.pid]["stock"] = stock + add
        save_products(products)
        await interaction.response.send_message(
            f"✅ 仕入れ完了！\n{products[self.pid]['name']} に {add}個 追加しました。\n👉 「🔄 パネル更新」を押すと表示に反映されます",
            ephemeral=True
        )

class AddProductModal(discord.ui.Modal, title="商品追加"):
    name = discord.ui.TextInput(label="商品名", required=True)
    price = discord.ui.TextInput(label="金額（円）", required=True)
    description = discord.ui.TextInput(label="説明（任意）", required=False, style=discord.TextStyle.long)
    stock = discord.ui.TextInput(label="在庫数（空欄=無限）", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.price.value.isdigit():
            await interaction.response.send_message("❌ 金額は数字で入力してください", ephemeral=True)
            return
        price = int(self.price.value)
        products = load_products()
        pid = f"prod_{len(products)+1:03d}"
        stock = None
        if self.stock.value and self.stock.value.isdigit():
            stock = int(self.stock.value)
        products[pid] = {
            "name": self.name.value,
            "price": price,
            "desc": self.description.value or "",
            "stock": stock
        }
        save_products(products)
        await interaction.response.send_message(
            f"✅ 追加完了！\nID: `{pid}`\n商品名: {self.name.value}\n金額: ￥{price}\n在庫: {stock if stock else '無限'}\n\n👉 「🔄 パネル更新」を押すと表示に反映されます",
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
                style=discord.ButtonStyle.secondary
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

# ===== ユーザー用パネル =====
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
            stock = prod.get("stock")
            disabled = stock is not None and stock <= 0
            if stock is None:
                stock_text = "無限"
            else:
                stock_text = f"{stock}個"
            self.add_item(discord.ui.Button(
                label=f"{prod['name']} ￥{prod['price']}" + (" [在庫切れ]" if disabled else ""),
                custom_id=f"vending_buy_{pid}",
                style=discord.ButtonStyle.secondary,
                disabled=disabled
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
            stock = prod.get("stock")
            if stock is not None and stock <= 0:
                await interaction.response.send_message("❌ 在庫がなくなりました", ephemeral=True)
                return False
            view = PurchaseConfirmView(pid, prod["name"], prod["price"])
            embed = discord.Embed(
                title="購入確認",
                description=f"**{prod['name']}**\n単価: {prod['price']}円\n\n購入する方法を選択してください。",
                color=PANEL_COLOR
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return False
        return True

class PurchaseConfirmView(discord.ui.View):
    def __init__(self, pid, name, price):
        super().__init__(timeout=180)
        self.pid = pid
        self.prod_name = name
        self.price = price

    @discord.ui.button(label="購入する", style=discord.ButtonStyle.secondary)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PaymentMethodView(self.pid, self.prod_name, self.price)
        embed = discord.Embed(
            title="お支払い方法選択",
            description=f"**{self.prod_name}**\n金額: {self.price}円\n\nお支払い方法を選択してください。",
            color=PANEL_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

class PaymentMethodView(discord.ui.View):
    def __init__(self, pid, name, price):
        super().__init__(timeout=180)
        self.pid = pid
        self.prod_name = name
        self.price = price

    @discord.ui.button(label="PayPayで支払う", style=discord.ButtonStyle.secondary)
    async def paypay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PayPayLinkModal(self.pid, self.prod_name, self.price)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

class PayPayLinkModal(discord.ui.Modal, title="PayPayリンク送信"):
    link = discord.ui.TextInput(
        label="PayPayリンクを貼り付け",
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

        # 在庫減少
        products = load_products()
        if self.pid in products:
            stock = products[self.pid].get("stock")
            if stock is not None:
                products[self.pid]["stock"] = stock - 1
                save_products(products)

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
                embed = discord.Embed(title="🛒 新規注文", color=PANEL_COLOR)
                embed.add_field(name="ユーザー", value=f"{interaction.user.mention}\n{interaction.user.id}", inline=False)
                embed.add_field(name="商品", value=f"{self.prod_name}\n￥{self.price}", inline=False)
                embed.add_field(name="チケットID", value=f"`{ticket_id}`", inline=False)
                embed.add_field(name="PayPayリンク", value=f"🔗 {self.link.value}", inline=False)
                embed.set_footer(text=datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"))
                await log_ch.send(embed=embed, view=OrderConfirmView(ticket_id))

# 永続対応
class OrderConfirmView(discord.ui.View):
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="✅ 確認・引き渡し完了",
        style=discord.ButtonStyle.secondary,
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
        embed = discord.Embed(title="✅ 引き渡し完了", color=PANEL_COLOR)
        await interaction.message.edit(embed=embed, view=None)

async def setup(tree: app_commands.CommandTree):
    @tree.command(name="自動販売機管理パネル", description="商品管理パネルを表示")
    async def admin_panel_cmd(interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        # 管理パネル送信と同時にユーザー用パネルも自動設置
        admin_embed = discord.Embed(
            title="⚙️ 自販機管理パネル",
            description="商品の追加・削除・仕入れ・更新ができます",
            color=PANEL_COLOR
        )
        await interaction.response.send_message(embed=admin_embed, view=VendingAdminPanelView())
        
        # ユーザー用パネルを同じチャンネルに自動設置
        products = load_products()
        if not products:
            await interaction.followup.send("⚠️ 商品が登録されていないため、まず商品を追加してください。", ephemeral=True)
            return
        user_embed = build_vending_embed()
        msg = await interaction.channel.send(embed=user_embed, view=VendingMachineView())
        _active_panel["channel_id"] = interaction.channel_id
        _active_panel["message_id"] = msg.id
        await interaction.followup.send("✅ ユーザー用パネルを設置しました！", ephemeral=True)
