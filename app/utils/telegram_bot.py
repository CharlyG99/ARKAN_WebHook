import requests

async def send_telegram_trade_signal(bot_token, channel_id, strategy_name, symbol, side, entry_price, order_id):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    message = f"""
  Trade Signal Alert 

Strategy: {strategy_name}
Symbol: {symbol}
Side: {side.upper()}
Entry Price: {entry_price}
Order ID: {order_id}

"""
    
    payload = {
        "chat_id": channel_id,
        "text": message
    }
    
    requests.post(url, json=payload)


async def send_telegram_close_signal(bot_token, channel_id, strategy_name, symbol, side, exit_price):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    message = f"""
  EXIT Signal Alert 

Strategy: {strategy_name}
Symbol: {symbol}
Side: {side.upper()}
Exit Price: {exit_price}

"""
    
    payload = {
        "chat_id": channel_id,
        "text": message
    }
    
    requests.post(url, json=payload)