import discord
from discord import app_commands
from core.common import is_owner

# ✅ 権限・説明の対応表（コマンド追加時はここに追記するだけ）
COMMAND_DETAILS = {
    "くじ引きパネル設置": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "くじ引き（抽選）パネルを表示・実行"
    },
    "ポイント確認パネル設置": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "自分の保有ポイントを確認"
    },
    "ログインボーナスパネル設置": {
        "setup": "だれでも",
        "use": "だれでも（1日1回）",
        "desc": "毎日ログインボーナスを受け取る"
    },
    "スロットパネル設置": {
        "setup": "だれでも",
        "use": "だれでも（ポイント消費）",
        "desc": "スロットをプレイ、配当はすべて15倍"
    },
    "ブラックジャックパネル設置": {
        "setup": "だれでも",
        "use": "だれでも（ポイント消費）",
        "desc": "ブラックジャックをプレイ"
    },
    "ハイローパネル設置": {
        "setup": "だれでも",
        "use": "だれでも（ポイント消費）",
        "desc": "ハイアンドローをプレイ"
    },
    "ポイント付与パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "指定ユーザーにポイントを付与・減算"
    },
    "emb": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "埋め込みメッセージを送信（タイトル・説明文・色指定可）"
    },
    "メッセージ全削除": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "実行したチャンネルのメッセージを一括削除"
    },
    "管理パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "キック・BAN・ミュートなどメンバー管理パネル"
    },
    "治安パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "禁止ワード・リンク制限・チャンネルロック・緊急封鎖など"
    },
    "招待リンクパネル": {
        "setup": "鯖メン以上",
        "use": "鯖メン以上",
        "desc": "招待リンクを生成（鯖メンは24時間限定、オーナーは全期限選択可）"
    },
    "バックアップパネル": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "データのバックアップ・復元・Bot再起動"
    },
    "オセロ": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "オセロ対戦を開始"
    },
    "オセロパネル設置": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "オセロのルール・対戦パネルを表示"
    },
    "認証パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "ユーザー認証・自動ロール付与の設定"
    },
    "ロール付与パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "ロールを選択式で付与するパネルを作成"
    },
    "ロール剥奪パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "不要なロールを一括で剥奪"
    },
    "呼び出しパネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "メンバーを呼び出す通知パネル"
    },
    "通話パネル設置": {
        "setup": "オーナーのみ",
        "use": "オーナーのみ",
        "desc": "ボイスチャンネルの自動作成・管理パネル"
    },
    "ポイントランキングパネル設置": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "ポイント保有者のランキングを表示（自動更新）"
    },
    "コマンド確認パネル": {
        "setup": "だれでも",
        "use": "だれでも",
        "desc": "各コマンドの利用条件と機能を確認"
    }
}

class CommandListView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # ✅ 常時有効
        self.page = 0
        self.items_per_page = 4  # ✅ 1ページ4件でゆったり表示

    def make_embed(self, all_commands):
        # 登録されているコマンド一覧を取得
        cmds_with_info = []
        for cmd in all_commands:
            name = cmd.name
            info = COMMAND_DETAILS.get(name, {
                "setup": "要確認",
                "use": "要確認",
                "desc": cmd.description or "説明なし"
            })
            cmds_with_info.append({
                "name": f"/{name}",
                "setup": info["setup"],
                "use": info["use"],
                "desc": info["desc"]
            })

        # ページ計算
        total_pages = (len(cmds_with_info) + self.items_per_page - 1) // self.items_per_page
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        page_items = cmds_with_info[start:end]

        embed = discord.Embed(
            title=f"📋 コマンド一覧  ({self.page+1}/{total_pages}ページ)",
            description=f"全{len(cmds_with_info)}件のコマンドが登録されています",
            color=0x3498DB
        )

        # ✅ 1件ごとに区切り線を入れて見やすく
        for idx, info in enumerate(page_items):
            embed.add_field(
                name=f"🔹 {info['name']}",
                value=(
                    f"┌──────────────────────\n"
                    f"│ 🔧 設置できる人：{info['setup']}\n"
                    f"│ 👤 使える人　　：{info['use']}\n"
                    f"│ 📝 機能説明　　：{info['desc']}\n"
                    f"└──────────────────────"
                ),
                inline=False
            )

        embed.set_footer(text=f"ページ切替ボタンで移動できます｜最新の状態を自動取得")
        return embed

    @discord.ui.button(label="◀️ 前へ", style=discord.ButtonStyle.secondary, custom_id="cmdlist:prev")
    async def prev_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await itx.response.edit_message(embed=self.make_embed(itx.tree.get_commands()), view=self)
        else:
            await itx.response.defer()

    @discord.ui.button(label="次へ ▶️", style=discord.ButtonStyle.primary, custom_id="cmdlist:next")
    async def next_btn(self, itx: discord.Interaction, btn: discord.ui.Button):
        max_page = (len(itx.tree.get_commands()) + self.items_per_page - 1) // self.items_per_page - 1
        if self.page < max_page:
            self.page += 1
            await itx.response.edit_message(embed=self.make_embed(itx.tree.get_commands()), view=self)
        else:
            await itx.response.defer()

async def setup(tree: app_commands.CommandTree):
    bot = tree.client
    bot.add_view(CommandListView())  # ✅ 永続View登録

    @tree.command(
        name="コマンド確認パネル",
        description="各コマンドの利用条件と機能を確認（常時表示）"
    )
    async def cmd_list_panel(itx: discord.Interaction):
        view = CommandListView()
        await itx.response.send_message(
            embed=view.make_embed(tree.get_commands()),
            view=view,
            ephemeral=False  # ✅ サーバーに公開・常時残る
        )
        await itx.followup.send(
            "✅ コマンド一覧パネルを設置しました\n"
            "コマンド追加時は自動で更新されます",
            ephemeral=True
        )
