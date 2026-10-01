import logging
import re
from typing import Any, Dict, List
import httpx
from bs4 import BeautifulSoup
from src.core.schema import RawPost, NewsArticle, AnnouncementItem
from src.tools.base import Tool, ToolParameter

logger = logging.getLogger(__name__)


class StockForumScraper(Tool):
    """
    多源金融情报与东方财富股吧全量采集工具
    涵盖：
    1. 散户社区极端情绪与反讽言论（东方财富股吧，默认抓取全量最大深度）
    2. 主流专业财经媒体研报与主力动向（新浪财经个股滚动资讯）
    3. 上市公司官方定期报告与权威公告（新浪/东财披露专区）
    """
    name = "stock_scraper"
    description = "采集 A 股标的的多源金融情报，包括股吧散户帖子、主流财经新闻与官方公告"
    parameters = [
        ToolParameter(
            name="stock_code",
            type="string",
            description="6位A股股票代码，例如 600519 或 002594",
            required=True,
        ),
        ToolParameter(
            name="max_posts",
            type="integer",
            description="抓取散户发帖最大数量",
            required=False,
            default=30,
        ),
    ]

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    SPAM_PATTERNS = [
        r"微[信x]|加[vV]|进群|免费领|涨停战法|牛股推荐|内幕|私信|带飞",
        r"点击链接|加老师|领取代码|短线翻倍",
    ]
    SPAM_REGEX = re.compile("|".join(SPAM_PATTERNS))

    def __init__(self, timeout: float = 8.0):
        super().__init__()
        self.timeout = timeout

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Tool 标准执行入口"""
        stock_code = kwargs.get("stock_code", "")
        # LLM 可能传入 "30篇" 之类的非纯数字参数，做健壮性兜底
        try:
            max_posts = int(str(kwargs.get("max_posts", 30)).strip().split()[0])
        except (ValueError, IndexError):
            logger.warning(f"max_posts 参数非法: {kwargs.get('max_posts')!r}，回退默认值 30")
            max_posts = 30
        posts = self.fetch_guba_posts(stock_code, max_posts=max_posts)
        news = self.fetch_financial_news(stock_code, max_items=5)
        announcements = self.fetch_announcements(stock_code, max_items=4)
        return {
            "posts": [p.model_dump() for p in posts],
            "news": [n.model_dump() for n in news],
            "announcements": [a.model_dump() for a in announcements],
        }

    def _format_symbol(self, stock_code: str) -> str:
        """转换 6 位股票代码为带市场前缀的代码 (如 sh600584, sz002594)"""
        # 仅保留数字，防止外部输入拼接进 URL 造成路径操纵
        code = re.sub(r"\D", "", str(stock_code))
        if code.startswith(("60", "68", "90", "5")):
            return f"sh{code}"
        elif code.startswith(("00", "30", "20", "2")):
            return f"sz{code}"
        elif code.startswith(("8", "4", "92")):
            return f"bj{code}"
        return f"sh{code}"

    def fetch_guba_posts(self, stock_code: str, max_posts: int = 30) -> List[RawPost]:
        """
        全量最大深度采集东方财富股吧的散户原帖（默认提取该页全量有效样本，去除水军广告）
        """
        clean_code = re.sub(r"\D", "", str(stock_code or ""))
        if not clean_code or len(clean_code) < 5:
            logger.warning(f"股吧爬取跳过: 非法股票代码输入 [{stock_code!r}]")
            return []
        url = f"https://guba.eastmoney.com/list,{clean_code}.html"
        try:
            with httpx.Client(timeout=self.timeout, headers=self.DEFAULT_HEADERS) as client:
                resp = client.get(url)
                resp.raise_for_status()
                html_content = resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"股吧爬取失败 [{clean_code}]: {e}")
            return []

        try:
            soup = BeautifulSoup(html_content, "html.parser")
            items = soup.select("tr.listitem")
        except Exception as e:
            # 畸形 HTML 的解析异常同样纳入降级保护，避免逃逸后拖垮整条流水线
            logger.warning(f"股吧页面解析失败 [{clean_code}]: {e}")
            return []

        posts: List[RawPost] = []
        for item in items:
            tds = item.find_all("td")
            if len(tds) < 5:
                continue

            try:
                read_cnt = int(tds[0].get_text(strip=True) or 0)
                comment_cnt = int(tds[1].get_text(strip=True) or 0)
                title_elem = tds[2].find("a")
                title = title_elem.get_text(strip=True) if title_elem else tds[2].get_text(strip=True)
                href = title_elem["href"] if title_elem and "href" in title_elem.attrs else None
                author = tds[3].get_text(strip=True)
                pub_time = tds[4].get_text(strip=True)

                if self._is_spam(title):
                    continue

                posts.append(
                    RawPost(
                        title=title,
                        author=author,
                        publish_time=pub_time,
                        read_count=read_cnt,
                        comment_count=comment_cnt,
                        url=f"https://guba.eastmoney.com{href}" if href and href.startswith("/") else href,
                    )
                )

                if len(posts) >= max_posts:
                    break
            except Exception as e:
                logger.debug(f"解析单条发帖异常: {e}")
                continue

        return posts

    def fetch_financial_news(self, stock_code: str, max_items: int = 5) -> List[NewsArticle]:
        """
        多源抓取主流专业财经媒体个股滚动新闻（主力资金、研报评级、行业催化）
        """
        clean_code = re.sub(r"\D", "", str(stock_code or ""))
        if not clean_code or len(clean_code) < 5:
            logger.warning(f"专业资讯爬取跳过: 非法股票代码输入 [{stock_code!r}]")
            return []
        symbol = self._format_symbol(stock_code)
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{symbol}.phtml"
        news_list: List[NewsArticle] = []
        try:
            with httpx.Client(timeout=self.timeout, headers=self.DEFAULT_HEADERS) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content.decode("gbk", errors="replace"), "html.parser")
                    items = soup.select(".datelist ul a")
                    for elem in items[:max_items]:
                        title = elem.get_text(strip=True)
                        href = elem.get("href", "")
                        if title and len(title) > 6:
                            news_list.append(
                                NewsArticle(
                                    title=title,
                                    summary=title,  # 新浪新闻列表页标题即包含最核心事件脉络
                                    source="新浪财经/专业媒体",
                                    url=href if href.startswith("http") else f"https:{href}" if href.startswith("//") else href,
                                )
                            )
        except Exception as e:
            logger.warning(f"专业财经资讯抓取异常 [{stock_code}]: {e}")

        return news_list

    def fetch_announcements(self, stock_code: str, max_items: int = 4) -> List[AnnouncementItem]:
        """
        抓取上市公司官方披露公告（财报年报、重大事项、重组、定增）
        """
        clean_code = re.sub(r"\D", "", str(stock_code or ""))
        if not clean_code or len(clean_code) < 5:
            logger.warning(f"官方披露爬取跳过: 非法股票代码输入 [{stock_code!r}]")
            return []
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_Bulletin/stockid/{clean_code}/page_type/ndbg.phtml"
        ann_list: List[AnnouncementItem] = []
        try:
            with httpx.Client(timeout=self.timeout, headers=self.DEFAULT_HEADERS) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content.decode("gbk", errors="replace"), "html.parser")
                    items = soup.select(".datelist ul a")
                    for elem in items[:max_items]:
                        title = elem.get_text(strip=True)
                        href = elem.get("href", "")
                        if title:
                            # 自动归类公告类别
                            category = "官方披露"
                            if any(k in title for k in ("报告", "年报", "半年报", "季报")):
                                category = "定期财报"
                            elif any(k in title for k in ("合同", "中标", "签约", "大单")):
                                category = "重大经营"
                            elif any(k in title for k in ("重组", "增持", "回购", "激励")):
                                category = "资本运作"
                            elif any(k in title for k in ("减持", "问询", "立案", "违规", "警示", "退市")):
                                category = "合规警示"

                            ann_list.append(
                                AnnouncementItem(
                                    title=title,
                                    category=category,
                                    url=href if href.startswith("http") else f"https:{href}" if href.startswith("//") else href,
                                )
                            )
        except Exception as e:
            logger.warning(f"官方公告披露抓取异常 [{stock_code}]: {e}")

        return ann_list

    def _is_spam(self, text: str) -> bool:
        return bool(self.SPAM_REGEX.search(text))
