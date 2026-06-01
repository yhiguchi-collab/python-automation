"""
週次競合価格モニタリングスクリプト
urls.csv の各 URL から価格を取得し、先週との差分をレポートして Gmail 送信する。
"""

import collections
import csv
import json
import logging
import os
import random
import re
import smtplib
import time
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

HISTORY_DIR = BASE_DIR / "price_history"
REPORTS_DIR = BASE_DIR / "reports"
CSV_PATH = BASE_DIR / "urls.csv"

HISTORY_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "price_monitor.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 順番に試す CSS セレクタ（具体的なものを先に）
PRICE_SELECTORS = [
    "[itemprop='price']",
    "[data-price]",
    ".price",
    "#priceblock_ourprice",
    ".a-price-whole",
    ".woocommerce-Price-amount",
    "[class*='price'][class*='amount']",
    "[class*='price'][class*='value']",
    "[class*='price'][class*='color']",
    "[class*='price']",
    ".amount",
]

# 通貨記号またはコードが付いた数値にマッチ
PRICE_RE = re.compile(
    r"[¥$£€￥]\s*([\d,]+(?:\.\d{1,2})?)"
    r"|"
    r"([\d,]+(?:\.\d{1,2})?)\s*(?:円|税込|USD|JPY|GBP|EUR)\b",
    re.IGNORECASE,
)

_robots_cache: dict[str, RobotFileParser] = {}


def get_robots(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if domain not in _robots_cache:
        rp = RobotFileParser()
        rp.set_url(f"{domain}/robots.txt")
        try:
            rp.read()
            logger.info(f"robots.txt 読み込み: {domain}/robots.txt")
        except Exception as e:
            logger.warning(f"robots.txt 読み込み失敗（全 URL 許可扱い）: {domain}: {e}")
        _robots_cache[domain] = rp
    return _robots_cache[domain]


def _parse_price(raw: str) -> float | None:
    m = PRICE_RE.search(raw)
    if m:
        value = m.group(1) or m.group(2)
        try:
            return float(value.replace(",", ""))
        except ValueError:
            pass
    return None


def extract_price(soup: BeautifulSoup) -> float | None:
    # 1. JSON-LD 構造化データ
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                data = data[0]
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0]
            raw = offers.get("price")
            if raw is not None:
                return float(str(raw).replace(",", ""))
        except Exception:
            pass

    # 2. meta タグ
    for prop in ("product:price:amount", "og:price:amount"):
        tag = soup.find("meta", {"property": prop})
        if tag and tag.get("content"):
            try:
                return float(str(tag["content"]).replace(",", ""))
            except Exception:
                pass

    # 3. CSS セレクタ
    for selector in PRICE_SELECTORS:
        el = soup.select_one(selector)
        if not el:
            continue
        raw = str(el.get("content") or el.get("data-price") or el.get_text())
        price = _parse_price(raw)
        if price is not None:
            return price

    # 4. 全文テキストへの正規表現フォールバック（最頻値を採用）
    candidates: list[float] = []
    for m in PRICE_RE.finditer(soup.get_text()):
        raw = m.group(1) or m.group(2)
        try:
            v = float(raw.replace(",", ""))
            if 1 <= v <= 10_000_000:
                candidates.append(v)
        except ValueError:
            pass
    if candidates:
        return collections.Counter(candidates).most_common(1)[0][0]

    return None


def fetch_price(product: dict, session: requests.Session) -> float | None:
    url = product["url"]
    rp = get_robots(url)

    if not rp.can_fetch(USER_AGENT, url):
        logger.warning(f"robots.txt によりアクセス禁止: {product['name']} ({url})")
        return None

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        price = extract_price(soup)
        if price is None:
            logger.warning(f"価格が見つかりませんでした: {product['name']} ({url})")
        return price
    except requests.exceptions.ConnectionError as e:
        logger.error(f"接続エラー [{product['name']}]: {e}")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP エラー [{product['name']}]: {e}")
    except requests.exceptions.Timeout as e:
        logger.error(f"タイムアウト [{product['name']}]: {e}")
    except Exception as e:
        logger.error(f"予期しないエラー [{product['name']}]: {e}")
    return None


