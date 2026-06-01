# 競合価格モニタリングツール

競合3社の商品ページから価格を自動取得し、先週との差分をMarkdownレポートにまとめてGmailで送信する週次自動化スクリプト。

---

## 必要な環境

| 項目 | バージョン |
|---|---|
| Python | 3.10 以上 |
| requests | 2.34 以上 |
| beautifulsoup4 | 4.14 以上 |
| python-dotenv | 1.2 以上 |

> Python 3.10 未満では `str | None` 型ヒント構文がサポートされないため動作しません。

---

## セットアップ手順

### 1. 仮想環境の作成と有効化

```powershell
# リポジトリのルートで実行
python -m venv .venv
.venv\Scripts\activate
```

### 2. ライブラリのインストール

```powershell
pip install -r requirements.txt
```

### 3. 環境変数の設定（Gmail送信を使う場合）

`.env.example` をコピーして `.env` を作成し、Gmail の認証情報を入力します。

```powershell
Copy-Item .env.example .env
```

`.env` をテキストエディタで開き、以下を設定してください。

```
GMAIL_ADDRESS=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
REPORT_RECIPIENT=recipient@example.com
```

> **App Password の取得方法**
> Google アカウント → セキュリティ → 2段階認証 → アプリパスワード → 「その他」で名称を入力して生成

### 4. 対象URLの設定

`urls.csv` を編集して、監視したい商品ページのURLを登録します。

```csv
商品名,URL,カテゴリ
商品A（競合A社）,https://example-shop-a.com/product-a,家電
商品B（競合B社）,https://example-shop-b.com/product-b,家電
商品C（競合C社）,https://example-shop-c.com/product-c,家電
```

| 列 | 内容 | 例 |
|---|---|---|
| 商品名 | レポートに表示する名称 | `ノートPC-A（競合A社）` |
| URL | 商品ページの URL | `https://example.com/product` |
| カテゴリ | レポートのグループ見出し | `PC`・`スマートフォン` など |

---

## 実行方法

`price_monitor/` ディレクトリに移動してから実行します。

```powershell
cd price_monitor
python price_monitor.py
```

または、リポジトリルートから実行する場合：

```powershell
.venv\Scripts\python.exe price_monitor/price_monitor.py
```

### 実行結果

```
price_monitor/
├── price_history/
│   └── 20260602.json        # 当日の価格データ（翌週の差分算出に使用）
├── reports/
│   └── report_20260602.md   # Markdownレポート
└── price_monitor.log        # 実行ログ
```

### レポートの出力例

```markdown
# 競合価格比較レポート

- 今週: 2026-06-09
- 先週: 2026-06-02

## 家電

| 商品名 | 今週 | 先週 | 変動額 | 変動率 |
|---|---|---|---|---|
| 商品A（競合A社） | ¥48,000 | ¥50,000 | ▼¥2,000 | -4.0% |
| 商品B（競合B社） | ¥52,000 | ¥51,000 | ▲¥1,000 | +2.0% |
| 商品C（競合C社） | ¥49,800 | ¥49,800 | －¥0 | +0.0% |
```

---

## 設定できる項目

### 環境変数（`price_monitor/.env`）

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GMAIL_ADDRESS` | メール送信時 | 送信元の Gmail アドレス |
| `GMAIL_APP_PASSWORD` | メール送信時 | Google アカウントのアプリパスワード（通常のパスワードは不可） |
| `REPORT_RECIPIENT` | メール送信時 | レポートの送信先メールアドレス |

> 3つの変数のうち1つでも未設定の場合、メール送信はスキップされます（スクリプト自体は正常に動作します）。

### `urls.csv` の列

| 列名 | 必須 | 説明 |
|---|---|---|
| `商品名` | ○ | レポートおよびログに表示する識別名 |
| `URL` | ○ | 価格を取得する商品ページの URL |
| `カテゴリ` | ○ | レポートのセクション見出しとして使用 |

---

## よくあるエラーと対処法

### Gmail 認証エラー

```
Gmail 認証エラー（App Password を確認してください）: ...
```

**原因**: `GMAIL_APP_PASSWORD` が通常のパスワードになっている、またはアプリパスワードが無効になっている。

**対処法**:
1. Google アカウント → セキュリティ → 2段階認証 が有効か確認する
2. アプリパスワードを再生成して `.env` を更新する
3. アプリパスワードはスペースなしの16文字（例: `abcdabcdabcdabcd`）で設定する

---

### 価格が見つからない

```
[WARNING] 価格が見つかりませんでした: 商品名 (https://...)
```

**原因**: 対象サイトが JavaScript でレンダリングしている、またはサイト固有の構造に対応していない。

**対処法**:
- 対象サイトが JavaScript レンダリングを使っている場合は、`scrape_quotes.py`（Playwright版）を参考に Playwright での実装に切り替える
- ブラウザの開発者ツールで価格要素のクラス名を調べ、スクリプト内の `PRICE_SELECTORS` リストに追加する

---

### 接続エラー・タイムアウト

```
[ERROR] 接続エラー [商品名]: ...
[ERROR] タイムアウト [商品名]: ...
```

**原因**: ネットワーク不通、対象サーバーがダウン、またはアクセスがブロックされている。

**対処法**:
- ブラウザで手動アクセスして URL が正しいか確認する
- スクリプト内の `timeout=15`（秒）を大きくする
- アクセスブロックの場合は対象サイトの利用規約を確認する

---

### robots.txt によるアクセス禁止

```
[WARNING] robots.txt によりアクセス禁止のため中断: 商品名 (https://...)
```

**原因**: 対象サイトの `robots.txt` でスクレイピングが禁止されている。

**対処法**: 該当 URL を `urls.csv` から削除し、公式 API や手動確認に切り替える。

---

### `ModuleNotFoundError`

```
ModuleNotFoundError: No module named 'requests'
```

**原因**: 仮想環境が有効化されていない、またはライブラリ未インストール。

**対処法**:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```
