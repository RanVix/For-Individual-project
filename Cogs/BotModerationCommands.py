import time
import disnake
from disnake.ext import commands, tasks
import sqlite3
import re
from disnake.ext.commands import Range


class BotModerationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.create_database()
        self.conn = sqlite3.connect('bot_db.db')
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bans (
                        username TEXT,
                        userid INTEGER,
                        ban_time REAL,
                        unban_time REAL,
                        reason TEXT
                    )
                ''')
        self.conn.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        self.auto_unban.start()

    def create_database(self):
        with sqlite3.connect('bot_db.db') as db:
            cursor = db.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS temp_roles (
                    user_id INTEGER,
                    role_id INTEGER,
                    guild_id INTEGER,
                    end_time INTEGER,
                    issued_time INTEGER,
                    issued_by TEXT
                )
            ''')
            db.commit()

    @tasks.loop(seconds=10)
    async def check_expired_roles(self):
        with sqlite3.connect('bot_db.db') as db:
            cursor = db.cursor()
            cursor.execute('SELECT user_id, role_id, guild_id FROM temp_roles WHERE end_time <= ?',
                           (disnake.utils.utcnow().timestamp(),))
            rows = cursor.fetchall()

            for row in rows:
                user_id, role_id, guild_id = row
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    continue
                member = guild.get_member(user_id)
                role = guild.get_role(role_id)

                if member and role:
                    # Проверяем права бота
                    bot_permissions = guild.me.guild_permissions
                    if not bot_permissions.manage_roles:
                        print(f'На сервере {guild.name} не удалось выполнить проверку на роли из-за недостатка прав.')
                        continue  # Переход к следующему члену

                    try:
                        await member.remove_roles(role)
                        print(f'Роль {role.name} была снята с пользователя {member.display_name} в гильдии {guild.name}.')  # Лог о снятии роли
                        cursor.execute('DELETE FROM temp_roles WHERE user_id = ? AND role_id = ? AND guild_id = ?',
                                       (member.id, role.id, guild.id))
                        db.commit()
                    except disnake.Forbidden:
                        pass
                    except disnake.HTTPException as e:
                        print(f'Ошибка при удалении роли: {e}')

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_expired_roles.start()
        self.auto_unban.start()


    @commands.slash_command(name="unmute", description="Снимает печать мьюта")
    @commands.has_permissions(mute_members=True)
    async def unmute(self, ctx, member: disnake.Member):
        user_id = member.id
        if not ctx.guild.me.guild_permissions.manage_roles:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="У меня нет прав на управление ролями!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return
        if ctx.guild.me.top_role <= member.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу размутить этого пользователя, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return
        if member == ctx.me:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Хорошая попытка, но бота нельзя мутить/анмутить😎",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif ctx.author.top_role <= member.top_role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Ошибка, нельзя снять мут с {member.mention}. Его роль главнее!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
        elif member.guild_permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете снять мут с {member.mention}, так как у него есть права администратора!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        else:
            muted_role = disnake.utils.get(ctx.guild.roles, name="Muted")
            if muted_role in member.roles:
                self.cursor.execute('DELETE FROM mutes WHERE userid = ?', (user_id,))
                self.conn.commit()
                await member.remove_roles(muted_role)
                embedEr = disnake.Embed(title="Выполнено!😎",
                                        description=f'{member.mention} был размучен. Его размутил {ctx.author.mention}',
                                        colour=disnake.Color.orange())
                embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embedEr,delete_after=5)
            else:
                embedEr = disnake.Embed(title="Ошибка!😥",
                                        description=f'{member.mention} не имеет роли "Muted"',
                                        colour=disnake.Color.orange())
                embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                await ctx.send(embed=embedEr, ephemeral=True)

    @commands.slash_command(name="ban", description="Банит пользователя на указанное время.")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: disnake.Member, duration: str, *, reason: str = 'не указана'):
        await ctx.response.defer()
        if not ctx.guild.me.guild_permissions.ban_members:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав на бан пользователей!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        if ctx.guild.me.top_role <= user.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return

        if user == ctx.me:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Я не стану банить сам себя!😎",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif ctx.author == user:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Не бань себя!😨",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif ctx.author.top_role <= user.top_role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете забанить {user.mention}. Его роль главнее или равна вашей!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif user.guild_permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете забанить {user.mention}, так как у него есть права администратора!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        # Парсинг времени
        pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
        match = re.fullmatch(pattern, duration)

        if not match:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Неправильный формат времени. Используйте XdYhZmWs.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        days, hours, minutes, seconds = match.groups()
        days = int(days) if days else 0
        hours = int(hours) if hours else 0
        minutes = int(minutes) if minutes else 0
        seconds = int(seconds) if seconds else 0

        # Проверка допустимых значений
        if hours >= 24 or minutes >= 60 or seconds >= 60:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Часы не могут превышать 24, минуты и секунды — 60.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        # Перевод времени в секунды
        duration_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds

        ban_time = time.time()
        unban_time = ban_time + duration_seconds
        embedEr = disnake.Embed(title="Выполнено!😎",
                                description=f'Пользователь {user.mention} был забанен на {duration}. Причина: {reason}. Забанил: {ctx.author.mention}',
                                colour=disnake.Color.orange())
        embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embedEr)

        await ctx.guild.ban(user, reason=reason)

        self.cursor.execute('''
                    INSERT INTO bans (username, userid, ban_time, unban_time, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user.name, user.id, ban_time, unban_time, reason))
        self.conn.commit()

    @ban.error
    async def ban_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Пожалуйста, укажите действительного пользователя.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)

    @tasks.loop(seconds=12)
    async def auto_unban(self):
        self.cursor.execute('SELECT * FROM bans WHERE unban_time <= ?', (time.time(),))
        bans = self.cursor.fetchall()
        for ban in bans:
            user_id = ban[1]
            print(user_id)
            for guild in self.bot.guilds:
                try:
                    await guild.unban(disnake.Object(id=user_id))
                    self.cursor.execute('DELETE FROM bans WHERE userid = ?', (user_id,))
                    self.conn.commit()
                    print(f'Разбанил {user_id}')
                except disnake.HTTPException:
                    pass

    @commands.slash_command(name="unban", description="Разбанить пользователя по его ID")
    @commands.has_permissions(ban_members=True)
    async def unban(self, interaction: disnake.ApplicationCommandInteraction, user_id: str):
        if not interaction.guild.me.guild_permissions.ban_members:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав на бан/разбан пользователей!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if not user_id.isdigit():
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Пожалуйста, укажите корректный User ID (только цифры)!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        user_id = int(user_id)
        guild = interaction.guild

        try:
            user = await self.bot.fetch_user(user_id)
            await guild.unban(user)
            embedEr = disnake.Embed(title="Выполнено!😎", description=f"Пользователь {user.mention} был разбанен.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr)
            self.cursor.execute('DELETE FROM bans WHERE userid = ?', (user_id,))
            self.conn.commit()
        except disnake.NotFound:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Пользователь не найден или не забанен!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
        except disnake.Forbidden:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав на разбан пользователя!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
        except Exception as e:
            embedEr = disnake.Embed(title="Ошибка!😥", colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            print(f"Произошла ошибка в /unban: {str(e)}")


    @commands.slash_command(name="clear", description="Удаляет определенное количество сообщений из чата.")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, interaction: disnake.ApplicationCommandInteraction, amount: Range[int, 1, 1000], user: disnake.Member = None):
        await interaction.response.defer()
        if not interaction.guild.me.guild_permissions.manage_messages:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для удаления сообщений.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if not interaction.author.guild_permissions.manage_messages:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У вас нет прав для выполнения данной команды!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if not interaction.guild.me.guild_permissions.manage_messages:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для удаления сообщений.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if amount < 1:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Пожалуйста, укажите количество сообщений больше 0.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if user is None:
            deleted_messages = await interaction.channel.purge(limit=amount)
        else:
            def check(m):
                return m.author.id == user.id

            deleted_messages = await interaction.channel.purge(limit=amount, check=check)
        embedEr = disnake.Embed(title="Выполнено!😎",
                                description=f'Пользователь {interaction.author.mention} запросил удалении сообщений. Удалено {len(deleted_messages)} сообщений.',
                                colour=disnake.Color.orange())
        embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        await interaction.send(embed=embedEr)


    @commands.slash_command(name="slowmode", description="Включает режим замедения сообщений.")
    @commands.has_permissions(manage_messages=True, manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.response.defer()
        if not ctx.author.guild_permissions.manage_messages:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У вас нет прав для выполнения данной команды!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
        if not ctx.guild.me.guild_permissions.manage_channels:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для изменения настроек канала.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        if seconds < 0:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Время не может быть отрицательным!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            embedEr = disnake.Embed(title="Выполнено!😎",
                                    description="Режим медленных сообщений отключен.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr)
        else:
            embedEr = disnake.Embed(title="Выполнено!😎",
                                    description=f"Режим медленных сообщений включен. Задержка: {seconds} секунд. Включил его: {ctx.author.mention}",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr)


    @commands.slash_command(name="kick", description="Кикает пользователя с сервера.")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: disnake.Member, *, reason="Нарушение правил."):
        await ctx.response.defer()
        if not ctx.author.guild_permissions.kick_members:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У вас нет прав для выполнения данной команды!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.kick_members:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для кика пользователей.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        if ctx.guild.me.top_role <= member.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return
        if member == ctx.me:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Хорошая попытка, но бота нельзя кикнуть.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif ctx.author.mention == member:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Нельзя себя кикнуть!😱",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        elif ctx.author.top_role <= member.top_role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Ошибка, нельзя кикнуть {member.mention}. Его роль главнее или равна вашей!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
        elif member.guild_permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете кикнуть {member.mention}, так как у него есть права администратора!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        else:
            embedEr = disnake.Embed(title="Выполнено!😎",
                                    description=f"Пользователь {ctx.author.mention} исключил пользователя {member.mention}",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr)
            await member.kick(reason=reason)
            await ctx.message.delete(delay=3)


    @commands.slash_command(name="give_role", description="Выдать роль пользователю.")
    @commands.has_permissions(manage_roles=True)
    async def give_role(self, interaction: disnake.ApplicationCommandInteraction,
                        member: disnake.Member,
                        role: disnake.Role):
        if member.bot:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете выдавать роли ботам!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if not interaction.guild.me.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для выдачи ролей.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if interaction.guild.me.top_role <= member.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embed, ephemeral=True)
            return
        # Проверка: есть ли у роли права администратора
        if role.permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете выдавать роли с правами администратора.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        # Проверка: может ли бот выдать эту роль
        if role.position >= interaction.guild.me.roles[-1].position:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня недостаточно прав для выдачи этой роли. Моя роль ниже.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if role in member.roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"{member.mention} уже имеет роль {role.mention}.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if not interaction.guild.me.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для выдачи ролей.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        # Выдача роли
        await member.add_roles(role)
        embedEr = disnake.Embed(title="Выполнено!😎",
                                description=f"{role.mention} была выдана {member.mention}.",
                                colour=disnake.Color.orange())
        embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        await interaction.send(embed=embedEr)

    @commands.slash_command(name="remove_role", description="Удалить роль у пользователя.")
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, interaction: disnake.ApplicationCommandInteraction,
                          member: disnake.Member,
                          role: disnake.Role):
        if member.bot:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете забрать роли ботов!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if not interaction.guild.me.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для выдачи/забора ролей.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if interaction.guild.me.top_role <= member.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embed, ephemeral=True)
            return

        if role.permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете забирать роли с правами администратора!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if role.position >= interaction.guild.me.roles[-1].position:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня недостаточно прав для взятия этой роли. Моя роль ниже.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if role == interaction.guild.default_role:  # Проверка на роль @everyone
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Нельзя удалить роль @everyone!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if role not in member.roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"{member.mention} не имеет роль {role.mention}.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        if member.guild_permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"Вы не можете снять роль с {member.mention}, так как у него есть права администратора!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        await member.remove_roles(role)
        embedEr = disnake.Embed(title="Успех!✅",
                                description=f"{role.mention} была удалена у {member.mention}.",
                                colour=disnake.Color.green())
        embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        await interaction.send(embed=embedEr)

    @commands.slash_command(name="temp_role", description="Выдает временную роль участнику.")
    @commands.has_permissions(manage_roles=True)
    async def temp_role(self, ctx, member: disnake.Member, role: disnake.Role, duration: str):
        await ctx.response.defer()
        if member.bot:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете выдавать роли ботам!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        if not ctx.guild.me.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня нет прав для выдачи/забора ролей.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        if ctx.guild.me.top_role <= member.top_role:
            embed = disnake.Embed(title="Ошибка!😥",
                                  description="Я не могу взаимодействовать с этим пользователем, так как моя роль ниже его!",
                                  colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
            return
        if role in member.roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f"{member.mention} уже имеет роль {role.mention}.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return
        bot_role = ctx.guild.me.top_role
        if role >= bot_role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У меня недостаточно прав для выдачи этой роли. Моя роль ниже.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        # Проверка формата времени
        pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
        match = re.fullmatch(pattern, duration)

        if not match:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Неправильный формат времени. Используйте XdYhZmWs.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        days, hours, minutes, seconds = map(lambda x: int(x) if x else 0, match.groups())

        # Проверка допустимых значений
        if hours >= 24 or minutes >= 60 or seconds >= 60:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Часы не могут превышать 24, минуты и секунды — 60.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        # Перевод времени в секунды
        total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds

        if total_seconds <= 0:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Пожалуйста, укажите допустимую продолжительность.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embedEr, ephemeral=True)
            return

        # Выдаем роль
        await member.add_roles(role)

        # Записываем информацию о выданной роли в базу данных
        end_time = disnake.utils.utcnow().timestamp() + total_seconds
        issued_time = disnake.utils.utcnow().timestamp()
        issued_by = ctx.author.display_name

        with sqlite3.connect('bot_db.db') as db:
            cursor = db.cursor()
            cursor.execute(
                'INSERT INTO temp_roles (user_id, role_id, guild_id, end_time, issued_time, issued_by) VALUES (?, ?, ?, ?, ?, ?)',
                (member.id, role.id, ctx.guild.id, end_time, issued_time, issued_by))
            db.commit()

        embedEr = disnake.Embed(title="Выполнено!😎",
                                description=f'Роль {role.name} выдана {member.mention} на {duration}. Выдано пользователем {issued_by}.',
                                colour=disnake.Color.orange())
        embedEr.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embedEr)


    @commands.slash_command(name="giveroleall", description="Выдает выбранную роль всем участникам сервера, кроме ботов")
    @commands.has_permissions(manage_roles=True)
    async def giveroleall(self, interaction: disnake.CommandInteraction, role: disnake.Role):
        if role.permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете выдавать роль с правами администратора.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        bot_member = interaction.guild.me
        if not bot_member.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У бота нет прав управлять ролями.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if bot_member.top_role <= role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Роль бота должна быть выше выдаваемой роли.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        failed_count = 0
        error_messages = []

        wait_embed = disnake.Embed(title="Команда выполняется!⏰", color=disnake.Color.orange())
        wait_embed.set_footer(text="⚠ | Скорость выполнения команды зависит от количества участников на вашем сервере!")
        await interaction.send(embed=wait_embed, ephemeral=True)

        for member in interaction.guild.members:
            if not member.bot and role not in member.roles:
                if member.top_role < bot_member.top_role:
                    try:
                        await member.add_roles(role)
                    except disnake.Forbidden:
                        failed_count += 1
                        error_messages.append(
                            f'Не удалось выдать роль {role.name} участнику {member.name} из-за недостатка прав.')
                    except disnake.HTTPException as e:
                        failed_count += 1
                        error_messages.append(f'Ошибка при выдаче роли {role.name} участнику {member.name}: {e}')

        success_message = disnake.Embed(title="Команда успешно выполнена!😎", color=disnake.Color.orange(), description=f'\nРоль **{role.name}** успешно выдана всем участникам сервера, у кого её не было и чья роль ниже роли бота!🤖\n')
        success_message.set_footer(text="\n⚠ | Если роль не была выдана какому-то участнику, то проверьте, может у участника есть роль, которая выше роли бота!")

        await interaction.edit_original_message(embed=success_message)


    @commands.slash_command(name="removeroleall", description="Забирает выбранную роль у всех участников сервера, кроме ботов")
    @commands.has_permissions(manage_roles=True)
    async def remove_role(self, interaction: disnake.CommandInteraction, role: disnake.Role):
        if role.permissions.administrator:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Вы не можете снимать роль с правами администратора.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        bot_member = interaction.guild.me
        if not bot_member.guild_permissions.manage_roles:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У бота нет прав управлять ролями.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        if bot_member.top_role <= role:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Роль бота должна быть выше снимаемой роли.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        failed_count = 0
        error_messages = []

        wait_embed = disnake.Embed(title="Команда выполняется!⏰", color=disnake.Color.orange())
        wait_embed.set_footer(text="⚠ | Скорость выполнения команды зависит от количества участников на вашем сервере!")
        await interaction.send(embed=wait_embed, ephemeral=True)

        for member in interaction.guild.members:
            if not member.bot and role in member.roles:
                if member.top_role < bot_member.top_role:
                    try:
                        await member.remove_roles(role)
                    except disnake.Forbidden:
                        failed_count += 1
                        error_messages.append(
                            f'Не удалось снять роль {role.name} у участника {member.name} из-за недостатка прав.')
                    except disnake.HTTPException as e:
                        failed_count += 1
                        error_messages.append(f'Ошибка при снятии роли {role.name} у участника {member.name}: {e}')

        success_message = disnake.Embed(title="Команда успешно выполнена!😎", color=disnake.Color.orange(), description=f'Роль **{role.name}** успешно снята со всех участников сервера, у кого она была и чья роль ниже роли бота!🤖')
        success_message.set_footer(text="\nЕсли роль не была выдана какому-то участнику, то проверьте, может у участника есть роль, которая выше роли бота!")

        await interaction.edit_original_message(embed=success_message)


def setup(bot):
    bot.add_cog(BotModerationCommands(bot))