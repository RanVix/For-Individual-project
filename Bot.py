import disnake
from disnake.ext import commands, tasks
import os
import time
import sqlite3
import re
import requests

conn = sqlite3.connect('bot_db.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS mutes (
        username TEXT,
        userid INTEGER,
        guild_id INTEGER,
        mute_time REAL,
        unmute_time REAL,
        reason TEXT
    )
''')
conn.commit()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS warnings (
        username TEXT,
        userid INTEGER,
        warn_time REAL,
        reason TEXT,
        warn_count INTEGER DEFAULT 0
    )
''')
conn.commit()


command_sync_flags = commands.CommandSyncFlags.default()
command_sync_flags.sync_commands_debug = True
bot = commands.Bot(command_prefix="!", help_command=None, command_sync_flags=command_sync_flags,intents=disnake.Intents.all(), reload=True)

#Мониторинги
SDC_TOKEN = 'Токен, его не могу показать)'
SDC_API_URL = f'https://api.server-discord.com/v2/bots/1284123685690802269/stats'

def send_stats():
    server_count = len(bot.guilds)
    shard_count = 1

    headers = {'Authorization': SDC_TOKEN}
    payload = {'servers': server_count, 'shards': shard_count}

    response = requests.post(SDC_API_URL, headers=headers, json=payload)
    if response.status_code == 200:
        pass
    else:
        print(f"Ошибка {response.status_code} {response.text}")

@tasks.loop(minutes=30)
async def update_stats():
    send_stats()


@bot.command()
@commands.is_owner()
async def load(ctx, extension):
    bot.load_extension(f"Cogs.{extension}")

@bot.command()
@commands.is_owner()
async def unload(ctx, extension):
    bot.unload_extension(f"Cogs.{extension}")

@bot.command()
@commands.is_owner()
async def reload(ctx, extension):
    bot.reload_extension(f"Cogs.{extension}")

