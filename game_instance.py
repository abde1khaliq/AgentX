from config import *
from root_data.languages import *
from handlers import *
from root_data.emojis import *
from Views import *
from root_data.destinations import *
from root_data.hints import *
import nextcord
from nextcord import *
from datetime import datetime, timezone
import asyncio
import random

class join_btn(nextcord.ui.View):
    def __init__(self, host, players, message, playercount, client, game_duration):
        super().__init__(timeout=25)
        self.host = host
        self.players = players
        self.message = message
        self.playercount = playercount
        self.client = client
        self.game_duration = game_duration
        self.button = nextcord.ui.Button(label='Enter Game', style=nextcord.ButtonStyle.green)
        self.button.callback = self.get_players
        self.add_item(self.button)
        self.game_started = False

    async def get_players(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        user = interaction.user
        user_info = {
            "id": user.id,
            "name": user.name,
            "display_name": user.display_name
        }

        if user.id not in [player["id"] for player in self.players]:
            self.players.append(user_info)
            await interaction.response.send_message(
                self.client.language_manager.get_translation(current_language, "joined_game_200_message"),
                ephemeral=True
            )
            await self.update_message(interaction)

        if len(self.players) >= self.playercount:
            self.game_started = True
            game = Game(players=self.players, host=self.host, playercount=self.playercount, client=self.client, game_duration=self.game_duration)
            self.client._game_instances[guild_id] = game
            logger.info(f"Game instance added for guild {guild_id}")

            await self.update_message_to_game_started(interaction)

            await game.setup(interaction)
            self.stop()

    async def update_message(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            spy_embed = nextcord.Embed(
                title=f'**{self.client.language_manager.get_translation(current_language, "title")}**',
                description=self.client.language_manager.get_translation(current_language, "spy_embed_description"),
                color=0x86E00E
            )
            spy_embed.add_field(
                name=f'{self.client.language_manager.get_translation(current_language, "host_message")} `{self.host}`',
                value='',
                inline=False
            )
            spy_embed.add_field(
                name=f'**{self.client.language_manager.get_translation(current_language, "player_list")}**',
                value='',
                inline=False
            )

            for i, player_info in enumerate(self.players):
                spy_embed.add_field(
                    name=f'**{i + 1}.** `{player_info["display_name"]}`',
                    value='',
                    inline=False
                )

            await self.message.edit(embed=spy_embed, view=self)
        except Exception as error:
            logger.error(f"Error in update_message: {error}")

    async def update_message_to_game_started(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            game_started_embed = nextcord.Embed(
                title=f'**{self.client.language_manager.get_translation(current_language, "game_started_title")}**',
                description=self.client.language_manager.get_translation(current_language, "game_started_description"),
                color=0xFFA500
            )

            await self.message.edit(embed=game_started_embed, view=None)
        except Exception as error:
            logger.error(f"Error in update_message_to_game_started: {error}")

    async def on_timeout(self):
        if not self.game_started:
            guild_id = self.message.guild.id
            if guild_id in self.client._game_instances:
                del self.client._game_instances[guild_id]
                logger.info(f"Game join phase timed out for guild {guild_id}. Not enough players joined.")

            try:
                timeout_embed = nextcord.Embed(
                    title="⏳ Join Phase Ended",
                    description=f"The join phase has ended. Only {len(self.players)} players joined, but {self.playercount} are required to start the game.",
                    color=0xFFA500
                )
                await self.message.edit(embed=timeout_embed, view=None)
            except Exception as error:
                logger.error(f"Error sending timeout message: {error}")
                
class Vote_btn(nextcord.ui.View):
    def __init__(self, players, game_instance, interaction):
        super().__init__(timeout=120)
        self.players = players
        self.votes = {player: 0 for player in players}
        self.voted_players = {}
        self.game_instance = game_instance
        self.interaction = interaction

        for player in players:
            btn = nextcord.ui.Button(label=f'{player}', style=nextcord.ButtonStyle.green)
            btn.callback = self.create_vote_callback(player)
            self.add_item(btn)

    def create_vote_callback(self, player):
        async def vote_callback(interaction: nextcord.Interaction):
            try:
                voter_id = interaction.user.id
                is_player_in_game = any(player_info["id"] == voter_id for player_info in self.game_instance.players)

                if not is_player_in_game:
                    await interaction.response.send_message(f"{error_emj} Only players in the game can vote!", ephemeral=True)
                    return

                if voter_id in self.voted_players:
                    await interaction.response.send_message(f"{error_emj} You have already voted!", ephemeral=True)
                    return

                if interaction.user.name == player:
                    await interaction.response.send_message(f"{error_emj} You cannot vote for yourself!", ephemeral=True)
                    return

                self.votes[player] += 1
                self.voted_players[voter_id] = player
                await interaction.response.send_message(f'{sucess_emj} You voted for {player}', ephemeral=True)

                await self.check_votes(interaction)
            except Exception as error:
                logger.error(f"Error in vote_callback for player {player}: {error}")

        return vote_callback

    async def check_votes(self, interaction: nextcord.Interaction):
        try:
            if len(self.voted_players) >= len(self.players) - 1:
                await self.game_instance.vote_management(self.interaction, self.votes)
                self.stop()
        except Exception as error:
            logger.error(f"Error in check_votes: {error}")

    async def on_timeout(self):
        try:
            guild_id = self.game_instance.disscusion_room.guild.id
            current_language = await load_server_language(guild_id)

            non_voting_players = [player for player in self.players if player not in self.voted_players]

            for player in non_voting_players:
                random_vote = random.choice([p for p in self.players if p != player])
                self.votes[random_vote] += 1
                self.voted_players[player] = random_vote

            timeout_embed = nextcord.Embed(
                title=self.game_instance.client.language_manager.get_translation(current_language, "vote_phase_ended"),
                description=self.game_instance.client.language_manager.get_translation(current_language, "auto_vote_message"),
                color=0xFFA500
            )
            await self.game_instance.disscusion_room.send(embed=timeout_embed)

            await self.game_instance.vote_management(self.interaction, self.votes)
        except Exception as error:
            logger.error(f"Error in on_timeout: {error}")

class Game():
    def __init__(self, host, players, playercount, client, game_duration):
        self.host = host if isinstance(host, nextcord.Member) else Interaction.guild.get_member(host["id"])
        self.players = players
        self.playercount = playercount
        self.client = client
        self.game_duration = game_duration
        self.in_game_role = None
        self.current_game_channel = None
        self.queue_channel = None
        self.agentx_category = None
        self.disscusion_room = None
        self.spy = None
        self._left_players = {}
        self.hint_cooldowns = {}
        self.hint_cooldown_duration = 30


    async def get_random_hint(self):
        return random.choice(hints)
    
    def is_player_on_cooldown(self, player_id):
        current_time = datetime.now().timestamp()
        if player_id in self.hint_cooldowns:
            last_used = self.hint_cooldowns[player_id]
            if current_time - last_used < self.hint_cooldown_duration:
                return True
        return False

    async def handle_player_leave(self, member):
        logger.info(f"Handling player leave for {member.display_name}")
        try:
            if member.id in [player["id"] for player in self.players]:
                if member.id not in self._left_players:
                    if member.id == self.host.id:
                        if len(self.players) > 1:
                            new_host_info = next(player for player in self.players if player["id"] != member.id)
                            new_host = member.guild.get_member(new_host_info["id"])
                            self.host = new_host
                            logger.info(f"Host has left. Reassigned host to {new_host.display_name}")

                    if self.disscusion_room:
                        guild_id = member.guild.id
                        current_language = await load_server_language(guild_id)
                        logger.info(f"Sending warning message for {member.display_name}")
                        warning_embed = nextcord.Embed(
                            title=f"{self.client.language_manager.get_translation(current_language, "member_left_midgame")}",
                            description=f"{member.display_name} {self.client.language_manager.get_translation(current_language, "member_left_midgame_desc")}",
                            color=0xFFA500
                        )
                        await self.disscusion_room.send(embed=warning_embed)

                    logger.info(f"Starting 10-second timer for {member.display_name}")
                    self._left_players[member.id] = asyncio.create_task(self._remove_player_after_timeout(member))
                    
        except Exception as error:
            logger.error(f"Error handling player leave: {error}")

    async def _remove_player_after_timeout(self, member):
        try:
            await asyncio.sleep(10)

            if member.voice and member.voice.channel == self.current_game_channel:
                if self.disscusion_room:
                    guild_id = member.guild.id
                    current_language = await load_server_language(guild_id)
                    returned_embed = nextcord.Embed(
                        title=f"{self.client.language_manager.get_translation(current_language, "player_returned_game")}",
                        description=f"{member.display_name} {self.client.language_manager.get_translation(current_language, "player_returned_game_desc")}",
                        color=0x00FF00
                    )
                    await self.disscusion_room.send(embed=returned_embed)
                del self._left_players[member.id]
            else:
                if self.disscusion_room:
                    guild_id = member.guild.id
                    current_language = await load_server_language(guild_id)
                    removed_embed = nextcord.Embed(
                        title=f"{self.client.language_manager.get_translation(current_language, "player_removed_midgame")}",
                        description=f"{member.display_name} {self.client.language_manager.get_translation(current_language, "player_removed_midgame_desc")}",
                        color=0xFF0000
                    )
                    await self.disscusion_room.send(embed=removed_embed)

                await self.remove_player(member)

                if self.spy and member.id == self.spy["id"]:
                    if self.disscusion_room:
                        spy_left_embed = nextcord.Embed(
                            title=f"{self.client.language_manager.get_translation(current_language, "spy_removed_midgame")}",
                            description=f"{member.display_name} {self.client.language_manager.get_translation(current_language, "spy_removed_midgame_desc")}",
                            color=0xFF0000
                        )
                        await self.disscusion_room.send(embed=spy_left_embed)
                    await self.cleanup(member)
                    logger.info("Spy has been removed. Game ended.")
                else:
                    if self.in_game_role in member.roles:
                        await member.remove_roles(self.in_game_role)
                    del self._left_players[member.id]
                    print(self.players)
        except Exception as error:
            logger.error(f"Error in _remove_player_after_timeout: {error}")

    async def remove_player(self, player):
        try:
            player_id = player.id if isinstance(player, nextcord.Member) else player["id"]

            if player_id == self.host.id:
                if len(self.players) > 3:
                    new_host_info = next(p for p in self.players if p["id"] != player_id)
                    new_host = player.guild.get_member(new_host_info["id"])
                    self.host = new_host
                    logger.info(f"Host has left. Reassigned host to {new_host.display_name}")

            self.players = [p for p in self.players if p["id"] != player_id]

            if len(self.players) < 2:
                guild = player.guild
                host_member = guild.get_member(self.host.id)
                await self.cleanup(host_member)
        except Exception as error:
            logger.error(f"Error in remove_player: {error}")

    async def init_roles(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        try:
            self.in_game_role = await self.client.get_guild(guild_id).create_role(
                name="AgentX In-Game",
                hoist=True,
                color=0x86E00E,
                permissions=nextcord.Permissions.none()
            )

            roles = interaction.guild.roles
            bot_member = interaction.guild.get_member(self.client.user.id)
            bot_top_role = bot_member.top_role
            new_position = bot_top_role.position - 1 if bot_top_role.position > 1 else 1

            await self.in_game_role.edit(position=new_position)

            for player_info in self.players:
                player_id = player_info["id"]
                player = interaction.guild.get_member(player_id)
                if player:
                    await player.add_roles(self.in_game_role)

            if self.agentx_category:
                await self.agentx_category.set_permissions(
                    interaction.guild.default_role,
                    view_channel=False,
                    connect=False,
                    send_messages=False,
                    read_message_history=False
                )

                await self.agentx_category.set_permissions(
                    self.in_game_role,
                    view_channel=True,
                    connect=True,
                    send_messages=True,
                    read_message_history=True
                )

        except nextcord.Forbidden as error:
            logger.error(f"Permission error in init_roles: {error}")
            await interaction.followup.send("I don't have permission to create or assign roles. Please check my permissions.")
        except nextcord.HTTPException as error:
            logger.error(f"HTTP error in init_roles: {error}")
            await interaction.followup.send("An error occurred while creating roles. Please try again later.")
        except Exception as error:
            logger.error(f"Unexpected error in init_roles: {error}")
            await interaction.followup.send("An unexpected error occurred. Please contact support.")

    async def revoke_roles(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id

        try:
            for player_info in self.players:
                player_id = player_info["id"]
                player = interaction.guild.get_member(player_id)
                if player:
                    await player.remove_roles(self.in_game_role)
            await self.in_game_role.delete()

        except Exception as error:
            logger.error(f"Error in revoke_roles: {error}")

    async def create_category(self, interaction: nextcord.Interaction, category_name: str):
        try:
            guild = interaction.guild
            existing_category = nextcord.utils.get(guild.categories, name=category_name)
            
            if not existing_category:
                category = await guild.create_category(name=category_name)
                return category
            else:
                return existing_category
        except Exception as error:
            logger.error(f"Error in create_category: {error}")
            return None
        
    async def delete_channels(self, interaction: nextcord.Interaction, channel):
        try:
            await channel.delete()
        except Exception as error:
            print(f"Error in delete_channels: {error}")

    async def delete_roles(self, interaction: nextcord.Interaction, role):
        try:
            await role.delete()
        except Exception as error:
            logger.error(f"Error in delete_roles: {error}")

    async def create_queue_channel(self, interaction: nextcord.Interaction, category: nextcord.CategoryChannel, channel_name: str, user_limit: int):
        try:
            guild = interaction.guild
            existing_channel = nextcord.utils.get(guild.channels, name=channel_name)
            
            if not existing_channel:
                voice_channel = await guild.create_voice_channel(name=channel_name, category=category, user_limit=user_limit)
                return voice_channel
            else:
                return existing_channel
        except Exception as error:
            logger.error(f"Error in create_queue_channel: {error}")
            return None

    async def create_game_channel(self, interaction: nextcord.Interaction, category: nextcord.CategoryChannel, channel_name: str, user_limit: int):
        try:
            guild = interaction.guild
            existing_channel = nextcord.utils.get(guild.channels, name=channel_name)
            
            if not existing_channel:
                voice_channel = await guild.create_voice_channel(name=channel_name, category=category, user_limit=user_limit)
                return voice_channel
            else:
                return existing_channel
        except Exception as error:
            logger.error(f"Error in create_game_channel: {error}")
            return None
        
    async def create_text_channel(self, interaction: nextcord.Interaction, category: nextcord.CategoryChannel, channel_name: str):
        try:
            guild = interaction.guild
            existing_channel = nextcord.utils.get(guild.text_channels, name=channel_name)
            
            if not existing_channel:
                text_channel = await guild.create_text_channel(name=channel_name, category=category)
                return text_channel
            else:
                return existing_channel
        except Exception as error:
            logger.error(f"Error in create_text_channel: {error}")
            return None
        
    async def cleanup(self, interaction: nextcord.Interaction):
        try:
            guild_id = interaction.guild.id
            if guild_id in self.client._game_instances:
                del self.client._game_instances[guild_id]

            if hasattr(self.client, '_active_views') and guild_id in self.client._active_views:
                join_view = self.client._active_views[guild_id]
                if hasattr(join_view, 'game_started'):
                    join_view.game_started = False
                    print(f"Game started flag reset to False for guild {guild_id}")

            for player_info in self.players:
                player_id = player_info["id"]
                player = interaction.guild.get_member(player_id)
                if player and self.in_game_role in player.roles:
                    await player.remove_roles(self.in_game_role)

            if self.in_game_role:
                await self.in_game_role.delete()

            if self.agentx_category:
                for channel in self.agentx_category.channels:
                    await channel.delete()
                await self.agentx_category.delete()

        except Exception as error:
            logger.error(f"Error in cleanup: {error}")
            
    async def setup(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            self.agentx_category = await self.create_category(interaction, "AgentX")
            self.queue_channel = await self.create_queue_channel(interaction, self.agentx_category, "AgentX Queue", self.playercount)
            await interaction.followup.send(self.client.language_manager.get_translation(current_language, "game_starting_message"))

            player_ids = {player["id"] for player in self.players}

            timeout = 60
            start_time = asyncio.get_event_loop().time()
            
            while True:
                queue_member_ids = {member.id for member in self.queue_channel.members}

                if player_ids.issubset(queue_member_ids):
                    await self.init_roles(interaction)

                    self.current_game_channel = await self.create_game_channel(interaction, self.agentx_category, 'AgentX Ongoing-Game', self.playercount)
                    logger.info(f"Game channel created: {self.current_game_channel.name}")

                    for member in self.queue_channel.members:
                        await member.move_to(self.current_game_channel)

                    await asyncio.sleep(1)

                    logger.info(self.players)

                    await self.delete_channels(interaction, self.queue_channel)

                    self.disscusion_room = await self.create_text_channel(interaction, self.agentx_category, "AgentX┃Discussion")

                    overwrites = self.disscusion_room.overwrites_for(self.in_game_role)
                    overwrites.view_channel = True
                    await self.disscusion_room.set_permissions(self.in_game_role, overwrite=overwrites)

                    await interaction.followup.send(self.client.language_manager.get_translation(current_language, "game_start"))
                    await self.logic(interaction)
                    break

                elapsed_time = asyncio.get_event_loop().time() - start_time
                if elapsed_time >= timeout:
                    await interaction.followup.send("Not all players joined the queue channel within the timeout period. The game has been canceled.")
                    await self.cleanup(interaction)
                    break
                await asyncio.sleep(5)

        except Exception as error:
            logger.error(f"Error in setup: {error}")

    async def logic(self, interaction: nextcord.Interaction):
        try:
            await self.identifier(interaction)
            await asyncio.sleep(5)
            await self.tutorial(interaction)
            await asyncio.sleep(3)
            await self.duration(interaction, self.game_duration)
        except Exception as error:
            logger.error(f"Error in logic: {error}")

    async def tutorial(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            await self.disscusion_room.send(f'{self.client.language_manager.get_translation(current_language, "tutorial_start")}\n{self.client.language_manager.get_translation(current_language, "tutorial_description")}')

        except Exception as error:
            logger.error(f"Error in tutorial: {error}")

    async def identifier(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            self.spy = random.choice(self.players)
            destination = random.choice(destinations)

            for player in self.players:
                member = nextcord.utils.get(interaction.guild.members, id=player["id"])
                if player["id"] == self.spy["id"]:
                    spy_player_embed = nextcord.Embed(
                        title=self.client.language_manager.get_translation(current_language, "user_is_spy_message"),
                        description=self.client.language_manager.get_translation(current_language, "user_is_spy_description"),
                        color=0xF12C2C
                    )
                    spy_player_embed.set_thumbnail(url='https://i.postimg.cc/Hn7H78SG/agent-X-logo2.png')
                    await member.send(embed=spy_player_embed)
                else:
                    detective_player_embed = nextcord.Embed(
                        title=self.client.language_manager.get_translation(current_language, "user_is_detective_message"),
                        description=self.client.language_manager.get_translation(current_language, "user_is_detective_description"),
                        color=0x87DE0D
                    )
                    detective_player_embed.set_thumbnail(url='https://i.postimg.cc/k5fnrmVH/agent-X-logo.png')
                    detective_player_embed.add_field(name='', value='', inline=False)
                    detective_player_embed.add_field(name=self.client.language_manager.get_translation(current_language, "location_message"), value=f'`{destination}`', inline=False)
                        
                    await member.send(embed=detective_player_embed)
        except Exception as error:
            logger.error(f"Error in identifier: {error}")

    async def duration(self, interaction: nextcord.Interaction, time):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            remaining_time = time * 60

            while remaining_time > 0:
                minutes, seconds = divmod(remaining_time, 60)
                timer_embed = nextcord.Embed(
                    title=self.client.language_manager.get_translation(current_language, "game_timer_embed_title"),
                    description=self.client.language_manager.get_translation(current_language, "time_remaining").format(minutes=minutes, seconds=seconds),
                    color=0x86E00E
                )
                
                if self.disscusion_room:
                    await self.disscusion_room.send(embed=timer_embed)

                await asyncio.sleep(60)
                remaining_time -= 60

            end_embed = nextcord.Embed(
                title=self.client.language_manager.get_translation(current_language, "game_timer_embed_title"),
                description=self.client.language_manager.get_translation(current_language, "time_is_up_message"),
                color=0x86E00E
            )
            
            if self.disscusion_room:
                await self.disscusion_room.send(embed=end_embed)

            await self.vote_phase(interaction)

        except Exception as error:
            logger.error(f"Error in start_timer: {error}")

    async def vote_phase(self, interaction: nextcord.Interaction):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            vote_embed = nextcord.Embed(
                title=self.client.language_manager.get_translation(current_language, "vote_embed_title"),
                description=self.client.language_manager.get_translation(current_language, "vote_embed_description"),
                color=0x86E00E
            )
            views = Vote_btn(players=[player["display_name"] for player in self.players], game_instance=self, interaction=interaction)
            if self.disscusion_room:
                await self.disscusion_room.send(embed=vote_embed, view=views)
        except Exception as error:
            logger.error(f"Error in vote_phase: {error}")

    async def vote_management(self, interaction: nextcord.Interaction, votes):
        guild_id = interaction.guild.id
        current_language = await load_server_language(guild_id)

        try:
            print(f"Votes received: {votes}")

            if not votes or len(votes) == 0:
                await interaction.followup.send("No votes were recorded. The game cannot proceed.", ephemeral=True)
                await self.cleanup(interaction)
                return

            max_votes = max(votes.values())
            candidates = [player for player, count in votes.items() if count == max_votes]

            logger.info(f"Candidates: {candidates}")

            if len(candidates) > 1:
                candidates_str = ", ".join(candidates)
                result0_embed = nextcord.Embed(
                    title=self.client.language_manager.get_translation(current_language, "title"),
                    description=f'{self.client.language_manager.get_translation(current_language, "game_tie")} {candidates_str}',
                    color=0x86E00E
                )
                if self.disscusion_room:
                    await self.disscusion_room.send(embed=result0_embed)
            else:
                voted_spy = candidates[0]
                spy_name = self.spy["display_name"]

                logger.info(f"Spy name: {spy_name}")
                logger.info(f"Detective won vote string: {self.client.language_manager.get_translation(current_language, 'detective_won_vote')}")
                logger.info(f"Spy won vote string: {self.client.language_manager.get_translation(current_language, 'spy_won_vote')}")

                if not spy_name:
                    spy_name = "Unknown"


                if voted_spy == spy_name:
                    result1_embed = nextcord.Embed(
                        title=self.client.language_manager.get_translation(current_language, "title"),
                        description=self.client.language_manager.get_translation(current_language, "detective_won_vote").format(voted_spy=spy_name),
                        color=0x86E00E
                    )
                    if self.disscusion_room:
                        await self.disscusion_room.send(embed=result1_embed)
                else:
                    result2_embed = nextcord.Embed(
                        title=self.client.language_manager.get_translation(current_language, "title"),
                        description=self.client.language_manager.get_translation(current_language, "spy_won_vote").format(spy=spy_name),
                        color=0x86E00E
                    )
                    if self.disscusion_room:
                        await self.disscusion_room.send(embed=result2_embed)

            if self.disscusion_room:
                await self.disscusion_room.send('Quitting Game...')
            await asyncio.sleep(5)
            await self.cleanup(interaction)
        except Exception as error:
            logger.error(f"Error in vote_management: {error}")