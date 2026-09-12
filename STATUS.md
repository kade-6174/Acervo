# Project Status

最終更新: 2026-09-12

## Current Task

追加タスク 0-SH「セルフホスト配備の土台」の実装と検証。

## Completed

- Phase 0のDjango開発基盤
- 開発用と本番用のCompose構成の分離
- Python 3.13、Gunicorn、非rootユーザーを用いたアプリイメージ定義
- Caddyを唯一の公開入口とし、PostgreSQLを内部ネットワークだけに配置
- PostgreSQL、写真、静的ファイル、Caddyデータの永続ボリューム定義
- Bootstrap 5.3.8とHTMX 2.0.10のローカル配信
- 本番必須環境変数の検証とDjangoの本番セキュリティ設定
- 直接HTTPS用Caddy構成と、任意のCloudflare Tunnel追加構成
- 本番コンテナ検証を行うGitHub Actionsジョブ
- 本番相当設定での `check --deploy`

## In Progress

- Dockerを利用した本番イメージとCompose構成の実動作確認

## Remaining

- イメージビルドと `docker compose config` の実行
- コンテナ内の非root実行、DB待機後のマイグレーション、ヘルスチェックの確認
- 再起動後のDB・写真永続化と、DBポート非公開の実動作確認
- 実際の公開ドメインでのHTTPS証明書取得
- 追加タスク0-SH完了後にPhase 1へ着手

## Tests

- `ruff check .`: 成功
- `ruff format --check .`: 成功（22ファイル）
- `python manage.py check --settings=config.settings.test`: 成功
- `python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（差分なし）
- `python manage.py test --settings=config.settings.test`: 成功（2件）
- 本番相当設定での `python manage.py check --deploy`: 成功
- 本番相当設定での `collectstatic`: 成功（135ファイル）
- Docker関連の確認: 未実行（このPCにDockerまたはPodmanが見つからないため）

## Problems

- このPCにDocker実行環境がないため、追加タスク0-SHのコンテナ確認項目は未完了。
- GitHub Actionsには本番コンテナ検証を追加したが、ユーザーの明示指示がないためGitHubへpushしておらず、未実行。
- 実ドメイン、公開方式、バックアップ保存先、MFAライブラリ、OSSライセンスは今後の設計・導入判断として残っている。

## Recent Changes

- `Dockerfile`、`compose.production.yaml`、`compose.cloudflare.yaml`
- `deploy/Caddyfile`、`deploy/entrypoint.sh`、`deploy/gunicorn.conf.py`
- `.env.production.example`、`.env.cloudflare.example`、`.dockerignore`
- `config/settings/base.py`、`config/settings/production.py`
- `static/vendor/`、`templates/base.html`
- `.github/workflows/ci.yml`、`pyproject.toml`
- `README.md`、`PLAN.md`、`STATUS.md`
