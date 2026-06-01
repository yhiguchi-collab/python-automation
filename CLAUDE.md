# python-automation

Python による業務自動化スクリプト群。

## 技術スタック

- Python 3.x
- 外部ライブラリは `requirements.txt` で管理
- 仮想環境（venv）を使用

## ディレクトリ構成

```
python-automation/
├── CLAUDE.md
├── requirements.txt   # 依存パッケージ一覧
├── .gitignore
└── scripts/           # 各種自動化スクリプト
```

## セットアップ

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## コーディング規約

- インデントはスペース 4 つ（PEP 8 準拠）
- 型ヒント（Type Hints）を積極的に使用
- コメントは WHY が自明でない箇所のみ（日本語可）
- 変数名・関数名はスネークケース

## Git 運用ルール

### 基本方針

**コードを変更するたびに、必ず GitHub へプッシュすること。**

ローカルコミットのみで作業を終わらせない。変更 → コミット → プッシュを 1 セットとする。

### 手順

1. 変更をステージング
   ```bash
   git add <変更ファイル>
   ```
2. コミット（日本語で変更内容を簡潔に記述）
   ```bash
   git commit -m "変更内容の説明"
   ```
3. GitHub へプッシュ
   ```bash
   git push origin main
   ```

### コミットメッセージ規約

- 日本語で記述してよい
- 変更の「何を」「なぜ」が伝わる内容にする
- 例: `CSVの読み込み処理を追加`、`バグ修正: 日付パースが失敗する問題`

### 注意事項

- センシティブな情報（APIキー、パスワード、認証情報等）は絶対にコミットしない
- `.env` ファイルは `.gitignore` に登録し、`.env.example` をコミットする
- `__pycache__/`、`.venv/`、`*.pyc` はコミットしない
