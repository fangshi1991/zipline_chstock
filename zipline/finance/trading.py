# encoding:utf-8
# Copyright 2014 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# asset_finder

import bisect
import logbook
import datetime

import pandas as pd
import numpy as np
from six import string_types
from sqlalchemy import create_engine

from zipline.data.loader import load_market_data
from zipline.utils import tradingcalendar_china
from zipline.assets import AssetFinder
from zipline.assets.asset_writer import (
    AssetDBWriterFromList,
    AssetDBWriterFromDictionary,
    AssetDBWriterFromDataFrame)
from zipline.errors import (
    NoFurtherDataError
)


log = logbook.Logger('Trading')


# The financial simulations in zipline depend on information
# about the benchmark index and the risk free rates of return.
# The benchmark index defines the benchmark returns used in
# the calculation of performance metrics such as alpha/beta. Many
# components, including risk, performance, transforms, and
# batch_transforms, need access to a calendar of trading days and
# market hours. The TradingEnvironment maintains two time keeping
# facilities:
#   - a DatetimeIndex of trading days for calendar calculations
#   - a timezone name, which should be local to the exchange
#   hosting the benchmark index. All dates are normalized to UTC
#   for serialization and storage, and the timezone is used to
#   ensure proper rollover through daylight savings and so on.
#
# User code will not normally need to use TradingEnvironment
# directly. If you are extending zipline's core financial
# components and need to use the environment, you must import the module and
# build a new TradingEnvironment object, then pass that TradingEnvironment as
# the 'env' arg to your TradingAlgorithm.
# _process_snapshot
#   zipline中的金融模拟取决于有关基准指数和无风险回报率的信息。
#   基准指数定义了在计算性能指标（如alpha / beta）时使用的基准回报。
#   许多组件（包括风险，性能，转换，batch_transforms）都需要访问交易日和市场时段的日历。
#    TradingEnvironment维护两个计时设施：
#    日历计算的交易日的DatetimeIndex
#   - 时区名称，应该是托管基准索引的交换所的本地名称。
#   所有日期都标准化为UTC以进行序列化和存储，时区用于确保通过夏令时进行适当的翻转等。
#   用户代码通常不需要直接使用TradingEnvironment。
#   如果要扩展zipline的核心财务组件并需要使用环境，则必须导入模块并构建新的TradingEnvironment对象，
#   然后将TradingEnvironment作为'env'arg传递给TradingAlgorithm。 _process_snapshot