def load_csv() -> list[dict]:
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return [
            {
                "name": r["商品名"].strip(),
                "url": r["URL"].strip(),
                "category": r["カテゴリ"].strip(),
            }
            for r in csv.DictReader(f)
        ]


def history_path(d: date) -> Path:
    return HISTORY_DIR / f"{d.strftime('%Y%m%d')}.json"


def load_history(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_history(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_report(current: dict, previous: dict) -> str:
    today = date.today()
    last_week = today - timedelta(weeks=1)
    lines = [
        "# 競合価格比較レポート",
        "",
        f"- 今週: {today.strftime('%Y-%m-%d')}",
        f"- 先週: {last_week.strftime('%Y-%m-%d')}",
        "",
    ]

    by_category: dict[str, list] = collections.defaultdict(list)
    for name, data in current.items():
        by_category[data["category"]].append((name, data))

    for cat in sorted(by_category):
        lines += [
            f"## {cat}",
            "",
            "| 商品名 | 今週 | 先週 | 変動額 | 変動率 |",
            "|---|---|---|---|---|",
        ]
        for name, data in sorted(by_category[cat]):
            curr = data.get("price")
            prev = previous.get(name, {}).get("price")
            if curr is None:
                prev_str = f"¥{prev:,.0f}" if prev is not None else "-"
                row = f"| {name} | 取得失敗 | {prev_str} | - | - |"
            elif prev is None:
                row = f"| {name} | ¥{curr:,.0f} | データなし | - | - |"
            else:
                diff = curr - prev
                pct = diff / prev * 100
                arrow = "▲" if diff > 0 else "▼" if diff < 0 else "－"
                row = (
                    f"| {name} | ¥{curr:,.0f} | ¥{prev:,.0f} | "
                    f"{arrow}¥{abs(diff):,.0f} | {pct:+.1f}% |"
                )
            lines.append(row)
        lines.append("")

    failed = [name for name, d in current.items() if d.get("price") is None]
    if failed:
        lines += ["## 取得失敗 URL", ""]
        for name in failed:
            lines.append(f"- {name}: {current[name]['url']}")
        lines.append("")

    return "\n".join(lines)


def send_gmail(subject: str, body: str) -> None:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("REPORT_RECIPIENT")

    if not all([sender, password, recipient]):
        logger.warning(
            "Gmail 設定が未完了のためメール送信をスキップします"
            "（price_monitor/.env を確認してください）"
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(sender, password)
            smtp.sendmail(sender, recipient, msg.as_string())
        logger.info(f"メール送信完了 → {recipient}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail 認証エラー（App Password を確認してください）: {e}")
    except Exception as e:
        logger.error(f"メール送信エラー: {e}")


def main() -> None:
    logger.info("=== 競合価格モニタリング 開始 ===")

    products = load_csv()
    logger.info(f"対象: {len(products)} 商品")

    today = date.today()
    previous = load_history(history_path(today - timedelta(weeks=1)))
    current: dict = {}

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    for i, product in enumerate(products):
        logger.info(f"[{i + 1}/{len(products)}] {product['name']}...")
        price = fetch_price(product, session)
        current[product["name"]] = {
            "url": product["url"],
            "category": product["category"],
            "price": price,
        }
        if i < len(products) - 1:
            wait = random.uniform(1, 3)
            logger.info(f"  -> {wait:.1f} 秒待機")
            time.sleep(wait)

    save_history(current, history_path(today))
    logger.info(f"価格履歴を保存: {history_path(today).name}")

    report = generate_report(current, previous)
    report_path = REPORTS_DIR / f"report_{today.strftime('%Y%m%d')}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"レポートを保存: {report_path.name}")

    subject = f"【競合価格レポート】{today.strftime('%Y年%m月%d日')} 週次比較"
    send_gmail(subject, report)

    logger.info("=== 完了 ===")


if __name__ == "__main__":
    main()
