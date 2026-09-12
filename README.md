# Acervo

標本・収蔵品・アーカイブを管理するための、オープンソースのコレクション管理システムです。

学校の部活動、研究室、小規模博物館、個人コレクションなどで、標本や資料の登録・検索・保管・履歴管理を継続できることを目指します。生物標本を最初の主な対象としますが、鉱物、化石、文化資料などにも広げられる設計にします。

> **開発準備中** — 現在は要件と設計を確定する段階です。実装状況は [STATUS.md](STATUS.md) を参照してください。

## 目指すこと

- スマートフォンからQRコードを読み取り、標本を素早く登録できる
- 標本番号、分類情報、採集・入手情報、保管場所、写真、履歴を一か所で管理できる
- 卒業後も記録を閲覧でき、現役部員への権限移行を安全に行える
- 少人数の団体でも、自分たちで長期運用・引き継ぎできる
- 個人情報を最小限にし、標本情報を安全に守る

## MVPの主な機能

- 標本の登録、検索、詳細表示、編集、写真追加、履歴追加
- 一意な標本番号の自動採番（例: `KDF-000123`）
- 未使用・使用済み・無効を区別するQRラベル
- 和名・学名・分類情報のローカル管理と外部候補検索
- 保管場所、状態、貸出・返却・売却などの履歴管理
- 標本ラベル・QRラベルのPDF出力
- 部員・管理者の権限管理、管理者MFA、監査ログ
- スマートフォンのホーム画面へ追加できるPWA

## 設計文書

- [PROJECT_SPEC.md](PROJECT_SPEC.md) — プロダクト要件と設計上の決定
- [PLAN.md](PLAN.md) — 実装フェーズと完了条件
- [AGENTS.md](AGENTS.md) — 開発時に守るルール
- [STATUS.md](STATUS.md) — 現在の進捗と次に行うこと

## 想定技術構成

実装開始時点で最新の互換性・保守状況を確認したうえで、原則として次を採用します。

- Django / Python
- PostgreSQL
- Django Templates + HTMX + Bootstrap（ReactはMVPでは採用しない）
- Web App Manifest + Service Worker
- Cloudflare Tunnel 経由のHTTPS公開

## 開発環境

必要なものはPython 3.13、PostgreSQL 18、Gitです。Dockerを利用できる環境では、同梱の`compose.yaml`で開発用PostgreSQLを起動できます。

### Windowsでの準備

```powershell
Copy-Item .env.example .env
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
docker compose up -d db
python manage.py migrate
python manage.py runserver
```

Dockerを使わない場合は、PostgreSQLを別途起動し、`.env`の接続情報を合わせてください。起動後は `http://127.0.0.1:8000/`、DBを含む稼働確認は `http://127.0.0.1:8000/health/` で確認できます。

### 品質確認

```powershell
ruff check .
ruff format --check .
python manage.py check --settings=config.settings.test
python manage.py test --settings=config.settings.test
```

通常の開発設定はPostgreSQLを使用します。ローカルの自動テストだけは高速に確認できるSQLiteインメモリ設定を使い、GitHub ActionsではPostgreSQL 18へ実際に接続して同じテストを実行します。

## ライセンス

ライセンスは未決定です。将来の公開方針を定めた時点で追加します。
