import logging
import os
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

_env_path = os.path.join('root_data', '.env')
load_dotenv(dotenv_path=_env_path)

token = os.getenv('BOT_TOKEN')