import logging
import re
from typing import List
import httpx
from bs4 import BeautifulSoup
from src.core.schema import RawPost

logger = logging.getLogger(__name__)

class StockForumScraper:
    """
    东方财富股吧真实爬取与反水军清洗工具
    """
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    SPAM_PATTERNS = [
        r"微[信x]|加[vV]|进群|免费领|涨停战法|牛股推荐|内幕|私信|带飞",
        r"点击链接|加老师|领取代码|短线翻倍",
    ]
    SPAM_REGEX = re.compile("|".join(SPAM_PATTERNS))

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_guba_posts(self, stock_code: str, max_posts: int = 20) -> List[RawPost]:
        url = f"https://guba.eastmoney.com/list,{stock_code}.html"
        try:
            with httpx.Client(timeout=self.timeout, headers=self.DEFAULT_HEADERS) as client:
                resp = client.get(url)
                resp.raise_for_status()
                html_content = resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning(f"股吧爬取失败 [{stock_code}]: {e}")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        items = soup.select("tr.listitem")

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

    def _is_spam(self, text: str) -> bool:
        return bool(self.SPAM_REGEX.search(text))
