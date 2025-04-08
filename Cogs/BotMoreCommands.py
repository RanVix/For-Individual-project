from typing import Union
import disnake
from disnake.ext import commands
import requests
import xml.etree.ElementTree as ET

class BotMoreCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @commands.slash_command(name='curs', description='Получить актуальный курс валют к рублю.')
    async def curs(self, interaction: disnake.CommandInteraction):
        url = 'https://www.cbr.ru/scripts/XML_daily.asp'
        try:
            response = requests.get(url)
            response.raise_for_status()

            root = ET.fromstring(response.content)

            currencies_of_interest = {
                "Доллар": "USD",
                "Евро": "EUR",
                "Юань": "CNY",
                "Лира": "TRY",
                "Гривна": "UAH",
                "Белорусские рубли": "BYN"
            }

            embed = disnake.Embed(title="Актуальный курс валют к рублю: ", color=disnake.Color.orange())
            embed.set_footer(text="Данные ЦБ РФ.")

            for currency in root.findall('Valute'):
                name = currency.find('Name').text
                value = currency.find('Value').text.replace(',', '.')
                code = currency.find('CharCode').text

                if code in currencies_of_interest.values():
                    embed.add_field(name=f"{name} ({code})", value=f"{value} руб.", inline=False)

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            embedEr = disnake.Embed(title="Ошибка!😥",colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            print(f'Произошла ошибка в /curs: {str(e)}')

    @commands.slash_command(name='avatar', description='Получить аватар пользователя.')
    async def avatar(self, interaction: disnake.CommandInteraction, user: Union[disnake.Member, disnake.User] = None):
        user = user or interaction.user

        avatar_url = user.avatar.url if user.avatar else None

        if avatar_url:
            embed = disnake.Embed(title=f"Аватар пользователя {user.name}", color=disnake.Color.orange(),
                                  description=f"[🔗 Ссылка на аватарку]({user.display_avatar.url})")
            embed.set_image(url=avatar_url)
            await interaction.response.send_message(embed=embed)
        else:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="У данного пользователя нет аватара!",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)


    @commands.slash_command(name='banner', description='Получить баннер пользователя.', breif='Получить баннер пользователя.', usage="banner <@пользователь>")
    async def banner(self, interaction: disnake.ApplicationCommandInteraction, user: Union[disnake.Member, disnake.User] = None):
        user = user or interaction.user
        user = await self.bot.fetch_user(user.id)
        if not user.banner:
            embed = disnake.Embed(title="Ошибка баннера😥", description="У пользователя нет баннера!", color=disnake.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        embed = disnake.Embed(title=f"Баннер {user}:",
                                description=f"[🔗 Ссылка на баннер]({user.banner.url})", color=disnake.Color.orange())
        embed.set_image(url=user.banner.url)
        await interaction.response.send_message(embed=embed)

def setup(bot):
    bot.add_cog(BotMoreCommands(bot))