#encoding:utf-8
# Copyright 2015 Quantopian, Inc.
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
from __future__ import division

import abc

import math

from copy import copy
from functools import partial

from six import with_metaclass

from zipline.finance.transaction import create_transaction
from zipline.utils.serialization_utils import (
    VERSION_LABEL
)

SELL = 1 << 0
BUY = 1 << 1
STOP = 1 << 2
LIMIT = 1 << 3


def transact_stub(slippage, commission, event, open_orders):
    """
    This is intended to be wrapped in a partial, so that the
    slippage and commission models can be enclosed.
    这是为了部分包装，因此可以包含滑点和佣金模型
    
    """
    #print event,u'你你你你你你你你'
    for order, transaction in slippage(event, open_orders):
        # transaction 里面包含sid, amount, dt, price, order_id, commission=None等,买的是早盘的价格
        #print u'原始价格',transaction.price
        #print order
        #print transaction
        if transaction and transaction.amount != 0:
            direction = math.copysign(1, transaction.amount)# 判断方向是买入还是卖出
            per_share, total_commission = commission.calculate(transaction)
            #print u'总体费用',total_commission
            transaction.price += per_share * direction# 价格变化，卖出就减去费用为价格，买入就加上交易费用
            transaction.price = float("%.2f"%transaction.price)
            transaction.commission = float('%.2f'%total_commission)
        #print u'调整价格',transaction.price
        yield order, transaction

# 交易部分，滑点和 费用
def transact_partial(slippage, commission):
    return partial(transact_stub, slippage, commission)


class LiquidityExceeded(Exception):
    pass


class SlippageModel(with_metaclass(abc.ABCMeta)):

    @property
    def volume_for_bar(self):
        return self._volume_for_bar

    @abc.abstractproperty
    def process_order(self, event, order):
        pass

    def simulate(self, event, current_orders):
        #print u'到这里了'

        self._volume_for_bar = 0

        for order in current_orders:

            if order.open_amount == 0:
                continue

            order.check_triggers(event)
            if not order.triggered:
                continue

            try:
                txn = self.process_order(event, order)
            except LiquidityExceeded:
                break

            if txn:
                self._volume_for_bar += abs(txn.amount)
                yield order, txn

    def __call__(self, event, current_orders, **kwargs):
        return self.simulate(event, current_orders, **kwargs)


class VolumeShareSlippage(SlippageModel):

    def __init__(self,
                 volume_limit=.25,
                 price_impact=0.1):

        self.volume_limit = volume_limit
        self.price_impact = price_impact

    def __repr__(self):
        return """
{class_name}(
    volume_limit={volume_limit},
    price_impact={price_impact})
""".strip().format(class_name=self.__class__.__name__,
                   volume_limit=self.volume_limit,
                   price_impact=self.price_impact)

    def process_order(self, event, order):

        max_volume = self.volume_limit * event.volume

        # price impact accounts for the total volume of transactions
        # created against the current minute bar
        # 价格影响占当前分钟栏创建的交易总量
        remaining_volume = max_volume - self.volume_for_bar
        if remaining_volume < 1:
            # we can't fill any more transactions
            raise LiquidityExceeded()

        # the current order amount will be the min of the
        # volume available in the bar or the open amount.
        cur_volume = int(min(remaining_volume, abs(order.open_amount)))

        if cur_volume < 1:
            return

        # tally the current amount into our total amount ordered.
        # total amount will be used to calculate price impact
        total_volume = self.volume_for_bar + cur_volume

        volume_share = min(total_volume / event.volume,
                           self.volume_limit)

        simulated_impact = volume_share ** 2 \
            * math.copysign(self.price_impact, order.direction) \
            * event.open
        if order.give_price==None:
            
            impacted_price = event.close + simulated_impact
        else:
            impacted_price = order.give_price+simulated_impact
        print u'收盘价',event.close,u'给定价',order.give_price,u'here里面'
        #print simulated_impact,u'滑点情况'
        #impacted_price = event.close + simulated_impact
        #print event ,u'event 情况'
        #raw_input()
        if order.limit:
            # this is tricky! if an order with a limit price has reached
            # the limit price, we will try to fill the order. do not fill
            # these shares if the impacted price is worse than the limit
            # price. return early to avoid creating the transaction.

            # buy order is worse if the impacted price is greater than
            # the limit price. sell order is worse if the impacted price
            # is less than the limit price
            if (order.direction > 0 and impacted_price > order.limit) or \
                    (order.direction < 0 and impacted_price < order.limit):
                return

        return create_transaction(
            event,
            order,
            impacted_price,
            math.copysign(cur_volume, order.direction)
        )

    def __getstate__(self):

        state_dict = copy(self.__dict__)

        STATE_VERSION = 1
        state_dict[VERSION_LABEL] = STATE_VERSION

        return state_dict

    def __setstate__(self, state):

        OLDEST_SUPPORTED_STATE = 1
        version = state.pop(VERSION_LABEL)

        if version < OLDEST_SUPPORTED_STATE:
            raise BaseException("VolumeShareSlippage saved state is too old.")

        self.__dict__.update(state)


class FixedSlippage(SlippageModel):

    def __init__(self, spread=0.0):
        """
        Use the fixed slippage model, which will just add/subtract
        a specified spread spread/2 will be added on buys and subtracted
        on sells per share
        """
        self.spread = spread

    def process_order(self, event, order):
        return create_transaction(
            event,
            order,
            event.price + (self.spread / 2.0 * order.direction),
            order.amount,
        )

    def __getstate__(self):

        state_dict = copy(self.__dict__)

        STATE_VERSION = 1
        state_dict[VERSION_LABEL] = STATE_VERSION

        return state_dict

    def __setstate__(self, state):

        OLDEST_SUPPORTED_STATE = 1
        version = state.pop(VERSION_LABEL)

        if version < OLDEST_SUPPORTED_STATE:
            raise BaseException("FixedSlippage saved state is too old.")

        self.__dict__.update(state)
