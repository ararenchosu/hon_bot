import discord
from discord import app_commands
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
import google.generativeai as genai

# ========== 🔧 設定（ID埋め込み済み）==========
TALK_CATEGORY_ID = 1560587255792275477    # チャンネル作成先カテゴリ
PANEL_CHANNEL_ID = 1560587467004842095    # パネル設置チャンネル
LOG_CHANNEL_ID = 1560587873739219044     # ログ送信先チャンネル
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")  # 環境変数から取得

# Gemini 基本設定
SYSTEM_PROMPT = """あなたはユーザー専用のおしゃべり相手です。
親しみやすく、絵文字を適度に使い、短すぎず長すぎない自然な会話をしてください。
ユーザーの話に共感したり、質問したりして会話を続けてください。
名前はまだ決まっていないので、ユーザーからつけてもらえると嬉しいです。"""

FIGHT_PROMPT_ADD = "\n【けんかモード】強気で少しツンツン・反発するような口調で話してください。言い返したりしてもOKです。"

JST = timezone(timedelta(hours=9))

# ========== データ管理 ==========
user_sessions = {}     # {user_id: {mode, started_at, chat, channel_id}}
active_channels = {}   # {user_id: channel_id}

# Gemini初期化
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 🔍 利用可能なモデルを表示
    print("=" * 50)
    print("🔍 利用可能なモデル一覧:")
    try:
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                print(f"   ✅ {m.name}")
    except Exception as e:
        print(f"   ❌ モデル一覧取得エラー: {e}")
    print("=" * 50)
    
    # ✅ 一覧の一番上のモデルを使用
    model = genai.GenerativeModel(
        model_name="models/gemini-2.5-flash",  # ← これに変更！
        generation_config={"temperature": 0.9, "top_p": 0.95, "max_output_tokens": 800}
    )
    print(f"🤖 使用するモデル: models/gemini-2.5-flash ✅")

def get_user_session(user_id):
    """ユーザーセッション取得または新規作成"""
    now = datetime.now(JST)
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "mode": "talk",
            "started_at": now,
            "chat": model.start_chat(history=[]) if GOOGLE_API_KEY else None,
            "channel_id": None
        }
    # 30分経過で会話履歴リセット
    if (now - user_sessions[user_id]["started_at"]).total_seconds() > 1800:
        user_sessions[user_id]["chat"] = model.start_chat(history=[]) if GOOGLE_API_KEY else None
        user_sessions[user_id]["started_at"] = now
    return user_sessions[user_id]

async def get_ai_reply(user_id, text):
    """Geminiから返答を取得"""
    if not GOOGLE_API_KEY:
        return "⚠️ APIキーが設定されていません。環境変数 GOOGLE_API_KEY を確認してください。"
    sess = get_user_session(user_id)
    prompt = SYSTEM_PROMPT
    if sess["mode"] == "fight":
        prompt += FIGHT_PROMPT_ADD
    prompt += f"\nユーザー：{text}"
    try:
        resp = sess["chat"].send_message(prompt)
        return resp.text.strip()[:1500]
    except Exception as e:
        print(f"Geminiエラー: {e}")
        return f"ごめんね、ちょっと考え中✨ もう一度言ってみて！\n(詳細: {str(e)[:100]})"

# ========== View定義 ==========
class MainPanelView(discord.ui.View):
    """モード選択パネル（永久表示）"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💬 おしゃべりモード", style=discord.ButtonStyle.primary, custom_id="ai_talk:mode_talk")
    async def talk_btn(self, itx: discord.Interaction, btn):
        await start_chat_session(itx, "talk")

    @discord.ui.button(label="😤 けんかモード", style=discord.ButtonStyle.danger, custom_id="ai_talk:mode_fight")
    async def fight_btn(self, itx: discord.Interaction, btn):
        await start_chat_session(itx, "fight")

class EndConfirmView(discord.ui.View):
    """終了確認画面"""
    def __init__(self):
        super().__init__(timeout=120)
        self.confirmed = None

    @discord.ui.button(label="✅ はい、終了する", style=discord.ButtonStyle.success)
    async def yes_btn(self, itx: discord.Interaction, btn):
        self.confirmed = True
        self.stop()
        await itx.response.defer()

    @discord.ui.button(label="❌ やめる", style=discord.ButtonStyle.secondary)
    async def no_btn(self, itx: discord.Interaction, btn):
        self.confirmed = False
        self.stop()
        await itx.response.edit_message(content="✅ 会話を続けます！", view=None)

class ChatControlView(discord.ui.View):
    """会話チャンネル下部の制御ボタン"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 会話を終了してチャンネル削除", style=discord.ButtonStyle.secondary, custom_id="ai_talk:end_chat")
    async def end_btn(self, itx: discord.Interaction, btn):
        if itx.user.id not in active_channels:
            await itx.response.send_message("❌ あなたのチャンネルではありません", ephemeral=True)
            return
        confirm_view = EndConfirmView()
        await itx.response.send_message(
            "⚠️ 本当に会話を終了しますか？\n会話ログを保存してからチャンネルを削除します。",
            view=confirm_view,
            ephemeral=True
        )
        await confirm_view.wait()
        if confirm_view.confirmed is None or not confirm_view.confirmed:
            return

        # ログ収集
        channel = itx.channel
        messages = []
        async for msg in channel.history(limit=None, oldest_first=True):
            if not msg.is_system():
                messages.append(msg)

        sess = get_user_session(itx.user.id)
        ended_at = datetime.now(JST)
        mode_name = "💬 おしゃべりモード" if sess["mode"] == "talk" else "😤 けんかモード"

        # ファイル名作成
        safe_name = re.sub(r"[^\w-]", "_", itx.user.name)
        filename = f"ai_log_{safe_name}_{ended_at.strftime('%Y%m%d_%H%M%S')}.txt"

        # ログ内容作成
        log_lines = [
            "=" * 50,
            "                    AI会話ログ",
            "=" * 50,
            f"👤 ユーザー名：{itx.user}",
            f"🆔 ユーザーID：{itx.user.id}",
            f"💬 モード：{mode_name}",
            f"📂 チャンネル：{channel.name}",
            f"⏰ 開始日時：{sess['started_at'].strftime('%Y-%m-%d %H:%M:%S')}",
            f"⏰ 終了日時：{ended_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"📊 総メッセージ数：{len(messages)}",
            "=" * 50,
            "\n【会話内容】"
        ]
        for msg in messages:
            role = "🤖 AI" if msg.author.bot else "👤 ユーザー"
            log_lines.append(
                f"{msg.created_at.astimezone(JST).strftime('%H:%M:%S')}  {role:8} ：{msg.content}"
            )
        log_lines.extend(["", "=" * 50, "以上です"])

        # 一時ファイル作成
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write("\n".join(log_lines))
            temp_path = f.name

        # ログ送信
        log_ch = itx.guild.get_channel(LOG_CHANNEL_ID)
        if log_ch:
            embed = discord.Embed(title="📝 AI会話ログが保存されました", color=0x3498DB)
            embed.add_field(name="👤 ユーザー", value=f"{itx.user}", inline=True)
            embed.add_field(name="💬 モード", value=mode_name, inline=True)
            embed.add_field(name="📊 メッセージ数", value=f"{len(messages)}件", inline=True)
            embed.add_field(name="⏰ 開始", value=sess["started_at"].strftime("%H:%M:%S"), inline=True)
            embed.add_field(name="⏰ 終了", value=ended_at.strftime("%H:%M:%S"), inline=True)
            try:
                await log_ch.send(embed=embed, file=discord.File(temp_path, filename=filename))
            except Exception as e:
                print(f"ログ送信エラー: {e}")
        os.remove(temp_path)

        # チャンネル削除
        del user_sessions[itx.user.id]
        del active_channels[itx.user.id]
        await channel.delete()

