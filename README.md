# Acervo

標本・収蔵品・アーカイブを自分たちのサーバーで管理するための、セルフホスト可能なオープンソースWebアプリケーションです。

学校の部活動、研究室、小規模博物館、個人コレクション等で、標本や資料の登録・検索・保管・履歴管理を継続できることを目指します。特定の学校専用ではなく、生物標本を最初の対象とする汎用システムです。MVPは1インスタンスを1組織が運用するセルフホスト方式であり、複数組織を同居させるマルチテナント機能は対象外です。

生物班の学校年度・回生による在籍判定、`kdf-biology.org`、Cloudflare Tunnel、Tailscaleは導入例であり、Acervoの固定要件ではありません。Symbiotaは非稼働の検証環境であり、現在のAcervoとは連携・移行・同時運用しません。公式サイト、Wiki、メールサービスも本リポジトリの管理対象外で、メール認証・メール確認・メールによるパスワードリセットは提供していません。

> **開発中** — 認証・管理者MFA、標本登録・検索・保護写真、QR・PDF・CSV、分類選択、PWA、管理画面、暗号化バックアップ・復元を実装しています。実ドメインの公開・管理者認証とiPhoneのPWA・カメラQR読取は確認済みです。本番サイト発行QRの写真読取、標本・写真を含む実環境の復元受入、管理者引き継ぎなどが残っています。Android実機受入はMVP完成後に実施します。Phase 1・Phase 9・Phase 10および7C-LIVE全体の完了は未確定です。正確な現在地は [STATUS.md](STATUS.md) を参照してください。

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

## スマートフォンで使う

HTTPSのサイトへログインし、ホームの「QRコードを読み取る」からカメラを起動する。最初は画面側のカメラを優先し、画面上のボタンで背面カメラと切り替えられる。カメラが利用できない場合は、QRの写真を選択するか、端末の標準カメラでQRを読む。いずれもAcervo側でログインと操作権限を確認する。

ホーム画面に追加する場合、iPhoneはSafariの共有メニューから「ホーム画面に追加」、AndroidはChromeのメニューから「アプリをインストール」または「ホーム画面に追加」を選ぶ。オフラインで表示できるのは接続案内だけで、標本の登録・検索・写真閲覧はオンラインで行う。

## 本番導入

本番導入は1台のLinuxホスト上のDocker Composeを正式構成とします。直接HTTPSが標準で、Cloudflare Tunnelは任意です。詳細な設定、起動、MFA、公開境界は[導入マニュアル](docs/DEPLOYMENT.md)、暗号化バックアップと空環境復元は[バックアップ・復元手順](docs/BACKUP_RESTORE.md)、実運用環境を操作する前の承認項目と中止条件は[Step 7C-LIVE 実施前確認](docs/LIVE_PREFLIGHT.md)を参照してください。

生物班への導入例は[生物班向け導入・運用例](docs/examples/KDF_BIOLOGY.md)、秘密値を含まない引継ぎ台帳の雛形は[非公開運用台帳テンプレート](docs/templates/PRIVATE_OPERATIONS_RUNBOOK.md)に分離しています。

## 設計文書

- [PROJECT_SPEC.md](PROJECT_SPEC.md) — プロダクト要件と設計上の決定
- [PLAN.md](PLAN.md) — Codexが実装する順序、テスト、完了条件
- [AGENTS.md](AGENTS.md) — Codexが守る恒久的な作業ルール
- [STATUS.md](STATUS.md) — 実装状況、テスト結果、問題点
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — 汎用導入マニュアル
- [docs/SPECIMEN_MANAGEMENT.md](docs/SPECIMEN_MANAGEMENT.md) — 標本の無効化・完全削除と写真削除の再試行
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — 更新・障害対応・リリース確認と管理者交代
- [docs/IPHONE_ACCEPTANCE.md](docs/IPHONE_ACCEPTANCE.md) — iPhoneでの表示更新・分類候補・本番発行QRの写真読取

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

別途記載があるものを除き、kade_6174が権利を有するAcervo固有のコード、文書、設定例は[Apache License 2.0](LICENSE)です。著作権表示は`Copyright 2026 kade_6174`です。商用利用、改変、再配布、非公開の派生版は同ライセンスの条件内で許容します。

第三者のコード、静的資産、依存パッケージ、コンテナ基盤にはそれぞれの元のライセンスが適用されます。確認済みの同梱資産と、公開Dockerイメージを正式配布する前に必要な棚卸しは[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。
