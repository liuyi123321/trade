from gateway import BinanceSpotHttp, OrderStatus, OrderType, OrderSide
from binance.client import Client
from utils import config
from utils import round_to
import logging
from datetime import datetime
from utils.config import signal_data
from utils.positions import Positions


class BinanceSpotTrader(object):

    def __init__(self):
        config.loads("D:\python_work\multi_pairs_martingle_bot-main\config.json")
        proxies ={
        'http':"http://127.0.0.1:1087",
        'https':"http://127.0.0.1:1087"
            }
        api_key="Ilq9DTQDJFV4SkH6x7TW4pnrNHVvB6OaHyqYlOOVB2IsULfr3zlG3f4yIwk6Defd"
        api_secret="96dklxVWLuykfBY71hj9yyQqQzgnEveYmiAFB6rTZCnMuXxG3ASjo6FVe3da5grj"
        self.http_client = Client(api_key,api_secret,{'proxies':proxies})
        self.order_id =0
        self.symbols_dict = {}  # 全市场的交易对.
        self.tickers_dict = {}  # 全市场的tickers数据.
        #self.buy_orders_dict = {}  
        #self.sell_orders_dict = {}  # 卖单字典. sell orders  {'symbol': [], 'symbol1': []}
        self.positions = Positions('spot_positions.json')
        self.initial_id = 0
    def Id_increment(self):
        self.order_id = self.order_id +1
        return self.order_id
    def get_exchange_info(self):
        data = self.http_client.get_exchange_info()
        if isinstance(data, dict):
            items = data.get('symbols', [])
            for item in items:
                symbol = item['symbol']
                if symbol.__contains__('UP') or symbol.__contains__('DOWN'):
                    continue
                if item.get('quoteAsset') == 'USDT' and item.get('status') == "TRADING":
                    symbol_data = {"symbol": symbol}
                    for filters in item['filters']:
                        if filters['filterType'] == 'PRICE_FILTER':
                            symbol_data['min_price'] = float(filters['tickSize'])
                        elif filters['filterType'] == 'LOT_SIZE':
                            symbol_data['min_qty'] = float(filters['stepSize'])
                        elif filters['filterType'] == 'MIN_NOTIONAL':
                            symbol_data['min_notional'] = float(filters['minNotional'])
                    self.symbols_dict[symbol] = symbol_data

    def get_all_tickers(self):

        tickers = self.http_client.get_ticker()
       # print(tickers)
        if isinstance(tickers, list):
            for tick in tickers:
                symbol = tick['symbol']
                ticker = {"bid_price": float(tick['bidPrice']), "ask_price": float(tick["askPrice"])}
                self.tickers_dict[symbol] = ticker
        else:
            self.tickers_dict = {}

    def get_klines(self, symbol: str, interval, limit):
        return self.http_client.get_klines(symbol=symbol, interval=interval, limit=limit)

    def start(self):
        print("start__begin")
        """
        执行核心逻辑，网格交易的逻辑.

        the grid trading logic
        :return:
        """
        '''
        获取价格数据
        '''
        symbols = self.positions.positions.keys()
        if len(symbols)>=1:
            print("暂无仓位")
        ##############################################
            self.get_all_tickers()
            if len(self.tickers_dict.keys()) == 0:
                return
        
            symbols = self.positions.positions.keys()
            print("Positons:",symbols)
            deleted_positions = []
            Orders = []
            for s in symbols:
                print(s)
                pos_data = self.positions.positions.get(s)
                pos = pos_data.get('pos')
                bid_price = self.tickers_dict.get(s, {}).get('bid_price', 0)  # bid price
                ask_price = self.tickers_dict.get(s, {}).get('ask_price', 0)  # ask price
                min_qty = self.symbols_dict.get(s, {}).get('min_qty')
                if bid_price > 0 and ask_price > 0:
                    value = pos * bid_price
                    if value < self.symbols_dict.get(s, {}).get('min_notional', 0):
                        print(f"{s} notional value is small, delete the position data.")
                        deleted_positions.append(s)  #
                        # del self.positions.positions[s]  # delete the position data if the position notional is very small.
                    else:
                        avg_price = pos_data.get('avg_price')
                        self.positions.update_profit_max_price(s, bid_price)
                        # 计算利润.
                        profit_pct = bid_price / avg_price - 1
                        pull_back_pct = self.positions.positions.get(s, {}).get('profit_max_price', 0) / bid_price - 1

                        dump_pct = self.positions.positions.get(s, {}).get('last_entry_price', 0) / bid_price - 1
                        current_increase_pos_count = self.positions.positions.get(s, {}).get('current_increase_pos_count',
                                                                                            1)

                        # there is profit here, consider whether exit this position.
                        if profit_pct >= config.exit_profit_pct and pull_back_pct >= config.profit_pull_back_pct:
                            """
                            the position has the profit and pull back meet requirements.
                            """
                            qty = round_to(abs(pos), min_qty)
                            #self.positions.update(symbol=s, trade_price=bid_price, trade_amount=qty, min_qty=min_qty,
                            #                     is_buy=False)            
                            Orders.append({"symbol":s,"trade_price":bid_price,"trade_amount":qty,"min_qty":min_qty,"is_buy":False})
                            
                            logging.info(
                                f"{s}: new sell order, price: {bid_price}, qty: {qty}, total_profit: {self.positions.total_profit}, time: {datetime.now()}")
                        # if the market price continue drop down you can increase your positions.

                        elif dump_pct >= config.increase_pos_when_drop_down and  current_increase_pos_count <= config.max_increase_pos_count:

                            # cancel the sell orders, when we want to place buy orders, we need to cancel the sell orders.
                        
                            buy_value = config.initial_trade_value * config.trade_value_multiplier ** current_increase_pos_count

                            qty = round_to(buy_value / bid_price, min_qty)

                            '''buy_order = self.http_client.place_order(symbol=s, order_side=OrderSide.BUY,
                                                                    order_type=OrderType.LIMIT, quantity=qty,
                                                                    price=bid_price)
                                                                    '''
                        # buy_order = {"clientOrderId":self.Id_increment(),"symbol":s,"buy_value":buy_value,"quantity":qty,"enterprice":bid_price}
                            #self.positions.update(symbol=s, trade_price=bid_price, trade_amount=qty, min_qty=min_qty,
                            #                     is_buy=True)
                            Orders.append({"symbol":s,"trade_price":bid_price,"trade_amount":qty,"min_qty":min_qty,"is_buy":True})
                            
                            logging.info(
                                f"{s}: buy order was filled, price: {bid_price}, qty: {qty}, total_profit: {self.positions.total_profit}, time: {datetime.now()}")
                            '''
                            #增加buy订单
                            if buy_order:
                                # resolve buy orders
                                orders = self.buy_orders_dict.get(s, [])
                                orders.append(buy_order)
                                self.buy_orders_dict[s] = orders'''

                else:
                    print(f"{s}: bid_price: {bid_price}, ask_price: {bid_price}")
            
            print("end!!")
            for s in deleted_positions:
                del self.positions.positions[s]  # delete the position data if the position notional is very small.
            for x in Orders:
                self.positions.update(symbol=x['symbol'],trade_price=x['trade_price'],trade_amount=x['trade_amount'],min_qty=x['min_qty'],is_buy=x['is_buy'])
            self.positions.save_data()        
        
        pos_symbols = self.positions.positions.keys()  # 有仓位的交易对信息.
        pos_count = len(pos_symbols)  # 仓位的个数.

        left_times = config.max_pairs - pos_count
        #print("买入信号",signal_data)
        if self.initial_id == signal_data.get('id', self.initial_id):
            # the id is not updated, indicates that the data is not updated.
            # print("the current initial_id is the same, we do nothing.")
            return
        self.get_all_tickers()
        if len(self.tickers_dict.keys()) == 0:
                return
        self.initial_id = signal_data.get('id', self.initial_id)
   
        index = 0
        for signal in signal_data.get('signals', []):
            s = signal['symbol']
            if signal['signal'] == 1 and index < left_times and s not in pos_symbols and signal[
                'hour_turnover'] >= config.turnover_threshold:
                ## allowed_lists and blocked_lists cannot be satisfied at the same time
                if len(config.allowed_lists) > 0 and s in config.allowed_lists:
                    index += 1
                    # the last one hour's the symbol jump over some percent.
                    self.place_order(s, signal['pct'], signal['pct_4h'])

                if s not in config.blocked_lists and len(config.allowed_lists) == 0:
                    index += 1
                    self.place_order(s, signal['pct'], signal['pct_4h'])

                if len(config.allowed_lists) == 0 and len(config.blocked_lists) == 0:
                    index += 1
                    self.place_order(s, signal['pct'], signal['pct_4h'])

    def place_order(self, symbol: str, hour_change: float, four_hour_change: float):

        buy_value = config.initial_trade_value
        min_qty = self.symbols_dict.get(symbol, {}).get('min_qty')
        bid_price = self.tickers_dict.get(symbol, {}).get('bid_price', 0)  # bid price
        if bid_price <= 0:
            print(f"error -> spot {symbol} bid_price is :{bid_price}")
            return

        qty = round_to(buy_value / bid_price, min_qty)
       
        ''' buy_order = self.http_client.place_order(symbol=symbol, order_side=OrderSide.BUY,
                                                 order_type=OrderType.LIMIT, quantity=qty,
                                                 price=bid_price)
                                                 '''
        buy_order = {"clientOrderId":self.Id_increment(),"symbol":symbol,"buy_value":buy_value,"quantity":qty,"enterprice":bid_price}
        #增加buy订单
        print(
            f"{symbol} hour change: {hour_change}, 4hour change: {four_hour_change}, place buy order: {buy_order}")
        '''
        if buy_order:
            # resolve buy orders
            orders = self.buy_orders_dict.get(symbol, [])
            orders.append(buy_order)
            self.buy_orders_dict[symbol] = orders
        ''' 
        self.positions.update(symbol=symbol, trade_price=bid_price, trade_amount=qty, min_qty=min_qty,
                                              is_buy=True)
    
        self.positions.save_data()

        logging.info(
                            f"{symbol}: new buy order , price: {bid_price}, qty: {qty}, total_profit: {self.positions.total_profit}, time: {datetime.now()}")