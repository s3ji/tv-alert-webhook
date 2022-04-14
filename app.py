import json, config
from flask import Flask, request, jsonify, render_template
from binance.client import Client
from binance.enums import *

app = Flask(__name__)

client = Client(config.API_KEY, config.API_SECRET)

def order(side, position, quantity, symbol, order_type, tp, sl):
    try:
        # Close all open orders
        client.futures_cancel_all_open_orders(symbol=symbol)

        order = client.futures_create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        
        # Place a TP
        client.futures_create_order(symbol=symbol, side=position, type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, stopPrice=tp, closePosition=True, timeInForce='GTE_GTC', workingType='MARK_PRICE', priceProtect=True)

        # Place an SL
        client.futures_create_order(symbol=symbol, side=position, type=FUTURE_ORDER_TYPE_STOP_MARKET, stopPrice=sl, closePosition=True, timeInForce='GTE_GTC', workingType='MARK_PRICE', priceProtect=True)
    except Exception as e:
        print("an exception occured - {}".format(e))
        return False

    return order

@app.route('/')
def welcome():
    return render_template('index.html')

@app.route('/webhook', methods=['POST'])
def webhook():
    data = json.loads(request.data)

    if data['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {
            "code": "error",
            "message": "Nice try, invalid passphrase"
        }

    if data['order_comment'] == 'L':
        side = 'BUY'
        position = 'SELL'

        tp_price = data['order_price'] + (data['order_price'] * config.TP)
        tp = round(tp_price,2)

        sl_price = data['order_price'] - (data['order_price'] * config.SL)
        sl = round(sl_price,2)
    elif data['order_comment'] == 'S':
        side = 'SELL'
        position = 'BUY'

        tp_price = data['order_price'] - (data['order_price'] * config.TP)
        tp = round(tp_price,2)

        sl_price = data['order_price'] + (data['order_price'] * config.SL)
        sl = round(sl_price,2)
    else:
        return {
            "code": "wait",
            "message": "waiting for buy/sell signal"
        }

    account_balance = 0
    account_balance_info = client.futures_account_balance()
    for item in account_balance_info:
        if item['asset'] == 'USDT':
            account_balance = float(item['balance'])
            break

    pricePrecision = 0
    f_quantity = 0

    balance_to_use = account_balance * config.PERCENT_AMOUNT
    quantity = balance_to_use * config.LEVERAGE / data['order_price']

    info = client.futures_exchange_info()

    if info['symbols'][0]['pair'] == data['ticker']:
        pricePrecision = info['symbols'][0]['pricePrecision']
    
    f_quantity = "{:0.0{}f}".format(quantity, pricePrecision)

    order_response = order(side, position, f_quantity, data['ticker'], FUTURE_ORDER_TYPE_MARKET, tp, sl)

    if order_response:
        return {
            "code": "success",
            "message": "order executed"
        }
    else:
        return {
            "code": "error",
            "message": "order failed"
        }