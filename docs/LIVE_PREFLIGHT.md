# Step 7C-LIVE 実施前確認

この文書は、Acervoを実運用の公開環境へ導入する前に、設計責任者と運用者が承認する確認事項です。DNS、Tunnel、秘密値、本番ホスト、実アカウントは操作・記載しません。導入先固有の実値は、アクセス制限された[非公開運用台帳テンプレート](templates/PRIVATE_OPERATIONS_RUNBOOK.md)の複製先で管理します。

Acervoは1インスタンスを1組織が運用する汎用ソフトウェアです。直接HTTPSが標準で、Cloudflare Tunnelは任意です。公開方式、公開hostname、組織名、在籍ポリシーをアプリコードへ固定しません。具体的な生物班の例は[生物班向け導入・運用例](examples/KDF_BIOLOGY.md)を参照してください。

## 承認前の確定チェックリスト

- [ ] 公開hostnameを確定した。最初のパスキー登録より前に確定し、`ACERVO_PUBLIC_BASE_URL`へHTTPS URLとして設定する。WebAuthn RP IDはこのhostnameから導出されるため、後からhostnameを変える場合は既存パスキーの再登録を計画する。
- [ ] `DJANGO_ALLOWED_HOSTS`は公開hostname、`DJANGO_CSRF_TRUSTED_ORIGINS`は同じHTTPS Originへ完全一致で設定する。
- [ ] 直接HTTPSまたはTunnel専用のどちらか一方を選んだ。共通基盤`compose.production.yaml`を単独起動せず、`compose.direct.yaml`と`compose.cloudflare.yaml`を同時に指定しない。
- [ ] 本番ホスト、管理経路、DNS・Cloudflare・サーバー・バックアップの各責任者、初期管理者username、継続運用管理者候補、障害時の連絡・引継ぎ方法を確定した。
- [ ] バックアップ保存先、暗号化方式、復元試験先、復元責任者を確定した。2人以上の`age`公開鍵をrecipientとして設定し、対応する秘密鍵は印刷・封緘して別々に保管する。パスワード、token、秘密鍵、Recovery Codesは台帳にも直接記載せず、保管場所への参照だけを残す。
- [ ] 実運用で確認するスマートフォン、OS、PC、ブラウザ、同期パスキープロバイダーを決めた。端末内パスキー、同期パスキー、TOTP、Recovery Codesのすべてを復旧経路として維持する。
- [ ] `DJANGO_SECRET_KEY`、`ACERVO_MFA_FERNET_KEYS`、DB資格情報、Tunnel tokenを別々に生成・保管できる。これらをGit、ログ、コマンド履歴へ出さない運用手段を確認した。

学校回生方式を選ぶ導入先だけは、`ACERVO_ENROLLMENT_POLICY=school_cohort`と、年度開始月・日、基準年度、基準年度の1年生回生を設定します。一般組織は`none`を選べます。旧`ACERVO_BASE_THIRD_YEAR_COHORT`は本番起動時に拒否されます。

## 承認後の受入順序

以下は承認後にだけ、選択した公開方式で実施します。各項目が期待結果を満たさない場合は、次へ進みません。

1. 本番設定を権限制限されたホスト上で作成する。公開URL、Host、CSRF Origin、サイト名、組織名、在籍ポリシーが整合し、秘密値が履歴・ログへ出ない。
2. 共通基盤と選択したoverlayのCompose設定を検証する。直接HTTPSでは`proxy`だけが80/tcp、443/tcp、443/udpを公開し、Tunnel専用では全サービスのホスト公開ポートがない。
3. イメージをビルドして起動し、migration、`check --deploy`、healthcheckを成功させる。`web`とPostgreSQLはCompose内部だけで到達可能である。
4. HTTPS、Secure Cookie、Host／Origin検証、転送ヘッダー信頼境界を確認する。直接HTTPSでは外部の転送ヘッダーを採用せず、Tunnel専用では信頼済み経路で正規化された`CF-Connecting-IP`だけを使う。
5. 初期管理者を作成し、初回パスワード変更、TOTP、Recovery Codes、WebAuthn、passwordless passkeyを順に受入する。管理者MFAゲートが、MFA未完了・古いMFA認証記録を拒否することを確認する。
6. member、学校回生方式を選んだ場合の卒業生member、adminの認可を確認する。保護写真が未認証の公開経路から取得できないことを確認する。
7. DB、写真、復元に必要な非公開設定のバックアップを取得し、空の検証環境へ復元する。ログイン、標本詳細、写真表示を確認し、再起動後もデータと設定が永続化することを確認する。
8. 障害時の停止・切戻しを確認する。後方互換性のないmigration後は旧アプリへ戻さず、直前バックアップからの復元を使う。

Phase 10の完全なバックアップ・復元手順は未完成です。このため、上記7の実行可能な手順、復元試験先、復元可能なバックアップが承認・確認されるまで、実データを扱うLIVE完了には進みません。

## 中止条件

次のいずれかに該当したら、外部作業を中止し、原因と安全な復旧方法を確認してから再承認します。

- 公開hostnameまたはWebAuthn RP IDの前提が未確定である。
- 秘密情報がリポジトリ、ログ、コマンド履歴へ露出する可能性がある。
- 本番ポート境界が仕様と異なる。
- 管理者MFAゲートが機能しない、または保護写真を未認証で取得できる。
- バックアップまたは空環境への復元手順が成立しない。
- PostgreSQL上の必須テストまたは本番Compose検証が失敗する。
- 本番データを破壊する可能性があり、復元可能なバックアップがない。
- 生物班固有の値を汎用コードへ固定する必要が生じる。
- `PROJECT_SPEC.md` と実装または文書に解消不能な矛盾がある。
