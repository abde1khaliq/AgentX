from config import *
from root_data.destinations import *
from root_data.emojis import *
from root_data.languages import *
from handlers import *
from game_instance import *
from Views import *

def check_premium_status(user_id):
    premium_users = []
    return user_id in premium_users

def has_premium():
    def decorator(func):
        async def wrapper(interaction: nextcord.Interaction):
            user_id = interaction.user.id
            is_premium_user = check_premium_status(user_id)
            if not is_premium_user:
                await interaction.response.send_message(f"{error_emj} You need to be a premium user to use this command.", ephemeral=True)
                return
            return await func(interaction)
        return wrapper
    return decorator