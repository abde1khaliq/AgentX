from config import *
from root_data.destinations import *
from root_data.emojis import *
from root_data.languages import *
from datetime import datetime, timezone
from handlers import *
from game_instance import *
from Views import *
from nextcord import *
from nextcord.ext import commands
from nextcord.ui import View, Button, Select
import signal
import sys
import asyncio

ALLOWED_USER_ID = 803701217439514695
TEST_SERVER_ID = 1340838364407922762

async def global_cleanup(client):
    for guild in client.guilds:
        try:
            for role in guild.roles:
                if role.name == "AgentX In-Game":
                    await role.delete()
                    logger.info(f"Deleted role 'AgentX In-Game' in guild {guild.name}")

            for category in guild.categories:
                if category.name == "AgentX":
                    for channel in category.channels:
                        await channel.delete()
                        logger.info(f"Deleted channel {channel.name} in guild {guild.name}")
                    await category.delete()
                    logger.info(f"Deleted category 'AgentX' in guild {guild.name}")

        except Exception as error:
            logger.error(f"Error cleaning up guild {guild.name}: {error}")

def handle_shutdown(signal, frame):
    logger.info("Shutting down gracefully...")
    for guild_id, game_instance in client._game_instances.items():
        logger.info(f"Cleaning up game instance in guild {guild_id}")
        asyncio.create_task(game_instance.cleanup(Interaction))
    asyncio.create_task(global_cleanup(client))
    sys.exit(0)

