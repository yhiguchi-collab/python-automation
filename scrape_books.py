"""
books.toscrape.com から書籍情報（タイトル・価格・在庫状況）を収集し
Markdown ファイルとして保存するスクリプト。
"""

import logging
import random
import time
from datetime import date
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "Mozilla/5.0 (compatible; PythonScraper/1.0)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def load_robots(base_url: str) -> RobotFileParser:
    rp = RobotFileParser()
    robots_url = urljoin(base_url, "/robots.txt")
    rp.set_url(robots_url)
    try:
        rp.read()
        logger.info(f"robots.txt を読み込みました: {robots_url}")
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗しました（全 URL を許可扱いにします）: {e}")
    return rp


def fetch(url: str, session: requests.Session) -> BeautifulSoup:
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"接続エラー: {e}")
        raise
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP エラー: {e}")
        raise
    except requests.exceptions.Timeout as e:
        logger.error(f"タイムアウト: {e}")
        raise


def parse_books(soup: BeautifulSoup) -> list[dict]:
    books = []
    for article in soup.select("article.product_pod"):
        title = article.select_one("h3 a")["title"]
        price = article.select_one("p.price_color").text.strip()
        availability = article.select_one("p.availability").text.strip()
        books.append({"title": title, "price": price, "availability": availability})
    return books


def next_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    btn = soup.select_one("li.next a")
    return urljoin(current_url, btn["href"]) if btn else None


def save_markdown(books: list[dict], path: str) -> None:
    today = date.today().strftime("%Y-%m-%d")
    rows = [
        f"# 書籍一覧 ({today})",
        f"\n収集件数: {len(books)} 件\n",
        "| タイトル | 価格 | 在庫状況 |",
        "|---|---|---|",
    ]
    for b in books:
        title = b["title"].replace("|", "\\|")
        price = b["price"].replace("|", "\\|")
        avail = b["availability"].replace("|", "\\|")
        rows.append(f"| {title} | {price} | {avail} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")


def main() -> None:
    rp = load_robots(BASE_URL)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    all_books: list[dict] = []
    current_url: str | None = BASE_URL
    page = 1

    while current_url:
        if not rp.can_fetch(USER_AGENT, current_url):
            logger.warning(f"robots.txt によりアクセス禁止のため中断: {current_url}")
            break

        logger.info(f"ページ {page} を取得中: {current_url}")
        try:
            soup = fetch(current_url, session)
        except Exception:
            logger.error("エラーが発生したためスクレイピングを中断します")
            break

        books = parse_books(soup)
        all_books.extend(books)
        logger.info(f"  -> {len(books)} 件取得（累計 {len(all_books)} 件）")

        current_url = next_page_url(soup, current_url)
        page += 1

        if current_url:
            wait = random.uniform(1, 3)
            logger.info(f"  -> {wait:.1f} 秒待機")
            time.sleep(wait)

    if not all_books:
        logger.warning("書籍データを取得できませんでした")
        return

    output = f"books_{date.today().strftime('%Y%m%d')}.md"
    save_markdown(all_books, output)
    logger.info(f"保存完了: {output}（計 {len(all_books)} 件）")


if __name__ == "__main__":
    main()
