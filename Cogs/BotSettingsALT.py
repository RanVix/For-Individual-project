import disnake
from disnake.ext import commands
import sqlite3
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta



class BotSettingsALT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_connection = self.create_database_connection()
        self.create_table()
        self.message_count = defaultdict(list)

    def create_database_connection(self):
        db_path = 'bot_db.sqlite'
        return sqlite3.connect(db_path)

    def create_table(self):
        cursor = self.db_connection.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER,
            initial_role TEXT,
            welcome_channel TEXT,
            initial_role_enabled BOOLEAN,
            welcome_enabled BOOLEAN,
            role_id INTEGER
            )
             ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS filters (
            guild_id INTEGER,
            word TEXT,
            PRIMARY KEY (guild_id, word)
            )
             ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS spam_settings (
            guild_id INTEGER PRIMARY KEY,
            max_messages INTEGER,
            time_frame INTEGER,
            is_spam_filter_enabled INTEGER
            )
             ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS caps_settings (
            guild_id INTEGER PRIMARY KEY,
            caps_percentage INTEGER DEFAULT 50,
            caps_filter_enabled BOOLEAN DEFAULT 0
            )
             ''')

        self.db_connection.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        await self.check_caps(message)

        conn = sqlite3.connect('bot_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT is_spam_filter_enabled, max_messages, time_frame FROM spam_settings WHERE guild_id=?",
                       (message.guild.id,))
        result = cursor.fetchone()

        if result:
            is_enabled, max_messages, time_frame = result
            if is_enabled == 0:
                return

            if await self.is_user_exempt(message, message.author):
                return

            await self.handle_spam_filter(message, max_messages, time_frame)

        await self.check_and_delete_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return
        await self.check_and_delete_message(after)
        await self.check_caps(after)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        conn = None
        try:
            conn = sqlite3.connect('bot_db.sqlite')
            cursor = conn.cursor()

            cursor.execute(
                "SELECT welcome_channel, welcome_enabled, initial_role, initial_role_enabled FROM settings WHERE guild_id = ?",
                (str(member.guild.id),)
            )
            data = cursor.fetchone()

            if data:
                welcome_channel_id, welcome_enabled, initial_role_id, initial_role_enabled = data

                welcome_channel_id = int(welcome_channel_id) if welcome_channel_id else None
                initial_role_id = int(initial_role_id) if initial_role_id else None

                print(f"Гильдия: {member.guild.name} (ID: {member.guild.id})")
                print(f"ID канала: {welcome_channel_id}, ID роли: {initial_role_id}")

                if welcome_enabled and welcome_channel_id:
                    welcome_channel = self.bot.get_channel(welcome_channel_id)
                    if welcome_channel:
                        try:
                            embed = disnake.Embed(title="Добро пожаловать!", description=f"Пользователь {member.mention}, зашел на сервер **{member.guild.name}**!" , color=disnake.Color.orange())
                            await welcome_channel.send(embed=embed)
                        except Exception as e:
                            print(f"Ошибка при отправке сообщения в канал приветствия: {e}")
                    else:
                        print(f"Канал с ID {welcome_channel_id} не найден.")

                if initial_role_enabled and initial_role_id:
                    role = member.guild.get_role(initial_role_id)
                    if role:
                        try:
                            await member.add_roles(role)
                        except Exception as e:
                            print(f"Ошибка при выдаче роли {role.name} участнику {member.name}: {e}")
                    else:
                        print(f"Роль с ID {initial_role_id} не найдена на сервере {member.guild.name}.")
            else:
                pass

        except sqlite3.Error as db_error:
            print(f"Ошибка при работе с базой данных: {db_error}")
        except Exception as e:
            print(f"Общая ошибка: {e}")
        finally:
            if conn:
                conn.close()

    async def is_user_exempt(self, message, user):
        guild_id = message.guild.id
        exempt_roles = self.get_exempt_roles(guild_id)

        # Проверка на наличие исключенной роли у пользователя
        if any(role.id in exempt_roles for role in user.roles):
            return True  # Пользователь исключен

        # Проверка на наличие роли в базе данных
        conn = sqlite3.connect('bot_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT role_id FROM settings WHERE guild_id=?", (guild_id,))
        result = cursor.fetchone()

        if result:
            role_id = result[0]
            if role_id is not None:
                role = message.guild.get_role(role_id)
                if role and role in user.roles:
                    print(f"{user.name} имеет роль {role.name}, игнорирование спам-фильтра.")
                    return True  # Игнорируем пользователя
                else:
                    print(f"{user.name} не имеет роли с ID {role_id}.")
        else:
            print(f"Не удалось найти роль для сервера {guild_id}. Возможно, она не была настроена.")

        return False  # Пользователь не исключен, можно продолжать обработку

    @commands.slash_command(name="show_settings", description="Посмотреть активные настройки бота.")
    @commands.has_permissions(manage_guild=True)
    async def show_settings(self, interaction: disnake.CommandInteraction):
        conn = sqlite3.connect('bot_db.sqlite')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM settings WHERE guild_id = ?", (interaction.guild.id,))
        settings = cursor.fetchone()

        if not settings:
            cursor.execute(
                "INSERT INTO settings (guild_id, initial_role, welcome_channel, initial_role_enabled, welcome_enabled) VALUES (?, ?, ?, ?, ?)",
                (interaction.guild.id, None, None, False, False))
            conn.commit()
            settings = (interaction.guild.id, None, None, False, False)

        cursor.execute("SELECT COUNT(*) FROM filters WHERE guild_id = ?", (interaction.guild.id,))
        has_filters = cursor.fetchone()[0] > 0

        cursor.execute("SELECT is_spam_filter_enabled FROM spam_settings WHERE guild_id = ?", (interaction.guild.id,))
        spam_setting = cursor.fetchone()
        is_spam_enabled = spam_setting[0] if spam_setting else 0

        cursor.execute("SELECT caps_filter_enabled FROM caps_settings WHERE guild_id = ?", (interaction.guild.id,))
        caps_setting = cursor.fetchone()
        is_caps_enabled = caps_setting[0] if caps_setting else 0

        chat_protection_enabled = has_filters or is_spam_enabled or is_caps_enabled

        embed = disnake.Embed(title="⚙ | Настройки бота на сервере", color=disnake.Color.orange())
        embed.add_field(name="Начальная роль:", value="Включена:white_check_mark:" if settings[3] else "Выключена:x:",
                        inline=False)
        embed.add_field(name="Приветствие новых участников:",
                        value="Включено:white_check_mark:" if settings[4] else "Выключена:x:", inline=False)
        embed.add_field(name="Защита чата:",
                        value="Включена:white_check_mark:" if chat_protection_enabled else "Выключена:x:", inline=False)
        embed.set_footer(text="⚠ | Используйте кнопку ниже, чтобы изменить настройки.")

        await interaction.send(embed=embed, ephemeral=True)


    @commands.slash_command(name="set_start_role", description="Настроить начальную роль, для тех, кто заходит на сервер!")
    @commands.has_permissions(manage_guild=True)
    async def set_start_role(self, interaction: disnake.CommandInteraction):
        await interaction.response.defer()
        role_select = disnake.ui.RoleSelect(placeholder="Выберите роль...")

        async def select_callback(interaction: disnake.MessageInteraction):
            await interaction.response.defer()
            role = role_select.values[0]

            if interaction.user.guild_permissions.manage_guild:
                selected_role_id = role.id

                # Проверка прав бота
                bot_member = interaction.guild.me
                if not bot_member.guild_permissions.manage_roles:
                    await interaction.followup.send("У бота недостаточно прав для управления ролями.", ephemeral=True,
                                                    delete_after=5)
                    return

                # Проверка иерархии ролей
                if role.position >= bot_member.top_role.position:
                    await interaction.followup.send("Выбранная роль выше роли бота в иерархии.", ephemeral=True,
                                                    delete_after=5)
                    return

                conn = sqlite3.connect('bot_db.sqlite')
                cursor = conn.cursor()

                cursor.execute("SELECT initial_role_enabled, initial_role FROM settings WHERE guild_id = ?",
                               (interaction.guild.id,))
                result = cursor.fetchone()

                if result is None:
                    cursor.execute(
                        "INSERT INTO settings (guild_id, initial_role, initial_role_enabled) VALUES (?, ?, ?)",
                        (interaction.guild.id, selected_role_id, True))
                    response_message = disnake.Embed(title="Начальная роль успешно включена!", color=disnake.Color.orange())
                else:
                    initial_role_enabled, current_role = result
                    if not initial_role_enabled:
                        cursor.execute(
                            "UPDATE settings SET initial_role = ?, initial_role_enabled = ? WHERE guild_id = ?",
                            (selected_role_id, True, interaction.guild.id))
                        response_message = disnake.Embed(title="Начальная роль успешно обновлена!", color=disnake.Color.orange())
                    else:
                        response_message = disnake.Embed(title="Начальная роль уже включена! Выключите и включите функцию для смены роли.", color=disnake.Color.orange())

                try:
                    await interaction.followup.send(embed=response_message, ephemeral=True, delete_after=5)
                except disnake.NotFound:
                    print("Ошибка: Вебхук не найден. Проверьте настройки вебхука в Discord.")
                except Exception as e:
                    print(f"Произошла другая ошибка: {e}")

                conn.commit()
                conn.close()
            else:
                await interaction.followup.send("У вас нет прав для выбора роли!", ephemeral=True, delete_after=5)

        role_select.callback = select_callback

        disable_button = disnake.ui.Button(label="Выключить начальную роль", style=disnake.ButtonStyle.danger)

        async def disable_callback(interaction: disnake.MessageInteraction):
            if interaction.user.guild_permissions.manage_guild:
                conn = sqlite3.connect('bot_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("SELECT initial_role_enabled, initial_role FROM settings WHERE guild_id = ?",
                               (interaction.guild.id,))
                result = cursor.fetchone()

                if result is None:
                    await interaction.response.send_message("Настройки для этого сервера не найдены.", ephemeral=True,
                                                            delete_after=5)
                    conn.close()
                    return

                initial_role_enabled, current_role = result

                if not initial_role_enabled:
                    await interaction.response.send_message("Начальная роль уже отключена!", ephemeral=True,
                                                            delete_after=5)
                    conn.close()
                    return

                cursor.execute("UPDATE settings SET initial_role_enabled = ?, initial_role = NULL WHERE guild_id = ?",
                               (False, interaction.guild.id))

                try:
                    success_embed = disnake.Embed(title="Функция успешно отключена!", color=disnake.Color.orange())
                    await interaction.response.send_message(embed=success_embed, ephemeral=True)
                except Exception as e:
                    print(f"Произошла ошибка при отправке сообщения: {e}")

                conn.commit()
                conn.close()
            else:
                await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                        delete_after=5)

        disable_button.callback = disable_callback

        view = disnake.ui.View(timeout=60)
        view.add_item(role_select)
        view.add_item(disable_button)

        embed = disnake.Embed(title="👀 | Выберите начальную роль", color=disnake.Color.orange())
        embed.add_field(name="Как пользоваться", value='В выпадающем меню выберите необходимую вам роль. После она автоматически '
                                                       'будет выдаваться пользователям как "начальная". Для выключения функции нажмите'
                                                       ' соответствующую кнопку.')
        embed.set_footer(text="⚠ | Выберите опцию, для настройки начальной роли")
        await interaction.send(embed=embed, view=view)


    @commands.slash_command(name="set_welcome_channel", description="Настроить канал, для приветствия!")
    @commands.has_permissions(manage_guild=True)
    async def set_welcome_channel(self, interaction: disnake.CommandInteraction):
        await interaction.response.defer()

        select = disnake.ui.ChannelSelect(placeholder="Выберите канал для приветствия...")

        async def select_callback(interaction):
            if interaction.user.guild_permissions.manage_guild:
                selected_channel = select.values[0]
                selected_channel_id = int(selected_channel.id)

                bot_member = interaction.guild.me
                if not selected_channel.permissions_for(bot_member).send_messages:
                    await interaction.response.send_message("У бота нет прав на отправку сообщений в выбранный канал.", ephemeral=True)
                    return

                conn = sqlite3.connect('bot_db.sqlite')
                cursor = conn.cursor()

                cursor.execute("SELECT welcome_enabled FROM settings WHERE guild_id = ?", (interaction.guild.id,))
                result = cursor.fetchone()

                if result:
                    enabled = result[0]

                    if not enabled:
                        cursor.execute(
                            "UPDATE settings SET welcome_channel = ?, welcome_enabled = ? WHERE guild_id = ?",
                            (selected_channel_id, True, interaction.guild.id))
                        embed = disnake.Embed(title="Приветствие новых участников успешно включено!", color=disnake.Color.orange())
                        await interaction.response.send_message(embed=embed)
                    else:
                        embed = disnake.Embed(title="Приветствие уже включено! Выключите его перед выбором нового канала.",
                                              color=disnake.Color.red())
                        await interaction.response.send_message(embed=embed)
                else:
                    cursor.execute("INSERT INTO settings (guild_id, welcome_channel, welcome_enabled) VALUES (?, ?, ?)",
                                   (interaction.guild.id, selected_channel_id, True))
                    embed = disnake.Embed(title="Приветствие новых участников успешно включено!",
                                          color=disnake.Color.orange())
                    await interaction.response.send_message(embed=embed)

                conn.commit()
                conn.close()
            else:
                await interaction.response.send_message("У вас нет прав для выбора канала!", ephemeral=True)

        select.callback = select_callback

        disable_button = disnake.ui.Button(label="Выключить приветствие", style=disnake.ButtonStyle.danger)

        async def disable_callback(interaction: disnake.MessageInteraction):
            if interaction.user.guild_permissions.manage_guild:
                conn = sqlite3.connect('bot_db.sqlite')
                cursor = conn.cursor()

                cursor.execute("SELECT welcome_enabled FROM settings WHERE guild_id = ?", (interaction.guild.id,))
                result = cursor.fetchone()

                if result:
                    enabled = result[0]
                    if enabled:
                        cursor.execute(
                            "UPDATE settings SET welcome_enabled = ?, welcome_channel = NULL WHERE guild_id = ?",
                            (False, interaction.guild.id))
                        embed = disnake.Embed(title="Приветствие новых участников успешно отключено!",
                                              color=disnake.Color.orange())
                        await interaction.response.send_message(embed=embed)
                    else:
                        embed = disnake.Embed(title="Приветствие новых участников уже отключено!",
                                              color=disnake.Color.red())
                        await interaction.response.send_message(embed=embed)
                else:
                    embed = disnake.Embed(title="настройки для этого сервера не найдены!",
                                          color=disnake.Color.red())
                    await interaction.response.send_message(embed=embed)

                conn.commit()
                conn.close()
            else:
                await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                        delete_after=5)

        disable_button.callback = disable_callback

        view = disnake.ui.View(timeout=60)
        view.add_item(select)
        view.add_item(disable_button)

        embed = disnake.Embed(title="🤗 | Выберите канал для приветствия:", color=disnake.Color.orange())
        embed.set_footer(
            text="⚠ | Выберите канал для приветствия новых участников. Здесь же вы можете отключить эту функцию.")
        await interaction.send(embed=embed, view=view)

    @commands.slash_command(name="set_admin_roles", description="Настроить роли админов! на них не влияют большинство ограничений бота!")
    @commands.has_permissions(manage_guild=True, manage_roles=True)
    async def set_admin_roles(self, interaction: disnake.CommandInteraction):
        await self.set_admin_func(interaction)

    async def set_admin_func(self, interaction: disnake.CommandInteraction, from_command: bool = True):
        await interaction.response.defer()
        guild_id = interaction.guild.id
        embed = disnake.Embed(title="😎 | Выбор ролей администраторов: ", color=disnake.Color.orange())
        embed.set_footer(text="⚠ | Выберите действие:")
        selected_roles_ids = self.get_roles(guild_id)
        selected_roles = ", ".join([f"<@&{role_id}>" for role_id in selected_roles_ids if interaction.guild.get_role(
            role_id)]) if selected_roles_ids else "Нет выбранных ролей."
        embed.add_field(name="Выбранные роли:", value=selected_roles, inline=False)

        button_select = disnake.ui.Button(label="Выбрать роли", style=disnake.ButtonStyle.secondary)
        button_remove = disnake.ui.Button(label="Удалить роль", style=disnake.ButtonStyle.danger)

        button_select.callback = self.select_role
        button_remove.callback = self.remove_role

        view = disnake.ui.View(timeout=60)
        view.add_item(button_select)
        view.add_item(button_remove)

        if from_command:
            await interaction.send(embed=embed, view=view)
        else:
            await interaction.message.edit(embed=embed, view=view)

    def get_roles(self, guild_id):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT role_id FROM settings WHERE guild_id = ?', (guild_id,))
        return [row[0] for row in cursor.fetchall()]

    async def select_role(self, interaction: disnake.MessageInteraction):
        if interaction.user.guild_permissions.manage_guild:
            roles = interaction.guild.roles
            options = [disnake.SelectOption(label=role.name, value=str(role.id)) for role in roles if
                       role.name != "@everyone"]

            if len(options) == 0:
                embed = disnake.Embed(title="Нет доступных ролей для выбора.", color=disnake.Color.red())
                await interaction.response.send_message(embed=embed)
                return

            select = disnake.ui.RoleSelect(placeholder="Выберите роли...", max_values=25, min_values=1)
            back_button = disnake.ui.Button(label="Назад", style=disnake.ButtonStyle.danger)
            back_button.callback = self.select_back

            async def select_callback(interaction: disnake.MessageInteraction):
                if interaction.user.guild_permissions.manage_guild:
                    selected_ids = [int(role_id.id) for role_id in select.values]
                    guild_id = interaction.guild.id

                    added_names = []
                    for role_id in selected_ids:
                        if self.add_role_to_db(guild_id, role_id):
                            added_names.append(next(role.name for role in roles if role.id == role_id))
                        else:
                            await interaction.response.send_message("Выбранные вами роли уже добавлены!",
                                                                    ephemeral=True)

                    if added_names:
                        await interaction.response.send_message(
                            f"Роли {', '.join(added_names)} добавлены как администраторы.",
                            ephemeral=True)
                else:
                    await interaction.response.send_message("У вас нет прав для использования меню!", ephemeral=True,
                                                            delete_after=5)

            select.callback = select_callback
            view = disnake.ui.View(timeout=60)
            view.add_item(select)
            view.add_item(back_button)

            embed = disnake.Embed(title="Выбор роли для добавления✅: ", color=disnake.Color.orange())
            embed.set_footer(text="Выберите роли, а после закройте выпадающее меню, для сохранения💫:")
            await interaction.message.delete()
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                    delete_after=5)


    def add_role_to_db(self, guild_id, role_id):
        cursor = self.db_connection.cursor()

        cursor.execute('SELECT COUNT(*) FROM settings WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
        exists = cursor.fetchone()[0] > 0

        if exists:
            return False

        try:
            cursor.execute('INSERT INTO settings (guild_id, role_id) VALUES (?, ?)', (guild_id, role_id))
            self.db_connection.commit()
            return True
        except sqlite3.IntegrityError:
            return False


    async def remove_role(self, interaction: disnake.MessageInteraction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                    delete_after=5)
            return

        guild_id = interaction.guild.id
        roles = self.get_roles(guild_id)

        if not roles:
            await interaction.response.send_message("Нет ролей для удаления.", ephemeral=True)
            return


        options = []
        for role_id in roles:
            role = interaction.guild.get_role(role_id)
            if role:
                options.append(disnake.SelectOption(label=role.name, value=str(role_id)))

        if not options:
            await interaction.response.send_message("Нет доступных ролей для удаления.", ephemeral=True)
            return

        select = disnake.ui.Select(placeholder="Выберите роли для удаления...", options=options)

        back_button = disnake.ui.Button(label="Назад", style=disnake.ButtonStyle.danger)
        back_button.callback = lambda inter: self.go_back(inter)


        async def select_callback(interaction: disnake.MessageInteraction):
            selected_role_ids = [int(role_id) for role_id in select.values]
            removed_roles = []

            for selected_role_id in selected_role_ids:
                if self.remove_role_from_db(guild_id, selected_role_id):
                    removed_roles.append(f"<@&{selected_role_id}>")

            if removed_roles:
                await interaction.response.send_message(f"Роли {', '.join(removed_roles)} удалены.", ephemeral=True)
            else:
                await interaction.response.send_message("Ошибка: выбранные роли не найдены в базе данных.",
                                                        ephemeral=True)

        select.callback = select_callback

        view = disnake.ui.View(timeout=60)
        view.add_item(select)
        view.add_item(back_button)

        embed = disnake.Embed(title="Выбор ролей для удаления❌: ", color=disnake.Color.orange())
        embed.set_footer(text="Выберите роли, а после закройте выпадающее меню, для сохранения:")

        try:
            await interaction.message.edit(embed=embed, view=view)
        except Exception as e:
            print(f"Ошибка при отправке сообщения: {e}")
            await interaction.response.send_message("Произошла ошибка при отображении меню.", ephemeral=True)


    def remove_role_from_db(self, guild_id, role_id):
        cursor = self.db_connection.cursor()
        cursor.execute('DELETE FROM settings WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
        self.db_connection.commit()
        return cursor.rowcount > 0

    async def go_back(self, interaction):
        if interaction.user.guild_permissions.manage_guild:
            await self.set_admin_func(interaction, False)
        else:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                    delete_after=5)

    async def select_back(self, interaction):
        if interaction.user.guild_permissions.manage_guild:
            await self.set_admin_func(interaction, False)
        else:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                    delete_after=5)


    @commands.slash_command(name="set_filter_words", description="Настроить роли слова, которые будет блокировать бот.")
    @commands.has_permissions(manage_guild=True)
    async def set_filter_words(self, interaction: disnake.CommandInteraction):
        if interaction.user.guild_permissions.manage_guild:
            current_filters = self.get_filters(interaction.guild.id)
            filters_display = ", ".join(current_filters) if current_filters else "Нет установленных фильтров."

            input_field = disnake.ui.TextInput(
                label="Запрещённые слова",
                placeholder="Введите слова, через ',' (например: слово1, слово2)",
                required=False,
                max_length=200,
                custom_id="forbidden_words_input"
            )

            remove_field = disnake.ui.TextInput(
                label="Удалить слова",
                placeholder="Введите слова, которые нужно удалить, через ',' (например: слово1, слово2)",
                required=False,
                max_length=200,
                custom_id="remove_words_input"
            )

            modal = disnake.ui.Modal(
                title="Настройка фильтров чата🔒",
                components=[input_field, remove_field]
            )

            await interaction.response.send_modal(modal)

            embed = disnake.Embed(title="Текущие фильтры", description=filters_display, color=disnake.Color.orange())
            await interaction.followup.send(embed=embed, ephemeral=True)

            def check(m):
                return m.user == interaction.user and m.channel == interaction.channel

            try:
                modal_interaction = await self.bot.wait_for('modal_submit', check=check, timeout=120)

                words_to_add = [word.strip().lower() for word in
                                modal_interaction.text_values.get("forbidden_words_input", "").split(',')]
                added_words = []
                for word in words_to_add:
                    if word:
                        if self.add_filter_to_db(interaction.guild.id, word):
                            added_words.append(word)
                        else:
                            await modal_interaction.send(f"Слово '{word}' уже существует в фильтрах.", ephemeral=True)

                if added_words:
                    await modal_interaction.send(f"Слова '{', '.join(added_words)}' добавлены в фильтры.",
                                                 ephemeral=True)

                words_to_remove = [word.strip().lower() for word in
                                   modal_interaction.text_values.get("remove_words_input", "").split(',')]
                removed_words = []
                for word in words_to_remove:
                    if word:
                        print(
                            f"Попытка удалить слово: '{word}' из фильтров для сервера {interaction.guild.id}.")  # Отладочное сообщение
                        if self.remove_filter_from_db(interaction.guild.id, word):
                            removed_words.append(word)
                        else:
                            await modal_interaction.send(f"Слово '{word}' не найдено в фильтрах.", ephemeral=True)

                if removed_words:
                    await modal_interaction.send(f"Слова '{', '.join(removed_words)}' удалены из фильтров.",
                                                 ephemeral=True)
                else:
                    await modal_interaction.send(
                        f"Ничего не удалено.",
                        ephemeral=True, delete_after=2)

            except asyncio.TimeoutError:
                print("Время ожидания истекло!")
        else:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True, delete_after=5)


    def get_filters(self, guild_id):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT word FROM filters WHERE guild_id = ?', (guild_id,))
        return [row[0] for row in cursor.fetchall()]

    def get_exempt_roles(self, guild_id):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT role_id FROM settings WHERE guild_id = ?', (guild_id,))
        return [row[0] for row in cursor.fetchall()]

    async def check_and_delete_message(self, message):
        guild_id = message.guild.id
        filters = self.get_filters(guild_id)

        exempt_roles = self.get_exempt_roles(guild_id)
        if any(role.id in exempt_roles for role in message.author.roles):
            return

        for word in filters:
            if word and word in message.content.lower():
                await message.delete()
                await message.author.send(
                    f"Ваше сообщение в {message.channel.mention} было удалено из-за наличия запрещённых слов.")
                return

    def add_filter_to_db(self, guild_id, word):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM filters WHERE guild_id = ? AND word = ?', (guild_id, word))
        exists = cursor.fetchone()[0] > 0

        if not exists:
            cursor.execute('INSERT INTO filters (guild_id, word) VALUES (?, ?)', (guild_id, word))
            self.db_connection.commit()
            print(f"Слово '{word}' добавлено в фильтры для сервера {guild_id}.")
            return True
        print(f"Слово '{word}' уже существует в фильтрах для сервера {guild_id}.")
        return False

    def remove_filter_from_db(self, guild_id, word):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM filters WHERE guild_id = ? AND word = ?', (guild_id, word))
        exists = cursor.fetchone()[0] > 0

        if exists:
            cursor.execute('DELETE FROM filters WHERE guild_id = ? AND word = ?', (guild_id, word))
            self.db_connection.commit()
            print(f"Слово '{word}' удалено из фильтров для сервера {guild_id}.")
            return True
        print(f"Слово '{word}' не найдено в фильтрах для сервера {guild_id}.")
        return False


    @commands.slash_command(name="set_spam_settings", description="Настройка спама. Сколько сообщений можно отправить за сколько-то секунд")
    @commands.has_permissions(manage_guild=True)
    async def set_spam_settings(self, interaction: disnake.CommandInteraction):
        await self.set_spam_func(interaction)

    async def set_spam_func(self, interaction: disnake.CommandInteraction, from_command: bool = True):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True,
                                                    delete_after=5)
            return

        conn = sqlite3.connect('bot_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT max_messages, time_frame, is_spam_filter_enabled FROM spam_settings WHERE guild_id=?", (interaction.guild.id,))
        result = cursor.fetchone()

        if result is None:
            max_messages = 5
            time_frame = 10
            is_spam_filter_enabled = 1
            cursor.execute(
                "INSERT INTO spam_settings (guild_id, max_messages, time_frame, is_spam_filter_enabled) VALUES (?, ?, ?, ?)",
                (interaction.guild.id, max_messages, time_frame, is_spam_filter_enabled))
            conn.commit()
        else:
            max_messages, time_frame, is_spam_filter_enabled = result

        embed = disnake.Embed(title="💻 | Настройки спам-фильтра", color=disnake.Color.orange())
        embed.add_field(name="Максимум сообщений", value=max_messages)
        embed.add_field(name="Время (сек.)⏰", value=time_frame)
        embed.add_field(name="Спам-фильтр", value="Включен🟢" if is_spam_filter_enabled else "Выключен🔴")

        set_button = disnake.ui.Button(label="Настроить", style=disnake.ButtonStyle.secondary, custom_id="configure_spam")
        enable_button = disnake.ui.Button(label="Включить спам-фильтр", style=disnake.ButtonStyle.secondary,custom_id="enable_spam_filter")
        disable_button = disnake.ui.Button(label="Отключить спам-фильтр", style=disnake.ButtonStyle.danger,custom_id="disable_spam_filter")

        async def disable_callback(interaction):
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True, delete_after=5)
                return
            cursor.execute("UPDATE spam_settings SET is_spam_filter_enabled=? WHERE guild_id=?",
                           (0, interaction.guild.id))
            conn.commit()
            await interaction.message.delete()
            await  self.set_spam_func(interaction, False)
            await interaction.response.send_message("Спам-фильтр отключен.", ephemeral=True)

        async def enable_callback(interaction):
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("У вас недостаточно прав!", ephemeral=True, delete_after=5)
                return
            cursor.execute("UPDATE spam_settings SET is_spam_filter_enabled=? WHERE guild_id=?",
                           (1, interaction.guild.id))
            conn.commit()
            await interaction.message.delete()
            await  self.set_spam_func(interaction, False)
            await interaction.response.send_message("Спам-фильтр включен.", ephemeral=True)

        disable_button.callback = disable_callback
        enable_button.callback = enable_callback

        view = disnake.ui.View(timeout=60)
        view.add_item(set_button)
        view.add_item(enable_button)
        view.add_item(disable_button)

        await interaction.send(embed=embed, view=view)


        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=60)
            max_messages, time_frame = map(int, msg.content.split(","))
            if max_messages <= 0 or time_frame <= 0:
                await interaction.send("Значения должны быть больше нуля.", ephemeral=True)
                return

            cursor.execute("UPDATE spam_settings SET max_messages=?, time_frame=? WHERE guild_id=?",
                           (max_messages, time_frame, interaction.guild.id))
            conn.commit()

            await interaction.send("Настройки успешно обновлены.", ephemeral=True)

        except ValueError:
            pass
        except asyncio.TimeoutError:
            print("Время ожидания истекло")

    async def handle_spam_filter(self, message, max_messages, time_frame):
        user_id = message.author.id
        current_time = datetime.now()

        # Удаляем устаревшие сообщения
        self.message_count[user_id] = [timestamp for timestamp in self.message_count[user_id] if
                                       timestamp > current_time - timedelta(seconds=time_frame)]

        # Добавляем текущее сообщение
        self.message_count[user_id].append(current_time)

        # Проверяем количество сообщений
        if len(self.message_count[user_id]) > max_messages:
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, прекратите спамить!",
                delete_after=1)

            muted_role = disnake.utils.get(message.guild.roles, name="Muted")

            if not muted_role:
                muted_role = await message.guild.create_role(name="Muted",reason="Создана автоматически для заморозки участников")
                await muted_role.edit(permissions=disnake.Permissions(send_messages=False, speak=False))

            if message.guild.me.top_role > muted_role:
                await message.author.add_roles(muted_role, reason="Превышение лимита сообщений")

                await asyncio.sleep(30)

                await message.author.remove_roles(muted_role, reason="Снятие мута по истечении времени")
            else:
                await message.channel.send("У меня нет разрешения на выдачу роли 'Muted'.")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            if interaction.data.get('custom_id') == "configure_spam":
                await self.open_config_modal(interaction)

    async def open_config_modal(self, interaction: disnake.Interaction):
        conn = sqlite3.connect('bot_db.sqlite')
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("У вас нет прав для изменения настроек!", ephemeral=True)
            return

        max_messages_input = disnake.ui.TextInput(
            label="Максимум сообщений",
            placeholder="Введите максимум сообщений...",
            required=True,
            max_length=10,
            custom_id="max_messages_input"
        )

        time_frame_input = disnake.ui.TextInput(
            label="Время (сек.)",
            placeholder="Введите время в секундах...",
            required=True,
            max_length=10,
            custom_id="time_frame_input"
        )

        modal = disnake.ui.Modal(
            title="Настройка спам-фильтра",
            components=[max_messages_input, time_frame_input]
        )

        await interaction.response.send_modal(modal)

        try:
            modal_interaction = await self.bot.wait_for("modal_submit", timeout=60.0)

            max_messages_str = modal_interaction.text_values["max_messages_input"]
            time_frame_str = modal_interaction.text_values["time_frame_input"]

            if not max_messages_str.isdigit() or not time_frame_str.isdigit():
                await modal_interaction.send("Пожалуйста, введите корректные числовые значения.", ephemeral=True)
                return

            max_messages = int(max_messages_str)
            time_frame = int(time_frame_str)

            if max_messages <= 0 or time_frame <= 0:
                await modal_interaction.send("Значения должны быть больше нуля.", ephemeral=True)
                return

            cursor = conn.cursor()
            cursor.execute("UPDATE spam_settings SET max_messages=?, time_frame=? WHERE guild_id=?",
                           (max_messages, time_frame, interaction.guild.id))
            conn.commit()

            await modal_interaction.send("Настройки успешно обновлены.", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.response.send_message("Время ожидания истекло. Пожалуйста, попробуйте снова.",
                                                    ephemeral=True)

    @commands.slash_command(name="set_caps_settings", description="Настройка капса. Какой процент капса допустим в сообщениях")
    @commands.has_permissions(manage_guild=True)
    async def set_caps(self, interaction: disnake.ApplicationCommandInteraction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("У вас нет прав для использования команды!", ephemeral=True,
                                                    delete_after=5)
            return
        await interaction.response.defer()
        caps_percentage, caps_filter_enabled = await self.get_caps_settings(interaction.guild.id)

        embed = disnake.Embed(title="😮 | Настройка Caps-фильтра", color=disnake.Color.orange())
        embed.add_field(name="Процент капса", value=f"{caps_percentage}%", inline=False)
        embed.add_field(name="Фильтр капса", value="Включен🟢" if caps_filter_enabled else "Выключен🔴", inline=False)

        enable_button = disnake.ui.Button(
            label="Включить фильтр",
            custom_id="enable_filter",
            style=disnake.ButtonStyle.secondary
        )

        disable_button = disnake.ui.Button(
            label="Выключить фильтр",
            custom_id="disable_filter",
            style=disnake.ButtonStyle.danger
        )

        configure_button = disnake.ui.Button(
            label="Настроить",
            custom_id="configure_filter",
            style=disnake.ButtonStyle.secondary
        )

        view = disnake.ui.View(timeout=60)
        view.add_item(configure_button)
        view.add_item(enable_button)
        view.add_item(disable_button)

        await interaction.send(embed=embed, view=view)

        async def enable_button_callback(interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("У вас нет прав для нажатия это кнопки!", ephemeral=True,
                                                        delete_after=5)
            if caps_filter_enabled:
                await interaction.response.send_message("Фильтр уже включён.", ephemeral=True)
            else:
                await self.set_caps_settings(interaction.guild.id, caps_percentage, True)
                await interaction.response.send_message("Фильтр капса включен.", ephemeral=True)

        async def disable_button_callback(interaction):
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("У вас нет прав для нажатия это кнопки!", ephemeral=True,
                                                        delete_after=5)
            if not caps_filter_enabled:
                await interaction.response.send_message("Фильтр уже выключен.", ephemeral=True)
            else:
                await self.set_caps_settings(interaction.guild.id, caps_percentage, False)
                await interaction.response.send_message("Фильтр капса выключен.", ephemeral=True)

        async def configure_button_callback(interaction):
            percentage_input = disnake.ui.TextInput(
                label="Процент капса",
                placeholder="Введите процент капса (0-100)",
                required=True,
                max_length=3,
                custom_id="caps_percentage_input",
            )

            modal = disnake.ui.Modal(
                title="Настройка Caps-фильтра",
                components=[percentage_input]
            )

            await interaction.response.send_modal(modal)

            modal_response = await self.bot.wait_for("modal_submit", check=lambda
                m: m.user == interaction.user and m.message.channel == interaction.channel)

            if modal_response.text_values:
                value = modal_response.text_values.get("caps_percentage_input")  # Получаем значение по custom_id

                if not value.isdigit():
                    await modal_response.send("Пожалуйста, введите только цифры.", ephemeral=True)
                    return

                percentage = int(value)

                if value.strip() == "":
                    await interaction.send("Ошибка: значение не может быть пустым или содержать только пробелы.",
                                           ephemeral=True)
                    return

                if percentage < 0 or percentage > 100:
                    await modal_response.send("Пожалуйста, введите число от 0 до 100.", ephemeral=True)
                    return

                await self.set_caps_settings(interaction.guild.id, percentage, caps_filter_enabled)
                await modal_response.send(f"Процент капса установлен на {percentage}%.", ephemeral=True)
            else:
                await modal_response.send("Не было введено никаких значений.", ephemeral=True)

        enable_button.callback = enable_button_callback
        disable_button.callback = disable_button_callback
        configure_button.callback = configure_button_callback

    async def get_caps_settings(self, guild_id):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT caps_percentage, caps_filter_enabled FROM caps_settings WHERE guild_id = ?', (guild_id,))
        result = cursor.fetchone()
        return result if result else (50, False)

    async def get_caps_roles(self, guild_id):
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT role_id FROM settings WHERE guild_id = ?', (guild_id,))
        roles = cursor.fetchall()
        return [role[0] for role in roles]  # Возвращаем список ID ролей

    async def check_caps(self, message: disnake.Message):
        caps_percentage, caps_filter_enabled = await self.get_caps_settings(message.guild.id)

        if not caps_filter_enabled:
            return

        total_chars = len(message.content)
        caps_chars = sum(1 for c in message.content if c.isupper())
        caps_ratio = (caps_chars / total_chars) * 100 if total_chars > 0 else 0

        caps_roles = await self.get_caps_roles(message.guild.id)
        if any(role.id in caps_roles for role in message.author.roles):
            return

        if caps_ratio > caps_percentage:
            await message.delete()

            warning_message = f"{message.author.mention}, ваше сообщение в канале {message.channel.mention} было удалено из-за превышения капса."
            try:
                await message.author.send(warning_message)
            except disnake.Forbidden:
                await message.channel.send(
                    f"{message.author.mention}, сообщение удалено за превышение капса!", delete_after=2)

    async def set_caps_settings(self, guild_id, percentage, enabled):
        with self.db_connection:
            self.db_connection.execute('''
                  INSERT INTO caps_settings (guild_id, caps_percentage, caps_filter_enabled)
                  VALUES (?, ?, ?)
                  ON CONFLICT(guild_id) DO UPDATE SET
                      caps_percentage=excluded.caps_percentage,
                      caps_filter_enabled=excluded.caps_filter_enabled
              ''', (guild_id, percentage, enabled))





def setup(bot):
    bot.add_cog(BotSettingsALT(bot))