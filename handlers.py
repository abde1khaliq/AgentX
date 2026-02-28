from config import *
import aiofiles
from nextcord.ext import tasks
from aiofiles import open as aio_open
from json import loads, dumps, JSONDecodeError
from typing import Dict, Any
import json
import asyncio

#! GUILD DATABASE INITIALIZATION --------------------------------------------------------------------

async def init_guild_database(guild, db_path='guilds_data.json'):
        try:
            if not os.path.exists(db_path):
                async with aiofiles.open(db_path, 'w') as file:
                    await file.write('{}')

            async with aiofiles.open(db_path, 'r+') as file:
                data = await file.read()
                try:
                    guild_data = json.loads(data or '{}')
                except json.JSONDecodeError:
                    print('Data is corrupted, attempting to fix...')
                    guild_data = {}

                guild_key = f"{guild.id}_{json.dumps(guild.name)}"
                
                if guild_key not in guild_data:
                    guild_data[guild_key] = {
                        "guild_id": guild.id,
                        "guild_name": guild.name,
                        "language": "English",
                        "is_premiumServer": False,
                        "game_queue_channel": None,
                        "game_channel_voice": None,
                        "game_discussion_channel": None,
                        "game_ingame_role": None
                    }
                    await file.seek(0)
                    await file.write(json.dumps(guild_data, indent=4))
                    await file.truncate()
                else:
                    print('Guild data already exists. No need to reinitialize.')
                    
        except Exception as error:
            print(f'An error occurred while initializing guild database: {error}')

#! GUILD DATA REFRESHING TASKS ---------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)

lock = asyncio.Lock()

@tasks.loop(minutes=30)
async def check_guild_data(self):
    await refresh_guild_data(self)

async def refresh_guild_data(self, db_path: str = 'guilds_data.json'):
    try:
        async with lock:
            async with aio_open(db_path, 'r+') as file:
                data = await file.read()
                try:
                    guild_data: Dict[str, Any] = loads(data or '{}')
                except JSONDecodeError:
                    logging.warning('JSONDecodeError: Data is corrupted, creating an empty guild data dictionary...')
                    guild_data = {}

                keys_to_delete = []
                for guild_key, stored_guild in guild_data.items():
                    if guild_key in guild_data:
                        if not any(guild.id == stored_guild.get("guild_id") and guild.name == stored_guild.get("guild_name") for guild in self.guilds):
                            keys_to_delete.append(guild_key)

                for key in keys_to_delete:
                    logging.info(f'Deleting corrupted entry: {key}')
                    del guild_data[key]

                for guild in self.guilds:
                    guild_key = f"{guild.id}_{dumps(guild.name)}"
                    if guild_key not in guild_data:
                        guild_data[guild_key] = {
                            "guild_id": guild.id,
                            "guild_name": guild.name,
                            "language": "English",
                            "is_premiumServer": False,
                            "game_queue_channel": None,
                            "game_channel_voice": None,
                            "game_discussion_channel": None,
                            "game_ingame_role": None

                        }
                    else:
                        stored_guild = guild_data[guild_key]
                        if (
                            stored_guild.get("guild_id") != guild.id or
                            stored_guild.get("guild_name") != guild.name
                        ):
                            logging.info(f'Data mismatch for guild {guild.name} ({guild.id}), updating data...')
                            stored_guild["guild_id"] = guild.id
                            stored_guild["guild_name"] = guild.name

                async with aio_open(f'{db_path}.backup', 'w') as backup_file:
                    await backup_file.write(data)

                try:
                    await file.seek(0)
                    await file.write(dumps(guild_data, indent=4))
                    await file.truncate()
                except JSONDecodeError:
                    logging.error('JSONEncodeError: Failed to encode guild data to JSON')

    except FileNotFoundError:
        async with aio_open(db_path, 'w') as file:
            logging.warning('FileNotFoundError: File not found, creating a new one...')
            await file.write('{}')

    except Exception as error:
        logging.error(f'An error occurred while refreshing guild data: {error}')

#! GUILD LANGUAGE HANDLER --------------------------------------------------------------------

async def load_server_language(guild_id, db_path = 'guilds_data.json'):
    try:
        async with aiofiles.open(db_path, 'r') as file:
            data = await file.read()
            guild_data = json.loads(data or '{}')
        for key, value in guild_data.items():
            if str(guild_id) in key:
                language = value["language"]
                return language
        print('GuildID was not found.')
        return "en"
    except FileNotFoundError:
        print('Language data file was not found.')
        return "en"
    except json.JSONDecodeError:
        print('Language data file is not valid JSON.')
        return "en"
    except Exception as error:
        print(f'An error occurred while loading server language: {error}')
        return "en"