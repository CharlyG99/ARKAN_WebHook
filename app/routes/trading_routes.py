# auth_routes.py
from fastapi import Security,APIRouter, HTTPException, Depends
from fastapi.security import APIKeyHeader
from utils.mongo import get_ticker,get_open_positions_from_account,get_accounts_for_broker, get_open_positions, update_trade_with_exit, get_open_position_info
from datetime import datetime
import logging
from config import settings
from models.trade_models import TradeRequest, Trades, CloseRequest, ticker
from utils.calculation import calculate_position_size,calculate_price_level, get_latest_open_position, update_trade_with_exit
import time
from dotenv import load_dotenv
from utils.telegram_bot import send_telegram_close_signal, send_telegram_trade_signal
from config import settings
from models.brokers import MT5Broker, credentials, DeleteAccountRequest
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)
bot_token = settings.tg_token
channel_id = settings.chan_id
mongo_uri = settings.mongo_uri
db_name = settings.mongo_db_name
client = AsyncIOMotorClient(mongo_uri)
db = client[db_name]
api_key_header = APIKeyHeader(name="X-API-Key")
admin_key_header = APIKeyHeader(name="X-Admin-Key")

# Add these security dependencies
async def verify_api_key(api_key: str | None = None):
    if not api_key:
        raise HTTPException(status_code=403, detail="No API key provided")
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

async def verify_admin_key(api_key: str = Security(admin_key_header)):
    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return api_key
async def get_broker(broker_name, username, password, server):
    if broker_name == 'MT5':
        broker = MT5Broker(username,password,server)
    return broker    

