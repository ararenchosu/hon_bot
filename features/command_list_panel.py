import discord
from discord import app_commands

# ✅ 「設置できる人」を追加！
COMMAND_INFO = [
    {
        "name": "/くじ引きパネル設置",
        "who": "だれでも",
        "setup_by": "だれでも",
        "desc": "くじ引き（抽選）パネルを表示・実行"
    },
    {
        "name": "/ポイント確認パネル設置",
        "who": "だれでも",
        "setup_by": "だれでも",
        "desc": "自分の保有ポイントを確認"
    },
    {
        "name": "/ログインボーナスパネル設置",
        "who": "だれでも（1日1回）",
        "setup_by": "だれでも",
        "desc": "毎日ログインボーナスを受け取る"
    },
    {
        "name": "/スロットパネル設置",
        "who": "だれでも（ポイント消費）",
        "setup_by": "だれでも",
        "desc": "スロットをプレイ、配当はすべて15倍"
    },
    {
        "name": "/ブラックジャックパネル設置",
        "who": "だれでも（ポイント消費）",
        "setup_by": "だれでも",
        "desc": "ブラックジャックをプレイ"
    },
    {
        "name": "/ハイローパネル設置",
        "who": "だれでも（ポイント消費）",
        "setup_by": "だれでも",
        "desc": "ハイアンドローをプレイ"
    },
    {
        "name": "/ポイント付与パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "指定ユーザーにポイントを付与・減算"
    },
    {
        "name": "/emb",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "埋め込みメッセージを送信（タイトル・説明文・色指定可）"
    },
    {
        "name": "/メッセージ全削除",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "実行したチャンネルのメッセージを一括削除"
    },
    {
        "name": "/管理パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "キック・BAN・ミュートなどメンバー管理パネル"
    },
    {
        "name": "/治安パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "禁止ワード・リンク制限・チャンネルロック・緊急封鎖など"
    },
    {
        "name": "/招待リンクパネル",
        "who": "鯖メン以上",
        "setup_by": "鯖メン以上",
        "desc": "招待リンクを生成（鯖メンは24時間限定、オーナーは全期限選択可）"
    },
    {
        "name": "/バックアップパネル",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "データのバックアップ・復元・Bot再起動"
    },
    {
        "name": "/オセロ",
        "who": "だれでも",
        "setup_by": "だれでも",
        "desc": "オセロ対戦を開始"
    },
    {
        "name": "/オセロパネル設置",
        "who": "だれでも",
        "setup_by": "だれでも",
        "desc": "オセロのルール・対戦パネルを表示"
    },
    {
        "name": "/認証パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "ユーザー認証・自動ロール付与の設定"
    },
    {
        "name": "/ロール付与パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "ロールを選択式で付与するパネルを作成"
    },
    {
        "name": "/ロール剥奪パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "不要なロールを一括で剥奪"
    },
    {
        "name": "/呼び出しパネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "メンバーを呼び出す通知パネル"
    },
    {
        "name": "/通話パネル設置",
        "who": "オーナーのみ",
        "setup_by": "オーナーのみ",
        "desc": "ボイスチャンネルの自動作成・管理パネル"
    },
    {
        "name": "/ポイントランキングパネル設置",
        "who": "だれでも",
        "setup_by": "だれでも",
        "desc": "ポイント保有者のランキングを表示（自動更新）"
    }
]

class CommandListView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.page = 0
        self.items_per_page = 5

    def make_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_items = COMMAND_INFO[start:end]
        total_pages = (len(COMMAND_INFO) + self.items_per_page - 1) // self.items_per_page

        embed = discord.Embed(
            title=f"📋 コマンド一覧  ({self.page+1}/{total_pages}ページ)",
            color=0x3498DB
        )
        for info in page_items:
            embed.add_field(
                name=f"🔹 {info['name']}",
                value=(
                    f"🔧 設置できる人：{info['setup_by']}\n"
                    f"👤 使える人：{info['who']}\n"
                    f"📝 機能：{info['desc']}"
                ),
                inline=False
            )
        embed.set_footer(text=f"全{len(COMMAND_INFO)}件 ｜ ボタンでページ切替できます")
        return embed

    @discord.ui.button(label="◀️ 前へ", style=discord.ButtonStyle.secondary, custom_id="cmdlist:prev")
    async def prev_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await itx.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await itx.response.defer()

    @discord.ui.button(label="次へ ▶️", style=discord.ButtonStyle.primary, custom_id="cmdlist:next")
    async def next_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        max_page = (len(COMMAND_INFO) + self.items_per_page - 1) // self.items_per_page - 1
        if self.page < max_page:
            self.page += 1
            await itx.response.edit_message(embed=self.make_embed(), view=self)
        else:
            await itx.response.defer()

async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    bot.add_view(CommandListView())

    @tree.command(
        name="コマンド確認パネル",
        description="各コマンドの利用条件と機能を確認"
    )
    async def cmd_list_panel(itx: discord.Interaction):
        view = CommandListView()
        await itx.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)
