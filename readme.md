# 简介
zipline_chstock 为zipine 的本地化化版本。使用python2.7进行改写。使用本zipline时，请注意python 版本。
# 主要变动
## 1. 数据来源变动
基于原有的zipline 开发主要是为了适应美国市场，所以其数据的来源主要包括雅虎以及其他本地数据。所以本次我们将数据来源全部应用到本地，主要为mongodb数据库，读者可以根据自己本身数据情况，选择数据的来源，并进行改写。
*数据获取部分主要在zipline/data目录下，loader 和 mongodb,原zipline只存在loader文件夹，获取本地和从雅虎上获取的数据。mongodb.py
主要是对于mongodb的操作，loader 主要通过mongodb获取分钟和日线数据，并转换成相应的格式。*
## 2. 交易日历的改写
日历改写，由于中美交易时间不一致性，调整交易的日历序列，适用于国内
*交易日历部分主要在zipline/utils 目录下，原交易日历为tradingcalendar.py从此文件中，get_no_trading_days,get_trading_days,get_early_closes,以及get_open_and_close四个重要的函数。由于交易如的不一致性，这里需要将其进行调整，由于本zipline 仅用于回测研究，不涉及交易。所以这里的trading_days我们使用指数‘000001’的交易日期作为交易日期。
3. 涨跌停等规则的改写，买空卖空的改写，日内买卖限制t+1制度的改写。
4. 交易单元的改写，原交易仅支持day 和minute 周期的回测，本次改写增加了tick 数据回测系列，不过鉴于zipline 是事件驱动型框架，跟随每个tick进行回测耗时会比价大。
5. 其他部分改写，包括为了加速回测速度，对部分运算进行cython 的改写等。
# 使用方法
按照原始的文件布局，下载所有的文件，对应安装所需要版本的包，参考demo进行使用
#联系
如果有哪些不明白的地方，欢迎联系qq：94006733。会抽空统一回复
