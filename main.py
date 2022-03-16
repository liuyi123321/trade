from lib2to3.pgen2.token import MINUS
import time
import logging
from trader.binance_spot_trader import BinanceSpotTrader
from trader.binance_future_trader import BinanceFutureTrader
from utils import config
from apscheduler.schedulers.background import BackgroundScheduler

format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=format, filename='log.txt')
logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
logger = logging.getLogger('binance')
from typing import Union
import numpy as np
import pandas as pd
from datetime import datetime

pd.set_option('expand_frame_repr', False)

from utils.config import signal_data


def get_data(trader: Union[BinanceFutureTrader, BinanceSpotTrader]):
    # traders.symbols is a dict data structure.
    symbols = trader.symbols_dict.keys()

    signals = []

    # we calculate the signal here.
    for symbol in symbols:
        klines = trader.get_klines(symbol=symbol, interval='15m', limit=1000)
        if len(klines) > 800:
            df = pd.DataFrame(klines, dtype=np.float64,
                              columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'turnover', 'a2',
                                       'a3', 'a4', 'a5'])
            df = df[['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover']]
            df.set_index('open_time', inplace=True)
            df.index = pd.to_datetime(df.index, unit='ms') + pd.Timedelta(hours=8)

            df_4hour = df.resample(rule='1H').agg({'open': 'first',
                                        'high': 'max',
                                        'low': 'min',
                                        'close': 'last',
                                        'volume': 'sum',
                                        'turnover': 'sum'
                                        })

            # print(df)

            # calculate the pair's price change is one hour. you can modify the code below.
            pct = df['close'] / df['open'] - 1
            pct_4h = df_4hour['close']/df_4hour['open'] - 1
            
            value = {'pct': pct[-1], 'pct_4h':pct_4h[-1] , 'symbol': symbol, 'hour_turnover': df['turnover'][-1]}

            if value['pct_4h'] > 1:
                continue
            # calculate your signal here.
            if value['pct'] >= config.pump_pct or value['pct_4h'] >= config.pump_pct_4h:
                # the signal 1 mean buy signal.
                value['signal'] = 1
            elif value['pct'] <= -config.pump_pct or value['pct_4h'] <= -config.pump_pct_4h:
                value['signal'] = -1
            else:
                value['signal'] = 0

            signals.append(value)

    signals.sort(key=lambda x: x['pct'], reverse=True)
    signal_data['id'] = signal_data['id'] + 1
    signal_data['time'] = datetime.now()
    signal_data['signals'] = signals
   # print(signal_data)

if __name__ == '__main__':

    #读取配置信息，展示禁止列表
    config.loads('./config.json')
    print(config.blocked_lists)
    #确定交易类型
    if config.platform == 'binance_spot':  # binance_spot
        trader = BinanceSpotTrader()
    else:
        trader = BinanceFutureTrader()

    #获取所有交易对信息
    trader.get_exchange_info()
    #测试signal
    get_data(trader)  # for testing
    #每一小时进行查找 
    scheduler = BackgroundScheduler(timezone= 'Asia/Shanghai')
    scheduler.add_job(get_data, trigger='cron', minute='*/15', args=(trader,))
    scheduler.start()
    
    while True:
        print("hello word!")
        time.sleep(10)
        trader.start()

"""
strategy idea: c

1. 每1个小时会挑选出前几个波动率最大的交易对(假设交易的是四个交易对).
2. 然后根据设置的参数进行下单(假设有两个仓位,那么波动率最大的两个，且他们过去一段时间是暴涨过的)
3. 然后让他们执行马丁策略.

"""
