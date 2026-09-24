import re
import urllib.parse
import urllib.request
from typing import Optional, Tuple, Dict, List


class StockResolver:
    """
    股票实体解析器：
    支持从用户的自然语言提问中精准抽取并解析 A 股代码与股票名称。
    采用：6 位代码正则 + 内存高频缓存 + 停用词词界切分 + 动态联想。
    """

    # 本地高频股票静态词典缓存
    POPULAR_STOCKS: Dict[str, str] = {
        '长电科技': '600584',
        '贵州茅台': '600519',
        '茅台': '600519',
        '比亚迪': '002594',
        '宁德时代': '300750',
        '赛力斯': '601127',
        '太极实业': '600667',
        '中芯国际': '688981',
        '东方财富': '300059',
        '中国平安': '601318',
        '平安银行': '000001',
        '招商银行': '600036',
        '五粮液': '000858',
        '科大讯飞': '002230',
        '中兴通讯': '000063',
        '立讯精密': '002475',
        '药明康德': '603259',
        '工业富联': '601138',
        '隆基绿能': '601012',
    }

    _RUNTIME_CACHE: Dict[str, Optional[Tuple[str, str]]] = {}

    # 常见对话停用词列表（用于边界切分）
    STOP_WORDS = [
        '成交额', '成交量', '全天', '成交', '量能', '现价', '价格', '收盘价',
        '帮我', '看看', '分析', '情绪', '散户', '今天', '昨天', '明天',
        '怎么样', '有没有', '诱多', '风险', '行情', '大家', '都在', '说什么',
        '股票', '最近', '现在', '请问', '如何', '怎样', '走势', '查查',
        '查询', '诊断', '了解', '主力', '出货', '洗盘', '跌了', '涨了',
        '买入', '卖出', '仓位', '多少', '那它', '这个', '这只', '刚才',
        '什么', '怎么', '模型', '你好', '谢谢', '哪些', '反讽', '为什么'
    ]

    @classmethod
    def resolve_from_text(cls, query: str) -> Optional[Tuple[str, str]]:
        if not query or not query.strip():
            return None

        clean_query = query.strip()

        # 1. 优先正则提取 6 位 A 股数字代码 (60/68/00/30 开头)
        code_match = re.search(r'\b(60\d{4}|68\d{4}|00\d{4}|30\d{4})\b', clean_query)
        if code_match:
            stock_code = code_match.group(1)
            stock_name = cls.search_name_by_code(stock_code) or f'A股 {stock_code}'
            return stock_code, stock_name

        # 2. 静态词典快速命中 (按词长降序匹配)
        sorted_keys = sorted(cls.POPULAR_STOCKS.keys(), key=lambda k: len(k), reverse=True)
        for name in sorted_keys:
            if name in clean_query:
                code = cls.POPULAR_STOCKS[name]
                return code, name

        # 3. 停用词切分：将原句中的已知停用词替换为空格，避免“全天成交”跨词产生“天成”
        sanitized = clean_query
        for sw in sorted(cls.STOP_WORDS, key=len, reverse=True):
            sanitized = sanitized.replace(sw, ' ')

        # 提取保留下来的中文名词块
        tokens = [re.sub(r'[^一-龥a-zA-Z0-9]', '', t) for t in sanitized.split()]
        tokens = [t for t in tokens if len(t) >= 2]

        for token in tokens:
            # 尝试直接检索完整 token（如“太极实业”）
            if token in cls._RUNTIME_CACHE:
                cached = cls._RUNTIME_CACHE[token]
                if cached:
                    return cached
                continue

            res = cls.search_online(token)
            cls._RUNTIME_CACHE[token] = res
            if res:
                return res

        return None

    @classmethod
    def search_name_by_code(cls, stock_code: str) -> Optional[str]:
        try:
            url = f'http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={stock_code}'
            req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                text = resp.read().decode('gbk', errors='ignore')
            if 'suggestvalue="' in text:
                val = text.split('suggestvalue="')[1].split('"')[0]
                if val:
                    first_item = val.split(';')[0].split(',')
                    if len(first_item) >= 3 and first_item[2] == stock_code:
                        return first_item[0]
        except Exception:
            pass
        return None

    @classmethod
    def search_online(cls, keyword: str) -> Optional[Tuple[str, str]]:
        try:
            encoded_key = urllib.parse.quote(keyword)
            url = f'http://suggest3.sinajs.cn/suggest/type=11,12,13,14,15&key={encoded_key}'
            req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2) as resp:
                text = resp.read().decode('gbk', errors='ignore')

            if 'suggestvalue="' in text:
                val = text.split('suggestvalue="')[1].split('"')[0]
                if val:
                    items = val.split(';')
                    for item in items:
                        parts = item.split(',')
                        if len(parts) >= 4:
                            name = parts[0]
                            code = parts[2]
                            # 严格匹配：keyword 必须是股票名称的前缀或完全一致
                            if (name.startswith(keyword) or keyword == name) and re.match(r'^(60\d{4}|68\d{4}|00\d{4}|30\d{4})$', code):
                                return code, name
        except Exception:
            pass
        return None
