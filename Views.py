from config import *
from root_data.emojis import *
from root_data.languages import *
from handlers import *
from nextcord import ui
import nextcord

class Language_DropdownView(ui.View):
    def __init__(self, client, guild_id):
        super().__init__()
        self.client = client
        self.guild_id = guild_id

        try:
            language_codes = self.client.language_manager.languages.keys()
            options = [
                nextcord.SelectOption(
                    label=lang,
                    value=lang,
                    description=self.client.language_manager.get_translation(lang, "language_description")
                ) for lang in language_codes if self.client.language_manager.get_translation(lang, "language_description") != "Translation not found."
            ]
            
            select = ui.Select(
                placeholder='Choose your preferred language...',
                options=options
            )

            select.callback = self.language_handler_callback
            self.add_item(select)
        except Exception as error:
            print(f"An error occurred while initializing the language dropdown: {error}")

    async def language_handler_callback(self, interaction: nextcord.Interaction):
        try:
            language = interaction.data["values"][0]
            result = self.client.language_manager.set_language(language)

            if result == f'Language set to {language}':
                self.client.guild_language[self.guild_id] = language
                await interaction.response.send_message(
                    content=f'{result} {self.client.language_manager.get_translation(language, "language_flag")}',
                    ephemeral=True
                )
                await self.update_guild_language(language)
            else:
                await interaction.response.send_message(
                    content=f'{error_emj} Invalid language.',
                    ephemeral=True
                )
        except Exception as error:
            print(f"An error occurred while handling the language selection: {error}")

    async def update_guild_language(self, language):
        self.db_path = self.client.db_path

        try:
            async with aiofiles.open(self.db_path, 'r+') as file:
                data = await file.read()
                guild_data = json.loads(data or '{}')

                guild_key = f"{self.guild_id}_{json.dumps(self.client.get_guild(self.guild_id).name)}"
                if guild_key in guild_data:
                    guild_data[guild_key]["language"] = language
                    
                await file.seek(0)
                await file.write(json.dumps(guild_data, indent=4))
                await file.truncate()
        except Exception as error:
            print(f"An error occurred while updating the guild language: {error}")

