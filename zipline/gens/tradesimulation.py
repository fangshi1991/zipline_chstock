# -*- coding: UTF-8 -*-
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
# raw_input()
# _handle_data
# print 
from datetime import timedelta
from itertools import takewhile

from contextlib2 import ExitStack
from logbook import Logger, Processor
from pandas.tslib import normalize_date

from zipline.errors import SidsNotFound
from zipline.finance.trading import NoFurtherDataError
from zipline.protocol import (
    BarData,
    DATASOURCE_TYPE,
    Event,
    SIDData,
)
from zipline.utils.api_support import ZiplineAPI
from zipline.utils.data import SortedDict

log = Logger('Trade Simulation')


class AlgorithmSimulator(object):

    EMISSION_TO_PERF_KEY_MAP = {
        'minute': 'minute_perf',
        'daily': 'daily_perf'
    }

    def __init__(self, algo, sim_params):

        # ==============
        # Simulation
        # Param Setup
        # ==============
        self.sim_params = sim_params

        # ==============
        # Algo Setup
        # ==============
        self.algo = algo
        self.algo_start = normalize_date(self.sim_params.first_open)
        self.env = algo.trading_environment

        # ==============
        # Snapshot Setup
        # ============== 

        _day = timedelta(days=1)

        def _get_removal_date(sid,
                              finder=self.env.asset_finder,
                              default=self.sim_params.last_close + _day):
            """
            Get the date of the morning on which we should remove an asset from
            data.

            If we don't have an auto_close_date, this is just the end of the
            simulation.

            If we have an auto_close_date, then we remove assets from data on
            max(asset.auto_close_date, asset.end_date + timedelta(days=1))

            We hold assets at least until auto_close_date because up until that
            date the user might still hold positions or have open orders in an
            expired asset.

            We hold assets at least until end_date + 1, because an asset
            continues trading until the **end** of its end_date.  Even if an
            asset auto-closed before the end_date (say, because Interactive
            Brokers clears futures positions prior the actual notice or
            expiration), there may still be trades arriving that represent
            signals for other assets that are still tradeable. (Particularly in
            the futures case, trading in the final days of a contract are
            likely relevant for trading the next contract on the same future
            chain.)
            获取上午的日期，我们应该从数据中删除资产。

            #如果我们没有auto_close_date，那只是结束了
            #模拟。

            #如果我们有auto_close_date，那么我们从数据中删除资产
            #max（asset.auto_close_date，asset.end_date + timedelta（days = 1））

            #我们至少持有资产直到auto_close_date，因为直到那之前
            #用户可能仍然持有头寸或在一个开仓订单的日期
            #过期资产。

            #我们持有资产至少到end_date + 1，因为资产
            #继续交易直到其end_date的**结束**。即使是
            #end_date之前的资产自动关闭（比如因为Interactive
            #经纪人在实际通知之前清算期货头寸或
            #到期），可能仍有交易到达代表
            #其他资产仍可交易的信号。 （特别是在
            #期货案例，在合约的最后几天进行交易
            #可能与在同一个未来交易下一份合约有关
            #链。）
            """
            try:
                asset = finder.retrieve_asset(sid)
            except ValueError:
                # Handle sid not an int, such as from a custom source.
                # So that they don't compare equal to other sids, and we'd
                # blow up comparing strings to ints, let's give them unique
                # close dates.
                return default + timedelta(microseconds=id(sid))
            except SidsNotFound:
                return default

            auto_close_date = asset.auto_close_date
            if auto_close_date is None:
                # If we don't have an auto_close_date, we never remove an asset
                # from the user's portfolio.
                return default

            end_date = asset.end_date
            if end_date is None:
                # If we have an auto_close_date but not an end_date, clear the
                # asset from data when we clear positions/orders.
                return auto_close_date

            # If we have both, make close once we're on or after the
            # auto_close_date, and strictly after the end_date.
            # See docstring above for an explanation of this logic.
            return max(auto_close_date, end_date + _day)

        self._get_removal_date = _get_removal_date

        # The algorithm's data as of our most recent event.
        # Maintain sids in order by asset close date, so that we can more
        # efficiently remove them when their times come...算法的数据是我们最近的事件。
        # 按资产截止日期按顺序维护sid，以便我们可以在时间到来时更有效地删除它们...
        self.current_data = BarData(SortedDict(self._get_removal_date))
        # We don't have a datetime for the current snapshot until we
        # receive a message.在收到消息之前，我们没有当前快照的日期时间
        self.simulation_dt = None

        # =============
        # Logging Setup
        # =============

        # Processor function for injecting the algo_dt into
        # user prints/logs.
        def inject_algo_dt(record):
            if 'algo_dt' not in record.extra:
                record.extra['algo_dt'] = self.simulation_dt
        self.processor = Processor(inject_algo_dt)

    def transform(self, stream_in):
        """
        Main generator work loop.
        """
        # Initialize the mkt_close
        mkt_open = self.algo.perf_tracker.market_open
        mkt_close = self.algo.perf_tracker.market_close


        # inject the current algo
        # snapshot time to any log record generated.
		# with 。。。as 是一种上下文管理器，打开与关闭。exitstack（）是一个语法糖

        with ExitStack() as stack:
            stack.enter_context(self.processor)
            stack.enter_context(ZiplineAPI(self.algo))

            data_frequency = self.sim_params.data_frequency
            self._call_before_trading_start(mkt_open)

            for date, snapshot in stream_in:
                #print date,u'在主循环之内的date',self.algo_start
                #raw_input()
                #for i in snapshot:
                #    print i
                #raw_input()
                
            # snapshot,为迭代的数据系统，包括时间，股票数据等

                # 进入主循环，跟随日期进行循环
                self.simulation_dt = date #模拟日期
                self.on_dt_changed(date)

                # If we're still in the warmup period.  Use the event to
                # update our universe, but don't yield any perf messages,
                # and don't send a snapshot to handle_data.
                # 如果在热身阶段
                # 判断是否进入交易日期，若开始了则handle_data发送给
                # 判断是否进行到达模拟开始的时间
                if date < self.algo_start:
                    for event in snapshot:
                        if event.type == DATASOURCE_TYPE.SPLIT:
                            self.algo.blotter.process_split(event)
                        elif event.type == DATASOURCE_TYPE.TRADE:
                            self.update_universe(event)
                            self.algo.perf_tracker.process_trade(event)
                        elif event.type == DATASOURCE_TYPE.CUSTOM:
                            self.update_universe(event)
                    if self.algo.history_container:
                        #print self.current_data
                        self.algo.history_container.update(self.current_data,date)
                else:
                    
                # 进入每日信息的处理，
                    messages = self._process_snapshot(
                        date,
                        snapshot,
                        self.algo.instant_fill,
                    )
                    # Perf messages are only emitted if the snapshot contained
                    # a benchmark event.
                    for message in messages:
                        yield message

                    # When emitting minutely, we need to call
                    # before_trading_start before the next trading day begins
                    if date == mkt_close:
                        if mkt_close <= self.algo.perf_tracker.last_close:
                            before_last_close = \
                                mkt_close < self.algo.perf_tracker.last_close
                            try:
                                mkt_open, mkt_close = \
                                    self.env.next_open_and_close(mkt_close)

                            except NoFurtherDataError:
                                # If at the end of backtest history,
                                # skip advancing market close.
                                pass

                            if before_last_close:
                                self._call_before_trading_start(mkt_open)

                    elif data_frequency == 'daily':
                        next_day = self.env.next_trading_day(date)

                        if next_day is not None and \
                           next_day < self.algo.perf_tracker.last_close:
                            self._call_before_trading_start(next_day) #如果下一天非空，并且next不是表现的最后一天。last_close,就
                    self.algo.portfolio_needs_update = True
                    self.algo.account_needs_update = True
                    self.algo.performance_needs_update = True
            risk_message = self.algo.perf_tracker.handle_simulation_end()
            yield risk_message

    def _process_snapshot(self, dt, snapshot, instant_fill):
	# 进程快照，用于对每日的数据进行处理。如果instal_fill =TRUE 我们延迟处理，直到handle_data被调用，
    # 每次处理，都先调用handle处理，看是否需要进行处理
        """
        Process a stream of events corresponding to a single datetime, possibly
        returning a perf message to be yielded.
        If @instant_fill = True, we delay processing of events until after the
        user's call to handle_data, and we process the user's placed orders
       before the snapshot's events.  Note that this introduces a lookahead
        bias, since the user effectively is effectively placing orders that are
        filled based on trades that happened prior to the call the handle_data.

        If @instant_fill = False, we process Trade events before calling
        handle_data.  This means that orders are filled based on trades
        occurring in the next snapshot.  This is the more conservative model,
        and as such it is the default behavior in TradingAlgorithm.
        """

        # Flags indicating whether we saw any events of type TRADE and type
        # BENCHMARK.  Respectively, these control whether or not handle_data is
        # called for this snapshot and whether we emit a perf message for this
        # snapshot.
        #  标志意味着是否我们看到任何类型的事件（trade或者benchmar）,他们分别控制是否为此快照调用handle_data
        # 以及是否为此快照发送perf信息
        any_trade_occurred = False
        benchmark_event_occurred = False
        if instant_fill:
            events_to_be_processed = []

        # Assign process events to variables to avoid attribute access in
        # innermost loops.
        # Done here, to allow for perf_tracker or blotter to be swapped out
        # or changed in between snapshots.
        # 将进程事件分配给变量以避免在最内层循环中进行属性访问。
        # 在此处完成，允许在快照之间换出或更改perf_tracker或blotter。
        perf_process_trade = self.algo.perf_tracker.process_trade
        perf_process_transaction = self.algo.perf_tracker.process_transaction
        perf_process_order = self.algo.perf_tracker.process_order # tracker 里面的数据process_order，对order数据进行处理
        perf_process_benchmark = self.algo.perf_tracker.process_benchmark
        perf_process_split = self.algo.perf_tracker.process_split
        perf_process_dividend = self.algo.perf_tracker.process_dividend
        perf_process_commission = self.algo.perf_tracker.process_commission
        perf_process_close_position = \
            self.algo.perf_tracker.process_close_position
        blotter_process_trade = self.algo.blotter.process_trade
        blotter_process_benchmark = self.algo.blotter.process_benchmark

        # Containers for the snapshotted events, so that the events are
        # processed in a predictable order, without relying on the sorted order
        # of the individual sources.
        # 快照事件的容器，以便可以顺序的处理事件，不用去追溯每个源的排序顺序

        # There is only one benchmark per snapshot, will be set to the current
        # benchmark iff it occurs.
        # 每个快照只有一个基准，如果发生时就将其设置为单签的基准
        benchmark = None
        # trades and customs are initialized as a list since process_snapshot
        # is most often called on market bars, which could contain trades or
        # custom events.
        # 交易和customs 被初始化为一个list ,因为进程快照经常被call,他们中包含交易和custom事件
        trades = []
        customs = []
        closes = []

        # splits and dividends are processed once a day.
        # 分割和分红每天处理一次
        #
        # The avoidance of creating the list every time this is called is more
        # to attempt to show that this is the infrequent case of the method,
        # since the performance benefit from deferring the list allocation is
        # marginal.  splits list will be allocated when a split occurs in the
        # snapshot.
        # 每次调用此列表时，避免创建每次都要创建列表
        splits = None
        # dividends list will be allocated when a dividend occurs in the
        # snapshot.
        dividends = None
        for event in snapshot:
            #print event
            if event.type == DATASOURCE_TYPE.TRADE:
                trades.append(event)
            elif event.type == DATASOURCE_TYPE.BENCHMARK:
                benchmark = event
            elif event.type == DATASOURCE_TYPE.SPLIT:
                if splits is None:
                    splits = []
                splits.append(event)
            elif event.type == DATASOURCE_TYPE.CUSTOM:
                customs.append(event)
            elif event.type == DATASOURCE_TYPE.DIVIDEND:
                if dividends is None:
                    dividends = []
                dividends.append(event)
            elif event.type == DATASOURCE_TYPE.CLOSE_POSITION:
                closes.append(event)
            else:
                raise log.warn("Unrecognized event=%s".format(event))

        # Handle benchmark first. 首先处理基准
        # 内部经纪人实施取决于首先处理的基准，以便可以注入经纪人报告的交易和佣金。
        # Internal broker implementation depends on the benchmark being
        # processed first so that transactions and commissions reported from
        # the broker can be injected.
        if benchmark is not None:
            benchmark_event_occurred = True
            perf_process_benchmark(benchmark)
            for txn, order in blotter_process_benchmark(benchmark):# 好像并没有运行到这里
                if txn.type == DATASOURCE_TYPE.TRANSACTION:
                    perf_process_transaction(txn)
                elif txn.type == DATASOURCE_TYPE.COMMISSION:
                    perf_process_commission(txn)
                perf_process_order(order)
        for trade in trades:
            #print trade,u'数据情况'
            #raw_input()
            self.update_universe(trade)
            any_trade_occurred = True
            if instant_fill:
                events_to_be_processed.append(trade)
            else:
                for txn, order in blotter_process_trade(trade):
                    if txn.type == DATASOURCE_TYPE.TRANSACTION:
                        perf_process_transaction(txn)
                    elif txn.type == DATASOURCE_TYPE.COMMISSION:
                        perf_process_commission(txn)
                    perf_process_order(order)
                perf_process_trade(trade)

        for custom in customs:
            self.update_universe(custom)

        for close in closes:
            self.update_universe(close)
            perf_process_close_position(close)

        if splits is not None: # 拆分
            for split in splits: 
                # process_split is not assigned to a variable since it is
                # called rarely compared to the other event processors.
                self.algo.blotter.process_split(split)
                perf_process_split(split)

        if dividends is not None: # 分红
            for dividend in dividends:
                perf_process_dividend(dividend)

        if any_trade_occurred:
            # 这里进行每次handle_data的处理
            new_orders = self._call_handle_data()
            for order in new_orders:
                perf_process_order(order)

        if instant_fill:
            # 这里handle_data已经被调用，并且已经下单，根据此快照中的事件填充用户订单
            # Now that handle_data has been called and orders have been placed,
            # process the event stream to fill user orders based on the events
            # from this snapshot. 
            for trade in events_to_be_processed: # events_to_be_processed 包含单日的股票数据
                #print trade
                for txn, order in blotter_process_trade(trade): # 进行处理
                    # txn 为下一步进行的价格以及成本花费等
                    if txn is not None:
                        #print u'进入到这里2'
                        #print txn.sid,txn.amount,txn.price,txn.commission
                        #raw_input()
                        #print u'进入到这里隔离perf_process_transactions'
                        perf_process_transaction(txn)
                    if order is not None:
                        perf_process_order(order)
                perf_process_trade(trade)

        if benchmark_event_occurred:
            return self.generate_messages(dt)
        else:
            return ()

    def _call_handle_data(self):
        """
        Call the user's handle_data, returning any orders placed by the algo
        during the call.
        # call 使用者的handle_data,返回算法发出的任何命令在call的时候
        """
        # 在algo中寻找事件管理的handle_data
        self.algo.event_manager.handle_data(
            self.algo,
            self.current_data,
            self.simulation_dt,
        )
        # 获取handle_data中的命令后并将其付给orders，将new_orders在此置为空置
        orders = self.algo.blotter.new_orders
        self.algo.blotter.new_orders = []
        return orders

    def _call_before_trading_start(self, dt):
        dt = normalize_date(dt)
        self.simulation_dt = dt
        self.on_dt_changed(dt)

        self._cleanup_expired_assets(dt, self.current_data, self.algo.blotter)

        self.algo.before_trading_start(self.current_data)

    def _cleanup_expired_assets(self, dt, current_data, algo_blotter):
        """
        Clear out any assets that have expired before starting a new sim day.

        Performs three functions:

        1. Finds all assets for which we have open orders and clears any
           orders whose assets are on or after their auto_close_date.

        2. Finds all assets for which we have positions and generates
           close_position events for any assets that have reached their
           auto_close_date.

        3. Finds and removes from data all sids for which
           _get_removal_date(sid) <= dt.
        """
        algo = self.algo
        expired = list(takewhile(
            lambda asset_id: self._get_removal_date(asset_id) <= dt,
            self.current_data
        ))
        for sid in expired:
            try:
                del self.current_data[sid]
            except KeyError:
                continue

        def create_close_position_event(asset):
            event = Event({
                'dt': dt,
                'type': DATASOURCE_TYPE.CLOSE_POSITION,
                'sid': asset.sid,
            })
            return event

        def past_auto_close_date(asset):
            acd = asset.auto_close_date
            return acd is not None and acd <= dt

        # Remove positions in any sids that have reached their auto_close date.
        to_clear = []
        finder = algo.asset_finder
        perf_tracker = algo.perf_tracker
        nonempty_position_assets = finder.retrieve_all(
            # get_nonempty_position_sids us just the non-empty positions, and
            # also avoids an unnecessary re-compuation of the portfolio.
            perf_tracker.position_tracker.get_nonempty_position_sids()
        )
        for asset in nonempty_position_assets:
            if past_auto_close_date(asset):
                to_clear.append(asset)
        for close_event in map(create_close_position_event, to_clear):
            perf_tracker.process_close_position(close_event)

        # Remove open orders for any sids that have reached their
        # auto_close_date.
        blotter = algo.blotter
        to_cancel = []
        for asset in blotter.open_orders:
            if past_auto_close_date(asset):
                to_cancel.append(asset)
        for asset in to_cancel:
            blotter.cancel_all(asset)

    def on_dt_changed(self, dt):
        if self.algo.datetime != dt:
            self.algo.on_dt_changed(dt)

    def generate_messages(self, dt):
        """
        Generator that yields perf messages for the given datetime.
        """
        # Ensure that updated_portfolio has been called at least once for this
        # dt before we emit a perf message.  This is a no-op if
        # updated_portfolio has already been called this dt.
        self.algo.updated_portfolio()
        self.algo.updated_account()

        rvars = self.algo.recorded_vars
        if self.algo.perf_tracker.emission_rate == 'daily':
            perf_message = \
                self.algo.perf_tracker.handle_market_close_daily()
            perf_message['daily_perf']['recorded_vars'] = rvars
            yield perf_message

        elif self.algo.perf_tracker.emission_rate == 'minute':
            # close the minute in the tracker, and collect the daily message if
            # the minute is the close of the trading day
            minute_message, daily_message = \
                self.algo.perf_tracker.handle_minute_close(dt)

            # collect and yield the minute's perf message
            minute_message['minute_perf']['recorded_vars'] = rvars
            yield minute_message

            # if there was a daily perf message, collect and yield it
            if daily_message:
                daily_message['daily_perf']['recorded_vars'] = rvars
                yield daily_message

    def update_universe(self, event):
        """
        Update the universe with new event information.
        # 更新股票池到最新的事件信息
        """
        # Update our knowledge of this event's sid
        # rather than use if event.sid in ..., just trying
        # and handling the excep tion is significantly faster
        try:
            sid_data = self.current_data[event.sid]
        except KeyError:
            sid_data = self.current_data[event.sid] = SIDData(event.sid)
        #print help(sid_data)
        sid_data.__dict__.update(event.__dict__)
