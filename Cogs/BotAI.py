import disnake
from disnake.ext import commands
import aiohttp
import asyncio
from deep_translator import GoogleTranslator
import asyncio
from g4f.client import Client
import sys
import os

LOG_CHANNEL_ID = 1298679265809924096

class BotAiCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.slash_command(name="ask", description="Спросите вопрос у нейросети. А она ответит и поможет вам.")
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def ask(self, ctx, *, question: str):
        embedGeneration = disnake.Embed(
            title="Генерация ответа на ваш вопрос началась:🎰",
            description="Ожидайте...⏰",
            colour=disnake.Color.orange()
        )
        embedGeneration.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embedGeneration)

        try:
            async def get_ai_response():
                client = Client()
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": question}],
                        web_search=False
                    )
                )
                sys.stdout = sys.__stdout__
                response_text = response.choices[0].message.content
                # Удаляем строку с логином, если она есть
                if response_text.startswith("[[Login to OpenAI ChatGPT]]()"):
                    response_text = response_text.replace("[[Login to OpenAI ChatGPT]]()\n", "")
                return "\n".join(response_text.split("\n"))

            chat_gpt_response = await get_ai_response()
        except Exception as e:
            chat_gpt_response = "Извините, произошла ошибка."

        print(chat_gpt_response)

        embedAnswer = disnake.Embed(
            description=chat_gpt_response,
            title="Ответ от ИИ:💻",
            colour=disnake.Color.orange()
        )
        embedAnswer.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
        await ctx.send(embed=embedAnswer)

        log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = disnake.Embed(
                title="Лог команды",
                description=f"**ID пользователя:** {ctx.author.id}\n"
                            f"**Имя пользователя:** {ctx.author.name}\n"
                            f"**Сервер:** {ctx.guild.name}\n"
                            f"**Вопрос:** {question}\n"
                            f"**Ответ ИИ:** {chat_gpt_response}",
                colour=disnake.Color.orange()
            )
            if ctx.guild.icon:
                log_embed.set_thumbnail(url=ctx.guild.icon.url)
            await log_channel.send(embed=log_embed)
        else:
            print("Канал для логов не найден.")

    # @commands.slash_command(name="ask", description="Спросите вопрос у нейросети. А она ответит и поможет вам.")
    # async def ask(self, ctx, *, question: str):
    #     embedDisabled = disnake.Embed(
    #         title="Извините, но команда временно отключена...😥",
    #         description="Извините, но в настоящее время команда 'ask' недоступна. Сервис, через который она работала к сожалению не доступен. Я постоянно проверяю его и при первой возможности сразу "
    #                     "верну команду! Подробнее читайте в канале с новостями бота. Из-за того, что я живу в России, то альтернатив к сожалению довольно мало. Прошу понять и простить",
    #         colour=disnake.Color.red()
    #     )
    #     embedDisabled.set_author(name="Ranny", icon_url=ctx.me.avatar.url)

    #     await ctx.send(embed=embedDisabled)


    @commands.slash_command(name="imagine", description="Генерирует любое изображение по вашему заказу.")
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def imagine(self, ctx, *, prompt: str):
        log_channel_id = 1298679265809924096
        prompt = GoogleTranslator(source='auto', target="en").translate(prompt)
        API_KEY = "53rbb_cp3MqgekjoxJJKLQ"
        payload = {
            'models': ['Anything Diffusion'],
            "prompt": prompt,
            "params": {
                "width": 512,
                "height": 512,
                "steps": 30,
                "sampler_name": "k_lms"
            },
            "nsfw": False,
            "censor_nsfw": True,
            "trusted_workers": True
        }
        headers = {
            "apikey": API_KEY,
            "Content-Type": "application/json"
        }

        await ctx.response.defer()

        async with aiohttp.ClientSession() as session:
            async with session.post("https://stablehorde.net/api/v2/generate/async", json=payload,
                                    headers=headers) as response:
                if response.status == 202:
                    embedGeneration = disnake.Embed(
                        title="Генерирую изображение...✨", description="Обычно это занимает не больше минуты ⏰")
                    embedGeneration.set_author(name="Ranny", icon_url=ctx.me.avatar.url)

                    await ctx.edit_original_response(embed=embedGeneration)
                    data = await response.json()
                    request_id = data.get("id")
                    print("ID вашего запроса:", request_id)
                else:
                    embederror = disnake.Embed(
                        title="Ошибка!😭")
                    embederror.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                    await ctx.edit_original_response(embed=embederror)
                    return

            while True:
                async with session.get(f"https://stablehorde.net/api/v2/generate/status/{request_id}",
                                       headers=headers) as status_response:
                    status_data = await status_response.json()

                    if status_data.get("done"):
                        image_url = status_data['generations'][0]['img']
                        if image_url:
                            await ctx.send(content=image_url)
                            await self.log_generation(ctx, prompt, image_url, log_channel_id)
                        else:
                            embedError2 = disnake.Embed(
                                title="Не удалось получить изображение.😥")
                            embedError2.set_author(name="Ranny", icon_url=ctx.me.avatar.url)
                            await ctx.edit_original_response(embed=embedError2)
                        break
                    else:
                        await asyncio.sleep(10)


    async def log_generation(self, ctx, prompt, image_url, log_channel_id):
        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel:
            embed = disnake.Embed(title="Лог генерации", color=disnake.Color.orange(),
            description=f'**ID пользователя:** {ctx.author.id}\n'
                        f'**Имя пользователя:** {ctx.author.name}\n'
                        f'**Сервер:** {ctx.guild.name}\n'
                        f'**Запрос:** {prompt}\n')
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            await log_channel.send(embed=embed)
            await  log_channel.send(image_url)


def setup(bot):
    bot.add_cog(BotAiCommands(bot))
