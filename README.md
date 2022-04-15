# Tradingview webhook (works only for Binance Futures)
# How to install (For Local/Production)
- Download latest `python` on https://www.python.org/
- Run `pip install -r requirements.txt`
- Copy `.env.example` file and rename it to `.env`, and edit values
- Deploy to any cloud services like `Heroku` 

# How to use on Tradingview
- Create new alert, enter your domain url (e.g. https://sample.herokuapp.com/webhook) - Don't forget to include `/webhook` in the URL
- Enter message (make sure the `passphrase` is matched from your `.env`): \
`{
    "passphrase": "passphrase",
    "exchange": "{{exchange}}",
    "ticker": "{{ticker}}",
    "order_comment": "{{strategy.order.comment}}", 
    "order_price":  {{strategy.order.price}}
}`
