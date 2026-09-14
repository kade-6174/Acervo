# Acervo

標本・収蔵品・アーカイブを自分たちのサーバーで管理するための、セルフホスト可能なオープンソースWebアプリケーションです。

学校の部活動、研究室、小規模博物館、個人コレクション等で、標本や資料の登録・検索・保管・履歴管理を継続できることを目指します。生物標本を最初の対象としますが、組織名や標本番号の接頭辞は設定で変更できます。

> **開発中** — TOTP、Recovery Codes、WebAuthn第二要素、パスキーの登録・管理・パスワードレスログイン、および管理者MFAゲートの中央適用と最小管理入口は実装済みです。Windows＋Chrome＋Windows Hello＋`localhost`で実機受入を完了しています。管理操作、role変更、管理者MFAリセット、監査ログは未実装で、Step 5Cも未着手です。実運用HTTPSドメイン、同期パスキー、Chrome以外の実運用対象ブラウザは未確認です。正確な現在地は [STATUS.md](STATUS.md) を参照してください。

## 主な機能（MVP）

- スマートフォンでQRを読み取り、標本と写真を登録
- 一意な標本番号の自動採番
- 未使用・使用済み・無効を区別するQRラベル
- 標本の検索、編集、保管場所、状態、貸出・返却等の履歴
- 和名・学名・分類情報のローカル管理と任意の外部候補検索
- 標本ラベル・QRラベルのPDF出力
- 部員・卒業生・管理者の権限、管理者MFA、監査ログ
- スマートフォンのホーム画面へ追加できるPWA
- バックアップ・復元を含むセルフホスト運用

## 本番構成

正式な本番構成は、1台のLinuxホスト上でDocker Composeを使います。

```text
ブラウザ ──HTTPS── Caddy ── Django/Gunicorn ── PostgreSQL
                              │
                              └── 保護された写真ボリューム
```

- Caddyだけを外部公開し、アプリとDBは内部ネットワークに置きます。
- PostgreSQLと写真は永続ボリュームへ保存します。
- 直接HTTPSを標準とし、Cloudflare Tunnelはポート開放できない場合の任意構成です。
- Cloudflare、S3、外部CDNがなくても主要機能を利用できます。
- DBと写真を毎日バックアップし、サーバーとは別の保存先へ複製します。

`compose.yaml` は開発専用、`compose.production.yaml` は本番専用です。本番では次の手順で準備します。

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# .env.productionのドメイン、許可ホスト、CSRFオリジン、秘密値を変更する
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml build
docker compose -f compose.production.yaml up -d
docker compose -f compose.production.yaml ps
```

`DJANGO_SECRET_KEY` と `POSTGRES_PASSWORD` には、インスタンスごとに生成した長いランダム値を設定してください。直接HTTPSでは、設定したドメインのA/AAAAレコードをサーバーへ向け、外部から80/443番へ到達できる必要があります。Caddyが証明書を取得・更新します。

本番ではCaddyだけがホストへポートを公開します。GunicornとPostgreSQLにはホスト側の公開ポートがありません。`/admin/` はCaddyで拒否し、`/static/` だけをCaddyから配信します。アップロード写真は静的ディレクトリに置かず、今後実装するDjangoの認証付き経路から返します。

### Cloudflare Tunnelを使う場合（任意）

Tunnelは本体から分離した追加Composeとして提供します。Cloudflare側でリモート管理Tunnelを作り、公開ホスト名のオリジンを `http://proxy:8080` に設定します。

```bash
cp .env.cloudflare.example .env.cloudflare
chmod 600 .env.cloudflare
# .env.cloudflareへTunnel tokenを設定する
docker compose \
  -f compose.production.yaml \
  -f compose.cloudflare.yaml \
  up -d
```

Tunnel tokenは秘密情報です。リポジトリやログへ記録しないでください。Tunnelを使わない通常構成では、`.env.cloudflare`も追加Composeも不要です。

## 設計文書

- [PROJECT_SPEC.md](PROJECT_SPEC.md) — プロダクト要件と設計上の決定
- [PLAN.md](PLAN.md) — Codexが実装する順序、テスト、完了条件
- [AGENTS.md](AGENTS.md) — Codexが守る恒久的な作業ルール
- [STATUS.md](STATUS.md) — 実装状況、テスト結果、問題点

現在はパスキー／セキュリティキーの登録・管理、パスワードログイン後の第二要素認証、passwordless passkeyログインを提供します。パスキーsignupは公開していません。

## 開発環境

必要なものはPython 3.13、PostgreSQL 18、Gitです。Dockerを利用できる環境では、同梱の開発用 `compose.yaml` でPostgreSQLを起動できます。

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

起動後は `http://127.0.0.1:8000/`、DBを含む稼働確認は `http://127.0.0.1:8000/health/` で確認できます。

### 品質確認

```powershell
ruff check .
ruff format --check .
python manage.py check --settings=config.settings.test
python manage.py test --settings=config.settings.test
```

通常の開発設定はPostgreSQLを使用します。ローカルの高速テストはSQLiteインメモリ設定を使いますが、DB制約・トランザクション・競合を含む重要テストはPostgreSQL上でも実行します。

## ライセンス

ライセンスは未決定です。公開方針を定めた時点で追加します。
