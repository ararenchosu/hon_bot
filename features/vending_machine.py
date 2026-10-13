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
PANEL_COLOR = 0x1C8A5B

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

def build_vending_embed():
    products = load_products()
    desc = "好きなデコレーションが格安で買えます！購入後チケットでお渡しします。\n"
    desc += "────────────────────────────\n"
    for pid, prod in products.items():
        stock = prod.get("stock")
        if stock is None:
            stock_text = "無限"
        else:
            stock_text = f"{stock}個（手動仕入れ）"
        desc += f"**{prod['name']}**\n"
        if prod.get("desc"):
            desc += f"{prod['desc']}\n"
        desc += f"価格:{prod['price']}円 | 在庫:{stock_text}"
        if prod.get("option"):
            desc += f" | オプション:{prod['option']}"
        if prod.get("max_order"):
            desc += f" | 最大注文数:{prod['max_order']}"
        desc += "\n────────────────────────────\n"
    embed = discord.Embed(title="🛒 商品一覧", description=desc, color=PANEL_COLOR)
    embed.set_footer(text="Created by vending system • Components V2")
    return embed

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

    @discord.ui.button(label="✏️ パネル編集", style=discord.ButtonStyle.secondary, custom_id="vending_admin_edit", row=0)
    async def edit_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = ProductEditSelectView()
        await interaction.response.send_message("編集する商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="➖ 商品削除", style=discord.ButtonStyle.secondary, custom_id="vending_admin_remove", row=1)
    async def remove_product_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = ProductRemoveSelectView()
        await interaction.response.send_message("削除する商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="📥 仕入れ", style=discord.ButtonStyle.secondary, custom_id="vending_admin_restock", row=1)
    async def restock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        view = RestockSelectView()
        await interaction.response.send_message("仕入れる商品を選んでください👇", view=view, ephemeral=True)

    @discord.ui.button(label="🔄 パネル更新", style=discord.ButtonStyle.secondary, custom_id="vending_admin_refresh", row=2)
    async def refresh_panel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _active_panel["message_id"]:
            await interaction.response.send_message("⚠️ 先に `/自動販売機設置` を実行してください", ephemeral=True)
            return
        channel = interaction.guild.get_channel(_active_panel["channel_id"])
        if not channel:
            await interaction.response.send_message("❌ チャンネルが見つかりません", ephemeral=True)
            return
        try:
            message = await channel.fetch_message(_active_panel["message_id"])
            await message.edit(embed=build_vending_embed(), view=VendingMachineView())
            await interaction.response.send_message("✅ パネルを更新しました！", ephemeral=True)
        except:
            await interaction.response.send_message("❌ パネルが見つかりません。再設置してください", ephemeral=True)

# ===== 選択ベース共通親View（タイムアウト対策）=====
class ProductSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.products = load_products()
        self._build_buttons()

    def _build_buttons(self):
        for pid, prod in self.products.items():
            stock = prod.get("stock")
            stock_text = "無限" if stock is None else f"{stock}個"
            self.add_item(discord.ui.Button(
                label=f"{prod['name']} | 在庫:{stock_text}",
                custom_id=f"{self.prefix}_{pid}",
                style=discord.ButtonStyle.secondary
            ))
        self.add_item(discord.ui.Button(
            label="キャンセル",
            custom_id=f"{self.prefix}_cancel",
            style=discord.ButtonStyle.secondary,
            row=4
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 管理者専用です", ephemeral=True)
            return False
        return True

    async def callback_handler(self, interaction: discord.Interaction, action_cls):
        cid = interaction.data.get("custom_id", "")
        if cid.endswith("_cancel"):
            await interaction.response.defer()
            await interaction.message.delete()
            return
        pid = cid.replace(f"{self.prefix}_", "")
        if pid not in self.products:
            await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
            return
        await interaction.response.send_modal(action_cls(pid))
        try:
            await interaction.message.delete()
        except:
            pass

# ===== 仕入れ =====
class RestockSelectView(ProductSelectView):
    prefix = "restock"
    def __init__(self):
        super().__init__()
    @discord.ui.button(label="仮", custom_id="dummy", style=discord.ButtonStyle.secondary)
    async def dummy(self, interaction, button):
        pass
    async def on_callback(self, interaction):
        await self.callback_handler(interaction, RestockModal)

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
            await interaction.response.send_message("⚠️ 在庫無限設定のため仕入れ不要です", ephemeral=True)
            return
        products[self.pid]["stock"] = stock + add
        save_products(products)
        await interaction.response.send_message(
            f"✅ 仕入れ完了！\n{products[self.pid]['name']} に {add}個 追加\n👉 「🔄 パネル更新」で反映",
            ephemeral=True
        )

# ===== 削除 =====
class ProductRemoveSelectView(ProductSelectView):
    prefix = "remove"
    def __init__(self):
        super().__init__()
    @discord.ui.button(label="仮", custom_id="dummy", style=discord.ButtonStyle.secondary)
    async def dummy(self, interaction, button):
        pass
    async def on_callback(self, interaction):
        cid = interaction.data.get("custom_id", "")
        if cid.endswith("_cancel"):
            await interaction.response.defer()
            await interaction.message.delete()
            return
        pid = cid.replace(f"{self.prefix}_", "")
        products = load_products()
        if pid not in products:
            await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
            return
        del products[pid]
        save_products(products)
        await interaction.response.send_message(f"✅ 削除完了！\n👉 「🔄 パネル更新」で反映", ephemeral=True)
        try:
            await interaction.message.delete()
        except:
            pass

# ===== 編集 =====
class ProductEditSelectView(ProductSelectView):
    prefix = "edit"
    def __init__(self):
        super().__init__()
    @discord.ui.button(label="仮", custom_id="dummy", style=discord.ButtonStyle.secondary)
    async def dummy(self, interaction, button):
        pass
    async def on_callback(self, interaction):
        await self.callback_handler(interaction, EditProductModal)

class EditProductModal(discord.ui.Modal, title="商品編集"):
    name = discord.ui.TextInput(label="商品名", required=True)
    price = discord.ui.TextInput(label="金額（円）", required=True)
    description = discord.ui.TextInput(label="説明（任意）", required=False, style=discord.TextStyle.long)
    stock = discord.ui.TextInput(label="在庫数（空欄=無限）", required=False)
    option = discord.ui.TextInput(label="オプション（任意）", required=False)
    max_order = discord.ui.TextInput(label="最大注文数（任意）", required=False)

    def __init__(self, pid):
        super().__init__()
        self.pid = pid
        prod = load_products()[pid]
        self.name.default = prod["name"]
        self.price.default = str(prod["price"])
        self.description.default = prod.get("desc", "")
        self.stock.default = "" if prod.get("stock") is None else str(prod["stock"])
        self.option.default = prod.get("option", "")
        self.max_order.default = str(prod.get("max_order", "")) if prod.get("max_order") else ""

    async def on_submit(self, interaction: discord.Interaction):
        if not self.price.value.isdigit():
            await interaction.response.send_message("❌ 金額は数字で", ephemeral=True)
            return
        price = int(self.price.value)
        products = load_products()
        stock = None if not self.stock.value.strip() else int(self.stock.value)
        products[self.pid].update({
            "name": self.name.value,
            "price": price,
            "desc": self.description.value,
            "stock": stock,
            "option": self.option.value or None,
            "max_order": int(self.max_order.value) if self.max_order.value.isdigit() else None
        })
        save_products(products)
        await interaction.response.send_message(f"✅ 編集完了！\n👉 「🔄 パネル更新」で反映", ephemeral=True)

# ===== 商品追加 =====
class AddProductModal(discord.ui.Modal, title="商品追加"):
    name = discord.ui.TextInput(label="商品名", required=True)
    price = discord.ui.TextInput(label="金額（円）", required=True)
    description = discord.ui.TextInput(label="説明（任意）", required=False, style=discord.TextStyle.long)
    stock = discord.ui.TextInput(label="在庫数（空欄=無限）", required=False)
    option = discord.ui.TextInput(label="オプション（任意）", required=False)
    max_order = discord.ui.TextInput(label="最大注文数（任意）", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.price.value.isdigit():
            await interaction.response.send_message("❌ 金額は数字で", ephemeral=True)
            return
        price = int(self.price.value)
        products = load_products()
        pid = f"prod_{len(products)+1:03d}"
        stock = None if not self.stock.value.strip() else int(self.stock.value)
        products[pid] = {
            "name": self.name.value,
            "price": price,
            "desc": self.description.value or "",
            "stock": stock,
            "option": self.option.value or None,
            "max_order": int(self.max_order.value) if self.max_order.value.isdigit() else None
        }
        save_products(products)
        await interaction.response.send_message(
            f"✅ 追加完了！\n商品名: {self.name.value}\n金額: ￥{price}\n👉 「🔄 パネル更新」で反映",
            ephemeral=True
        )

# ===== ユーザー用：商品選択ボタン =====
class VendingMachineView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="商品を選択", style=discord.ButtonStyle.secondary, custom_id="vending_select", row=0)
    async def select_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 商品が登録されていません", ephemeral=True)
            return
        await interaction.response.send_message("購入する商品を選んでください👇", view=ProductBuySelectView(), ephemeral=True)

class ProductBuySelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        products = load_products()
        for pid, prod in products.items():
            stock = prod.get("stock")
            disabled = stock is not None and stock <= 0
            stock_text = "無限" if stock is None else f"{stock}個"
            label = f"{prod['name']} | {prod['price']}円 | 在庫:{stock_text}"
            if prod.get("max_order"):
                label += f" | 最大{prod['max_order']}個"
            self.add_item(discord.ui.Button(
                label=label,
                custom_id=f"buy_{pid}",
                style=discord.ButtonStyle.secondary,
                disabled=disabled
            ))
        self.add_item(discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.secondary, row=4, custom_id="buy_cancel"))

    async def interaction_check(self, interaction: discord.Interaction):
        cid = interaction.data.get("custom_id", "")
        if cid == "buy_cancel":
            await interaction.response.defer()
            await interaction.message.delete()
            return False
        if cid.startswith("buy_"):
            pid = cid.replace("buy_", "")
            products = load_products()
            if pid not in products:
                await interaction.response.send_message("❌ 存在しない商品です", ephemeral=True)
                return False
            prod = products[pid]
            stock = prod.get("stock")
            if stock is not None and stock <= 0:
                await interaction.response.send_message("❌ 在庫がありません", ephemeral=True)
                return False
            embed = discord.Embed(
                title="購入確認",
                description=f"**{prod['name']}**\n価格: {prod['price']}円\n{prod.get('desc', '')}",
                color=PANEL_COLOR
            )
            await interaction.response.edit_message(embed=embed, view=PurchaseConfirmView(pid, prod["name"], prod["price"]))
            return False
        return True

# ===== 購入確認 =====
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
            description=f"**{self.prod_name}**\n金額: {self.price}円",
            color=PANEL_COLOR
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except:
            pass

# ===== 支払い =====
class PaymentMethodView(discord.ui.View):
    def __init__(self, pid, name, price):
        super().__init__(timeout=180)
        self.pid = pid
        self.prod_name = name
        self.price = price

    @discord.ui.button(label="PayPayで支払う", style=discord.ButtonStyle.secondary)
    async def paypay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PayPayLinkModal(self.pid, self.prod_name, self.price))

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

class PayPayLinkModal(discord.ui.Modal, title="PayPayリンク送信"):
    link = discord.ui.TextInput(label="PayPayリンクを貼り付け", required=True, style=discord.TextStyle.short)
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
        products = load_products()
        if self.pid in products:
            stock = products[self.pid].get("stock")
            if stock is not None:
                products[self.pid]["stock"] = stock - 1
                save_products(products)
        await interaction.response.send_message(
            f"✅ 受付完了！\n🎫 チケットID：`{ticket_id}`\n📦 商品：{self.prod_name}\n💴 金額：￥{self.price}",
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

# ===== 引き渡し確認 =====
class OrderConfirmView(discord.ui.View):
    def __init__(self, ticket_id=None):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
    @discord.ui.button(label="✅ 確認・引き渡し完了", style=discord.ButtonStyle.secondary, custom_id="vending_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = self.ticket_id
        if not ticket_id:
            try:
                if interaction.message and interaction.message.embeds:
                    for f in interaction.message.embeds[0].fields:
                        if "チケットID" in f.name:
                            ticket_id = f.value.replace("`", "").strip()
            except: pass
        if not ticket_id:
            await interaction.response.send_message("❌ ID取得不可", ephemeral=True)
            return
        orders = load_orders()
        if ticket_id not in orders:
            await interaction.response.send_message("❌ 存在しない注文", ephemeral=True)
            return
        orders[ticket_id]["status"] = "completed"
        save_orders(orders)
        await interaction.response.send_message(f"✅ `{ticket_id}` 完了", ephemeral=True)
        await interaction.message.edit(embed=discord.Embed(title="✅ 引き渡し完了", color=PANEL_COLOR), view=None)

# ===== コマンド登録 =====
async def setup(tree: app_commands.CommandTree):
    @tree.command(name="自動販売機管理", description="管理パネル表示")
    async def admin_cmd(interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        embed = discord.Embed(
            title="⚙️ 自販機管理パネル",
            description="商品追加・編集・削除・仕入れ・更新ができます\n先に `/自動販売機設置` を実行してください",
            color=PANEL_COLOR
        )
        await interaction.response.send_message(embed=embed, view=VendingAdminPanelView(), ephemeral=True)

    @tree.command(name="自動販売機設置", description="ユーザー用パネルを設置")
    async def place_cmd(interaction: discord.Interaction):
        if not is_owner(interaction):
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        products = load_products()
        if not products:
            await interaction.response.send_message("⚠️ 先に `/自動販売機管理` から商品を追加してください", ephemeral=True)
            return
        if _active_panel["message_id"] and _active_panel["channel_id"] == interaction.channel_id:
            try:
                ch = interaction.guild.get_channel(_active_panel["channel_id"])
                if ch:
                    await ch.fetch_message(_active_panel["message_id"]).delete()
            except: pass
        msg = await interaction.channel.send(embed=build_vending_embed(), view=VendingMachineView())
        _active_panel.update({"channel_id": interaction.channel_id, "message_id": msg.id})
        await interaction.response.send_message("✅ 設置完了！", ephemeral=True)
