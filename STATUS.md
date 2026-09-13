# Project Status

最終更新: 2026-09-14

## Current Task

Phase 1C Sub-step 3C（Recovery Codesの一回限り表示・直接ダウンロード・再生成）の実装とローカル検証を完了。Sub-step 3D、ログイン時MFA、WebAuthn、パスキー、管理者MFAゲートには未着手。

## Completed

- Sub-step 3Cレビュー指摘対応として、Clipboard APIの機能検出・例外処理、日本語 `aria-live` 通知、Blob保存の開始・失敗通知、一時リンク削除・Object URL破棄、再生成フォームの通常二重送信防止を追加
- Recovery Codesだけを持つ利用者の再生成POSTがallauth標準フォームで拒否され、Authenticator、暗号化seed、used mask、閲覧済み時刻が不変で、レスポンスへ平文コードを返さない回帰テストを追加
- 監査補正コミット `66c63fc` と `7dcb3ca` を変更・squashせず `origin/main` へpushし、GitHub Actions run 34754182073 の `test` と `production-container` が全成功したことを確認
- `templates/mfa/recovery_codes/index.html` と `generate.html` を追加し、初回だけの日本語表示、10個のコードの個別行表示、コピー、ブラウザ永続ストレージを使わない一時Blobによるファイル保存、保存確認、未確認離脱のbest-effort警告、再訪時の平文非表示を実装
- allauth標準のRecovery Codes生成・一回性・ユーザー行ロック・再認証・10個発行を維持し、Acervo側は画面と最小の遷移境界だけを実装。古い認証状態の再生成POSTは再認証へ案内するが、allauthのPOST再送を使わず、再認証後も生成確認GETへ戻るようにした
- 再生成確認画面へ未使用数、全旧コードの即時無効化、取消不能、TOTPを無効にしないこと、新コードも一度だけ表示すること、明示的な実行・キャンセル導線を追加
- `mfa_generate_recovery_codes` にも `never_cache` を適用し、Recovery Codesの表示・再生成・直接ダウンロード成功応答で `Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private` を実測
- `accounts/tests/test_mfa_recovery_codes.py` を追加し、初回表示・再訪・表示後/ダウンロード後の403・再生成・旧コード無効化・TOTP維持・CSRF・stale session・初回パスワード変更ゲート・匿名拒否を検証
- Gemini移行期間の全5コミット・全9変更ファイルを、実コード、django-allauth 65.19.3本体、テスト、実レスポンス・DB状態、GitHub Actions実行結果から照合
- URL公開範囲、stale session再認証、初回パスワード変更ゲート、TOTP登録・無効化、MultiFernet統合、Recovery Codes SHOW_ONCE、Cache-Control、クライアントIP信頼境界を再検証
- `accounts/tests/test_mfa_urls.py` と `accounts/tests/test_mfa_totp.py` を補強し、状態変更POSTの初回パスワードゲート、CSRF拒否、stale時のRecovery Codes非再生成、再認証方法列挙、専用IPヘッダーによる実レート制限、SHOW_ONCE後の平文非再表示を追加検証
- `PLAN.md` から誤って削除された完了済みPhase 1C Step 2を復元し、`STATUS.md` の矛盾したキャッシュ記録・テスト件数・残作業記録を実測結果に合わせて修正
- `accounts/mfa_urls.py` で `never_cache` を `recovery_views.view_recovery_codes` に適用し、初回Recovery Codes平文表示画面のキャッシュ無効化（`Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private`）を実装（`mfa_activate_totp`, `mfa_view_recovery_codes`, `mfa_download_recovery_codes` の3画面すべてで確実なキャッシュ無効化を統一）
- `accounts/mfa_urls.py` で `never_cache` を `totp_views.activate_totp` に適用し、TOTPシークレット（秘密鍵）表示画面の確実なキャッシュ無効化（`Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private`）を実装
- `templates/mfa/totp/activate_form.html` を新設し、TOTP登録の日本語UI、3ステップ手順説明、QRコード（SVG data URI）、手動入力用キー、ワンクリックコピー機能（外部依存なしローカルJS）、6桁確認コード入力フォームを実装
- `templates/mfa/totp/deactivate_form.html` を新設し、TOTP無効化確認画面の日本語UI（見出し「認証アプリによる二要素認証を無効にしますか？」）、セキュリティ警告、安全なPOST無効化フォームを実装
- `templates/mfa/index.html` を新設し、二要素認証管理画面の日本語UI、TOTP設定状態（未設定 / 設定済み）に応じた登録・無効化導線、リカバリーコード導線維持、パスキー（WebAuthn）「準備中」バッジ表示を実装
- `accounts/tests/test_mfa_totp.py` を新設し、UI描画、QRコード生成、手動入力キー、never_cacheヘッダー、不正コード拒否、正当コード登録成功とDB上のMultiFernet暗号化保存（平文非保存）、リカバリーコード画面自動遷移、GET無効化非削除、POST無効化実行、stale session再認証誘導、初回パスワード変更ゲート遮断、WebAuthn・mfa_authenticate非露出を網羅（全93テスト成功）
- `ALLAUTH_TRUSTED_CLIENT_IP_HEADER`（`X-Acervo-Client-IP`）環境下でallauthのrate-limitが機能することを確認し、テストリクエストへ専用クライアントIPヘッダーを付与して検証パス
- `accounts/mfa_urls.py` を新設し、TOTP・リカバリーコード設定管理に必要な最小限のview（`mfa_index`, `mfa_reauthenticate`, `mfa_activate_totp`, `mfa_deactivate_totp`, `mfa_view_recovery_codes`, `mfa_generate_recovery_codes`, `mfa_download_recovery_codes`）を明示的にマッピング
- `accounts/urls.py` に `path("reauthenticate/", views.reauthenticate, name="account_reauthenticate")` および `path("mfa/", include("accounts.mfa_urls"))` を追加
- `REAUTHENTICATION_TIMEOUT` 超過の古いセッション（stale session）で保護操作（無効化・再生成）をPOSTした際に、`account_reauthenticate` および `mfa_reauthenticate` が存在しないことで発生する `NoReverseMatch` 例外を特定し、補正ルーティングにより安全にパスワード再認証へ302リダイレクトされることを実証
- ログイン時MFAチャレンジURL（`mfa_authenticate`）およびWebAuthn関連URL（`mfa_list_webauthn` 等）の完全非露出（404およびNoReverseMatch）をテストで維持
- `InitialPasswordChangeMiddleware` がMFA・再認証関連全URLを確実に遮断し `account_change_password` へ302リダイレクトすることを検証
- 匿名ユーザーが各URLへのアクセスで `account_login?next=...` へリダイレクトされることを検証
- 通常認証済みユーザーによるMFA各画面への到達性、およびGETのみでの状態変更防止を検証
- `MFA_RECOVERY_CODES_SHOW_ONCE = True` により、初回ダウンロード成功後に2回目のダウンロードが 403 PermissionDenied となり、一覧画面のコードがマスキングされる防御仕様を実証
- MFA URLルーティング・アクセス制御・stale session再認証テスト（`accounts/tests/test_mfa_urls.py`）の追加（全84テスト成功）
- `accounts/adapters.py` に `AcervoMFAAdapter(DefaultMFAAdapter)` を実装し、`encrypt()` / `decrypt()` をオーバーライド
- `config/settings/base.py` に `MFA_ADAPTER = "accounts.adapters.AcervoMFAAdapter"` を設定
- `MultiFernet` による先頭鍵暗号化・全登録鍵復号・旧鍵ローテーション互換性・不正暗号文の安全な拒否
- allauth標準の `TOTP.activate` および `RecoveryCodes.activate` 経路でのDB平文非保存・暗号化保存を検証
- MFA Adapter単体およびallauth TOTP/RecoveryCodes統合テストの追加（全73テスト成功）
- `cryptography==50.0.1` を直接依存へ追加
- `INSTALLED_APPS` への `allauth.mfa` 有効化とMFA基本設定（ブラウザ信頼無効化、リカバリーコード数10・一度限り表示、WebAuthn安全設定）
- `accounts/security.py` による `ACERVO_MFA_FERNET_KEYS` のFernet鍵バリデーション
- 本番環境（`production.py`）での鍵未設定・不正鍵・空文字・不正複数キー時の起動失敗（秘密鍵の非漏洩）
- 本番環境での安全でないWebAuthnオリジン許可の拒否

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
- Phase 1の認証・MFA基盤として `django-allauth[mfa]==65.19.3` を採用
- WebAuthnパスキー、TOTP、一度だけ表示するリカバリーコードの役割と復旧順序を決定
- パスキーログインを有効、セルフ登録・パスキー登録による新規アカウント作成を無効とする方針を決定
- 管理者MFAゲート、MFA秘密の暗号化・鍵ローテーション、緊急リセット方針を決定
- レート制限共有にPostgreSQL-backed `DatabaseCache`、実IP判定にCaddyが正規化する専用ヘッダーを採用
- `accounts` アプリと `AbstractUser` ベースのCustom User Model
- username、member/admin role、正の回生、初回パスワード変更フラグ、Django標準の有効状態
- `AUTH_USER_MODEL = "accounts.User"` とaccounts初回マイグレーション
- 4月1日を境界とする学校年度と、2026年度31回生を基準にした学年・在籍状態の純粋な算出処理
- role・回生のモデル検証とDB制約、未入学相当の未来回生の新規作成拒否
- 通常ユーザー・superuserをCustom Userとして作成するUser manager
- 非同期User managerで、同期版と同じ `full_clean()` をthread-sensitiveな同期処理として保存前に安全に実行
- managerと `full_clean()` を経由しない直接保存に対するrole・正の回生のDB制約テスト
- `django-allauth[mfa]==65.19.3` の導入と、Phase 1Bに限定した `allauth`・`allauth.account` の有効化
- username/passwordのみの日本語ログイン、パスワード変更、POSTログアウト画面
- セルフ登録、メールログイン・確認・リセット導線、ログインコード、ソーシャルログインの無効化
- 安全な内部 `next` だけを許可するログイン後リダイレクトと、無効ユーザー・CSRFの拒否
- 暗号学的乱数とDjango password validatorを使う一時パスワード付きユーザー作成・再発行サービス
- 再発行対象の行ロック、既存セッション無効化、平文パスワードの非保存
- `bootstrap_admin` コマンドと、既存username・既存有効adminを変更しない再実行安全性
- `must_change_password` 利用者をパスワード変更とPOSTログアウト以外から遮断するサーバー側middleware
- 正常なパスワード変更時だけのフラグ解除と、現在セッションの維持
- 本番default cacheのPostgreSQL `DatabaseCache` 化と `acervo_rate_limit_cache` の冪等初期化
- django-allauth 65.19.3既定のログイン・失敗レート制限と、期限付き429応答
- Caddyの直接HTTPS・Tunnel別クライアントIP正規化と `X-Acervo-Client-IP` の強制上書き
- Django側での専用IPヘッダー限定、`X-Forwarded-For` 非信頼、Tunnel用8080番のホスト非公開

