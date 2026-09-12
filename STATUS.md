# Acervo 開発状況

最終更新: 2026-09-12

## 現在地

**Phase 0 — プロジェクト基盤: 完了**

Python 3.13、Django 5.2 LTS、PostgreSQL 18を前提とする開発基盤を実装した。ローカルの設定確認・lint・format・2件のテストに加え、GitHub ActionsでPostgreSQLへの接続、マイグレーション、同じテストが成功した。

## 今回完了したこと

- `README.md` を日本語のプロダクト概要として整備
- `PROJECT_SPEC.md` に機能、権限、QR、セキュリティ、運用の決定を記録
- `PLAN.md` にPhase 0〜10と完了条件を記録
- `AGENTS.md` に実装・テスト・Git運用の恒久ルールを記録
- ライセンスは未決定として維持
- 環境別Django設定、基本URL、ホーム画面、DBヘルスチェックを追加
- PostgreSQL 18の開発用Compose設定とGitHub Actionsを追加
- Python依存関係、Ruff設定、環境変数テンプレートを追加

## 変更ファイル

- `README.md`
- `PROJECT_SPEC.md`
- `PLAN.md`
- `AGENTS.md`
- `STATUS.md`
- `.env.example`
- `.gitattributes`
- `.github/workflows/ci.yml`
- `.gitignore`
- `.python-version`
- `compose.yaml`
- `pyproject.toml`
- `manage.py`
- `config/`
- `core/`
- `static/`
- `templates/`

## テスト・確認

- `ruff check .`: 成功
- `ruff format --check .`: 成功（21ファイル）
- `python manage.py check --settings=config.settings.test`: 成功
- `python manage.py test --settings=config.settings.test`: 成功（2件）
- PostgreSQL 18への実接続・マイグレーション: GitHub Actionsで成功
- GitHub Actions `品質確認`（run 34680963472）: 成功

## 未解決事項

- ライセンスの選定（将来のOSS公開方針に合わせて決定）
- 本番ドメイン、Cloudflare Tunnel、バックアップ先
- 分類データの取り込み対象と各データソースの再利用条件
- BootstrapとHTMXの本番向け自前配信方法（Phase 10までにCDN依存を解消）

## 次に行うこと

Phase 1として、Custom User Model、回生からの在籍判定、初回パスワード変更、権限の土台を設計・実装する。MFAの具体的な依存関係は、実装前に保守状況と対応バージョンを確認する。
