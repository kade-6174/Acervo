# Project Status

最終更新: 2026-09-12

## Current Task

追加タスク0-SH「セルフホスト配備の土台」の修正と自動検証は完了。Phase 1には未着手。

## Completed

- Phase 0のDjango開発基盤
- 開発用と本番用のCompose構成の分離
- Python 3.13、Gunicorn、非rootユーザーを用いたアプリイメージ定義
- Caddyを唯一の公開入口とし、PostgreSQLとGunicornを内部ネットワークだけに配置
- PostgreSQL、写真、静的ファイル、Caddyデータの永続ボリューム定義
- Bootstrap 5.3.8とHTMX 2.0.10のローカル配信
- 本番必須環境変数の検証とDjangoの本番セキュリティ設定
- 直接HTTPS用Caddy構成と、任意のCloudflare Tunnel追加構成
- Webヘルスチェックへ `X-Forwarded-Proto: https` を追加
- Gunicornの制御ソケットを無効化し、読み取り専用ファイルシステムで起動可能に修正
- Caddyで `/admin/` とその配下を404にする公開経路遮断
- GitHub Actionsによる本番Composeの起動・疎通・永続化検証

## In Progress

- なし

## Remaining

- 実際の公開ドメイン決定後に、直接HTTPSの証明書取得を手動確認する
- Phase 1は設計責任者から開始指示があるまで着手しない

## Tests

### ローカル

- `ruff check .`: 成功
- `ruff format --check .`: 成功（22ファイル）
- `python manage.py check --settings=config.settings.test`: 成功
- `python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（差分なし）
- `python manage.py test --settings=config.settings.test`: 成功（2件）
- 本番相当設定での `python manage.py check --deploy`: 成功

### GitHub Actions

- 最終成功: run 34683368629
- 通常テストジョブ: 成功
- 本番ComposeとCloudflare追加Composeの設定検証: 成功
- 本番Webイメージのビルド: 成功
- `db`、`web`、`proxy` のhealthy確認: 成功
- Web実行UID `10001`: 成功
- コンテナ内 `manage.py check --deploy`: 成功
- Caddy経由 `/health/`: 200
- Caddy経由 `/static/css/acervo.css`: 200
- Caddy経由 `/admin/`: 404
- Web 8000番・DB 5432番のホスト非公開: 成功
- DBコンテナ再作成後の確認データ保持: 成功
- Webコンテナ再作成後の `/app/media` 確認ファイル保持: 成功

### 修正中の失敗履歴

- run 34682467963: Webがunhealthy。HTTPS転送ヘッダー不足と読み取り専用環境のGunicorn設定を修正。
- run 34682933452: Caddy疎通が400。CIリクエストへ許可済みHostを追加。
- run 34683037889、34683139632: `/admin/` が404にならない。Caddyの拒否処理を専用 `handle` へ修正。
- run 34683250910: ポート非公開検証コマンドが非ゼロ終了。Dockerの `PortBindings` を直接検査する方式へ修正。

## Problems

- 追加タスク0-SHの自動検証に未解決の問題はない。
- 実ドメインでの証明書取得は、公開ドメインと本番ホスト決定後の手動確認事項として残る。

## Recent Changes

- `compose.production.yaml`: HTTPSを考慮したWebヘルスチェック
- `deploy/gunicorn.conf.py`: 読み取り専用環境向け制御ソケット無効化
- `deploy/Caddyfile`: 管理画面の公開経路遮断修正
- `.github/workflows/ci.yml`: 本番サービス、疎通、ポート、永続化の検証追加
- `PLAN.md`、`STATUS.md`: 追加タスク0-SHの実績反映
