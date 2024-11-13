from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings
import logging
from config import settings
import datetime
from typing import List, Dict
from models.trade_models import Trades, ticker
# Load environment variables from .env file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mongo_uri = settings.mongo_uri
db_name = settings.mongo_db_name
client = AsyncIOMotorClient(mongo_uri)
db = client[db_name]

class MongoSettings(BaseSettings):
    uri: str = settings.mongo_uri
    db_name: str = settings.mongo_db_name


settings = MongoSettings()


class MongoDB:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.database = self.client[db_name]
        logger.info(f"Connected to MongoDB at {uri}")

    def get_database(self):
        return self.database

    async def close(self):
        logger.info("Closing MongoDB connection")
        self.client.close()


mongo = MongoDB(settings.uri, settings.db_name)

async def get_accounts_for_broker(broker: str) -> List[dict]:
    # Fetch accounts for the specified broker from the database
    cursor = db.accounts.find({"broker": broker})
    return await cursor.to_list(length=None)

async def get_open_positions(username: int, strategy: str, symbol: str) -> List[Trades]:
    cursor = db.trades.find({
        "username": username,
        "strategy_name": strategy,
        "symbol": symbol,
        "exit": None  # Only get open positions
    })
    return await cursor.to_list(length=None)

async def update_trade_with_exit(position_id: str, exit_price: float):
    result = await db.trades.update_one(
        {"order_id": position_id},
        {"$set": {"exit": exit_price}}
    )
    if result.modified_count == 0:
        logger.warning(f"No trade found with order_id: {position_id}")

async def get_open_position_info( symbol: str, username: str) -> str:
    position = await db.trades.find_one({
        "symbol": symbol,
        "username": username,
        "exit": None  # Only get open positions
    })  
    if position:
        return position
    else:
        return None
    
async def get_open_positions_from_account(username: int, broker_name: str) -> List[Trades]:
    try:
        cursor = db.trades.find({
            "username": username,
            "broker": broker_name,
            "exit": None  # Only get open positions
        })
        
        positions = await cursor.to_list(length=None)
        logger.info(f"Found {len(positions)} open positions for user {username} on broker {broker_name}")
        return positions
        
    except Exception as e:
        logger.error(f"Error querying open positions: {str(e)}")
        raise
async def get_ticker(ticker: str) -> List[ticker]:
    try:
        cursor = db.ticker.find({"ticker": ticker,})
        return cursor
        
    except Exception as e:
        logger.error(f"Error querying open positions: {str(e)}")
        raise
