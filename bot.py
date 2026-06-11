
# company_performance_bot.py
# 설치:
# pip install discord.py pillow qrcode[pil] requests

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import time

import io
import qrcode
import requests

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("xp.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id TEXT PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    join_date INTEGER DEFAULT 0
)
""")
conn.commit()

def ensure_user(uid):
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users(user_id,xp,join_date) VALUES(?,?,?)",
            (uid, 0, int(time.time()))
        )
        conn.commit()

def get_xp(uid):
    ensure_user(uid)
    cur.execute("SELECT xp FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()[0]

def add_xp(uid, amount):
    ensure_user(uid)
    cur.execute("UPDATE users SET xp=xp+? WHERE user_id=?", (amount, uid))
    conn.commit()

def set_xp(uid, amount):
    ensure_user(uid)
    cur.execute("UPDATE users SET xp=? WHERE user_id=?", (amount, uid))
    conn.commit()

def get_level(xp):
    return int((xp / 120) ** 0.55) if xp > 0 else 0

def get_rank(level):
    if level >= 80: return "부장"
    if level >= 60: return "차장"
    if level >= 40: return "과장"
    if level >= 20: return "팀장"
    if level >= 10: return "대리"
    if level >= 3: return "사원"
    return "인턴"
async def update_role(member, level):

    role_names = [
        "인턴",
        "사원",
        "대리",
        "팀장",
        "과장",
        "차장",
        "부장"
    ]

    target_rank = get_rank(level)

    for role_name in role_names:

        role = discord.utils.get(
            member.guild.roles,
            name=role_name
        )

        if role and role in member.roles:
            await member.remove_roles(role)

    new_role = discord.utils.get(
        member.guild.roles,
        name=target_rank
    )

    if new_role:
        await member.add_roles(new_role)

    return target_rank


async def promotion_notice(
    channel,
    member,
    rank_name,
    level
):

    embed = discord.Embed(
        title="📢 인사발령",
        description=(
            f"{member.mention}님의 우수한 성과가 인정되어\n\n"
            f"『 {rank_name} 』 직급으로 승진하였습니다."
        ),
        color=0x2ecc71
    )

    embed.add_field(
        name="성과등급",
        value=f"Lv.{level}"
    )

    embed.set_footer(
        text="뚱콩 컴퍼니 인사팀"
    )

    await channel.send(embed=embed)

def create_employee_card(user, xp, level, rank_name, join_date):
    print("사원증 생성 시작")
    card = Image.new("RGB", (900, 550), (245, 245, 245))
    draw = ImageDraw.Draw(card)

    try:
        font_big = ImageFont.truetype(
        "NotoSansKR-Regular.ttf",
        40
    )

        font_mid = ImageFont.truetype(
        "NotoSansKR-Regular.ttf",
        24
    )

        print("NotoSansKR 로딩 성공")


    draw.rectangle((0, 0, 900, 80), fill=(30, 30, 30))

    draw.text(
        (20, 15),
        "뚱콩컴퍼니",
        fill="white",
        font=font_big
    )
    draw.text(
        (25, 55),
        "EMPLOYEE IDENTIFICATION CARD",
        fill=(220, 220, 220),
        font=font_mid
    )
    avatar_data = requests.get(
        user.display_avatar.url
    ).content

    avatar = Image.open(
        io.BytesIO(avatar_data)
    )

    avatar = avatar.resize((180, 180))

    card.paste(
        avatar,
        (40, 120)
    )

    emp_id = f"EMP-{str(user.id)[-6:]}"

    draw.text(
        (260, 120),
        f"이름 : {user.name}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 170),
        f"직급 : {rank_name}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 220),
        f"사번 : {emp_id}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 270),
        f"입사일 : {join_date}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 320),
        f"성과등급 : Lv.{level}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 370),
        f"누적성과 : {xp}P",
        fill="black",
        font=font_mid
    )

    qr = qrcode.make(emp_id)
    qr = qr.resize((180, 180))

    card.paste(
        qr,
        (680, 300)
    )

    output = io.BytesIO()

    card.save(
        output,
        format="PNG"
    )

    output.seek(0)

    return output

cooldown = {}

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    uid = str(message.author.id)
    now = time.time()

    if uid in cooldown and now - cooldown[uid] < 4:
        return

    cooldown[uid] = now

    old_xp = get_xp(uid)

    add_xp(uid, 2)

    new_xp = get_xp(uid)

    old_level = get_level(old_xp)
    new_level = get_level(new_xp)

    if new_level > old_level:

        rank_name = await update_role(
            message.author,
            new_level
        )

        await promotion_notice(
            message.channel,
            message.author,
            rank_name,
            new_level
        )
@bot.event
async def on_ready():

    synced = await bot.tree.sync()

    print(f"동기화 명령어 수: {len(synced)}")

    for cmd in synced:
        print(cmd.name)

    print(f"{bot.user} 로그인 완료")

@bot.tree.command(name="rank", description="사내 성과 카드")
async def rank(interaction: discord.Interaction):

    uid = str(interaction.user.id)

    xp = get_xp(uid)
    level = get_level(xp)
    rank_name = get_rank(level)

    cur.execute(
        "SELECT join_date FROM users WHERE user_id=?",
        (uid,)
    )

    join_date = cur.fetchone()[0]

    join_date = time.strftime(
        "%Y-%m-%d",
        time.localtime(join_date)
    )

    card = create_employee_card(
        interaction.user,
        xp,
        level,
        rank_name,
        join_date
    )

    file = discord.File(
        card,
        filename="employee_card.png"
    )

    await interaction.response.send_message(
        file=file
    )

@bot.tree.command(name="top", description="사내 성과 순위")
async def top(interaction: discord.Interaction):
    cur.execute("SELECT user_id,xp FROM users ORDER BY xp DESC LIMIT 10")
    rows = cur.fetchall()

    msg = "🏆 사내 성과 순위\n\n"
    for i, (uid, xp) in enumerate(rows, start=1):
        msg += f"{i}. <@{uid}> - {xp}P\n"

    await interaction.response.send_message(msg)
@bot.tree.command(name="addxp", description="XP 추가")
@app_commands.describe(
    member="대상",
    amount="추가할 XP"
)
async def addxp(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용 가능",
            ephemeral=True
        )

    add_xp(
        str(member.id),
        amount
    )

    await interaction.response.send_message(
        f"{member.mention}에게 {amount}P 지급 완료"
    )

@bot.tree.command(name="setxp", description="XP 설정")
@app_commands.describe(
    member="대상",
    amount="설정할 XP"
)
async def setxp(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용 가능",
            ephemeral=True
        )

    set_xp(
        str(member.id),
        amount
    )

    await interaction.response.send_message(
        f"{member.mention} XP를 {amount}P로 설정"
    )
@bot.tree.command(name="removexp", description="XP 차감")
@app_commands.describe(
    member="대상",
    amount="차감할 XP"
)
async def removexp(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용 가능",
            ephemeral=True
        )

    current = get_xp(
        str(member.id)
    )

    new_xp = max(
        current - amount,
        0
    )

    set_xp(
        str(member.id),
        new_xp
    )

    await interaction.response.send_message(
        f"{member.mention} XP {amount}P 차감"
    )
@bot.tree.command(name="reset", description="XP 초기화")
async def reset(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용 가능",
            ephemeral=True
        )

    set_xp(
        str(member.id),
        0
    )

    await interaction.response.send_message(
        f"{member.mention} 초기화 완료"
    )
@bot.tree.command(name="setlevel", description="레벨 설정")
async def setlevel(
    interaction: discord.Interaction,
    member: discord.Member,
    level: int
):

    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "관리자만 사용 가능",
            ephemeral=True
        )

    xp = int(
        (level / 0.55) ** (1 / 0.55)
    ) if level > 0 else 0

    set_xp(
        str(member.id),
        xp
    )

    await interaction.response.send_message(
        f"{member.mention} 레벨 {level} 설정 완료"
    )
# 토큰 입력
import os

bot.run(os.getenv("TOKEN"))
