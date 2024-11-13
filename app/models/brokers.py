from typing import Dict, Any
import MetaTrader5 as mt5
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio
import time 
logger = logging.getLogger(__name__)

class MT5Broker():
    def __init__(self, username, password, server, suffix=None):
        self.username = username
        self.password = password
        self.server = server
        self.connected = False
        self.minlot = self.maxlot = self.decpos = None


       
        self.connect()


        
    def connect( self ):
        self.connected = False
        
        if not mt5.initialize():
            logger.critical("MT5 initialization failed, unable to connect" )
            mt5.shutdown()
            return False
        if not mt5.login(self.username, self.password, self.server):
            logger.critical("MT5 login failed, unable to connect")
            mt5.shutdown()
            return False
        #check mt5.terminal_info() and make sure MT5 is connected to the exchange
        timeout = datetime.now() + timedelta( seconds = 60 )
        while True:
            data = mt5.terminal_info()._asdict()
            if data['connected']:
                self.connected = True
                return True
            if datetime.now > timeout:
                logger.critical("MT5 failed to connect to exchange")
                mt5.shutdown()
                return False
            time.sleep( 10 )

    def get_price(self, symbol, side):
        if not self.connect():
            return None

        try:
            data = mt5.symbol_info_tick(symbol)._asdict()
            price_bid = float(data['bid'])
            price_ask = float(data['ask'])
            
            self.connected = True  # Move this here, as it will be set if no exception occurs
            
            if side.lower() == 'buy':
                return price_ask
            elif side.lower() == 'sell':
                return price_bid
            else:
                logger.warning(f"Invalid side: {side}. Returning None.")
                return None
            
        except Exception as e:
            logger.critical(f"MT5 symbol_info_tick() failed: {str(e)}")
            self.connected = False
            return None

        #finally:
        #    mt5.shutdown()
            
    def market_order( self, symbol, dir, lotsize, price, SL, TP):
        for attempt in range(3):
            try:    
                if not self.connect():
                    return False 
                
                if dir == "buy":
                    order_type = mt5.ORDER_TYPE_BUY            
                else:
                    order_type = mt5.ORDER_TYPE_SELL

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lotsize,
                    "type": order_type,
                    "price": price,
                    "sl": SL,
                    "tp": TP,
                    "deviation": int( price / 100 ),
                    "magic": 999999,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                print(request)
                try:
                    result = mt5.order_send(request)
                except Exception as e:
                    logger.critical(f"Exception occurred during order_send: {str(e)}")
                    return False    
                print(result)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Successfully opened trade {symbol} trade size {lotsize:.2f} entry price {price:.2f}")
                    return result
                else:
                    logger.critical(f"Failed to open trade {symbol}, mt5 returned error {result}")
                    if attempt < 2:  # Only sleep if we're going to retry
                        time.sleep(1)
                        continue
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                if attempt < 2:  # Change from 3 to 2 since range(3) is 0,1,2
                    time.sleep(1)
                    continue
            
            finally:
                mt5.shutdown()

    def get_last_pnl( self, symbol ):
        if not self.connect():
            return False
        last_pnl = 0
        last_time = None
        positions = mt5.history_deals_get( datetime.now() - timedelta(days=5), datetime.now() ) 
        if positions is None or len(positions) == 0:
            logger.critical("get_last_pnl for {symbol} failed")
            return 0
        for position in positions:
            pos_dict = position._asdict()
            if pos_dict['symbol'] == symbol + self.symbol_suffix:
                if last_time is None or pos_dict['time_msc'] > last_time:
                    last_time = pos_dict['time_msc']
                    last_pnl = pos_dict['profit']

        mt5.shutdown()
        return last_pnl
        
    def close_position( self, symbol, deal_id, side,volume):
        for attempt in range(3):
            try:    
                if not self.connect():
                    return False
                
                    
                if side == "buy":
                    # reverse order direction to close
                    order_type = mt5.ORDER_TYPE_SELL
                    price = self.get_price(symbol,side= "sell")
                else:
                    order_type = mt5.ORDER_TYPE_BUY
                    price = self.get_price(symbol,side= "buy")
            
                request={
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float("{:.2f}".format(volume)),
                    "type": order_type,
                    "position": deal_id,
                    "price": float("{:.2f}".format(price)),
                    "magic": 999999,
                    "comment": "Close trade",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                    "deviation": int( price/100 ),
                }
                print(request)
                result = mt5.order_send(request)
                print(result)

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"Successfully closed trade {deal_id}")
                    return result
                else:
                    logger.critical(f"retry to close trade {deal_id}")
                    if attempt < 2:  # Only sleep if we're going to retry
                        time.sleep(1)
                        continue
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                if attempt < 2:
                    time.sleep(1)
                    continue
            finally:
                mt5.shutdown()
            
    
    def get_balance(self):
        if not self.connect():
            return
        try:
            data = mt5.account_info()._asdict()
            print(data)
            balance = data['balance']
            print(balance)
            #equity = data['equity']
            return balance
        except:  
            logger.critical(f"MT5 get balance failed" )
            self.connected = False 
    def check_positon(self):
        if not self.connect():
            return False
        positions=mt5.positions_total()
        if positions>0:
            print(positions)
            return positions
        else:
            return None 
    
"""         
class CTraderBroker(BrokerBase):
    def __init__(self, username: str, password: str, server: str):
        self.ctrader = Ctrader(server, username, password)

    async def connect(self) -> bool:
        return await self.ctrader.connect()

    async def place_order(self, symbol: str, order_type: str, volume: float, price: float = None) -> Dict[str, Any]:
        if order_type.lower() == "buy":
            result = await self.ctrader.buyLimit(symbol, volume, takeProfit=None, stopLoss=None)
        else:
            result = await self.ctrader.sellLimit(symbol, volume, takeProfit=None, stopLoss=None)
        return {"order_id": result['pos_id'], "executed_price": result['price']}

    async def close_order(self, order_id: str) -> bool:
        return await self.ctrader.closePosition(order_id)

    async def get_price(self, symbol: str) -> float:
        quotes = await self.ctrader.quote(symbol)
        return quotes['ask']

    async def get_balance(self) -> float:
        account_info = await self.ctrader.getAccountInfo()
        return account_info['balance']

    async def get_pnl(self) -> float:
        account_info = await self.ctrader.getAccountInfo()
        return account_info['profit']"""
    
"""
class TradingService:
    def __init__(self, broker: BrokerBase):
        self.broker = broker

    async def execute_trade(self, symbol: str, order_type: str, volume: float):
        if not await self.broker.connect():
            raise Exception("Failed to connect to broker")

        price = await self.broker.get_price(symbol)
        order_result = await self.broker.place_order(symbol, order_type, volume, price)

        balance = await self.broker.get_balance()
        pnl = await self.broker.get_pnl()

        return {
            "order_id": order_result["order_id"],
            "executed_price": order_result["executed_price"],
            "current_balance": balance,
            "current_pnl": pnl
        }

    async def close_trade(self, order_id: str):
        if not await self.broker.connect():
            raise Exception("Failed to connect to broker")

        close_result = await self.broker.close_order(order_id)
        if not close_result:
            raise Exception("Failed to close order")

        balance = await self.broker.get_balance()
        pnl = await self.broker.get_pnl()

        return {
            "order_closed": True,
            "current_balance": balance,
            "current_pnl": pnl
        }"""

class credentials(BaseModel):
    broker: str
    username: int
    password: str
    server : str
class DeleteAccountRequest(BaseModel):
    username: int