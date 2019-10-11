# encoding:utf-8
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
# write by fangshi

# 鉴于zipline 本身包括融资融券，卖空买空交易，这里根据国内交易方式对order进行改写
# 要求在handle_data中并不进行直接order,而是将所有的order,转换成order_list，进行统一处理
# data_frequency


import time
import pandas as pd
from zipline import TradingAlgorithm
from zipline.api import order, sid,get_datetime,symbol
import copy

# 定义一个类，用于对order命令的拓展用于进行所有的order措施，先卖后买
class OrderList(object):
    def __init__(self, pre_time=0,now_time=0,cash=0,amount = 0):
        self.pre_time = pre_time
        self.now_time = now_time
        self.cash = cash
        self.amount = amount# 这里面均指可使用的
        
        """
        """
        
    def order_list(self,orders,date,cash,amount,date_frequency = 'day',Financing=False):
        #print self.amount
        #print orders
     #其中order内部包含各种命令，内部的order 格式为[股票代码，买卖数量，价格，交易时间，每个order开始的资金量，每个bar开始的股票数量]
        sell_order = [i for i in orders if i[1]<0]
        buy_order =[t for t in orders if t[1]>0]
    # 以上部分为将order的命令分为买入卖出，执行先卖出后买入的策略
        if self.now_time == self.pre_time == 0:
            #print u'更牛逼'
            self.now_time = date
            self.pre_time = date
            self.amountq = amount # order 交易前的
            self.cash = cash #
    
    # 这里我们执行的是先卖后买策略,日间交易，非融资融券
        if date_frequency=='day' and Financing == False:
            #self.amountq = amount # order 交易前的
            self.cash = cash #
            #print amount,orders
            #print raw_input()
            for sell in sell_order:
                if abs(sell[1])<=amount[sell[0].symbol]:
                    order(sell[0],sell[1])
                    self.cash+=abs(sell[1]*sell[2])
                else:
                    order(sell[0],amount[sell[0].symbol])
                    self.cash+=abs(amount[sell[0].symbol]*sell[2])
            for buy in buy_order:
                if self.cash>=buy[1]*buy[2]:
                    order(buy[0],buy[1])
                    self.cash = self.cash - buy[1]*buy[2]
                elif self.cash>0 and self.cash<buy[1]*buy[2]:
                    buy[1] = (self.cash//(buy[2]*100))*100
                    order(buy[0],buy[1])
                    self.cash = self.cash - buy[1]*buy[2]
                else:
                    pass
    
    # 这里我们执行先卖后买的策略，日内分钟交易，非融资融券
        if date_frequency =='minute' and Financing == False:
            #print u'买入order',buy_order
            #print u'卖出order',sell_order
            self.cash = cash
            self.amountq =amount
            if orders ==[]:
                pass
            else:
                # 进行先卖
                if self.amountq !={}:
                    for sell in sell_order:
                        #print sell
                        #raw_input()
                        sell[2] = float("%.2f"%sell[2])
                        if abs(sell[1])<self.amountq[sell[0].symbol]:
                            if sell[1]<0:
                                print date,u'卖出',sell[0].symbol,sell[1],sell[2]
                                order(sell[0],sell[1])
                                self.cash=self.cash + abs(sell[1]*sell[2])
                                self.amountq[sell[0].symbol]= int(self.amountq[sell[0].symbol])-abs(sell[1])
                            #print self.amountq[sell[0]],'print self.amount[sell[0]].amount'
                        else:
                            sell[1] = -1*self.amountq[sell[0].symbol]
                            if sell[1]<0:
                                print date,u'卖出',sell[0].symbol,sell[1],sell[2]
                                order(sell[0],sell[1])
                                self.cash = self.cash +abs(sell[1]*sell[2])
                                self.amountq[sell[0].symbol]= int(self.amountq[sell[0].symbol])-abs(sell[1])
                            #print self.amountq[sell[0].symbol],'print self.amount[sell[0]].amount'
                for buy in buy_order:
                    buy[2] = float("%.2f"%buy[2])
                    #print self.cash,u'资金量',self.cash/buy[2],buy[2]*buy[1]
                    buy[1]= buy[1] - buy[1]%100
                    if self.cash>=buy[2]*buy[1]:
                        #print  u'买盘这里'
                        if buy[1]>0:
                            print date,u'这里是买入',buy[2],buy[1],buy[0].symbol
                            order(buy[0],buy[1])
                        #print u'进入这里买1'
                            self.cash = self.cash - buy[1]*buy[2]
                    elif self.cash>0 and self.cash <buy[1]*buy[2]:
                        buy[1] = (self.cash//(buy[2]*100))*100
                        #print u'进入这里买2'
                        if buy[1]>0:
                            print date,u'这里是买入',buy[2],buy[1],buy[0].symbol
                            order(buy[0],buy[1])
                            self.cash = self.cash - buy[1]*buy[2]
                    else:
                        print u'无操作'
                        pass
                  
                    
            
    
    
        
    # 
    