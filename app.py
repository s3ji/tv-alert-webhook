import os
import json
from flask import Flask, request, jsonify, render_template
from binance.client import Client
from binance.enums import *
from discord_webhook import DiscordWebhook, DiscordEmbed

def send_discord_message(title, message):
    if os.environ.get("DISCORD_WEBHOOK"):
        webhook = DiscordWebhook(url=os.environ.get("DISCORD_WEBHOOK"))

        # create embed object for webhook
        # you can set the color as a decimal (color=242424) or hex (color='03b2f8') number
        embed = DiscordEmbed(title=title, description=message, color='03b2f8')

        # add embed object to webhook
        webhook.add_embed(embed)
        webhook.execute()
    else:
        return False

def check_required_env():
    REQUIRED_ENV_VARS = ["ENVIRONMENT", "ENABLE_TRADE", "WEBHOOK_PASSPHRASE", "API_KEY", "API_SECRET", "PERCENT_AMOUNT", "LEVERAGE", "MARGIN_TYPE", "TP", "SL"]

    for var in REQUIRED_ENV_VARS:
        if var not in os.environ:
            send_discord_message("Environment Error", "Failed because {} is not set.".format(var))
            raise EnvironmentError("Failed because {} is not set.".format(var))
        if not os.environ.get(var):
            send_discord_message("Environment Error", "Failed because {} is empty.".format(var))
            raise EnvironmentError("Failed because {} is empty.".format(var))

check_required_env()

if os.environ.get("ENVIRONMENT") == 'LOCAL':
    from dotenv import load_dotenv
    load_dotenv()

app = Flask(__name__)

ENABLE_TRADE = os.environ.get('ENABLE_TRADE', 'no')
WEBHOOK_PASSPHRASE = os.environ.get('WEBHOOK_PASSPHRASE')
API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')
PERCENT_AMOUNT = os.environ.get('PERCENT_AMOUNT')
LEVERAGE = os.environ.get('LEVERAGE')
MARGIN_TYPE = os.environ.get('MARGIN_TYPE')
TP = os.environ.get('TP')
SL = os.environ.get('SL')

client = Client(API_KEY, API_SECRET)

def change_leverage(symbol, leverage, margin_type):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
    except Exception as e:
        send_discord_message("Error in Change Leverage/Margin Type", f"Symbol: {symbol}, error: {e}")

def get_price_precision(price, precision):
    format = "{:0.0{}f}".format(price, precision)
    p_price = float(format)
    return p_price

def order(side, quantity, symbol, order_type):
    try:
        # Close all open orders
        client.futures_cancel_all_open_orders(symbol=symbol)

        # Create market order
        order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)

        send_discord_message("Order executed", f"{side} - {symbol} - {quantity} - {LEVERAGE}")
    except Exception as e:
        send_discord_message("Order Failed", "An exception occured - {}".format(e))
        return False

    return order

@app.route('/')
def welcome():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    if ENABLE_TRADE == 'no':
        send_discord_message("Error", "Trading is not enabled.")
        return {
            "code": "error",
            "message": "trading is not enabled"
        }

    data = json.loads(request.data)

    if data['passphrase'] != WEBHOOK_PASSPHRASE:
        send_discord_message("Error", "Invalid passphrase.")
        return {
            "code": "error",
            "message": "Nice try, invalid passphrase"
        }

    symbol = data['ticker']
    ticker = symbol.replace("PERP", "")

    isValidSymbol = False
    pricePrecision = 0
    qtyPrecision = 0
    
    info = client.futures_exchange_info()

    for x in info['symbols']:
        if x['symbol'] == ticker:
            isValidSymbol = True
            pricePrecision = x['pricePrecision']
            qtyPrecision = x['quantityPrecision']

    if isValidSymbol == False:
        send_discord_message("Error", "Invalid symbol - {}".format(ticker))
        return {
            "code": "invalid_symbol",
            "message": "symbol is not valid"
        }

    change_leverage(ticker, LEVERAGE, MARGIN_TYPE)

    #if info['symbols'][0]['pair'] == ticker:
    #    pricePrecision = info['symbols'][0]['pricePrecision']

    account_balance = 0
    account_balance_info = client.futures_account_balance()
    for item in account_balance_info:
        if item['asset'] == 'USDT':
            account_balance = float(item['balance'])
            break

    if data['order_comment'] == 'L':
        side = 'BUY'
        position = 'SELL'

        tp_price = float(data['order_price']) * (1 + float(TP))
        tp = get_price_precision(tp_price, pricePrecision)

        sl_price = float(data['order_price']) * (1 - float(SL))
        sl = get_price_precision(sl_price, pricePrecision)
    elif data['order_comment'] == 'S':
        side = 'SELL'
        position = 'BUY'

        tp_price = float(data['order_price']) * (1 - float(TP))
        tp = get_price_precision(tp_price, pricePrecision)

        sl_price = float(data['order_price']) * (1 + float(SL))
        sl = get_price_precision(sl_price, pricePrecision)
    else:
        send_discord_message("Error", "Waiting for buy/sell signal")
        return {
            "code": "wait",
            "message": "waiting for buy/sell signal"
        }

    f_quantity = 0

    balance_to_use = float(account_balance) * float(PERCENT_AMOUNT)
    quantity = float(balance_to_use) * float(LEVERAGE) / float(data['order_price'])
    
    f_quantity = get_price_precision(quantity, qtyPrecision)

    order_response = order(side, f_quantity, ticker, FUTURE_ORDER_TYPE_MARKET)

    if order_response:
        # Place a TP
        client.futures_create_order(symbol=ticker, side=position, type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, stopPrice=tp, closePosition=True, timeInForce='GTE_GTC', workingType='MARK_PRICE', priceProtect=True)

        # Place an SL
        client.futures_create_order(symbol=ticker, side=position, type=FUTURE_ORDER_TYPE_STOP_MARKET, stopPrice=sl, closePosition=True, timeInForce='GTE_GTC', workingType='MARK_PRICE', priceProtect=True)

        return {
            "code": "success",
            "message": "order executed"
        }
    else:
        return {
            "code": "error",
            "message": "order failed"
        }