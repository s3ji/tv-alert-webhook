import os
import json
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from binance.client import Client
from binance.enums import *

load_dotenv()

app = Flask(__name__)

ENABLE_TRADE = os.environ.get('ENABLE_TRADE', 'no')
WEBHOOK_PASSPHRASE = os.environ.get('WEBHOOK_PASSPHRASE')
API_KEY = os.environ.get('API_KEY')
API_SECRET = os.environ.get('API_SECRET')
PERCENT_AMOUNT = float(os.environ.get('PERCENT_AMOUNT'))
LEVERAGE = os.environ.get('LEVERAGE')
MARGIN_TYPE = os.environ.get('MARGIN_TYPE')
TP = float(os.environ.get('TP'))
SL = float(os.environ.get('SL'))

client = Client(API_KEY, API_SECRET)

def change_leverage(symbol, leverage, margin_type):
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
    except Exception as e:
        print(f"Symbol: {symbol}, error: {e}")

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
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return order

@app.route('/')
def welcome():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    if ENABLE_TRADE == 'no':
        return {
            "code": "error",
            "message": "trading is not enabled"
        }

    data = json.loads(request.data)

    if data['passphrase'] != WEBHOOK_PASSPHRASE:
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

        tp_price = data['order_price'] * (1 + TP)
        tp = get_price_precision(tp_price, pricePrecision)

        sl_price = data['order_price'] * (1 - SL)
        sl = get_price_precision(sl_price, pricePrecision)
    elif data['order_comment'] == 'S':
        side = 'SELL'
        position = 'BUY'

        tp_price = data['order_price'] * (1 - TP)
        tp = get_price_precision(tp_price, pricePrecision)

        sl_price = data['order_price'] * (1 + SL)
        sl = get_price_precision(sl_price, pricePrecision)
    else:
        return {
            "code": "wait",
            "message": "waiting for buy/sell signal"
        }

    f_quantity = 0

    balance_to_use = account_balance * PERCENT_AMOUNT
    quantity = balance_to_use * LEVERAGE / data['order_price']
    
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