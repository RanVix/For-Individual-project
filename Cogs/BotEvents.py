import disnake
from disnake.ext import commands, tasks
from disnake.ext.commands import BotMissingPermissions


class BotEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(minutes=20)
    async def update_status(self):
        users = sum(len(guild.members) for guild in self.bot.guilds)
        await self.bot.change_presence(status=disnake.Status.online, activity=disnake.Game(f'📊Наблюдаю за {users} людьми, а в частности за их безопасностью!🔗 | /help'))

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Бот {self.bot.user} готов к работе!')
        self.update_status.start()


    #Обработчик ошибок!
    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx, error):
        print(error)
        if isinstance(error, commands.CommandOnCooldown):
            embed = disnake.Embed(title="Ошибка!😥",
                                    description=f"{ctx.author}, команда уже была использована на сервере. Подождите! (на /imagine задержка 60 секунд, на /ask 30 секунд)⏰",
                                    colour=disnake.Color.red())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, commands.MissingPermissions):
            embed = disnake.Embed(title="Ошибка!😥",
                                    description=f"{ctx.author}, у вас недостаточно прав для выполнения этой команды!😥",
                                    colour=disnake.Color.red())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
        elif isinstance(error, BotMissingPermissions):
            embed = disnake.Embed(title="Ошибка!😥",
                                    description="У меня недостаточно прав для выполнения этой команды!😰",
                                    colour=disnake.Color.red())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)
        else:
            embed = disnake.Embed(description="**Неизвестная ошибка!**🧰",
                                    colour=disnake.Color.red())
            embed.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
            await ctx.send(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(BotEvents(bot))