class TradingEnvironment(object):

    # Token used as a substitute for pickling objects that contain a
    # reference to a TradingEnvironment
    # 令牌用作替代包含对TradingEnvironment的引用的酸洗对象
    PERSISTENT_TOKEN = "<TradingEnvironment>"

    def __init__(
        self,
        load=None,
        bm_symbol='000001',
        exchange_tz="Asia/Shanghai",
        min_date=None,
        max_date=None,
        env_trading_calendar=tradingcalendar_china,
        asset_db_path=':memory:'
    ):
        """
        @load is function that returns benchmark_returns and treasury_curves
        The treasury_curves are expected to be a DataFrame with an index of
        dates and columns of the curve names, e.g. '10year', '1month', etc.
        # load是返回benchmark_returns和treasury_curves的函数.tourasury_curves应该是一个DataFrame，
        # 其中包含曲线名称的日期和列的索引，例如： '10年'，'1个月'等
        """
        self.trading_day = env_trading_calendar.trading_day.copy()

        # `tc_td` is short for "trading calendar trading days"
        tc_td = env_trading_calendar.trading_days
        self.trading_days = tc_td[tc_td.slice_indexer(min_date, max_date)]
        #print self.trading_day,'trading_days'
        

        self.first_trading_day = self.trading_days[0]
        self.last_trading_day = self.trading_days[-1]
        #print self.first_trading_day,self.last_trading_day
        self.early_closes = env_trading_calendar.get_early_closes(
            self.first_trading_day, self.last_trading_day)

        self.open_and_closes = env_trading_calendar.open_and_closes.loc[
            self.trading_days]

        self.bm_symbol = bm_symbol
        if not load:
            load = load_market_data
            
        # 下面的用于基准每日收益情况，以及国债收益率情况
        #print self.trading_day
        #print self.trading_days
        self.benchmark_returns, self.treasury_curves = \
            load(self.trading_day, self.trading_days, self.bm_symbol)
        #print self.benchmark_returns
        #raw_input()
        if max_date:
            tr_c = self.treasury_curves
            # Mask the treasury curves down to the current date.
            # In the case of live trading, the last date in the treasury
            # curves would be the day before the date considered to be
            # 'today'.
            self.treasury_curves = tr_c[tr_c.index <= max_date]
        self.exchange_tz = exchange_tz
        if isinstance(asset_db_path, string_types):
            asset_db_path = 'sqlite:///%s' % asset_db_path
            self.engine = engine = create_engine(asset_db_path)
            AssetDBWriterFromDictionary().init_db(engine)
        else:
            self.engine = engine = asset_db_path

        if engine is not None:
            self.asset_finder = AssetFinder(engine)
        else:
            self.asset_finder = None

    def write_data(self,
                   engine=None,
                   equities_data=None,
                   futures_data=None,
                   exchanges_data=None,
                   root_symbols_data=None,
                   equities_df=None,
                   futures_df=None,
                   exchanges_df=None,
                   root_symbols_df=None,
                   equities_identifiers=None,
                   futures_identifiers=None,
                   exchanges_identifiers=None,
                   root_symbols_identifiers=None,
                   allow_sid_assignment=True):
        """ Write the supplied data to the database.

        Parameters
        ----------
        equities_data: dict, optional
            A dictionary of equity metadata
        futures_data: dict, optional
            A dictionary of futures metadata
        exchanges_data: dict, optional
            A dictionary of exchanges metadata
        root_symbols_data: dict, optional
            A dictionary of root symbols metadata
        equities_df: pandas.DataFrame, optional
            A pandas.DataFrame of equity metadata
        futures_df: pandas.DataFrame, optional
            A pandas.DataFrame of futures metadata
        exchanges_df: pandas.DataFrame, optional
            A pandas.DataFrame of exchanges metadata
        root_symbols_df: pandas.DataFrame, optional
            A pandas.DataFrame of root symbols metadata
        equities_identifiers: list, optional
            A list of equities identifiers (sids, symbols, Assets)
        futures_identifiers: list, optional
            A list of futures identifiers (sids, symbols, Assets)
        exchanges_identifiers: list, optional
            A list of exchanges identifiers (ids or names)
        root_symbols_identifiers: list, optional
            A list of root symbols identifiers (ids or symbols)
    将提供的数据写入数据库。
        
    参数
    ----------
    equities_data：dict，可选
    权益元数据字典
    futures_data：dict，可选
    期货元数据字典
     exchange_data：dict，可选
    交换元数据的字典
    root_symbols_data：dict，可选
    根符号元数据的字典
    equities_df：pandas.DataFrame，可选
    权益元数据的pandas.DataFrame
    futures_df：pandas.DataFrame，可选
    期货元数据的pandas.DataFrame
    exchange_df：pandas.DataFrame，可选
    交换元数据的pandas.DataFrame
    root_symbols_df：pandas.DataFrame，可选
    根符号元数据的pandas.DataFrame
    equities_identifiers：list，optional
    股票标识符列表（sids，symbols，Assets）
        futures_identifiers：list，optional
    期货标识符列表（sids，symbols，Assets）
        exchange_identifiers：list，可选
    交换标识符列表（ID或名称）
    root_symbols_identifiers：list，可选
    根符号标识符列表（ID或符号）
        “””
        """
        if engine:
            self.engine = engine

        # If any pandas.DataFrame data has been provided,
        # write it to the database.
        has_rows = lambda df: df is not None and len(df) > 0
        if any(map(has_rows, [equities_df,
                              futures_df,
                              exchanges_df,
                              root_symbols_df])):
            self._write_data_dataframes(
                equities=equities_df,
                futures=futures_df,
                exchanges=exchanges_df,
                root_symbols=root_symbols_df,
            )

        # Same for dicts.
        has_data = lambda d: d is not None and len(d) > 0
        if any(map(has_data, [equities_data,
                              futures_data,
                              exchanges_data,
                              futures_data])):
            self._write_data_dicts(
                equities=equities_data,
                futures=futures_data,
                exchanges=exchanges_data,
                root_symbols=root_symbols_data
            )

        # Same for iterables.
        if any(map(has_data, [equities_identifiers,
                              futures_identifiers,
                              exchanges_identifiers,
                              root_symbols_identifiers])):
            self._write_data_lists(
                equities=equities_identifiers,
                futures=futures_identifiers,
                exchanges=exchanges_identifiers,
                root_symbols=root_symbols_identifiers,
                allow_sid_assignment=allow_sid_assignment
            )

    def _write_data_lists(self, equities=None, futures=None, exchanges=None,
                          root_symbols=None, allow_sid_assignment=True):
        AssetDBWriterFromList(equities, futures, exchanges, root_symbols)\
            .write_all(self.engine, allow_sid_assignment=allow_sid_assignment)

    def _write_data_dicts(self, equities=None, futures=None, exchanges=None,
                          root_symbols=None):
        AssetDBWriterFromDictionary(equities, futures, exchanges, root_symbols)\
            .write_all(self.engine)

    def _write_data_dataframes(self, equities=None, futures=None,
                               exchanges=None, root_symbols=None):
        AssetDBWriterFromDataFrame(equities, futures, exchanges, root_symbols)\
            .write_all(self.engine)

    def normalize_date(self, test_date):
        test_date = pd.Timestamp(test_date, tz='UTC')
        return pd.tseries.tools.normalize_date(test_date)

    def utc_dt_in_exchange(self, dt):
        return pd.Timestamp(dt).tz_convert(self.exchange_tz)

    def exchange_dt_in_utc(self, dt):
        return pd.Timestamp(dt, tz=self.exchange_tz).tz_convert('UTC')

    def is_market_hours(self, test_date):
        if not self.is_trading_day(test_date):
            return False

        mkt_open, mkt_close = self.get_open_and_close(test_date)
        return test_date >= mkt_open and test_date <= mkt_close

    def is_trading_day(self, test_date):
        dt = self.normalize_date(test_date)
        return (dt in self.trading_days)

    def next_trading_day(self, test_date):
        dt = self.normalize_date(test_date)
        delta = datetime.timedelta(days=1)

        while dt <= self.last_trading_day:
            dt += delta
            if dt in self.trading_days:
                return dt

        return None

    def previous_trading_day(self, test_date):
        dt = self.normalize_date(test_date)
        delta = datetime.timedelta(days=-1)

        while self.first_trading_day < dt:
            dt += delta
            if dt in self.trading_days:
                return dt

        return None

    def add_trading_days(self, n, date):
        """
        Adds n trading days to date. If this would fall outside of the
        trading calendar, a NoFurtherDataError is raised.

        :Arguments:
            n : int
                The number of days to add to date, this can be positive or
                negative.
            date : datetime
                The date to add to.

        :Returns:
            new_date : datetime
                n trading days added to date.
        """
        if n == 1:
            return self.next_trading_day(date)
        if n == -1:
            return self.previous_trading_day(date)

        idx = self.get_index(date) + n
        if idx < 0 or idx >= len(self.trading_days):
            raise NoFurtherDataError(
                msg='Cannot add %d days to %s' % (n, date)
            )

        return self.trading_days[idx]

    def days_in_range(self, start, end):
        mask = ((self.trading_days >= start) &
                (self.trading_days <= end))
        return self.trading_days[mask]

    def opens_in_range(self, start, end):
        return self.open_and_closes.market_open.loc[start:end]

    def closes_in_range(self, start, end):
        return self.open_and_closes.market_close.loc[start:end]

    def minutes_for_days_in_range(self, start, end):
        """
        Get all market minutes for the days between start and end, inclusive.
        """
        start_date = self.normalize_date(start)
        end_date = self.normalize_date(end)

        all_minutes = []
        for day in self.days_in_range(start_date, end_date):
            day_minutes = self.market_minutes_for_day(day)
            all_minutes.append(day_minutes)

        # Concatenate all minutes and truncate minutes before start/after end.
        return pd.DatetimeIndex(
            np.concatenate(all_minutes), copy=False, tz='UTC',
        )

    def next_open_and_close(self, start_date):
        """
        Given the start_date, returns the next open and close of
        the market.
        """
        next_open = self.next_trading_day(start_date)

        if next_open is None:
            raise NoFurtherDataError(
                msg=("Attempt to backtest beyond available history. "
                     "Last known date: %s" % self.last_trading_day)
            )

        return self.get_open_and_close(next_open)

    def previous_open_and_close(self, start_date):
        """
        Given the start_date, returns the previous open and close of the
        market.
        """
        previous = self.previous_trading_day(start_date)

        if previous is None:
            raise NoFurtherDataError(
                msg=("Attempt to backtest beyond available history. "
                     "First known date: %s" % self.first_trading_day)
            )
        return self.get_open_and_close(previous)

    def next_market_minute(self, start):
        """
        Get the next market minute after @start. This is either the immediate
        next minute, the open of the same day if @start is before the market
        open on a trading day, or the open of the next market day after @start.
        """
        if self.is_trading_day(start):
            market_open, market_close = self.get_open_and_close(start)
            #print market_open, market_close
            # If start before market open on a trading day, return market open.
            if start < market_open:
                return market_open
            # If start is during trading hours, then get the next minute.
            elif start < market_close:
                #print start.hour,start.minute
                if start.hour ==9 and start.minute ==25:
                    return start + datetime.timedelta(minutes = 5)
                elif start.hour ==11 and start.minute ==29:
                    return start+datetime.timedelta(minutes=91)
                else:
                    return start + datetime.timedelta(minutes=1)
        # If start is not in a trading day, or is after the market close
        # then return the open of the *next* trading day.
        return self.next_open_and_close(start)[0]

    def previous_market_minute(self, start):
        """
        Get the next market minute before @start. This is either the immediate
        previous minute, the close of the same day if @start is after the close
        on a trading day, or the close of the market day before @start.
        """
        if self.is_trading_day(start):
            market_open, market_close = self.get_open_and_close(start)
            # If start after the market close, return market close.
            if start > market_close:
                return market_close
            # If start is during trading hours, then get previous minute.
            if start > market_open:
                return start - datetime.timedelta(minutes=1)
        # If start is not a trading day, or is before the market open
        # then return the close of the *previous* trading day.
        return self.previous_open_and_close(start)[1]

    def get_open_and_close(self, day):
        #print day.date()
        #raw_input()
        #print index
        index = self.open_and_closes.index.get_loc(day.date())
        todays_minutes = self.open_and_closes.iloc[index]
        #print index,u'index的数据'
        #print todays_minutes,u'todays_minutes的数据'
        return todays_minutes[0], todays_minutes[1]

    def market_minutes_for_day(self, stamp):
        market_open, market_close = self.get_open_and_close(stamp)
        return pd.date_range(market_open, market_close, freq='T')

    def open_close_window(self, start, count, offset=0, step=1):
        """
        Return a DataFrame containing `count` market opens and closes,
        beginning with `start` + `offset` days and continuing `step` minutes at
        a time.
        """
        # TODO: Correctly handle end of data.
        start_idx = self.get_index(start) + offset
        stop_idx = start_idx + (count * step)

        index = np.arange(start_idx, stop_idx, step)

        return self.open_and_closes.iloc[index]

    def market_minute_window(self, start, count, step=1):
        """
        Return a DatetimeIndex containing `count` market minutes, starting with
        `start` and continuing `step` minutes at a time.
        """
        if not self.is_market_hours(start):
            raise ValueError("market_minute_window starting at "
                             "non-market time {minute}".format(minute=start))

        all_minutes = []

        current_day_minutes = self.market_minutes_for_day(start)
        first_minute_idx = current_day_minutes.searchsorted(start)
        minutes_in_range = current_day_minutes[first_minute_idx::step]

        # Build up list of lists of days' market minutes until we have count
        # minutes stored altogether.
        while True:

            if len(minutes_in_range) >= count:
                # Truncate off extra minutes
                minutes_in_range = minutes_in_range[:count]

            all_minutes.append(minutes_in_range)
            count -= len(minutes_in_range)
            if count <= 0:
                break

            if step > 0:
                start, _ = self.next_open_and_close(start)
                current_day_minutes = self.market_minutes_for_day(start)
            else:
                _, start = self.previous_open_and_close(start)
                current_day_minutes = self.market_minutes_for_day(start)

            minutes_in_range = current_day_minutes[::step]

        # Concatenate all the accumulated minutes.
        return pd.DatetimeIndex(
            np.concatenate(all_minutes), copy=False, tz='UTC',
        )

    def trading_day_distance(self, first_date, second_date):
        first_date = self.normalize_date(first_date)
        second_date = self.normalize_date(second_date)

        # TODO: May be able to replace the following with searchsorted.
        # Find leftmost item greater than or equal to day
        i = bisect.bisect_left(self.trading_days, first_date)
        if i == len(self.trading_days):  # nothing found
            return None
        j = bisect.bisect_left(self.trading_days, second_date)
        if j == len(self.trading_days):
            return None

        return j - i

    def get_index(self, dt):
        """
        Return the index of the given @dt, or the index of the preceding
        trading day if the given dt is not in the trading calendar.
        """
        ndt = self.normalize_date(dt)
        if ndt in self.trading_days:
            return self.trading_days.searchsorted(ndt)
        else:
            return self.trading_days.searchsorted(ndt) - 1