for filename in os.listdir("Cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"Cogs.{filename[:-3]}")

#Нужные функции
async def create_muted_role(guild):
    try:
        muted_role = disnake.utils.get(guild.roles, name="Muted")
        if not muted_role:
            muted_role = await guild.create_role(name="Muted", permissions=disnake.Permissions.none())
            await muted_role.edit(permissions=disnake.Permissions(send_messages=False, speak=False))
        return muted_role
    except disnake.Forbidden:
        print("Нет прав для создания мут-роли.")
    except disnake.HTTPException as e:
        print(f"Ошибка создания мут роли: {e.status} {e.text}")
    except Exception as e:
        print(f"Ошибка в создании роли мута: {e}")


#Сообщение о новых серверах
@bot.event
async def on_guild_join(guild):
    channel = bot.get_channel(1297167617072566282)
    if channel:
        embed = disnake.Embed(title=f"Бот добавлен на сервер {guild.name}!", color=disnake.Color.green())
        embed.add_field(name="Название сервера:", value=guild.name)
        embed.add_field(name="Количество участников", value=guild.member_count)
        embed.add_field(name="Создатель сервера", value=guild.owner.mention)
        embed.add_field(name="ID создателя", value=guild.owner.id)
        embed.add_field(name="ID сервера", value=guild.id)
        embed.set_thumbnail(url=guild.icon)
        await channel.send(embed=embed)

    owner = guild.owner

    embed = disnake.Embed(
        title="👋 | Спасибо за приглашение!",
        description=f"Спасибо за добавление меня на сервер **{guild.name}**!",
        color=disnake.Color.orange(),
    )

    embed.add_field(name="Информация💻", value="С моими командами можно ознакомиться, используя `/help`.\n" +
                                              "Перед использованием моего функционала, переместите мою роль как можно выше! "
                                              "Это нужно для корректной работы моих функций. "
                                              "После моей настройки, о ней в `/help`, я начну оберегать твой сервер от опасностей!", inline=False)
    embed.add_field(name="Ссылки🔗", value="[Добавить бота](https://discord.com/oauth2/authorize?client_id=1284123685690802269&permissions=8&integration_type=0&scope=applications.commands+bot)\n"
                        "[Сервер поддержки](https://discord.gg/cmc6DNhKKK)\n"+
                        "[Мой разработчик](https://discord.com/users/619946431452807189/)\n"+
                        "[Политика конфиденциальности](https://github.com/RanVix/RannyBot/blob/main/PrivacyPolicy.md)\n", inline=False)
    embed.set_footer(text="⚠ | Если у вас есть вопросы, не стесняйтесь спрашивать!")

    try:
        await owner.send(embed=embed)
        print(f'Приветственное сообщение отправлено {owner.name}.')
    except disnake.Forbidden:
        print(f'Не удалось отправить сообщение {owner.name}.')

@bot.event
async def on_guild_remove(guild):
    channel = bot.get_channel(1297167617072566282)
    if channel:
        embed = disnake.Embed(title=f"Бот удален с сервера {guild.name}", color=disnake.Color.red())
        embed.add_field(name="Название сервера", value=guild.name)
        embed.add_field(name="Количество участников", value=guild.member_count)
        embed.add_field(name="Создатель сервера", value=guild.owner.mention)
        embed.add_field(name="ID создателя", value=guild.owner.id)
        embed.add_field(name="ID сервера", value=guild.id)
        embed.set_thumbnail(url=guild.icon)
        await channel.send(embed=embed)



#Костыли
@bot.slash_command(name="mute", description="Запрещает пользователям писать и говорить.")
@commands.has_permissions(mute_members=True)
async def mute(ctx, user: disnake.Member, duration: str, *, reason: str = 'не указана'):
    # Проверка прав бота на выдачу роли
    if not ctx.guild.me.guild_permissions.manage_roles:
        embed = disnake.Embed(title="Ошибка!😥",
                              description="У меня нет прав на управление ролями!",
                              colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return

    # Проверка положения роли бота
    if ctx.guild.me.top_role <= user.top_role:
        embed = disnake.Embed(title="Ошибка!😥",
                              description="Я не могу мутить этого пользователя, так как моя роль ниже его!",
                              colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return

    # Проверка на попытку мута самого себя или администраторов
    if user == ctx.me:
        embed = disnake.Embed(title="Ошибка!😥", description="Я хоть и бот, но не глупый. Я не стану мутить себя!!😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author == user:
        embed = disnake.Embed(title="Ошибка!😥", description="Не муть себя! Тебе же плохо будет..😥", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author.top_role <= user.top_role:
        embed = disnake.Embed(title="Ошибка!😥", description=f"Вы не можете мутить {user.mention}. Его роль главнее или равна вашей!😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif user.guild_permissions.administrator:
        embed = disnake.Embed(title="Ошибка!😥",
                                description=f"Вы не можете замутить {user.mention}, так как у него есть права администратора!",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return

    # Проверка наличия существующего мута
    cursor.execute("SELECT * FROM mutes WHERE userid = ? AND guild_id = ?", (user.id, ctx.guild.id))
    existing_mute = cursor.fetchone()

    if existing_mute:
        # Удаляем старый мут из базы данных
        cursor.execute("DELETE FROM mutes WHERE userid = ? AND guild_id = ?", (user.id, ctx.guild.id))
        conn.commit()

    # Парсинг времени
    pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    match = re.fullmatch(pattern, duration)

    if not match:
        embed = disnake.Embed(title="Ошибка!😥", description="Неправильный формат времени. Используйте XdYhZmWs.",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return

    days, hours, minutes, seconds = match.groups()
    days = int(days) if days else 0
    hours = int(hours) if hours else 0
    minutes = int(minutes) if minutes else 0
    seconds = int(seconds) if seconds else 0

    # Проверка допустимых значений
    if hours >= 24 or minutes >= 60 or seconds >= 60:
        embed = disnake.Embed(title="Ошибка!😥", description="Часы не могут превышать 24, минуты и секунды — 60.",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return

    duration_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds

    mute_time = time.time()
    unmute_time = mute_time + duration_seconds

    muted_role = await create_muted_role(ctx.guild)  # Создание роли, если она не существует
    await user.add_roles(muted_role)

    cursor.execute(''' 
        INSERT INTO mutes (username, userid, guild_id, mute_time, unmute_time, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.name, user.id, ctx.guild.id, mute_time, unmute_time, reason))
    conn.commit()

    embed = disnake.Embed(title="Успешно выполнена!😎",
                            description=f'{user.mention} был замучен на {duration}. Его замутил: {ctx.author.mention}',
                            colour=disnake.Color.orange())
    embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
    await ctx.send(embed=embed, delete_after=5)
    print(f'{user.mention} был замучен на {duration}. Его замутил: {ctx.author.mention}')


@tasks.loop(seconds=11)
async def auto_unmute():
    cursor.execute('SELECT * FROM mutes WHERE unmute_time <= ?', (time.time(),))
    mutes = cursor.fetchall()
    for mute in mutes:
        user_id = mute[1]
        guild_id = mute[2]
        guild = bot.get_guild(guild_id)  # Получаем конкретный гильдию по guild_id
        if guild:
            user = guild.get_member(user_id)
            if user:  # Проверка, что пользователь существует на сервере
                muted_role = disnake.utils.get(guild.roles, name='Muted')
                if muted_role:  # Проверка, что роль существует
                    await user.remove_roles(muted_role)
                    cursor.execute('DELETE FROM mutes WHERE userid = ? AND guild_id = ?', (user_id, guild_id))
                    conn.commit()
                    print(f'Размучен {user_id} из гильдии {guild.name}')

@bot.event
async def on_ready():
    auto_unmute.start()
    update_stats.start()

@bot.slash_command(name="warn", description="Выдает предупреждение участнику.")
@commands.has_permissions(ban_members=True, kick_members=True)
async def warn(ctx, user: disnake.Member, *, reason: str = 'не указана'):
    if ctx.guild.me.top_role <= user.top_role:
        embed = disnake.Embed(title="Ошибка!😥",
                              description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                              colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    if user == ctx.me:
        embed = disnake.Embed(title="Ошибка!😥", description="Я не буду выдавать варн сам себе!😭", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author.mention == user:
        embed = disnake.Embed(title="Ошибка!😥", description="Не варни себя! Тебе же плохо будет..😥", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author.top_role <= user.top_role:
        embed = disnake.Embed(title="Ошибка!😥", description=f"Вы не можете варнить {user.mention}. Его роль главнее или равна вашей!😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
    elif user.guild_permissions.administrator:
        embed = disnake.Embed(title="Ошибка!😥",
                                description=f"Вы не можете выдать варн {user.mention}, так как у него есть права администратора!",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    else:
        warn_time = time.time()
        cursor.execute('SELECT warn_count FROM warnings WHERE userid = ?', (user.id,))
        result = cursor.fetchone()
        if result:
            warn_count = result[0] + 1
        else:
            warn_count = 1
        if result:
            cursor.execute('''
                    UPDATE warnings SET warn_time = ?, reason = ?, warn_count = ?
                    WHERE userid = ?
                ''', (warn_time, reason, warn_count, user.id))
        else:
            cursor.execute('''
                    INSERT INTO warnings (username, userid, warn_time, reason, warn_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user.name, user.id, warn_time, reason, warn_count))
        conn.commit()
        if warn_count >= 3:
            await mute(ctx, user, "1d")
            cursor.execute('UPDATE warnings SET warn_count = 0 WHERE userid = ?', (user.id,))
            conn.commit()
            embed = disnake.Embed(title="Варн!⏰",
                                    description=f"{user.mention} был замучен за 3 предупреждения! Мут на 1 день.",
                                    colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=False, delete_after=5)
        embed = disnake.Embed(title="Варн!⏰",
                                description=f"{user.mention} получил предупреждение! Причина: {reason if reason else "Не указана"}. Всего на пользователе: {warn_count} варн(а)",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, delete_after=5)


@bot.slash_command(name="unwarn", description="Убирает предупреждение у участника.")
@commands.has_permissions(ban_members=True, kick_members=True)
async def unwarn(ctx, member: disnake.Member):
    if ctx.guild.me.top_role <= member.top_role:
        embed = disnake.Embed(title="Ошибка!😥",
                              description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                              colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    if member == ctx.me:
        embed = disnake.Embed(title="Ошибка!😥", description="Хорошая попытка, но боты не получают варны. А еще не теряют их.😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author.top_role <= member.top_role:
        embed = disnake.Embed(title="Ошибка!😥", description=f"Вы не можете снять варн с {member.mention}. Его роль главнее или равна вашей!😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif member.guild_permissions.administrator:
        embed = disnake.Embed(title="Ошибка!😥",
                                description=f"Вы не можете снять варн {member.mention}, так как у него есть права администратора!",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    else:
        cursor.execute('SELECT warn_count FROM warnings WHERE userid = ?', (member.id,))
        result = cursor.fetchone()
        if result:
            warn_count = result[0]
            if warn_count > 0:
                warn_count -= 1
                cursor.execute('UPDATE warnings SET warn_count = ? WHERE userid = ?', (warn_count, member.id))
                conn.commit()
                embed = disnake.Embed(title="Выполнено!😎",
                                        description=f'{member.mention} лишился предупреждения! Всего на пользователе: {warn_count} варн(а)',
                                        colour=disnake.Color.orange())
                embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embed, delete_after=5)
            else:
                embed = disnake.Embed(title="Ошибка!😥",
                                        description=f"Вы не можете снять варн с {member.mention}, у него их нет.😎",
                                        colour=disnake.Color.orange())
                embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embed, ephemeral=True)
        else:
            embed = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете снять варн с {member.mention}, у него их нет.😎",
                                    colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)


@bot.slash_command(name="resetwarns", description="Убирает все предупреждения у участника!")
@commands.has_permissions(ban_members=True, kick_members=True)
async def resetwarns(ctx, member: disnake.Member):
    if ctx.guild.me.top_role <= member.top_role:
        embed = disnake.Embed(title="Ошибка!😥",
                              description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                              colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    if member == ctx.me:
        embed = disnake.Embed(title="Ошибка!😥", description="Хорошая попытка, но боты не получают варны. А еще не теряют их.😎", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    elif ctx.author.top_role <= member.top_role:
        embed = disnake.Embed(title="Ошибка!😥", description=f"Вы не можете ресетнуть варны с {member.mention}. Его роль главнее или равна вашей!", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
    elif member.guild_permissions.administrator:
        embed = disnake.Embed(title="Ошибка!😥",
                                description=f"Вы не можете снять варны с {member.mention}, так как у него есть права администратора!",
                                colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embed, ephemeral=True)
        return
    else:
        cursor.execute('SELECT warn_count FROM warnings WHERE userid = ?', (member.id,))
        result = cursor.fetchone()
        if result:
            warn_count = result[0]
            if warn_count > 0:
                warn_count = 0
                cursor.execute('UPDATE warnings SET warn_count = ? WHERE userid = ?', (warn_count, member.id))
                conn.commit()
                embed = disnake.Embed(title="Выполнено!😎",
                                        description=f'{member.mention} лишился всех предупреждений! Всего на пользователе: {warn_count} варнов',
                                        colour=disnake.Color.orange())
                embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embed, delete_after=5)
            else:
                embed = disnake.Embed(title="Ошибка!😥",
                                        description=f"Вы не можете ресетнуть варны с {member.mention}, у него их нет.😎",
                                        colour=disnake.Color.orange())
                embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embed, ephemeral=True)
        else:
            embed = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете ресетнуть варны с {member.mention}, у него их нет.😎",
                                    colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)

bot.run("Токен, его не могу показать")