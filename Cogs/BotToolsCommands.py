import disnake
from disnake.ext import commands
import random
from deep_translator import GoogleTranslator
import segno
import os
import tempfile

class BotToolsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @commands.slash_command(name="random", description="Выводит рандомное число в заданном диапозоне.")
    async def random(self, interaction: disnake.CommandInteraction, min: int, max: int):
        if min >= max:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description="Начальное значение должно быть меньше конечного.",
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return
        number = random.randint(min, max)
        embedEr = disnake.Embed(title="Случайное число🎰",
                                description=f'Случайное число от {min} до {max}: {number}',
                                colour=disnake.Color.orange())
        embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
        await interaction.send(embed=embedEr)

    @commands.slash_command(name='translate', description='Переведет текст на указанный язык.')
    async def translate(self, interaction: disnake.CommandInteraction, text: str, dest_language: str):
        await interaction.response.defer()

        # Список поддерживаемых языковых кодов
        supported_languages = ['en', 'es', 'fr', 'de', 'ru', 'zh', 'ja', 'it']  # и другие

        if dest_language not in supported_languages:
            embedEr = disnake.Embed(title="Ошибка!😥",
                                    description=f'Некорректный языковой код: {dest_language}. Пожалуйста, используйте один из следующих кодов: {", ".join(supported_languages)}.',
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            return

        try:
            translated = GoogleTranslator(source='auto', target=dest_language).translate(text)

            embedEr = disnake.Embed(title="Перевод🔊",
                                    description=f'Переведенный текст: {translated}',
                                    colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr)
        except Exception as e:
            embedEr = disnake.Embed(title="Ошибка!😥", colour=disnake.Color.orange())
            embedEr.set_author(name="Ranny", icon_url=interaction.me.avatar.url)
            await interaction.send(embed=embedEr, ephemeral=True)
            print(f'Произошла ошибка при переводе: {str(e)}')


    @commands.slash_command(name='qrcode', description='Создает qrcode из вашего текста!')
    async def qrcode_command(self, interaction: disnake.ApplicationCommandInteraction, text: str):
        qr = segno.make(text, error='h')

        tmp_file_path = os.path.join(tempfile.gettempdir(), "qrcode.png")
        qr.save(tmp_file_path, scale=4)

        await interaction.send("Вот ваш QR-код:", file=disnake.File(tmp_file_path))

        os.remove(tmp_file_path)

def setup(bot):
    bot.add_cog(BotToolsCommands(bot))