@router.post("/place_order/{api_key}")
async def place_order(tradereq: TradeRequest, api_key: str):
    await verify_api_key(api_key)
    for brokername in tradereq.broker:
        accounts = await get_accounts_for_broker(brokername)
        
        if not accounts:
            raise HTTPException(status_code=404, detail=f"No accounts found for broker {tradereq.broker}")
        
        for account in accounts:
            username = account['username']
            password = account['password']
            server = account['server']

            broker = await get_broker(brokername, username, password, server)
            current_position = await get_open_position_info(tradereq.symbol, username)

            if current_position:
                current_side = current_position["side"]
                current_strategy = current_position["strategy_name"]
                
                if current_side == tradereq.action:
                    # Same side, proceed to place the order
                    logger.info(f"Existing {current_side} position matches new signal. Proceeding to place additional order.")
                elif current_strategy == tradereq.strat:
                    # Opposite side, same strategy, close current position
                    try:
                        result = broker.close_position(
                            tradereq.symbol,
                            current_position["order_id"],
                            current_side,
                            current_position["volume"]
                        )
                        logger.info(f"Closed existing {current_side} trade for strategy {current_strategy} before opening new {tradereq.action} trade")
                        if result:
                            await update_trade_with_exit(current_position["order_id"], result.price)
                            await send_telegram_close_signal(
                                settings.tg_token,
                                settings.chan_id,
                                current_strategy,
                                tradereq.symbol,
                                current_side,
                                result.price
                            )
                    except Exception as e:
                        logger.error(f"Failed to close existing trade: {e}")
                        continue  # Skip to next account if closing fails
                else:
                    # Opposite side, different strategy, ignore the signal
                    logger.info(f"Ignoring signal: Existing {current_side} trade for different strategy {current_strategy}.")
                    continue  # Skip to next account

            # At this point, either there was no existing position, or it was closed, or it's on the same side
            try:
                # Get account balance and calculate order size
                account_balance = broker.get_balance()
                
                ticker =await get_ticker(tradereq.symbol)
                volume = await calculate_position_size(account_balance,tradereq.volume,ticker["contract"],ticker["margin"],ticker["leverage"],ticker["comission"],tradereq.price,0.01)

                if tradereq.stoploss:
                    tradereq.stoploss = await calculate_price_level(tradereq.price, tradereq.stoploss, tradereq.action, 'sl')
                else:
                    tradereq.stoploss = None

                if tradereq.takeprofit:
                    tradereq.takeprofit = await calculate_price_level(tradereq.price, tradereq.takeprofit, tradereq.action, 'tp')
                else:
                    tradereq.takeprofit = None

                # Get current price 
                current_price = broker.get_price(tradereq.symbol, tradereq.action)

                # Execute the trade
                result = broker.market_order(
                    tradereq.symbol,
                    tradereq.action,
                    volume,
                    current_price,
                    tradereq.stoploss,
                    tradereq.takeprofit
                )

                trade = Trades(
                    order_id=result.order,
                    username=username,
                    broker=brokername,
                    strategy_name=tradereq.strat,
                    symbol=tradereq.symbol,
                    volume=volume,
                    side=tradereq.action,
                    entry=result.price,
                    exit=None
                )

                # Insert the validated data into MongoDB
                await db.trades.insert_one(trade.model_dump())

                await send_telegram_trade_signal(
                    settings.tg_token, settings.chan_id, tradereq.strat, tradereq.symbol,
                    tradereq.action, result.price, order_id=result.deal
                )

                return {
                    "message": "Order placed successfully",
                    "order_details": result,
                    "calculated_volume": volume,
                    "adjusted_stoploss": tradereq.stoploss,
                    "adjusted_takeprofit": tradereq.takeprofit,
                    
                }

            except Exception as e:
                logger.exception(f"Error placing order: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=400, detail="No valid accounts found to place the order")

@router.post("/close_position/{api_key}")
async def close_position(closereq: CloseRequest,api_key: str):
    await verify_api_key(api_key)
    try:
        for broker_name in closereq.broker:
            accounts = await get_accounts_for_broker(broker_name)
            
            if not accounts:
                logger.warning(f"No accounts found for broker: {broker_name}")
                continue

            for account in accounts:
                username = account['username']
                password = account['password']
                server = account['server']
                
                try:
                    broker = await get_broker(broker_name, username, password, server)
                    
                    # Query the positions in the db by the strategy and the symbol
                    positions = await get_open_positions(username, closereq.strategy_name, closereq.symbol)
                    
                    if positions:

                        for position in positions:
                            position_id = int(position['order_id'])
                            volume = position['volume'] 
                            
                            try:
                                
                                close_response = broker.close_position(closereq.symbol, position_id, closereq.side, volume)
                                closed_price = close_response.price

                                await update_trade_with_exit(position_id, closed_price)
                                await send_telegram_close_signal(
                                    settings.tg_token,
                                    settings.chan_id,
                                    closereq.strategy_name,
                                    closereq.symbol,
                                    position.side,  # Use the side from the position, not from closereq
                                    closed_price
                                )
                                
                                logger.info(f"Successfully closed position: {position_id} at price: {closed_price}")
                            except Exception as e:
                                logger.error(f"Error closing position after 3 attempts {position_id}: {str(e)}")
                                # Continue to next position even if one fails
                                continue
                    else:
                        logger.info(f"No open positions found for strategy: {closereq.strategy_name}, symbol: {closereq.symbol}")
                        continue           
                except Exception as e:
                    logger.error(f"Error with broker {broker_name} for account {username}: {str(e)}")
                        # Continue to next account even if one fails
                    continue

            return {"message": "Close position operation completed"}

    except Exception as e:
        logger.exception(f"Error in close_position: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/add_account")
async def add_credentials(cred: credentials, api_key: str ):
    await verify_admin_key(api_key)
    try:
        result = await db.accounts.insert_one(cred.model_dump())
        return {"message": "Account added successfully", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding account: {str(e)}")



@router.delete("/delete_account")
async def delete_account(request: DeleteAccountRequest,api_key: str):
    await verify_admin_key(api_key)
    try:
        result = await db.accounts.delete_one({"username": request.username})
        if result.deleted_count == 1:
            return {"message": f"Account with username '{request.username}' deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Account with username '{request.username}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting account: {str(e)}")
    

        
@router.post("/add_ticker")
async def add_credentials(tick: ticker,api_key: str):
    await verify_admin_key(api_key)
    try:
        result = await db.accounts.insert_one(tick.model_dump())
        return {"message": "Account added successfully", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding account: {str(e)}")
