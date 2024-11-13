from fastapi import APIRouter, HTTPException
from models.trade_models import CloseRequest
from utils.mongo import mongo
import logging
from datetime import datetime
from bson import ObjectId
from config import settings
from models.trade_models import TradeRequest
from typing import List, Dict, Any, Optional
    

def is_amount_positive(order_type, stop_type):
    return (order_type == "buy" and stop_type != "sl") or (order_type == "sell" and stop_type == "sl")

async def calculate_price_level(entry_price, percentage, order_type, stop_type="sl"):
    price = entry_price

    price *= (1 + percentage/100) if is_amount_positive(order_type, stop_type) else (1 - percentage/100)

    return round(price, 4)

async def calculate_ordersize(price, volumeper, equity):
    percentage = volumeper / 100
    
    order_size = (equity * percentage) / price
    
    return round(order_size, 4)


async def get_latest_open_position(symbol: str, strategy_name: str):
    db = mongo.get_database()
    trades_collection = db.get_collection("trades")
    
    # Find the latest open trade for the given symbol and strategy_name
    latest_trade = await trades_collection.find_one(
        {
            "symbol": symbol,
            "strategy_name": strategy_name,
            "exit": {"$exists": False}  # Assuming 'exit' field is added when position is closed
        },
        sort=[("date", -1)]
    )
    
    if not latest_trade:
        raise HTTPException(status_code=404, detail="Open position not found")
    
    return latest_trade

async def update_trade_with_exit(trade_id: ObjectId, exit_price: float):
    db = mongo.get_database()
    trades_collection = db.get_collection("trades")
    
    result = await trades_collection.update_one(
        {"_id": trade_id},
        {"$set": {"exit": exit_price, "closed_at": datetime.utcnow()}})
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update trade with exit price")
    
    
    
async def save_trade(trade_data: dict):
    db = mongo.get_database()
    trades_collection = db.get_collection("trades")
    result = await trades_collection.insert_one(trade_data)
    

async def reconcile_positions(
    db_positions: List[Dict[str, Any]], 
    broker_positions: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:

    try:
        # If there are no DB positions, return empty list
        if not db_positions:
            return None

        # If broker_positions is None, treat all DB positions as missing
        if broker_positions is None:
            
            return db_positions
        # Create a set of broker deal IDs for faster lookup
        broker_deals = {pos["deal"] for pos in broker_positions}
        
        # Find positions that are in DB but not in broker
        missing_positions = []
        
        for db_position in db_positions:
            deal_id = db_position["orderid"]
            
            if deal_id not in broker_deals:
                missing_positions.append(db_position)
                
    
        return missing_positions
                
    except Exception as e:
        raise

def round_to_nearest_lot(size: float, min_lot_size: float = 0.01) -> float:

    return round(size / min_lot_size) * min_lot_size

def calculate_position_size(
    account_balance: float,
    risk_percentage: float,
    contract_size: float,
    margin_percent: float,
    leverage: float,
    commission_rate: float,
    asset_price: float,
    min_lot_size: float = 0.01
) -> dict:
    """
    Calculate position size targeting a specific position value percentage of account
    with proper rounding to nearest lot size
    """
    target_position_value = account_balance * (risk_percentage / 100)
    
    contract_value = contract_size * asset_price
    
    required_lots = target_position_value / contract_value
    
    recommended_lots = round_to_nearest_lot(required_lots, min_lot_size)
    
    margin_per_lot = (contract_value * margin_percent / 100)
    
    margin_used = recommended_lots * margin_per_lot
    
    actual_position_value = recommended_lots * contract_value
    
    effective_leverage = actual_position_value / margin_used if margin_used > 0 else 0
    
    # Check if leverage is within limits
    if effective_leverage > leverage:
        # Recalculate lots based on leverage limit
        max_lots_by_leverage = (account_balance * leverage) / (contract_value * margin_percent / 100)
        recommended_lots = round_to_nearest_lot(
            min(required_lots, max_lots_by_leverage),
            min_lot_size
        )
        # Recalculate final values
        margin_used = recommended_lots * margin_per_lot
        actual_position_value = recommended_lots * contract_value
    
    return recommended_lots