class Client(nextcord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_application_commands()
        self.language_manager = LanguageManager()
        self.guild_language = {}
        self.db_path = 'guilds_data.json'
        self._active_views = {}
        self._game_instances = {}

    async def on_ready(self):
        await self.change_presence(status=nextcord.Status.online, activity=nextcord.Activity(type=nextcord.ActivityType.playing, name='/commands'))
        logger.info(f'Logged in as {self.user.name} ({self.user.id})')
        await global_cleanup(self)
        await check_guild_data(self)

    async def on_member_update(self, before, after):
        try:
            guild_id = after.guild.id

            if guild_id in self._game_instances:
                game_instance = self._game_instances[guild_id]
                in_game_role = game_instance.in_game_role

                is_player_in_game = any(player["id"] == after.id for player in game_instance.players)

                if is_player_in_game and in_game_role in before.roles and in_game_role not in after.roles:
                    await after.add_roles(in_game_role)
                    logger.info(f"Re-added AgentX In-Game role to {after.display_name}")
                
                elif not is_player_in_game and in_game_role in after.roles:
                    await after.remove_roles(in_game_role)
                    logger.info(f"Removed AgentX In-Game role from {after.display_name} (not part of the game)")
        except Exception as error:
            logger.error(f"Error in on_member_update: {error}")

    async def on_guild_join(self, guild):
        await init_guild_database(guild)
        welcome_channel = nextcord.utils.get(guild.text_channels, name='general')

        if not welcome_channel:
            welcome_channel = guild.text_channels[0] if guild.text_channels else None

        if welcome_channel:
            welcome_embed = nextcord.Embed(
                title='🕵️ **AgentX Has Arrived!** 🕵️',
                description=(
                    "Greetings, Detectives and Spies!\n\n"
                    "I'm **AgentX**, your top-secret companion for thrilling spy games. "
                    "Gear up, gather your intel, and get ready for an adventure of intrigue and espionage.\n\n"
                    "Type `/commands` to see how you can get started. Let the spy games begin!\n\n"
                    "If you face any errors or bugs, please contact our support team at [Support Server](https://discord.gg/6fMyHbsDWS)"
                    ""
                ),
                color=0x86E00E
            )
            welcome_embed.set_thumbnail(url='https://i.postimg.cc/L5brQtNp/A-2.png')
            welcome_embed.set_footer(text='Keep your eyes open and trust no one...')

            await welcome_channel.send(embed=welcome_embed)

    async def on_voice_state_update(self, member, before, after):
        logger.info(f"Voice state update detected for {member.display_name}:")
        logger.info(f"Before: {before.channel.name if before.channel else 'None'}")
        logger.info(f"After: {after.channel.name if after.channel else 'None'}")

        guild_id = member.guild.id
        if guild_id in self._game_instances:
            game_instance = self._game_instances[guild_id]

            is_player_in_game = any(player["id"] == member.id for player in game_instance.players)

            if after.channel and not is_player_in_game:
                if after.channel == game_instance.queue_channel or after.channel == game_instance.current_game_channel:
                    logger.info(f"Kicking {member.display_name} from the channel (not part of the game).")
                    await member.move_to(None)

            if before.channel and before.channel == game_instance.current_game_channel:
                logger.info(f"Player {member.display_name} left the game channel: {before.channel.name}")
                await game_instance.handle_player_leave(member)

    def add_application_commands(self):
        @self.slash_command(name='host', description='Host a game of AgentX')
        async def hostgame_command(interaction: nextcord.Interaction,
                                playercount: int = SlashOption(description="Number of players (min 5, max 15)", min_value=5, max_value=15),
                                game_duration: int = SlashOption(description="Time in minutes (5-30)", min_value=5, max_value=30)):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)
                host = interaction.user
                blocked_server_id = 1278383458749780042

                if guild_id == blocked_server_id:
                    await interaction.response.send_message("This command is not available in this server.", ephemeral=True)
                    return

                if guild_id in self._game_instances:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "game_started_error"),
                        ephemeral=True
                    )
                    return

                if playercount < 5:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "not_enough_players_error"), ephemeral=True
                    )
                    return
                elif playercount > 15:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "too_many_players_error"), ephemeral=True
                    )
                    return
                
                if game_duration < 5:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "invalid_duration_error_min"), ephemeral=True
                    )
                elif game_duration > 30:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "invalid_duration_error_max"), ephemeral=True
                    )
                    return

                players = []

                spy_embed = nextcord.Embed(
                    title=f'**{self.language_manager.get_translation(current_language, "title")}**',
                    description=self.language_manager.get_translation(current_language, "spy_embed_description"),
                    color=0x86E00E
                )
                spy_embed.add_field(name=f"{self.language_manager.get_translation(current_language, 'host_message')} {host}", value='', inline=False)
                spy_embed.add_field(name=f"**{self.language_manager.get_translation(current_language, 'player_list')}**", value='', inline=False)
                spy_embed.set_footer(text="Time remaining 25 seconds")

                views = join_btn(host=host, players=players, playercount=playercount, message=None, client=self, game_duration=game_duration)
                message = await interaction.response.send_message(embed=spy_embed, view=views)
                views.message = message

                self._active_views[guild_id] = views

            except Exception as error:
                logger.error(f"Error in host_game: {error}")

        @self.slash_command(name='hint', description='Get a hint related to the location')
        async def hint_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                if guild_id not in self._game_instances:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "no_active_game_error"),
                        ephemeral=True
                    )
                    return

                game_instance = self._game_instances[guild_id]

                is_player_in_game = any(player["id"] == interaction.user.id for player in game_instance.players)
                if not is_player_in_game:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "only_players_can_use_hint"),
                        ephemeral=True
                    )
                    return

                if interaction.channel != game_instance.disscusion_room:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "hint_command_only_in_discussion_room"),
                        ephemeral=True
                    )
                    return

                if game_instance.is_player_on_cooldown(interaction.user.id):
                    remaining_time = game_instance.hint_cooldown_duration - (datetime.now().timestamp() - game_instance.hint_cooldowns[interaction.user.id])
                    cooldown_message = self.language_manager.get_translation(current_language, "hint_cooldown_message").format(seconds=round(remaining_time))
                    await interaction.response.send_message(
                        cooldown_message,
                        ephemeral=True
                    )
                    return

                hint = await game_instance.get_random_hint()
                await interaction.response.send_message(hint, ephemeral=False)

                game_instance.hint_cooldowns[interaction.user.id] = datetime.now().timestamp()

            except Exception as error:
                logger.error(f"Error in hint_command: {error}")

        @self.slash_command(name='stop', description='Stop the current game of AgentX')
        async def stopgame_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                if guild_id not in self._game_instances:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "no_active_game_error"),
                        ephemeral=True
                    )
                    return

                game_instance = self._game_instances[guild_id]

                if interaction.user.id != game_instance.host.id:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "only_host_can_stop_error"),
                        ephemeral=True
                    )
                    return

                await game_instance.cleanup(interaction)
                del self._game_instances[guild_id]

                await interaction.response.send_message(
                    self.language_manager.get_translation(current_language, "game_stopped_successfully"),
                    ephemeral=True
                )

            except Exception as error:
                logger.error(f"Error in stop_game: {error}")

        @self.slash_command(name='guide', description='Displays AgentX Guide menu')
        async def guide_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                help_embed = nextcord.Embed(
                    title=f'**AgentX Guide**',
                    description='',
                    color=0x86E00E
                )

                help_embed.add_field(name=f'{num1} **. {self.language_manager.get_translation(current_language, "help", "faq1")}**',
                                    value=f'{self.language_manager.get_translation(current_language, "help", "what_is_bot")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num2} **. {self.language_manager.get_translation(current_language, "help", "faq2")}**',
                                    value=f'{self.language_manager.get_translation(current_language, "help", "start_game")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num3} **. {self.language_manager.get_translation(current_language, "help", "faq3")}**',
                                    value=f'{self.language_manager.get_translation(current_language, "help", "join_game_help")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num4} **. {self.language_manager.get_translation(current_language, "help", "faq4")}**', 
                                    value=f'{self.language_manager.get_translation(current_language, "help", "during_game")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num5} **. {self.language_manager.get_translation(current_language, "help", "faq5")}**', 
                                    value=f'{self.language_manager.get_translation(current_language, "help", "roles")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num6} **. {self.language_manager.get_translation(current_language, "help", "faq6")}**',
                                    value=f'{self.language_manager.get_translation(current_language, "help", "how_to_play_part1")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num7} **. {self.language_manager.get_translation(current_language, "help", "faq7")}**',
                                    value=f'{self.language_manager.get_translation(current_language, "help", "how_to_play_part2")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num8} **. {self.language_manager.get_translation(current_language, "help", "faq8")}**', 
                                    value=f'{self.language_manager.get_translation(current_language, "help", "how_to_vote")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num9} **. {self.language_manager.get_translation(current_language, "help", "faq9")}**', 
                                    value=f'{self.language_manager.get_translation(current_language, "help", "spy_guess_correct")}', inline=False)
                help_embed.add_field(name='', value='', inline=False)
                help_embed.add_field(name=f'{num10} **. {self.language_manager.get_translation(current_language, "help", "faq10")}**',
                                     value=f'{self.language_manager.get_translation(current_language, "help", "report_issues")}', inline=False)

                await interaction.response.send_message(embed=help_embed, ephemeral=True)
            except Exception as error:
                logger.error(f"Error in help_command: {error}")

        @self.slash_command(name='commands', description='Shows AgentX commands')
        async def cmds_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                cmds_embed = nextcord.Embed(
                    title=f'{self.language_manager.get_translation(current_language, "agentx_commands_title")}',
                    description=f'{self.language_manager.get_translation(current_language, "agentx_commands_desc")}',
                    color=0x86E00E
                )

                cmds_embed.add_field(
                    name='🎮 **| Game Commands**', 
                    value='Enhance your gaming experience with these commands:',
                    inline=False
                )
                cmds_embed.add_field(
                    name='',
                    value=(
                        f'`/guide` - {self.language_manager.get_translation(current_language, "guide_command")}\n'
                        f'`/host` - {self.language_manager.get_translation(current_language, "host_command")}\n'
                        f'`/hint` - {self.language_manager.get_translation(current_language, "hint_command")}\n'
                        f'`/stop` - {self.language_manager.get_translation(current_language, "stop_command")}'
                    ),
                    inline=False
                )

                cmds_embed.add_field(
                    name='🎭 **| Misc Commands**', 
                    value='Useful miscellaneous commands to enhance your experience:',
                    inline=False
                )
                cmds_embed.add_field(
                    name='',
                    value=(
                        f'`/support` - {self.language_manager.get_translation(current_language, "support_command")}\n'
                        f'`/report` - {self.language_manager.get_translation(current_language, "report_command")}\n'
                        f'`/invite` - {self.language_manager.get_translation(current_language, "invite_command")}\n'
                        f'`/ping` - {self.language_manager.get_translation(current_language, "ping_command")}'
                    ),
                    inline=False
                )

                cmds_embed.add_field(
                    name='👑 **| Owner Commands**', 
                    value='Commands available only to server owners:',
                    inline=False
                )
                cmds_embed.add_field(
                    name='',
                    value=(
                        f'`/settings` - {self.language_manager.get_translation(current_language, "set_language_command")}\n'
                    ),
                    inline=False
                )

                cmds_embed.set_thumbnail(url='https://i.postimg.cc/L5brQtNp/A-2.png')
                await interaction.response.send_message(embed=cmds_embed, ephemeral=True)
            except Exception as error:
                logger.error(f"Error in cmds_command: {error}")

        @self.slash_command(name='report', description='Report a bug in the bot')
        async def report_bug_command(interaction: nextcord.Interaction, description: str):
            try:
                owner_id = 803701217439514695
                owner = await self.fetch_user(owner_id)
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                if not owner:
                    await interaction.response.send_message(
                        self.language_manager.get_translation(current_language, "report_bug_error_message"), 
                        ephemeral=True
                    )
                    return

                bug_report_embed = nextcord.Embed(
                    title="🐛 New Bug Report",
                    description=description,
                    color=0xFF0000
                )
                bug_report_embed.set_author(
                    name=interaction.user.display_name, 
                    icon_url=interaction.user.avatar.url
                )
                bug_report_embed.add_field(
                    name="Guild",
                    value=f'`{interaction.guild.name}`', 
                    inline=True
                )
                bug_report_embed.add_field(
                    name="Channel",
                    value=f'`{interaction.channel.name}`', 
                    inline=True
                )
                bug_report_embed.set_footer(
                    text=f"User ID: {interaction.user.id}"
                )

                await owner.send(embed=bug_report_embed)

                await interaction.response.send_message(
                    self.language_manager.get_translation(current_language, "report_bug_success_message"), 
                    ephemeral=True
                )

            except Exception as error:
                logger.error(f"Error in report_bug_command: {error}")
                await interaction.response.send_message(
                    self.language_manager.get_translation(current_language, "report_bug_error_message"), 
                    ephemeral=True
                )

        @self.slash_command(name='invite', description='Invite AgentX to your server')
        async def invite_command(interaction: nextcord.Interaction):
            try:
                channel = interaction.guild.text_channels[0] if interaction.guild.text_channels else None
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                if channel:
                    invite_url = 'https://discord.com/oauth2/authorize?client_id=1342208198089637969&permissions=8&integration_type=0&scope=bot'
                    invite_embed = nextcord.Embed(
                        title=f'{self.language_manager.get_translation(current_language, "invite_agentX")}',
                        description=f'{self.language_manager.get_translation(current_language, "invite_agentX_desc")}\n**[Invite Link]({invite_url})**',
                        color=0x86E00E
                    )
                    await interaction.response.send_message(embed=invite_embed, ephemeral=True)
                else:
                    await interaction.response.send_message("No text channels available to create an invite link.", ephemeral=True)
            except Exception as error:
                logger.error(f"Error in invite_command: {error}")

        @self.slash_command(name='support', description='Sends the official support server link')
        async def support_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                support_server_link = 'https://discord.gg/6fMyHbsDWS'
                support_embed = nextcord.Embed(
                    title=f'{self.language_manager.get_translation(current_language, "official_support_server")}',
                    description=f'{self.language_manager.get_translation(current_language, "official_support_server_desc")}\n**[Support Server]({support_server_link})**',
                    color=0x86E00E
                )
                await interaction.response.send_message(embed=support_embed, ephemeral=True)
            except Exception as error:
                logger.error(f"Error in support_command: {error}")

        @self.slash_command(name='ping', description='Sends the ping status')
        async def ping_command(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                latency = round(client.latency * 1000)
                api_latency = client.latency * 1000
                current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

                if latency > 400:
                    latency_emoji = bad_emj
                elif latency > 200:
                    latency_emoji = mid_emj
                else:
                    latency_emoji = good_emj

                if api_latency > 400:
                    api_latency_emoji = bad_emj
                elif api_latency > 200:
                    api_latency_emoji = mid_emj
                else:
                    api_latency_emoji = good_emj

                ping_embed = nextcord.Embed(
                    title='Ping Status',
                    description=(
                        f"{latency_emoji} **Latency:** {latency}ms\n"
                        f"{api_latency_emoji} **API Latency:** {api_latency:.2f}ms\n"
                    ),
                    color=0x86E00E
                )

                ping_embed.set_footer(text=f'{self.language_manager.get_translation(current_language, 'current_time')}: {current_time}')

                await interaction.response.send_message(embed=ping_embed, ephemeral=True)
            except Exception as error:
                logger.error(f"Error in ping_command: {error}")
                
        @self.slash_command(name="settings", description="Displays AgentX bot settings")
        async def settings(interaction: nextcord.Interaction):
            try:
                guild_id = interaction.guild.id
                current_language = await load_server_language(guild_id)

                if interaction.user.guild_permissions.administrator:
                    embed = nextcord.Embed(
                        title=f"{self.language_manager.get_translation(current_language, "agentX_settings_title")}",
                        description=f"{self.language_manager.get_translation(current_language, "agentX_settings_desc")}",
                        color=0x86E00E
                    )

                    embed.add_field(
                        name=f"{self.language_manager.get_translation(current_language, "current_language_title")}",
                        value=self.language_manager.get_translation(current_language, "current_language_desc").format(current_language=current_language),
                        inline=False
                    )

                    embed.set_thumbnail(url="https://i.postimg.cc/L5brQtNp/A-2.png")

                    view = Language_DropdownView(self, guild_id)

                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        f'{self.language_manager.get_translation(current_language, "language_selection_error")}',
                        ephemeral=True
                    )
            except Exception as error:
                logger.error(f"Error in settings command: {error}")

        @self.slash_command(name='update', description='Updates the bot', guild_ids=[1278383458749780042])
        async def update_command(interaction: nextcord.Interaction):
            try:
                if interaction.user.id == ALLOWED_USER_ID:
                    await interaction.response.send_message(
                        "Please describe the update (features, bug fixes, improvements):", ephemeral=True
                    )

                    def check(m):
                        return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

                    msg = await self.wait_for('message', check=check)
                    desc = msg.content

                    await interaction.followup.send(
                        "Does this update include any new features? (yes/no)", ephemeral=True
                    )
                    msg = await self.wait_for('message', check=check)
                    includes_features = msg.content.lower() == 'yes'

                    if includes_features:
                        await interaction.followup.send(
                            "Please list the new features:", ephemeral=True
                        )
                        msg = await self.wait_for('message', check=check)
                        features = msg.content
                    else:
                        features = "No new features."

                    update_embed = nextcord.Embed(
                        title='🚀 **New AgentX Update**',
                        description='AgentX brought a new update',
                        color=0x86E00E
                    ).set_thumbnail(
                        url='https://i.postimg.cc/L5brQtNp/A-2.png'
                    ).set_footer(
                        text='Brought to you by AgentX',
                        icon_url='https://i.postimg.cc/L5brQtNp/A-2.png'
                    ).add_field(
                        name='What\'s New?',
                        value=f'{desc}',
                        inline=False
                    ).add_field(
                        name='New Features',
                        value=f'{features}',
                        inline=False
                    ).add_field(
                        name='Visit our Support Server',
                        value='[Click here to join](https://discord.gg/6fMyHbsDWS)',
                        inline=False
                    )

                    for guild in self.guilds:
                        channel = nextcord.utils.get(guild.text_channels, name='general') or guild.text_channels[0]
                        if channel:
                            await channel.send(embed=update_embed)

                    await interaction.followup.send(embed=update_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "You do not have permission to use this command.", ephemeral=True
                    )
            except Exception as error:
                logger.error(f"Error in update_command: {error}")

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

client = Client(intents=intents)
client.run(token)