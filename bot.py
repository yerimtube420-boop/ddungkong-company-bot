
# company_performance_bot.py
# 설치:
# pip install discord.py pillow qrcode[pil] requests

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import time
import os
import io
import qrcode
import requests
import random

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("/data/xp.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id TEXT PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    join_date INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS attendance(
    user_id TEXT PRIMARY KEY,
    last_attendance TEXT,
    streak INTEGER DEFAULT 0,
    total_attendance INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS attendance_log(
    user_id TEXT,
    date TEXT,
    PRIMARY KEY(user_id, date)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS investment(
    user_id TEXT PRIMARY KEY,
    invest_date TEXT,
    invest_count INTEGER DEFAULT 0
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
def get_next_rank_level(level):
    if level < 3:
        return 3, "사원"

    elif level < 10:
        return 10, "대리"

    elif level < 20:
        return 20, "팀장"

    elif level < 40:
        return 40, "과장"

    elif level < 60:
        return 60, "차장"

    elif level < 80:
        return 80, "부장"

    return None, None
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
    # 기존 직급 제거
    for role_name in role_names:
        role = discord.utils.get(
            member.guild.roles,
            name=role_name
        )

    if role and role in member.roles:
            await member.remove_roles(role)
    # 특별 직급 우선
    if member == member.guild.owner:
        target_rank = "회장님"

    elif discord.utils.get(member.roles, name="부회장님"):
        target_rank = "부회장님"

    elif discord.utils.get(member.roles, name="사장님"):
        target_rank = "사장님"

    else:
        target_rank = get_rank(level)


    new_role = discord.utils.get(
        member.guild.roles,
        name=target_rank
    )

    if new_role:
        await member.add_roles(new_role)

    return target_rank

from datetime import datetime

def attend(user_id):

    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
    SELECT last_attendance,
           streak,
           total_attendance
    FROM attendance
    WHERE user_id=?
    """, (user_id,))

    row = cur.fetchone()
    print("uid =", uid)
    print("row =", row)
    if row:

        last_date, streak, total = row

        if last_date == today:
            return False, streak

        streak += 1
        total += 1

        cur.execute("""
        UPDATE attendance
        SET last_attendance=?,
            streak=?,
            total_attendance=?
        WHERE user_id=?
        """, (
            today,
            streak,
            total,
            user_id
        ))

    else:

        streak = 1
        total = 1

        cur.execute("""
        INSERT INTO attendance(
            user_id,
            last_attendance,
            streak,
            total_attendance
        )
        VALUES (?, ?, ?, ?)
        """, (
            user_id,
            today,
            streak,
            total
        ))

    conn.commit()

    return True, streak

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
    next_level, next_rank = get_next_rank_level(level)
    print("사원증 생성 시작")
    card = Image.new("RGB", (900, 650), (245, 245, 245))
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

    except Exception as e:

        print("폰트 로딩 실패:", e)

        font_big = ImageFont.load_default()
        font_mid = ImageFont.load_default()

    draw.rectangle((0, 0, 900, 80), fill=(30, 30, 30))

    draw.text(
        (20, 10),
        "뚱콩컴퍼니",
        fill="white",
        font=font_big
    )
    draw.text(
        (55, 320),
        "사내 성과 카드",
        fill="black",
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
    cur.execute(
        """
        SELECT streak, total_attendance
        FROM attendance
        WHERE user_id = ?
        """,
        (str(user.id),)
    )

    row = cur.fetchone()

    if row:
        streak = row[0]
        total_attendance = row[1]
    else:
        streak = 0
        total_attendance = 0
    draw.text(
        (260, 120),
        f"이름 : {user.name}",
        fill="black",
        font=font_mid
    )
    display_rank = rank_name
    rank_color = "black"
    
    if rank_name == "회장님":
        rank_color = (184, 134, 11)

    elif rank_name == "부회장님":
        rank_color = (120, 120, 120)

    elif rank_name == "사장님":
        rank_color = (139, 69, 19)
    draw.text(
        (260, 170),
        f"직급 : {display_rank}",
        fill=rank_color,
        font=font_mid
    )
    if rank_name in ["회장님", "부회장님", "사장님"]:
        department = "경영진"
    else:
        department = "일반 직원"

    draw.text(
        (260, 220),
        f"부서 : {department}",
        fill="black",
        font=font_mid
    )
    draw.text(
        (260, 270),
        f"사번 : {emp_id}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 320),
        f"입사일 : {join_date}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 370),
        f"성과등급 : Lv.{level}",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 420),
        f"누적성과 : {xp}P",
        fill="black",
        font=font_mid
    )
    draw.text(
        (260, 470),
        f"출석일수 : {total_attendance}일",
        fill="black",
        font=font_mid
    )

    draw.text(
        (260, 500),
        f"연속출석 : {streak}일",
        fill="black",
        font=font_mid
    )
    if next_level:
        draw.text(
            (260, 550),
            f"다음 진급 : {next_rank} ({next_level - level}Lv)",
            fill="black",
            font=font_mid
        )
    else:
        draw.text(
            (260, 550),
            "최고 직급",
            fill=(184, 134, 11),
            font=font_mid
        )
    draw.rectangle(
    [(670, 390), (820, 520)],
    outline=(180, 180, 180),
    width=2
    )

    stamp = Image.open("stamp.png").convert("RGBA")

    stamp = stamp.resize((140, 140))


    draw.text(
        (700, 455),
        "공식 직인",
        fill=(160, 160, 160),
        font=font_mid
    )

    stamp = Image.open("stamp.png").convert("RGBA")

    stamp = stamp.resize((200, 200))

    card.paste(
        stamp,
        (645, 365),
        stamp
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
    
    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        INSERT OR IGNORE INTO attendance_log
        VALUES (?, ?)
        """,
        (uid, today)
    )
    conn.commit()
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
    user = interaction.user
    xp = get_xp(uid)
    level = get_level(xp)
    if user == interaction.guild.owner:
        rank_name = "회장님"

    elif discord.utils.get(user.roles, name="부회장님"):
        rank_name = "부회장님"

    elif discord.utils.get(user.roles, name="사장님"):
        rank_name = "사장님"

    else:
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
    await update_role(member, level)

    await interaction.response.send_message(
        f"{member.mention} 레벨 {level} 설정 완료"
    )
class InvestView(discord.ui.View):

    def __init__(self, bet, uid):
        super().__init__(timeout=60)

        self.bet = bet
        self.uid = uid

    async def process_result(
        self,
        interaction: discord.Interaction,
        location_name: str
    ):
        today = datetime.now().strftime("%Y-%m-%d")

        cur.execute(
            "SELECT invest_date, invest_count FROM investment WHERE user_id=?",
            (self.uid,)
    )

    row = cur.fetchone()

    if row:
        invest_date, invest_count = row

        if invest_date == today:

            if invest_count >= 5:
                return await interaction.response.send_message(
                    "오늘 투자 가능 횟수(5회)를 모두 사용했습니다.",
                    ephemeral=True
                )

            invest_count += 1

        else:
            invest_count = 1

    else:
        invest_count = 1
    xp = get_xp(self.uid)

    results = ["투자성공", "투자철회", "투자실패"]
    random.shuffle(results)

    result = results[0]

    if result == "투자성공":

        set_xp(self.uid, xp + self.bet)

        msg = f"📈 투자성공 !\n+{self.bet}P"

    elif result == "투자철회":

        msg = "📋 투자철회\n포인트 변동 없음"

    else:

        set_xp(self.uid, xp - self.bet)

        msg = f"📉 투자실패 !\n-{self.bet}P"
    cur.execute(
        """
        INSERT OR REPLACE INTO investment
        (user_id, invest_date, invest_count)
        VALUES (?, ?, ?)
        """,
        (self.uid, today, invest_count)
    )

    conn.commit()
    await interaction.response.edit_message(
            content=
            f"🏢 투자 결과\n\n"
            f"{msg}\n\n"
            f"오늘 사용 : {invest_count}/5",
            view=None
        )

    @discord.ui.button(
        emoji="🏢",
        style=discord.ButtonStyle.primary
    )
    async def hq(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.process_result(interaction, "🏢")

    @discord.ui.button(
        emoji="🏚️",
        style=discord.ButtonStyle.success
    )
    async def lab(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.process_result(interaction, "🏚️")

    @discord.ui.button(
        emoji="🏭",
        style=discord.ButtonStyle.danger
    )
    async def factory(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.process_result(interaction, "🏭")
@bot.tree.command(
    name="투자",
    description="성과 포인트 투자"
)
async def invest(
    interaction: discord.Interaction,
    bet: int
):

    uid = str(interaction.user.id)

    if bet < 10:
        return await interaction.response.send_message(
            "최소 투자금은 10P입니다.",
            ephemeral=True
        )

    if bet > 100:
        return await interaction.response.send_message(
            "최대 투자금은 100P입니다.",
            ephemeral=True
        )

    xp = get_xp(uid)

    if xp < bet:
        return await interaction.response.send_message(
            "포인트가 부족합니다.",
            ephemeral=True
        )

    await interaction.response.send_message(
        f"🏢 투자금 : {bet}P\n\n"
        f"투자 부서를 선택하세요.",
        view=InvestView(bet, uid)
    )

@bot.tree.command(
    name="출근",
    description="오늘의 출근"
)
async def attendance(
    interaction: discord.Interaction
):

    uid = str(interaction.user.id)

    success, streak = attend(uid)

    if not success:
        return await interaction.response.send_message(
            "오늘은 이미 출근했습니다."
        )

    add_xp(uid, 50)

    print("출근 XP 지급 완료")
    print("현재 XP:", get_xp(uid))

    await interaction.response.send_message(
        f"""🏢 출근 완료!

+50P 지급

연속 출근 : {streak}일"""
    )
# 토큰 입력   
bot.run(os.getenv("TOKEN"))