## In Progress

- なし

## Remaining

- 実際の公開ドメイン決定後に、直接HTTPSの証明書取得を手動確認する
- Phase 1C Sub-step 3D（ログイン時MFA認証画面および総合検証）

## Tests

### ローカル

- `ruff check .`: 成功
- `ruff format --check .`: 成功（52ファイル）
- `python manage.py check --settings=config.settings.test`: 成功
- `python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（差分なし）
- `python manage.py test accounts.tests.test_mfa_urls --settings=config.settings.test`: 成功（11件全成功）
- `python manage.py test accounts.tests.test_mfa_totp --settings=config.settings.test`: 成功（12件全成功）
- `python manage.py test accounts.tests.test_mfa_recovery_codes --settings=config.settings.test`: 成功（6件全成功）
- `python manage.py test --settings=config.settings.test`: 成功（SQLite、103件全成功）
- 本番相当設定での `python manage.py check --deploy`: 成功（警告なし、0 silenced）
- ローカルDocker検証: 未実行（このWindows環境にDocker CLIが存在しないため）。Sub-step 3C HEADのGitHub Actionsで本番コンテナ検証を実行し、全項目成功

### GitHub Actions

- Phase 1C Sub-step 3Cレビュー指摘修正（HEAD: `a65931e047f960b82e354edb5e5a081dc9d5c45d`）: run 34767393446（全ジョブ成功）
- `test` job: PostgreSQL 18.6上で全103テスト、Ruff lint・format、Django system check、migration差分なしを確認
- `production-container` job: 本番ComposeとCloudflare追加Compose、Caddy設定、本番イメージ、全サービスhealthy、非root・`check --deploy`、Caddy応答、共有cache table、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Phase 1C Sub-step 3C最終検証（HEAD: `7a22e1db24bd43bbf8ec614b3e71def7497890f2`）: run 34754570798（全ジョブ成功）
- `test` job: PostgreSQL 18.6上で全102テスト、Ruff lint・format、Django system check、migration差分なしを確認
- `production-container` job: 本番ComposeとCloudflare追加Compose、Caddy設定、本番イメージ、全サービスhealthy、非root・`check --deploy`、Caddy応答、共有cache table、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Gemini移行期間最終検証（HEAD: `eb02cce5642318388c3298379dd813177211c286`）: run 34752369353（全ジョブ成功）
- `test` job: 成功。PostgreSQL 18.6上で全93テスト、Ruff lint・format、Django system check、migration差分なしを確認
- `production-container` job: 成功。本番Compose・Cloudflare追加Compose、Caddy設定、本番イメージ、全サービスhealthy、非root・`check --deploy`、Caddy応答、共有cache table、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Phase 1C Sub-step 3A 最終検証（HEAD: 9e0ba84）: run 34750863642（全ジョブ成功）
- `test` job: 成功（35s）
- PostgreSQL 18上で全84テスト成功
- `production-container` job: 成功（1m36s）
- Ruff lint、Ruff format check、Django system check: 成功
- migration差分確認（差分なし）、本番 `check --deploy`（警告なし、0 silenced）: 成功
- Docker Compose本番相当起動、Caddy設定変換・検証: 成功
- ヘルスチェック（`db`、`web`、`proxy` 全healthy）: 成功
- PostgreSQL DatabaseCacheのレート制限テーブル（`acervo_rate_limit_cache`）確認: 成功
- 直接HTTPSとTunnelのクライアントIP境界確認: 成功
- アプリ（8000番）とDB（5432番）のホスト非公開確認: 成功
- DBデータおよび写真ボリュームの永続化確認: 成功
- Phase 1B最終検証: run 34742303012（全ジョブ成功）
- PostgreSQL 18でallauth・accountsマイグレーションと全55テスト: 成功
- Ruff lint、Ruff format check、Django system check: 成功
- 本番ComposeとCloudflare追加Composeの設定検証: 成功
- Caddy 2.11.4でadapt・validate: 成功
- 本番Webイメージのビルド: 成功
- Phase 1B追加後の0-SH本番コンテナ検証: 成功
- PostgreSQL DatabaseCacheの独立instance間レート制限共有: 成功
- `createcachetable` 再実行時の既存データ保持: 成功
- 連続ログイン試行の期限付き429応答: 成功
- 直接HTTPS相当経路とTunnel経路のクライアントIP判定・偽装ヘッダー無視: 成功
- Caddy経由 `/accounts/login/`: 200
- `acervo_rate_limit_cache` tableの存在確認: 成功
- Phase 1A追加修正の最終検証: run 34741189245（全ジョブ成功）
- PostgreSQL 18でaccounts初回マイグレーションと全20テスト: 成功
- Phase 1A初回実装成功: run 34705401207
- 実装内容の全項目成功: run 34683368629
- 通常テストジョブ: 成功
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

- run 34748018570: 本番コンテナ起動時に `.env.production` のプレースホルダーがFail-Fastバリデーションで拒否されwebがunhealthy。CI内で一時Fernet鍵を動的生成・注入するよう修正。
- run 34742173720: 直接HTTPS検証で接続先コンテナ名がTLS SNIに使われ失敗。検証用SNIを `acervo.localhost` に固定して修正。
- run 34682467963: Webがunhealthy。HTTPS転送ヘッダー不足と読み取り専用環境のGunicorn設定を修正。
- run 34682933452: Caddy疎通が400。CIリクエストへ許可済みHostを追加。
- run 34683037889、34683139632: `/admin/` が404にならない。Caddyの拒否処理を専用 `handle` へ修正。
- run 34683250910: ポート非公開検証コマンドが非ゼロ終了。Dockerの `PortBindings` を直接検査する方式へ修正。

## Problems

- Phase 1Bと追加タスク0-SHの自動検証に未解決の問題はない。
- 実ドメインでの証明書取得は、公開ドメインと本番ホスト決定後の手動確認事項として残る。
- 既存開発DBへDjango標準Userのauthマイグレーションを適用済みの場合、Custom Userへの後付け切替は安全に継続できない。対象は開発用PostgreSQL DBと開発用Composeの `postgres_data` ボリューム（通常 `acervo_postgres_data`）。今回は接続、削除、初期化を行っていない。再作成が必要な環境では、保存データの有無を確認し、設計責任者または運用者の承認を得て別作業で行う。
- `mfa_authenticate` はSub-step 3Dまで意図的に非公開である。この中間状態ではTOTP設定後の次回パスワードログイン時にMFAチャレンジを完了できないため、Phase 1C全体の完成版として本番提供しない。

## Change history

- `accounts/mfa_urls.py`: `never_cache` を `view_recovery_codes` にも適用し、Recovery Codes表示画面の確実なキャッシュ無効化を実装
- `accounts/tests/test_mfa_urls.py`: `view_recovery_codes` および `download_recovery_codes` の `never_cache` ヘッダーアサーションを更新
- `templates/mfa/totp/activate_form.html`, `templates/mfa/totp/deactivate_form.html`, `templates/mfa/index.html`: TOTP登録・無効化・MFA設定一覧の日本語UIテンプレートを作成
- `accounts/mfa_urls.py`: `never_cache` を適用し、TOTPシークレット表示画面のキャッシュ無効化を実装
- `accounts/tests/test_mfa_totp.py`: TOTP登録・無効化の日本語UI・フロー・キャッシュ無効化・暗号化保存・stale session再認証の網羅テストを追加（全93テスト成功）
- `PLAN.md`, `STATUS.md`: Phase 1C Sub-step 3B の完了実績を記録
- `.github/workflows/ci.yml`: 本番コンテナ検証ジョブで一時Fernet鍵を動的生成・注入するよう修正（秘密情報のログ非表示）
- `accounts/adapters.py`: `AcervoMFAAdapter.decrypt()` の例外捕捉を `InvalidToken` と `UnicodeError` に限定し、型検査を追加。設定不備などの予期しない例外を握りつぶさないよう改善
- `accounts/tests/test_mfa_adapter.py`: 非ASCII文字列、型不正、設定エラー非握りつぶしのテストを追加（全74テスト成功）
- `accounts/adapters.py`: `AcervoMFAAdapter(DefaultMFAAdapter)` を実装（`encrypt()` / `decrypt()` をMultiFernetでオーバーライド）
- `config/settings/base.py`: `MFA_ADAPTER = "accounts.adapters.AcervoMFAAdapter"` を追加
- `accounts/security.py`: `get_mfa_multi_fernet()` ヘルパー関数を追加
- `accounts/tests/test_mfa_adapter.py`: MFA Adapter単体、暗号化・復号、先頭鍵利用、旧鍵ローテーション互換、不正暗号文拒否、allauth TOTP/RecoveryCodesのDB暗号化保存（平文非保存）テストを追加
- `PLAN.md`、`STATUS.md`: Phase 1C Step 2 の完了実績を記録
- `pyproject.toml`: `cryptography==50.0.1` を直接依存へ追加
- `config/settings/base.py`: `allauth.mfa` 有効化、MFA基本設定（ブラウザ信頼無効化、リカバリーコード設定、WebAuthn安全設定）、`ACERVO_MFA_FERNET_KEYS`
- `config/settings/production.py`: Fernet鍵バリデーション、安全でないWebAuthnオリジン許可の拒否
- `config/settings/test.py`, `config/settings/development.py`: テスト用および開発用のFernetキー設定
- `.env.production.example`: `ACERVO_MFA_FERNET_KEYS` の例を追加
- `accounts/security.py`: `validate_mfa_fernet_keys` 実装
- `accounts/tests/test_deployment_config.py`: MFA設定検証、Fernet鍵バリデーション、本番設定失敗テストを追加
- `PLAN.md`、`STATUS.md`: Phase 1C Step 1 の完了実績を記録
- `compose.production.yaml`: HTTPSを考慮したWebヘルスチェック
- `deploy/gunicorn.conf.py`: 読み取り専用環境向け制御ソケット無効化
- `deploy/Caddyfile`: 管理画面の公開経路遮断修正
- `.github/workflows/ci.yml`: 本番サービス、疎通、ポート、永続化の検証追加
- `PLAN.md`、`STATUS.md`: 追加タスク0-SHの実績反映
- `PROJECT_SPEC.md`、`PLAN.md`: Phase 1のパスキー対応と実装順序を具体化
- `accounts/models.py`、`accounts/enrollment.py`: Custom Userと在籍判定
- `accounts/migrations/0001_initial.py`: Userモデルの初回マイグレーション
- `accounts/models.py`: 非同期User managerの保存前検証を非同期コンテキストで安全に実行
- `accounts/tests/`: 非同期manager、DB制約、年度境界、学年・在籍判定のテスト
- `config/settings/base.py`: `accounts` と `AUTH_USER_MODEL` の設定
- `Dockerfile`、`pyproject.toml`: accountsパッケージを本番イメージへ追加
- `pyproject.toml`、`config/settings/base.py`、`config/urls.py`: django-allauth依存、Phase 1B認証設定、URL
- `accounts/adapters.py`、`accounts/forms.py`、`accounts/middleware.py`: セルフ登録停止、認証フォーム、初回変更ゲート
- `accounts/services.py`、`accounts/management/commands/bootstrap_admin.py`: ユーザー作成・再発行サービスと初期管理者コマンド
- `templates/account/`、`templates/429.html`、`templates/base.html`: 日本語認証画面と期限付き制限画面
- `config/settings/production.py`、`deploy/entrypoint.sh`: PostgreSQL DatabaseCacheとcache table初期化
- `deploy/Caddyfile`: 直接HTTPS・Tunnel別のクライアントIP信頼境界
- `.github/workflows/ci.yml`: Caddy、認証経路、cache table、クライアントIP境界の本番コンテナ検証
- `accounts/tests/`、`core/tests/`: Phase 1Bの認証・サービス・ゲート・レート制限・配備設定テスト