class SimulationParameters(object):
    def __init__(self, period_start, period_end,
                 capital_base=10e3,
                 emission_rate='daily',
                 data_frequency='daily',
                 env=None):

        self.period_start = period_start
        self.period_end = period_end
        self.capital_base = capital_base

        self.emission_rate = emission_rate
        self.data_frequency = data_frequency

        # copied to algorithm's environment for runtime access
        self.arena = 'backtest'

        if env is not None:
            self.update_internal_from_env(env=env)

    def update_internal_from_env(self, env):

        assert self.period_start <= self.period_end, \
            "Period start falls after period end."

        assert self.period_start <= env.last_trading_day, \
            "Period start falls after the last known trading day."
        assert self.period_end >= env.first_trading_day, \
            "Period end falls before the first known trading day."

        self.first_open = self._calculate_first_open(env)
        self.last_close = self._calculate_last_close(env)

        start_index = env.get_index(self.first_open)
        end_index = env.get_index(self.last_close)

        # take an inclusive slice of the environment's
        # trading_days.
        self.trading_days = env.trading_days[start_index:end_index + 1]

    def _calculate_first_open(self, env):
        """
        Finds the first trading day on or after self.period_start.
        """
        first_open = self.period_start
        one_day = datetime.timedelta(days=1)

        while not env.is_trading_day(first_open):
            first_open = first_open + one_day

        mkt_open, _ = env.get_open_and_close(first_open)
        return mkt_open

    def _calculate_last_close(self, env):
        """
        Finds the last trading day on or before self.period_end
        """
        last_close = self.period_end
        one_day = datetime.timedelta(days=1)

        while not env.is_trading_day(last_close):
            last_close = last_close - one_day

        _, mkt_close = env.get_open_and_close(last_close)
        return mkt_close

    @property
    def days_in_period(self):
        """return the number of trading days within the period [start, end)"""
        return len(self.trading_days)

    def __repr__(self):
        return """
{class_name}(
    period_start={period_start},
    period_end={period_end},
    capital_base={capital_base},
    data_frequency={data_frequency},
    emission_rate={emission_rate},
    first_open={first_open},
    last_close={last_close})\
""".format(class_name=self.__class__.__name__,
           period_start=self.period_start,
           period_end=self.period_end,
           capital_base=self.capital_base,
           data_frequency=self.data_frequency,
           emission_rate=self.emission_rate,
           first_open=self.first_open,
           last_close=self.last_close)


def noop_load(*args, **kwargs):
    """
    A method that can be substituted in as the load method in a
    TradingEnvironment to prevent it from loading benchmarks.

    Accepts any arguments, but returns only a tuple of Nones regardless
    of input.
    """
    return None, None
