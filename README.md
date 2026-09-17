# Acervo

標本・収蔵品・アーカイブを自分たちのサーバーで管理するための、セルフホスト可能なオープンソースWebアプリケーションです。

学校の部活動、研究室、小規模博物館、個人コレクション等で、標本や資料の登録・検索・保管・履歴管理を継続できることを目指します。特定の学校専用ではなく、生物標本を最初の対象とする汎用システムです。MVPは1インスタンスを1組織が運用するセルフホスト方式であり、複数組織を同居させるマルチテナント機能は対象外です。

生物班の学校年度・回生による在籍判定、`kdf-biology.org`、Cloudflare Tunnel、Tailscaleは導入例であり、Acervoの固定要件ではありません。Symbiotaは非稼働の検証環境であり、現在のAcervoとは連携・移行・同時運用しません。公式サイト、Wiki、メールサービスも本リポジトリの管理対象外で、メール認証・メール確認・メールによるパスワードリセットは提供していません。

> **開発中** — TOTP、Recovery Codes、WebAuthn第二要素、パスキーの登録・管理・パスワードレスログイン、管理者MFAゲート、別管理者によるMFAリセット画面、最後の管理者向け緊急MFAリセットコマンドは実装・統合検証済みです。Windows＋Chrome＋Windows Hello＋`localhost`で実機受入を完了しています。実運用HTTPSドメイン、同期パスキー、Chrome以外の実運用対象ブラウザは未確認です。正確な現在地は [STATUS.md](STATUS.md) を参照してください。

## 主な機能（MVP）

- スマートフォンでQRを読み取り、標本と写真を登録
- 一意な標本番号の自動採番
- 未使用・使用済み・無効を区別するQRラベル
- 標本の検索、編集、保管場所、状態、貸出・返却等の履歴
- 和名・学名・分類情報のローカル管理と任意の外部候補検索
- 標本ラベル・QRラベルのPDF出力
- 利用者・管理者の権限、管理者MFA、監査ログ（学校回生方式では在校生・卒業生の区分も扱う）
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

`compose.yaml` は開発専用です。本番の `compose.production.yaml` は、公開ポートを持たない共通基盤です。単独では起動せず、直接HTTPSまたはCloudflare Tunnelの公開方式overlayを**どちらか一方だけ**組み合わせます。

### 直接HTTPS（標準）

直接HTTPSではCaddyだけが80/tcp、443/tcp、443/udpをホストへ公開します。GunicornとPostgreSQLはCompose内部ネットワークだけで利用します。

```bash
cp .env.production.example .env.production
chmod 600 .env.production
# .env.productionのドメイン、許可ホスト、CSRFオリジン、秘密値を変更する
docker compose -f compose.production.yaml -f compose.direct.yaml config --quiet
docker compose -f compose.production.yaml -f compose.direct.yaml build
docker compose -f compose.production.yaml -f compose.direct.yaml up -d
docker compose -f compose.production.yaml -f compose.direct.yaml ps
docker compose -f compose.production.yaml -f compose.direct.yaml down
```

`DJANGO_SECRET_KEY` と `POSTGRES_PASSWORD` には、インスタンスごとに生成した長いランダム値を設定してください。直接HTTPSでは、設定したドメインのA/AAAAレコードをサーバーへ向け、外部から80/443番へ到達できる必要があります。Caddyが証明書を取得・更新します。

本番ではCaddyだけがホストへポートを公開します。GunicornとPostgreSQLにはホスト側の公開ポートがありません。`/admin/` はCaddyで拒否し、`/static/` だけをCaddyから配信します。アップロード写真は静的ディレクトリに置かず、今後実装するDjangoの認証付き経路から返します。

### Cloudflare Tunnelを使う場合（任意）

Tunnel専用構成では、`proxy`、`web`、`db`、`tunnel`のいずれもホストポートを公開しません。受信ポート開放は不要です。Cloudflare側でリモート管理Tunnelを作り、公開ホスト名のオリジンを `http://proxy:8080` に設定する作業、DNS、実token、実接続はStep 7Cで行います。

```bash
cp .env.cloudflare.example .env.cloudflare
chmod 600 .env.cloudflare
# .env.cloudflareへTunnel tokenを設定する
docker compose \
  -f compose.production.yaml \
  -f compose.cloudflare.yaml \
  up -d
```

状態確認、停止、管理コマンドにも、選んだ公開方式と同じComposeファイルの組合せを使います。

```bash
# Tunnel専用構成の例
docker compose -f compose.production.yaml -f compose.cloudflare.yaml ps
docker compose -f compose.production.yaml -f compose.cloudflare.yaml down
docker compose -f compose.production.yaml -f compose.cloudflare.yaml exec web python manage.py reset_admin_mfa ADMIN_USERNAME
```

Tunnel tokenは秘密情報です。リポジトリ、コマンド文字列、ログへ記録しないでください。Tunnelを使わない直接HTTPS構成では、`.env.cloudflare`もTunnel overlayも不要です。厳格なホストファイアウォールを使う場合だけ、`cloudflared` からCloudflareへ7844/TCPおよび7844/UDPの送信を許可してください。Cloudflare AccessはAcervoのログインや管理者MFAの必須要件ではありません。

## 設計文書

- [PROJECT_SPEC.md](PROJECT_SPEC.md) — プロダクト要件と設計上の決定
- [PLAN.md](PLAN.md) — Codexが実装する順序、テスト、完了条件
- [AGENTS.md](AGENTS.md) — Codexが守る恒久的な作業ルール
- [STATUS.md](STATUS.md) — 実装状況、テスト結果、問題点

現在はパスキー／セキュリティキーの登録・管理、パスワードログイン後の第二要素認証、passwordless passkeyログインを提供します。パスキーsignupは公開していません。

## 緊急時の最後の管理者MFA復旧

通常のMFA喪失は、別の復旧可能な管理者が `/management/` のMFAリセット画面から対応します。`reset_admin_mfa` は、他にその操作を実行できる管理者がいない最後の有効adminだけの緊急復旧用です。

本番コンテナでは、対象usernameを指定して実行します。実行前に `RESET <username>` の完全一致確認が必要です。

```bash
# 直接HTTPS構成
docker compose -f compose.production.yaml -f compose.direct.yaml exec web python manage.py reset_admin_mfa ADMIN_USERNAME
```

`ADMIN_USERNAME` は実際に復旧する対象usernameへ置き換えてください。確認では `RESET 実際のusername` の完全一致入力が必要です。パスワードが不明な場合、このコマンドだけでは復旧できません。

このコマンドは対象の既存MFAとログインsessionを無効化しますが、パスワード、role、有効状態は変更せず、新しい秘密やRecovery Codesも出力しません。対象者は既存パスワードで再ログイン後、MFAを再登録する必要があります。

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
