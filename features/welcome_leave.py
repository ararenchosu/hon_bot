import discord
from datetime import datetime
from core.common import JST, WELCOME_LEAVE_CHANNEL_ID
from core.database import get_connection

def get_next_member_number():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM stats WHERE key='member_total'")
    r = cur.fetchone()
    num = r[0] + 1 if r else 1
    cur.execute("REPLACE INTO stats VALUES ('member_total', ?)", (num,))
    conn.commit()
    conn.close()
    return num

def make_member_embed(member, is_join=True):
    created_at = member.created_at.astimezone(JST)
    now = datetime.now(JST)
    account_age_days = (now - created_at).days
    created_str = created_at.strftime("%A, %B %d, %Y at %H:%M")
    number = get_next_member_number() if is_join else "―"
    account_type = "Bot" if member.bot else "ユーザー"

    if account_age_days < 30:
        age_note = f"{account_age_days}日前"
    elif account_age_days < 365:
        age_note = f"{account_age_days // 30}ヶ月前"
    else:
        age_note = f"{account_age_days // 365}年前"

    title = "📥 メンバーが参加しました！" if is_join else "📤 メンバーが退出しました"
    color = 0x2ecc71 if is_join else 0xe74c3c

    embed = discord.Embed(title=title, color=color, timestamp=now)
    embed.add_field(name="ユーザー名", value=f"{member.mention}\n`{member.name}`", inline=False)
    embed.add_field(name="ユーザーID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="アカウント作成日", value=f"{created_str}\n({age_note})", inline=False)
    embed.add_field(name="アカウント作成経過", value=f"{account_age_days}日", inline=False)
    embed.add_field(name="アカウント種類", value=account_type, inline=False)
    embed.add_field(name="メンバー数", value=f"{number}人目", inline=False)
    embed.set_footer(text=f"Guild ID: {member.guild.id}")
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed

async def on_member_join(member):
    if member.bot:
        return
    ch = member.guild.get_channel(WELCOME_LEAVE_CHANNEL_ID)
    if ch:
        embed = make_member_embed(member, is_join=True)
        await ch.send(embed=embed)

async def on_member_remove(member):
    if member.bot:
        return
    ch = member.guild.get_channel(WELCOME_LEAVE_CHANNEL_ID)
    if ch:
        embed = make_member_embed(member, is_join=False)
        await ch.send(embed=embed)

async def setup(tree):
    pass  # コマンドなし、イベントのみ登録
