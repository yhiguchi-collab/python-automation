"""
quotes.toscrape.com/js から名言（テキスト・著者）を収集し
Markdown ファイルとスクリーンショットとして保存するスクリプト。
JavaScript でレンダリングされるページに対応するため Playwright を使用。
"""

import asyncio
import logging
import random
from datetime import date
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

BASE_URL = "https://quotes.toscrape.com"
START_PATH = "/js"
USER_AGENT = "Mozilla/5.0 (compatible; PythonScraper/1.0)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scraper_quotes.log", encoding="utf-8"),
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


def save_markdown(quotes: list[dict], path: str) -> None:
    today = date.today().strftime("%Y-%m-%d")
    rows = [
        f"# 名言集 ({today})",
        f"\n収集件数: {len(quotes)} 件\n",
        "| 名言 | 著者 |",
        "|---|---|",
    ]
    for q in quotes:
        text = q["text"].replace("|", "\\|")
        author = q["author"].replace("|", "\\|")
        rows.append(f"| {text} | {author} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")


async def main() -> None:
    rp = load_robots(BASE_URL)

    all_quotes: list[dict] = []
    today_str = date.today().strftime("%Y%m%d")
    screenshot_path = f"quotes_{today_str}.png"
    md_path = f"quotes_{today_str}.md"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        current_path: str | None = START_PATH
        page_num = 1
        screenshot_taken = False

        while current_path:
            current_url = urljoin(BASE_URL, current_path)

            if not rp.can_fetch(USER_AGENT, current_url):
                logger.warning(f"robots.txt によりアクセス禁止のため中断: {current_url}")
                break

            logger.info(f"ページ {page_num} を取得中: {current_url}")

            try:
                await page.goto(current_url, wait_until="networkidle", timeout=15000)
                # JS レンダリング完了を .quote の出現で確認
                await page.wait_for_selector(".quote", timeout=10000)
            except PlaywrightTimeoutError as e:
                logger.error(f"タイムアウトエラー: {e}")
                break
            except Exception as e:
                logger.error(f"接続エラー: {e}")
                break

            # 最初のページのみスクリーンショットを保存
            if not screenshot_taken:
                await page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"スクリーンショットを保存しました: {screenshot_path}")
                screenshot_taken = True

            # 名言を抽出
            quote_elements = await page.query_selector_all(".quote")
            page_quotes: list[dict] = []
            for el in quote_elements:
                text_el = await el.query_selector(".text")
                author_el = await el.query_selector(".author")
                if text_el and author_el:
                    text = (await text_el.inner_text()).strip()
                    author = (await author_el.inner_text()).strip()
                    page_quotes.append({"text": text, "author": author})

            all_quotes.extend(page_quotes)
            logger.info(f"  -> {len(page_quotes)} 件取得（累計 {len(all_quotes)} 件）")

            # 次ページへ
            next_btn = await page.query_selector("li.next a")
            if next_btn:
                next_href = await next_btn.get_attribute("href")
                current_path = next_href
                page_num += 1
                wait = random.uniform(1, 3)
                logger.info(f"  -> {wait:.1f} 秒待機")
                await asyncio.sleep(wait)
            else:
                current_path = None

        await browser.close()

    if not all_quotes:
        logger.warning("名言データを取得できませんでした")
        return

    save_markdown(all_quotes, md_path)
    logger.info(f"保存完了: {md_path}（計 {len(all_quotes)} 件）")


if __name__ == "__main__":
    asyncio.run(main())