# ========== チャンネル作成処理 ==========
async def start_chat_session(itx, mode):
    """モード選択 → チャンネル作成または既存チャンネルへ案内"""
    guild = itx.guild
    category = guild.get_channel(TALK_CATEGORY_ID) if TALK_CATEGORY_ID else None

    # 既存チャンネルがある場合
    if itx.user.id in active_channels:
        ch = guild.get_channel(active_channels[itx.user.id])
        if ch:
            user_sessions[itx.user.id]["mode"] = mode
            await itx.response.send_message(
                f"✅ モードを切り替えました！ → {ch.mention}", ephemeral=True
            )
            return

    # 権限設定
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        itx.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    # オーナー閲覧権限
    for oid in [1256574550901133377, 1546348374922625065]:
        m = guild.get_member(oid)
        if m:
            overwrites[m] = discord.PermissionOverwrite(view_channel=True)

    mode_label = "おしゃべり" if mode == "talk" else "けんか"
    ch_name = f"{mode_label}-{itx.user.name}"

    try:
        channel = await guild.create_text_channel(
            name=ch_name, category=category, overwrites=overwrites
        )
    except Exception as e:
        await itx.response.send_message(f"❌ チャンネル作成エラー：{e}", ephemeral=True)
        return

    # セッション記録
    user_sessions[itx.user.id] = {
        "mode": mode,
        "started_at": datetime.now(JST),
        "chat": model.start_chat(history=[]) if GOOGLE_API_KEY else None,
        "channel_id": channel.id
    }
    active_channels[itx.user.id] = channel.id

    # 案内メッセージ
    mode_text = "優しくおしゃべりするモード" if mode == "talk" else "強気で言い返すモード"
    embed_color = 0x2ECC71 if mode == "talk" else 0xE74C3C
    embed = discord.Embed(
        title=f"✅ {mode_label}モード 開始！",
        description=f"ここで自由におしゃべりできます✨\n{mode_text}で応答します。",
        color=embed_color
    )
    await channel.send(embed=embed, view=ChatControlView())
    await itx.response.send_message(
        f"✅ チャンネル作成完了！ → {channel.mention}", ephemeral=True
    )

# ========== メッセージ処理 ==========
async def process_message(message: discord.Message):
    """ユーザーからのメッセージをAIに渡して返信"""
    if message.author.bot:
        return
    if message.author.id not in active_channels:
        return
    if message.channel.id != active_channels[message.author.id]:
        return
    reply = await get_ai_reply(message.author.id, message.content)
    async with message.channel.typing():
        await message.channel.send(reply)

# ========== セットアップ ==========
async def setup(tree: app_commands.CommandTree, bot=None):
    if bot is not None:
        bot.add_view(MainPanelView())
        bot.add_view(ChatControlView())
        print("  ✅ ai_talk 永続View登録完了")

    @tree.command(name="aiパネル設置", description="AIおしゃべりパネルを設置")
    async def cmd_ai_panel(itx: discord.Interaction):
        if itx.channel_id != PANEL_CHANNEL_ID:
            await itx.response.send_message(
                "❌ 指定されたチャンネル以外では設置できません", ephemeral=True
            )
            return
        embed = discord.Embed(
            title="🤖 AIおしゃべりパネル",
            description=(
                "下のボタンからモードを選んでください✨\n"
                "💬 **おしゃべりモード** → 優しく自然に会話\n"
                "😤 **けんかモード** → 強気でツンツンします\n"
                "専用チャンネルが作成され、1対1で話せます！"
            ),
            color=0x3498DB
        )
        await itx.response.send_message(embed=embed, view=MainPanelView())
