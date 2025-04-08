import disnake
from disnake.ext import commands
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime, timedelta


class BotInfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DATABASE = 'bot_db.db'
        self.executor = ThreadPoolExecutor()
        self.start_time = time.time()

    def fetch_warns(self, user_id):
        with sqlite3.connect(self.DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT warn_count FROM warnings WHERE userid = ?', (user_id,))
            return cursor.fetchone()

    @commands.slash_command(name='help', description="Призывает меню помощи. Там гайд по управлению ботом.")
    async def help(self, interaction: disnake.ApplicationCommandInteraction):
        embed = disnake.Embed(
            description="**Разработчик:** [RanVix](https://discord.com/users/619946431452807189/)\n**Поддержка:** https://discord.gg/cmc6DNhKKK\n**Версия бота:** 2.3.4",
            colour=disnake.Color.orange())

        embed.set_author(name="RannyBot",
                         url="https://discord.gg/cmc6DNhKKK",
                         icon_url=interaction.me.avatar.url)

        embed.add_field(name="💻Информация:",
                        value="`/help`, `/info`, `/stats`,\n `/server_info`,  `/user_info`,  `/warnson`",
                        inline=False)
        embed.add_field(name="📑Модерация:",
                        value="`/mute`, `/unmute`, `/ban`,\n`/unban`, `/kick`, `/clear`,\n`/warn`, `/unwarn`, `/resetwarns`,\n`/slowmode`, `/give_role`, `/remove_role`\n`/temp_role`, `/giveroleall`, `/removeroleall`",
                        inline=False)
        embed.add_field(name="🔨Инструменты:",
                        value="`/random`, `/translate`, `/qrcode`",
                        inline=False)
        embed.add_field(name="🎯Разное:",
                        value="`/curs`, `/avatar`, `/banner`",
                        inline=False)
        embed.add_field(name="💻ИИ:",
                        value="`/imagine`, `/ask`",
                        inline=False)
        embed.add_field(name="⚙Настройки:",
                        value="`/show_settings`, `/set_start_role`, `/set_welcome_channel`,\n `/set_admin_roles`, `/set_filter_words`, `/set_spam_settings`,\n `/set_caps_settings`",
                        inline=False)
        embed.add_field(name="🔎Бот на мониторингах:",
                        value="[Top.gg](https://top.gg/bot/1284123685690802269) | [Discords.com](https://discords.com/bots/bot/1284123685690802269) | [Discordbotlist](https://discord.ly/rannybot)\n  | [Discord Bots List](https://bots.server-discord.com/1284123685690802269) | [Boticord](https://boticord.top/bot/1284123685690802269?l=ru)",
                        inline=False)
        await interaction.send(embed=embed)

    @commands.slash_command(name="stats", description="Выдает статистку бота")
    async def stats(self, interaction: disnake.ApplicationCommandInteraction):
        guild = interaction.guild
        if guild is None:
            embed = disnake.Embed(title="Ошибка!😥",
                                    description="Не удалось получить информацию о сервере😥",
                                    colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embed, ephemeral=True)
            return

        total_members = sum(guild.member_count for guild in self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        total_roles = sum(len(guild.roles) for guild in self.bot.guilds)
        num_guilds = len(self.bot.guilds)
        bot_ping = round(self.bot.latency * 1000)

        # Время работы бота
        uptime = time.time() - self.start_time
        days = int(uptime // (24 * 3600))
        hours = int((uptime % (24 * 3600)) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        embed = disnake.Embed(title=f"Моя статистика:",
                            description=f'\n' + '\n' +
                                        f"**Серверов: **{num_guilds}" + "\n" +
                                        f"**Участников: **{total_members}" + "\n" +
                                        f"**Количество каналов: **{total_channels}" + "\n" +
                                        f"**Количество ролей: **{total_roles}" + "\n"+
                                        f"**Пинг: **{bot_ping} мс"+"\n"+
                                        f"**Время работы бота: **{days} Д, {hours} Ч, {minutes} М, {seconds} С ⏰"+"\n"+"\n" +
                                        f"**Разработчик: **[RanVix](https://discord.com/users/619946431452807189/)", colour=disnake.Color.orange())
        embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        embed.set_thumbnail(url=interaction.me.avatar.url)
        await interaction.send(embed=embed)

    @commands.slash_command(name="server_info", description="Выдает статистику данного сервера.")
    async def server_info(self, interaction: disnake.ApplicationCommandInteraction):
        guild = interaction.guild

        # Участники
        total_members = guild.member_count
        human_members = sum(1 for member in guild.members if not member.bot)
        bot_members = total_members - human_members

        # Статус участников
        statuses = {
            "online": sum(1 for member in guild.members if member.status == disnake.Status.online),
            "offline": sum(1 for member in guild.members if member.status == disnake.Status.offline),
            "dnd": sum(1 for member in guild.members if member.status == disnake.Status.dnd),
            "idle": sum(1 for member in guild.members if member.status == disnake.Status.idle),
        }

        # Информация по серверу
        created_at_days_ago = (disnake.utils.utcnow() - guild.created_at).days
        verification_level = str(guild.verification_level)
        if verification_level == "none":
            verification_level = "Нет"
        elif verification_level == "low":
            verification_level = "Низкий"
        elif verification_level == "medium":
            verification_level = "Средний"
        elif verification_level == "high":
            verification_level = "Высокий"
        elif verification_level == "very_high":
            verification_level = " Очень высокий"
        elif verification_level == "very high":
            verification_level = " Очень высокий"
        else:
            pass
        owner = guild.owner

        # Каналы
        total_channels = len(guild.channels)
        category_count = len(guild.categories)
        text_channel_count = len(guild.text_channels)
        voice_channel_count = len(guild.voice_channels)

        # Дополнительная информация
        role_count = len(guild.roles)
        emoji_count = len(guild.emojis)
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count

        embed = disnake.Embed(title=f"Статистика сервера: {guild.name}", color=disnake.Color.orange())
        embed.add_field(name="Участники",
                        value=f"👦 Всего: {total_members}\n🙍‍♂️ Людей: {human_members}\n🤖 Ботов: {bot_members}",
                        inline=False)
        embed.add_field(name="Статусы участников",
                        value=f"🟢 Онлайн: {statuses['online']}\n🟡 Неактивные: {statuses['idle']}\n🔴 Не беспокоить: {statuses['dnd']}\n⚫ Оффлайн: {statuses['offline']}",
                        inline=False)
        embed.add_field(name="Информация по серверу",
                        value=f"📆 Создан: `{guild.created_at.strftime('%Y-%m-%d')}` `(это было {created_at_days_ago} дней назад)`\n🔒 Уровень верификации: {verification_level}\n🤴 Владелец: {owner}",
                        inline=False)
        embed.add_field(name="Каналы",
                        value=f"💻 Общее: {total_channels}\n🧱 Категории: {category_count}\n📜 Текстовые: {text_channel_count}\n🔊 Голосовые: {voice_channel_count}",
                        inline=False)
        embed.add_field(name="Сторонняя информация",
                        value=f"🎭 Роли: {role_count}\n😀 Эмодзи: {emoji_count}\n👑 Уровень буста: {boost_level}\n👑 Количество бустов: {boost_count}",
                        inline=False)

        embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        embed.set_thumbnail(url=interaction.me.avatar.url)
        await interaction.send(embed=embed)

    @commands.slash_command(name="user_info", description="Выдает статистику человека, который ввел эту команду.")
    async def user_info(self, interaction: disnake.ApplicationCommandInteraction, member: disnake.Member = None):
        if member is None:
            member = interaction.author

        status = str(member.status).title()
        join_date = member.joined_at.strftime("%d-%m-%Y %H:%M:%S")
        registration_date = member.created_at.strftime("%d-%m-%Y %H:%M:%S")
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        embed = disnake.Embed(title=f"Ваша статистика: ",
                              colour=disnake.Color.orange(),
                              description=f"**Имя:** {member.name}({member.mention})" + '\n' +
                                          f"**ID:** {member.id}" + '\n' +
                                          f"**Статус: **{status}" + "\n" +
                                          f"**Дата присоединения:** {join_date}" + '\n' +
                                          f"**Дата регистрации вашего аккаунта: **{registration_date}" + "\n" +
                                          f"**Роли:** {', '.join(roles) if roles else 'Нет ролей'}" + "\n" +
                                          "\n" +
                                          "**Разработчик:** [RanVix](https://discord.com/users/619946431452807189/)")
        embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        embed.set_thumbnail(url=interaction.me.avatar.url)
        await interaction.send(embed=embed)

    @commands.slash_command(name="info", description="Выдает информацию о боте и его разработчике.")
    async def info(self, interaction: disnake.ApplicationCommandInteraction):
        bot_creation_date = datetime(2024, 9, 18)
        days_since_creation = (datetime.now() - bot_creation_date).days
        creation_date_str = bot_creation_date.strftime("%Y-%m-%d")
        embed = disnake.Embed(title="🤖 RannyBot",
                              colour=disnake.Color.orange(),
                              description="Здравствуй, я Ранни. Я твой верный помощник в суровом мире дискорда, буду помогать тебе модерировать сервер и делать его более функциональным!\n\n" +
                              "Мой префикс `/`. Меня можно гибко настроить. Для информации о моих командах пиши `/help`!")
        embed.add_field(name="📆 Создан",
                        value=f"`{creation_date_str}` `({days_since_creation} дней назад)`",
                        inline=False)
        embed.add_field(name="💻 Мой разработчик",
                        value="RanVix",
                        inline=False)
        embed.add_field(name="🔗 Ссылки",
                        value=
                        "[Добавить бота](https://discord.com/oauth2/authorize?client_id=1284123685690802269&permissions=8&integration_type=0&scope=applications.commands+bot)\n"
                        "[Сервер поддержки](https://discord.gg/cmc6DNhKKK)\n"+
                        "[Мой разработчик](https://discord.com/users/619946431452807189/)\n"+
                        "[Политика конфиденциальности](https://github.com/RanVix/RannyBot/blob/main/PrivacyPolicy.md)\n"+
                        "[Top.gg](https://top.gg/bot/1284123685690802269)\n"+
                        "[Discords.com](https://discords.com/bots/bot/1284123685690802269)\n"+
                        "[Discordbotlist](https://discord.ly/rannybot)\n"+
                        "[Discord Bots List](https://bots.server-discord.com/1284123685690802269)\n"+
                        "[Boticord](https://boticord.top/bot/1284123685690802269?l=ru)",
                        inline=False)
        embed.set_footer(text="Моя версия: 2.3.4")
        embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        embed.set_thumbnail(url=interaction.me.avatar.url)
        await interaction.send(embed=embed)

    @commands.slash_command(name="warnson", description="Поможет узнать, сколько на вас варнов.")
    async def warnson(self, interaction: disnake.ApplicationCommandInteraction, user: disnake.User = None):
        if user is None:
            user=interaction.author
        row = await self.bot.loop.run_in_executor(self.executor, self.fetch_warns, user.id)
        if row is None or row[0] == 0:
            embedif0 = disnake.Embed(title="Количество варнов на пользователе: ",
                                  description=f"{user.mention} не имеет варнов.", colour=disnake.Color.orange())
            embedif0.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedif0, delete_after=10)
        else:
            warn_count = row[0]
            embed = disnake.Embed(title="Количество варнов на пользователе: ",
                                     description=f"{user.mention} имеет {warn_count} варн(а).", colour=disnake.Color.orange())
            embed.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embed, delete_after=10)


def setup(bot):
    bot.add_cog(BotInfoCommands(bot))