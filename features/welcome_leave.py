import discord
from datetime import datetime
from core.common import JST, WELCOME_LEAVE_CHANNEL_ID

def get_human_member_count(guild: discord.Guild) -> int:
    """サーバー内のBot以外のユーザー数を返す"""
    return sum(1 for m in guild.members if not m.bot)

def make_member_embed(member: discord.Member, is_join: bool = True) -> discord.Embed:
    created_at = member.created_at.astimezone(JST)
    now = datetime.now(JST)
    account_age_days = (now - created_at).days
    created_str = created_at.strftime("%Y-%m-%d %H:%M:%S JST")
    
    # ✅ 現在のBot以外の総人数を取得
    total_humans = get_human_member_count(member.guild)
    # 参加時は+1、退出時はそのまま表示
    display_count = total_humans + 1 if is_join else total_humans
    
    account_type = "🤖 Bot" if member.bot else "👤 ユーザー"
    
    if account_age_days < 30:
        age_note = f"約{account_age_days}日前"
    elif account_age_days < 365:
        age_note = f"約{account_age_days // 30}ヶ月前"
    else:
        age_note = f"約{account_age_days // 365}年前"
    
    title = "📥 メンバーが参加しました！" if is_join else "📤 メンバーが退出しました"
    color = 0x2ecc71 if is_join else 0xe74c3c
    
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=now
    )
    embed.add_field(name="ユーザー名", value=f"{member.mention}\n`{member.name}`", inline=False)
    embed.add_field(name="ユーザーID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="アカウント作成日", value=f"{created_str}\n({age_note})", inline=False)
    embed.add_field(name="作成からの経過", value=f"**{account_age_days}日**", inline=False)
    embed.add_field(name="アカウント種類", value=account_type, inline=False)
    # ✅ 総ユーザー数に変更
    embed.add_field(
        name="👥 サーバー人数",
        value=f"**{display_count}人**",
        inline=False
    )
    embed.set_footer(text=f"サーバーID: {member.guild.id}")
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed

async def on_member_join(member: discord.Member) -> None:
    if member.bot:
        return
    ch = member.guild.get_channel(WELCOME_LEAVE_CHANNEL_ID)
    if ch:
        embed = make_member_embed(member, is_join=True)
        await ch.send(embed=embed)

async def on_member_remove(member: discord.Member) -> None:
    if member.bot:
        return
    ch = member.guild.get_channel(WELCOME_LEAVE_CHANNEL_ID)
    if ch:
        embed = make_member_embed(member, is_join=False)
        await ch.send(embed=embed)

async def setup(bot: discord.Client) -> None:
    bot.event(on_member_join)
    bot.event(on_member_remove)
    print("✅ welcome_leave イベント登録完了（サーバー総人数表示）")
