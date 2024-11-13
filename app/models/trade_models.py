from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, List, Dict,Union
from bson import ObjectId

class TradeRequest(BaseModel):
    broker: List[str]
    strat: str
    symbol: str
    volume: float
    action: str
    price: int
    stoploss: Optional[float] = None
    takeprofit: Optional[float] = None

class Trades(BaseModel): 
    order_id: int
    username:int
    broker: str
    strategy_name: str
    symbol: str
    volume: float
    side: str
    entry: float
    exit: Optional[Union[str, float, None]] = None
    date: datetime = Field(default_factory=datetime.now)
    class Config:     
        json_encoders = {ObjectId: str}

class CloseRequest(BaseModel):
    broker: List[str]
    strategy_name: str 
    symbol: str
    side: str

class ticker(BaseModel):
    ticker: str
    broker: str
    margin: float
    contract: int
    leverage: int

