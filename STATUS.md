# Project Status

最終更新: 2026-10-08

## Current Task

Phase 1C Step 6、Step 7A-SPEC、Step 7A、Step 7A-R2、Step 7B、Step 7C-DOC、Step 7C-DOC-R、Step 7C-LICENSE、Phase 10A（バックアップ・復元の先行部分）、Phase 4、Phase 5、Phase 6、Phase 7、Phase 8を完了。Phase 8はローカル実装・検証、GitHub Actions、VM200本番Compose反映、iPhoneでのホーム画面追加・閲覧・PWA内カメラQR読取を確認した。Android実機受入は運用者の決定でMVP完成後へ移し、未確認である。追加のカメラ切替機能はVM200へ反映し、iPhoneでの動作確認を完了した。写真選択欄はiPhoneで保存済み写真を選べるようになり、選択したスクリーンショットからQRを検出した。これは別の場所で作ったテストQRのため本番サイトのQR形式として拒否された。実際に本番サイトで発行したQR写真の読取は未確認。本番画面で製品名を固定表示しない修正はGitHub ActionsとVM200本番Compose反映まで完了した。Phase 9のQRラベル一括発行・PDF取得はローカル・CI・VM200本番Compose反映まで完了したが、Phase 9全体は未完了。導入先では署名付き暗号化バックアップの別ホスト保存とVM201への独立した空環境復元、実ドメインの公開、管理者のパスキー直接ログインを確認した。VM201では復元データを用いたDjangoビューのパスワードログイン・TOTP・管理画面・ログアウト後拒否と、再起動後のDB・写真用ボリューム永続化を確認した。別ホストの保存物3ファイルをVM201へストリームし、復元に使用した搬入物とのバイト一致も確認した。ただし復元処理への元の搬入経路はVM200である。VM201の実ブラウザ／HTTPS経路での認証は、運用者判断により今回省略した。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了。

## 2026-10-08 指定JSONによる蝶類和名分類と標本管理一覧

運用者が指定した`日本産蝶類_和名分類_328種.json`だけを日本産蝶類和名分類の参照元とする方針を`PROJECT_SPEC.md`へ記録した。運用者の承認を受け、元ファイルを変更せず`specimens/data/japanese_butterflies_ja_328.json`へコピーした。両ファイルのSHA-256は`1c9fb5a46cf825cc5e1a0ab04806571e502505e441a8edc6ed4b9406ac4cfa33`で一致する。出典とCC BY 3.0の適用を`THIRD_PARTY_NOTICES.md`へ明記した。取込コマンドは外部サイトを取得せず、このローカルJSONのみを読み、328種・9階級・階層の重複を保存前に検証する。新版`japanese-butterflies-ja-328`へ和名だけを取り込み、既存の便覧版レコード、学名、既存標本の分類参照は変更しない。再実行は同一版なら無変更、内容が異なる版なら上書きせず停止する。JSONにない学名は補完しない。

標本登録画面の和名分類選択を科→亜科→族（該当する場合）→属→種に拡張した。ブラウザで下位候補を絞り込み、送信時も親子関係を検証する。元JSONの界・門・綱・目もDBの階層として保持する。Phase 9の次の安全な範囲として、管理者MFAゲート配下に標本管理一覧を追加し、標本番号・分類名・状態で検索して詳細へ進めるようにした。標本無効化・完全削除の操作はまだ追加していない。これらは現行の履歴・QR・写真の保護参照と公開URLの意味を含むため、別途設計を確定する。

変更ファイルは`PROJECT_SPEC.md`、`THIRD_PARTY_NOTICES.md`、`STATUS.md`、`specimens/data/japanese_butterflies_ja_328.json`、`specimens/models.py`、`specimens/migrations/0004_alter_taxondatasetrecord_rank_and_more.py`、`specimens/management/commands/import_japanese_butterfly_taxa.py`、`specimens/forms.py`、`specimens/templates/specimens/register.html`、`static/js/taxon-hierarchy.js`、分類テスト、`management_portal/views.py`、`management_portal/urls.py`、管理トップ・標本管理一覧テンプレート、管理画面テストである。実JSONは328種、5科、21亜科、31族、168属、全557階層項目で、族がない48種を含む。ローカルSQLiteの全382テストは成功（PostgreSQL専用4件skip）。実JSONの件数・ハッシュ・取込結果、版違いと重複の拒否、冪等性、既存標本参照の保持、親子関係の不正送信、管理者以外とMFA未完了の拒否を確認した。Ruff lint・format、Django check、migration差分なし、JavaScript構文確認、`git diff --check`が成功した。Windowsサンドボックスでは既存の非同期DBテストが停止したため、同じテストと全体テストを通常権限で再実行して成功を確認した。PostgreSQL上のCI、本番取込み、実ブラウザの階層選択はこの記録時点では未実施。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

実装コミット`7c09fa6`と管理者向け標本一覧・作業結果のコミット`9a5df35`をGitHubへpushした。`9a5df35`のGitHub Actions run `37785585644`では、PostgreSQL上の`test`と、直接HTTPS・Tunnel・暗号化バックアップから空環境への復元を含む`production-container`がともに成功した。VM200は更新前に作業ツリーが清潔でHEADが`3feeb63`だった。PostgreSQL 18の更新前バックアップ`acervo-20261008T134137Z-bd773191b6c4`を終了コード0で作成し、保持規則により旧バックアップ`acervo-20261008T090018Z-9a38e52d4e7c`を1件削除した。`9a5df35`へfast-forward後、Cloudflare用Composeの設定検証は成功した。`up -d --build --wait`はguest agentのPID `1382729`で完了し、`exited=1`、`exitcode=0`、webのhealthyを確認した。最初の`check --deploy`は貼付時に末尾へ余分な`]`が付き終了コード2になったが、正しいコマンドで再実行し、問題0件・終了コード0を確認した。`migrate --check`は終了コード0。`docker compose ps`では`db`・`web`・`proxy`がhealthy、`tunnel`が稼働中で、webの実行UIDは`10001`だった。VM200の作業ツリーは清潔でHEADは`9a5df35`。

VM200のwebコンテナで`import_japanese_butterfly_taxa`を実行し、終了コード0を確認した。guest agent経由の日本語結果は文字化けしたため文言は判読できなかったが、DB照会は終了コード0で、データセット`japanese-butterflies-ja-328`に全557項目（5科・21亜科・31族・168属・328種）が保存されていることを英数字の出力で確認した。実ブラウザでの和名階層選択、管理者向け標本一覧、更新後のDB・写真ボリューム再起動永続化は未確認。本追記は文書だけのためVM200への再反映は不要。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-08 保管場所の編集・削除と導入先設定の参照画面

Phase 9の管理画面に、保管場所の名称・備考・上位場所の編集、未使用の保管場所の削除、導入先設定の参照画面を追加した。上位場所の変更時は自分自身・下位場所への移動と同階層の同名を拒否し、既存の下位場所は新しい階層へ一緒に移動する。削除は対象名の再入力、確認チェック、直近のTOTPまたはパスキー再認証を必須とし、標本または下位場所が参照する場所は削除しない。編集・削除と監査記録は同一トランザクションで保存し、監査記録失敗時は変更を巻き戻す。監査記録には名称・備考などの入力値を含めない。`audit.0008_alter_auditlog_action`は監査操作種別のみ追加し、保管場所のDB構造は変更しない。

導入先設定画面は`PROJECT_SPEC.md`のStep 7A方針に従い、環境変数で管理しているサイト表示名、組織名、在籍判定方式と年度切替日だけを読み取り専用で表示する。秘密鍵、パスワード、認証コード、公開URL等は表示せず、DB設定テーブルや動的切替は追加しない。変更ファイルは`audit/models.py`、`audit/migrations/0008_alter_auditlog_action.py`、`management_portal/views.py`、`management_portal/urls.py`、管理トップ・保管場所一覧・編集・削除・導入先設定のテンプレート、`management_portal/tests/test_storage_locations.py`、本書である。

ローカルの保管場所管理10テストとSQLiteの全376テストが成功（PostgreSQL専用4件skip）。権限・MFA不足、階層の循環、同階層の重複、存在しない上位場所、削除時の対象名不一致、参照中の場所の保護、監査記録失敗時の巻き戻しを確認した。Ruff lint・format、Django check、migration差分なし、`git diff --check`も成功した。PostgreSQL上のテスト、GitHub Actions、本番Composeへの反映、実ブラウザ受入はこの記録時点では未実施である。標本無効化・完全削除は未実装。現行モデルでは標本履歴・QR割当・写真が標本をPROTECT参照しており、完全削除には履歴と写真の保全・削除境界、QR tokenの無効化と番号不再利用の設計決定が必要である。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了とする。

実装コミット`3feeb63`をGitHubへpushした。GitHub Actions run `37648327103`はPostgreSQL上の`test`と、本番Composeの直接HTTPS・Tunnel構成、暗号化バックアップと空環境復元を含む`production-container`がともに成功した。VM200の更新前HEADは`928c3f2`で作業ツリーに変更なし。PostgreSQL 18の暗号化バックアップ`acervo-20261007T160344Z-7a7ea946a1e8`を終了コード0で作成し、保持規則により旧バックアップ`acervo-20261007T153928Z-9c8cd76d7581`を1件削除した。`3feeb63`へfast-forward後、Cloudflare用Compose設定検証、webイメージの再ビルドと`up -d --build --wait`は成功した。起動結果はguest agentのPID `918313`を`qm guest exec-status`で追跡し、`exited=1`、`exitcode=0`、`db`・`web`・`proxy`のhealthyを確認した。コンテナ内`check --deploy`は問題0件、`migrate --check`は終了コード0。`docker compose ps`では`db`・`web`・`proxy`がhealthy、`tunnel`が稼働中だった。webの実行UIDは`10001`、VM200の作業ツリーは清潔でHEADは`3feeb63`。実ブラウザでの編集・削除・導入先設定の受入と、更新後のDB・写真ボリューム再起動永続化は未確認。文書だけの本追記はVM200への再反映不要。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-08 保管場所の管理画面

Phase 9の保管場所管理の最初の範囲として、管理者が`/management/storage-locations/`で場所を一覧表示・追加できる画面を実装した。既存の保管場所を上位場所に指定でき、追加した場所は標本登録・編集の選択肢へ入る。利用者に表示する名称・備考は導入先で入力し、コードへ固定しない。管理ポータルの中央MFAゲートを通し、作成と「保管場所作成」の監査記録を同一トランザクションで保存する。`audit.0007_alter_auditlog_action`は監査操作種別だけを追加し、保管場所のDB構造は変更しない。

変更ファイルは`audit/models.py`、`audit/migrations/0007_alter_auditlog_action.py`、`management_portal/views.py`、`management_portal/urls.py`、`management_portal/templates/management_portal/index.html`、`management_portal/templates/management_portal/storage_location_list.html`、`management_portal/tests/test_storage_locations.py`である。管理画面の対象4テストで、階層作成、標本フォームへの反映、存在しない親と同じ上位場所での重複名の拒否、権限・MFA不足、監査記録失敗時の巻き戻しを確認した。SQLiteの全370テストは成功（PostgreSQL専用4件skip）。Ruff lint・format、Django check、migration差分なし、`git diff --check`も成功した。実装コミット`928c3f2`のGitHub Actions run `37644633462`では、PostgreSQL上の`test`と直接HTTPS・Tunnel・暗号化バックアップと空環境復元を含む`production-container`がともに成功した。

VM200への反映前は作業ツリーが清潔でHEADは`62b8375`。PostgreSQL 18の更新前バックアップ`acervo-20261007T153928Z-9c8cd76d7581`を作成成功し、保持規則により旧バックアップ`acervo-20261007T151615Z-556d56e56bc2`を1件削除した。`928c3f2`へfast-forward後、Cloudflare用Compose設定検証と`up -d --build --wait`は成功し、`db`・`web`・`proxy`・`tunnel`がhealthyになった。`check --deploy`は問題0件、`migrate --check`は終了コード0、`docker compose ps`では`db`・`web`・`proxy`がhealthyで`tunnel`は稼働中、webの実行UIDは`10001`だった。VM200の作業ツリーは清潔でHEADは`928c3f2`。実ブラウザでの受入と更新後のDB・写真永続化は未確認。場所の編集・削除、設定管理、標本無効化・完全削除などは残る。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了とする。

## 2026-10-07 QRラベル無効化の管理画面

`/management/qr-batches/`の発行履歴から、発行単位ごとのQRラベル状態を確認できる画面を追加した。QR識別子は画面・URL・監査記録へ出さず、管理用のQRラベル番号、状態、割当有無だけを表示する。未使用・割当済みいずれのQRも個別に無効化でき、無効化後は既存の標本割当履歴を保持しながら、QR URLによる標本登録・詳細表示を既存の410応答へ移す。

無効化は、対象QRラベル番号の再入力、確認チェック、管理ポータルの中央MFAゲート、直近のTOTPまたはパスキー再認証を必須とする。状態変更と「QRラベル無効化」の監査記録は同一トランザクションで行い、監査記録の保存に失敗した場合は無効化もロールバックする。監査操作種別追加の`audit.0006_alter_auditlog_action` migrationを含む。

変更ファイルは`audit/models.py`、`audit/migrations/0006_alter_auditlog_action.py`、`management_portal/views.py`、`management_portal/urls.py`、QRラベル管理テンプレート、`management_portal/tests/test_qr_batches.py`である。QR管理とQR基盤の対象27テスト、SQLiteの全366テスト（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分なし、`git diff --check`が成功した。コミット`62b8375`に対するGitHub Actions run `37635997071`と`37635996585`では、PostgreSQL上の`test`と、直接HTTPS・Tunnel・暗号化バックアップと空環境復元を含む`production-container`がともに成功した。

2026-10-08にVM200へ反映した。更新前の作業ツリーは清潔でHEADは`a06e13c`。更新前バックアップ`acervo-20261007T151615Z-556d56e56bc2`をPostgreSQL 18で作成し、保持規則により旧バックアップ`acervo-20261007T135501Z-19de5af02b70`を1件削除した。`62b8375`へfast-forward後、Cloudflare用Compose設定検証と`up -d --build --wait`は成功し、`db`・`web`・`proxy`・`tunnel`のhealthyを確認した。コンテナ内の`check --deploy`は問題0件、`migrate --check`は終了コード0、`docker compose ps`では`db`・`web`・`proxy`がhealthyで`tunnel`が稼働中、webの実行UIDは`10001`だった。VM200の作業ツリーは清潔でHEADは`62b8375`。実ブラウザでのQR無効化受入と更新後のDB・写真永続化は未確認である。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-07 日本産蝶類の分類階層選択

標本登録画面では、既に本番へ取り込まれている「日本産蝶類和名学名便覧」（CC BY 3.0、5科・328種）のデータを、和名を優先して表示する科・属・種の3段階選択にした。科を選ぶまで属を、属を選ぶまで種を選べないようにし、親子関係と異なる選択肢は画面で隠す。JavaScriptを迂回した送信でも、フォームが科→属→種の親子関係を検証し、最も下位の選択を標本の分類として保存する。他の分類を使う既存の選択欄は「その他の分類」として残し、便覧の分類との同時選択は拒否する。

分類を手入力で登録する画面では、分類階級を「科」「属」「種」「その他」の日本語で表示し、属には科、種には属だけを上位分類候補として表示する。送信時にも上位分類の必須・分類階級を検証する。取込コマンドは5科の和名（セセリチョウ科、シジミチョウ科、タテハチョウ科、アゲハチョウ科、シロチョウ科）を保存・補完するようにした。DB migrationはない。

変更ファイルは`specimens/forms.py`、`specimens/management/commands/import_japanese_butterfly_taxa.py`、`specimens/templates/specimens/register.html`、`specimens/templates/specimens/taxon_manual.html`、`static/js/taxon-hierarchy.js`、`specimens/tests/test_taxonomy.py`である。対象28テスト、SQLiteの全364テスト（PostgreSQL専用4件skip）、Ruff lint・format、JavaScript構文確認、Django check、migration差分なし、`git diff --check`が成功した。GitHub Actions run `37631440980` はPostgreSQL上の`test`と、直接HTTPS・Tunnel・暗号化バックアップと空環境復元を含む`production-container`がともに成功した。

VM200では更新前に暗号化バックアップ`acervo-20261007T135501Z-19de5af02b70`をPostgreSQL 18で作成し、保持規則により直前の`acervo-20261007T125655Z-6b609e7d2e01`を削除した。`6a0d246`から`a06e13c`へfast-forward後、Cloudflare用Compose設定検証、webイメージ再ビルド、`up -d --build --wait`はいずれも成功した。`check --deploy`は警告なし、`migrate --check`は終了コード0、`db`、`web`、`proxy`はhealthy、`tunnel`は稼働中、webのUIDは`10001`である。作業ツリーは清潔でHEADは`a06e13c`。取込コマンドを成功させ、データセットは5科・328種であることを再確認した。DB schema変更はない。iPhoneでの分類選択受入は未実施である。Phase 6の既存完了実績、Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体の完了状態は変更しない。

## 2026-10-07 導入先名以外の製品名固定表示を禁止

利用者に表示する画面、PWA、エラー、ダウンロード用ファイル名で製品名`Acervo`を固定表示しない方針を`PROJECT_SPEC.md`へ追加した。`ACERVO_SITE_NAME`が未設定の開発環境の既定値を「このサイト」に変更し、開発・本番の環境変数例も導入先依存の名称へ変更した。リカバリーコードをブラウザから保存する際のファイル名を`recovery-codes.txt`に統一した。画面用テンプレートと静的ファイルに固定表示の`Acervo`が残らないこと、既定サイト名、TOTP・WebAuthnのRP表示名、リカバリーコード保存名を回帰テストで確認した。変更ファイルは`PROJECT_SPEC.md`、`config/settings/base.py`、`.env.example`、`.env.production.example`、`templates/mfa/recovery_codes/index.html`、`core/tests/test_views.py`、`accounts/tests/test_deployment_config.py`、`accounts/tests/test_mfa_recovery_codes.py`で、DB migrationはない。対象42テスト、SQLiteの全360テスト（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分なし、`git diff --check`が成功した。GitHub Actions run `37623734100` は `test` と `production-container` がともに成功した。VM200では更新前に暗号化バックアップ`acervo-20261007T125655Z-6b609e7d2e01`を作成し、終了コード0と保持規則による直前1世代の削除を確認した。`0a91ea0`から`6a0d246`へfast-forward後の作業ツリーは清潔で、Cloudflare用Compose設定検証、`up -d --build --wait`、`check --deploy`、`migrate --check`はいずれも成功した。`db`、`web`、`proxy`、`tunnel`は稼働し、`db`、`web`、`proxy`はhealthy、webのUIDは`10001`である。VM200のHEADは`6a0d246`で作業ツリーは清潔。DB schema変更はない。実機でのQRラベル発行確認と新しいサイト名表示は未確認。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-07 QRラベル発行の確認操作

`/management/qr-batches/` の「QRラベルを発行」ボタンを、初期表示では無効にし、「発行内容を確認した」のチェック状態に応じて有効・無効を切り替えるようにした。サーバー側の確認必須バリデーションは維持しており、JavaScriptが動かない場合にも未確認の発行は拒否される。変更ファイルは`management_portal/templates/management_portal/qr_batch_list.html`と`management_portal/tests/test_qr_batches.py`で、DB migrationはない。QR管理画面の9テスト、SQLiteの全360テスト（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分なし、`git diff --check`が成功した。GitHub Actions run `37621728054` は `test` と `production-container` がともに成功し、VM200への反映結果は本項の直前に記録した`6a0d246`の更新で確認済み。Phase 9全体、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-07 本番画面の製品名固定表示を除去

運用者のiPhoneで同じスクリーンショットを再選択した結果、「AcervoのQRラベルではありません」と表示され、画像からQRを検出できていることを確認した。画像は本番サイトで発行したものではなく、別の場所で作ったテストQRだったため、同一サイトのUUIDv4 URL制限による拒否は期待どおり。本番サイト発行QRの写真読取は未確認。運用者の要望により、本番画面の固定文字列「Acervo」を導入先名または「このサイト」に置き換える。`templates/base.html`、`templates/account/`、`templates/mfa/`、`templates/429.html`、`management_portal/templates/management_portal/`、`specimens/templates/specimens/taxon_search.html`の表示文字列とタイトル、`static/js/qr-scan.js`のQRエラー、`static/pwa/offline.html`を変更した。`static/js/service-worker.js`のキャッシュ版を更新してPWAに新しい静的ファイルを取得させる。`core/tests/test_views.py`、`accounts/tests/test_mfa_urls.py`、`core/tests/pwa_js_test.cjs`を更新し、導入先表示名とQR判定、既存カメラ経路を確認した。対象Django 18テスト、SQLiteの全359テスト（PostgreSQL専用4件skip）、Node.js 4テスト、Ruff lint・format、Django check、migration差分なし、`git diff --check`は成功。画面用HTMLとJSの固定文字列を検索し、残存しないことを確認した。GitHub Actions run `37618051799` は `test` と `production-container` がともに成功した。VM200では、更新前に暗号化バックアップ`acervo-20261007T121033Z-e44b4287b247`を作成し、終了コード0と保持規則による旧1世代の削除を確認した。`0a91ea0`へfast-forward後の作業ツリーは清潔で、Cloudflare用Compose設定検証、`up -d --build --wait`、`check --deploy`、`migrate --check`はいずれも成功した。`db`、`web`、`proxy`、`tunnel`は稼働し、`db`、`web`、`proxy`はhealthy、webのUIDは`10001`である。VM200のHEADは`0a91ea0`で作業ツリーは清潔。DB schema変更はない。運用者の画面確認では、現在の本番サイト表示名に「Acervo」は含まれていない。実機での新表示と本番サイト発行QR写真の読取は未確認。Android実機受入はMVP完成後へ延期したまま。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了。

## 2026-10-07 保存済みQR画像の読取失敗

運用者のiPhone実機では写真選択画面が開いたが、選んだQRのスクリーンショットは「QRコードが見つかりませんでした」と表示された。同じQRは標準カメラで読める。原因は実画像で未確定。コード上、QRを読めても同一サイトのUUIDv4 URL以外なら、その判定表示を「見つかりませんでした」で上書きする不具合を確認した。`static/js/qr-scan.js`で判定表示を保持し、保存画像だけは最大辺1200pxで見つからない場合に2400pxでも試し、反転QRも探索する。カメラ読取・切替の処理は維持する。`static/js/service-worker.js`のキャッシュ版を更新し、PWAが新しいJSを取得できるようにした。`core/tests/pwa_js_test.cjs`に判定表示、再試行と既存カメラ経路の回帰テストを追加した。ローカルSQLiteの全358テスト成功（PostgreSQL専用4件skip）、Node.jsの4テスト、Ruff lint・format、Django check、migration差分なし、`git diff --check`は成功。ローカル修正時点ではGitHub Actions、VM200反映、iPhone再確認は未実施だった。Android実機受入はMVP完成後へ延期したまま。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了。

コミット`cd3f7b8`をpushした。GitHub Actions run 37615165785はPostgreSQL上の`test`と、直接HTTPS・Tunnel構成、暗号化バックアップ・空環境復元を含む`production-container`が全成功した。VM200では更新前の作業ツリーが清潔でHEADは`da0ba30`、暗号化バックアップ`acervo-20261007T114317Z-0f3c7be8a9b9`を作成成功（PostgreSQL 18、保持規則で旧1世代削除）。`cd3f7b8`へfast-forwardし、Cloudflare用Composeの`config --quiet`が成功した。`up -d --build --wait`はguest agentがPIDを返したため`qm guest exec-status`で完了を確認し、終了コード0、全サービスHealthyを確認した。`check --deploy`は警告なし、`migrate --check`は終了コード0、更新後の`docker compose ps`では`db`・`web`・`proxy`がhealthy、`tunnel`が稼働中だった。web UIDは10001、VM200の作業ツリーは清潔でHEADは`cd3f7b8`。DB schema変更はない。iPhoneで同じスクリーンショットの再読取、更新後のDB・写真ボリューム再起動永続化は未確認。前者を実機で確認し、結果に応じて表示または読取を再調査する。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-07 QR写真選択の案内と動作の整合

`templates/core/qr_scan.html`の写真ファイル入力から`capture="environment"`を外し、端末の保存済み画像を選択できる入力にした。`core/tests/test_views.py`に、写真選択の案内と画像ファイル入力の属性を確かめる回帰テストを追加した。カメラ読取・前面背面切替のJavaScriptとDB schemaは変更していない。ローカルSQLiteの全358テストは成功（PostgreSQL専用4件skip）。PWA用Node.jsの3テスト、Ruff lint・format、Django check、migration差分なし、`git diff --check`も成功した。最初に既定Pythonで試したDjango・Ruffの確認は依存未導入で実行できなかったため、既存`.venv`で再実行して成功した。コミット`e0c1ea3`をpushした。GitHub Actions run 37492995807ではPostgreSQL上の`test`と直接HTTPS・Tunnel構成および暗号化バックアップ・空環境復元を含む`production-container`が全成功した。iPhoneでの保存済み写真選択は未確認。Android実機受入はMVP完成後へ延期したまま。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了とする。

同日、運用者の追加依頼で読取画面の案内から「Acervoの」を外し、QRラベルの指示を簡潔にした。`templates/core/qr_scan.html`と`core/tests/test_views.py`を変更した。変更後の対象6テスト、Ruff lint・format、Django check、migration差分なし、`git diff --check`は成功。最初のRuff検査でテストの1行が長すぎると判明したため改行し、再検査で成功した。VM200の更新前バックアップ`acervo-20261007T104628Z-f0ea678adfc7`は作成成功（PostgreSQL 18、保持規則で旧1世代削除）。VM200の作業ツリーは清潔で更新前HEADは`78230a8`、`git fetch`後の`origin/main`は`e0c1ea3`だった。運用者が`e0c1ea3`へfast-forwardし、作業ツリーが清潔なことを確認した。新しい案内文を含むコミットのCI確認が終わるまで、コンテナ更新は保留する。

案内文変更をコミット`da0ba30`としてpushした。GitHub Actions run 37610136930はPostgreSQL上の`test`と、直接HTTPS・Tunnel構成および暗号化バックアップ・空環境復元を含む`production-container`が全成功した。VM200では`e0c1ea3`から`da0ba30`へfast-forwardし、Cloudflare用Composeの`config --quiet`が成功した。`up -d --build --wait`はguest agentの初回応答でPIDを返したため、`qm guest exec-status`で完了を確認した。終了コード0でwebイメージが再ビルドされ、`db`、`web`、`proxy`、`tunnel`がHealthyになった。更新後の`check --deploy`は問題0件、`migrate --check`は終了コード0、`docker compose ps`では`db`・`web`・`proxy`がhealthy、`tunnel`が稼働中だった。web UIDは10001、VM200のHEADは`da0ba30`で作業ツリーは清潔。DB schema変更はない。更新後のDB・写真ボリューム再起動永続化、実ブラウザの写真選択、実QR写真の読取は今回未確認。iPhone実機の最終確認は運用者が行う。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-07 PWA読取カメラの操作改善

運用者の要望により、QR読取開始時は画面側カメラを優先し、読取中に前面・背面を切り替えるボタンを追加した。切替前に既存カメラを解放し、切替失敗時は元の向きで再起動する。停止・画面離脱・非表示・遅れて届いたカメラ許可の際にも映像を解放する。Service Workerの静的資産キャッシュ版を更新し、既存PWAに新しい読取JSを取得させる。変更ファイルは`static/js/qr-scan.js`、`static/js/service-worker.js`、`templates/core/qr_scan.html`、`core/tests/pwa_js_test.cjs`、`core/tests/test_views.py`、`README.md`である。DB migrationはない。ローカルJSの3テストでは前面優先、両方向切替、切替失敗時の復旧、停止・遅延許可時の解放を確認した。ローカルSQLiteの全358テストは成功（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分なし、`git diff --check`も成功した。コミット`cdc77a4`のGitHub Actions run 37489490658では、PostgreSQL上の`test`と直接HTTPS・Tunnel構成、暗号化バックアップ・空環境復元を含む`production-container`が全成功した。VM200へ反映後、運用者がiPhone実機で前面・背面切替の動作確認を完了した。一方、写真選択欄は`capture="environment"`によりiPhoneで撮影画面が開くため、保存済み写真を選ぶ案内と一致しない。写真選択欄の修正・再確認は未実施。Android実機受入はMVP完成後へ延期したままとする。

## 2026-10-07 Phase 9 QRラベル管理画面の最初の実装

管理者MFAゲート配下の`/management/qr-batches/`で、1〜100枚の未使用QRを一括発行し、発行履歴と20mm角・1ページ1枚の印刷用PDFを取得できるようにした。無効化済みQRはPDFから除外する。入力確認、発行と監査記録の同一トランザクション、PDF生成成功後だけの印刷回数・監査記録更新を実装した。QRのUUID、標本番号、割当状態、認証方式は変更していない。変更ファイルは`audit/models.py`、`audit/migrations/0005_qr_batch_actions.py`、`management_portal/views.py`、`management_portal/urls.py`、`management_portal/templates/management_portal/index.html`、`management_portal/templates/management_portal/qr_batch_list.html`、`management_portal/tests/test_qr_batches.py`である。監査操作の選択肢追加以外にDB構造変更はない。

ローカルSQLiteではQR管理画面の8テストと全358テストが成功（PostgreSQL専用4件skip）。通常発行、権限不足、MFA未完了、入力不正、監査失敗時のロールバック、PDF生成失敗時の印刷記録なし、無効QRの除外を確認した。PWA用Node.jsの2テスト、Ruff lint・format、Django check、migration差分なし、`git diff --check`も成功した。コミット`1bb2110`のGitHub Actions run 37487839855では、PostgreSQL上の`test`と直接HTTPS・Tunnel構成、バックアップ・空環境復元を含む`production-container`が全成功した。VM200本番Composeへ反映済みだが、実印刷・実QRによる登録は未実施。Phase 9の残りであるQR無効化、保管場所・設定、標本無効化・完全削除なども未実装であり、Phase 9全体は未完了とする。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

同日、Phase 9 QR管理画面とPWAカメラ切替をVM200のCloudflare Tunnel本番構成へ反映した。更新前にPostgreSQL 18の暗号化バックアップ`acervo-20261006T155239Z-4fe0b16bafce`を作成し、保持規則により旧1世代を削除した。`947abfb`から`78230a8`へfast-forwardし、作業ツリーが空であること、Cloudflare用Compose設定検証、webイメージの再ビルドと`up -d --build --wait`の成功、全サービスのhealthyを確認した。コンテナ内`check --deploy`は警告なし、`migrate --check`は未適用migrationなし、`audit.0005_qr_batch_actions`は適用済み、web UIDは10001、VM200の作業ツリーは空だった。実ブラウザでのQR管理画面、実印刷、iPhoneカメラ切替の確認は未実施である。

## 2026-10-06 Phase 8 PWAのローカル実装

Manifest、192px・512pxの自己配信アイコン、standalone表示、Service Worker、オフライン案内を追加した。Service Workerは固定した静的資産と案内HTMLだけを保存し、標本詳細・写真・検索・CSV・API・管理画面や利用者情報を保存しない。オンライン画面の通信が失敗した場合に案内だけを返し、オフライン登録や後同期は提供しない。利用者ホームの主導線をQR読取とし、現在在籍のmemberまたはadminだけにアプリ内読取画面を許可する。

カメラ映像または選択した写真からQRを端末内で読み取る。固定版`jsQR 1.4.0`をApache-2.0ライセンスとともに自己配信する。公式npm配布物のSHA-512整合性を確認し、同梱JSのSHA-256は`bc40c8a15196236b2314db0856f72ca0b49980cd5413b8c852a7349f5fee0859`。読み取った文字列は現在のサイトと同じオリジンの`/q/<uuidv4>/`形式だけに制限する。QR到達後も既存のサーバー側ログイン・在籍・role判定を通す。端末カメラが使えない場合は写真選択または標準カメラから同じURLへ進める。

変更ファイルは`core/views.py`、`core/urls.py`、`core/tests/test_views.py`、`core/tests/pwa_js_test.cjs`、`templates/base.html`、`templates/core/home.html`、`templates/core/qr_scan.html`、`static/js/pwa-register.js`、`static/js/service-worker.js`、`static/js/qr-scan.js`、`static/pwa/`、`static/vendor/jsqr/`、`scripts/generate_pwa_icons.py`、`.github/workflows/ci.yml`、`.github/scripts/verify-production-compose.sh`、`pyproject.toml`、`THIRD_PARTY_NOTICES.md`、`README.md`である。DB migrationはない。ローカルSQLiteでは全350テスト成功（PostgreSQL専用4件skip）、Node.jsのPWA用2テスト成功、Ruff lint・format、Django check、migration差分確認、`git diff --check`が成功した。Node.jsテストでは静的資産以外をService Workerが保存しないこと、同一サイトのUUIDv4以外のQRを拒否することを検証した。コミット`947abfb`のGitHub Actions run 37483145390では`test`と`production-container`が全成功し、PostgreSQLテスト、PWA用Node.jsテスト、直接HTTPS／Cloudflare Tunnel構成、本番コンテナ、PWA資産の疎通、暗号化バックアップと空環境復元を確認した。

2026-10-07、VM200のCloudflare Tunnel本番構成へ反映した。更新前にPostgreSQL 18の暗号化バックアップ`acervo-20261006T150121Z-1289e8db6bcd`を作成し、保持規則により古い1世代を削除した。`f517f15`から`947abfb`へfast-forwardし、Cloudflare用Compose設定検証、webイメージの再ビルド、`up -d --build --wait`が成功した。コンテナ内`check --deploy`は警告なし、`migrate --check`は未適用migrationなし、`db`、`web`、`proxy`はhealthy、`tunnel`は稼働中、webのUIDは10001、VM200の作業ツリーは空だった。DB migrationの追加はない。iPhoneではホーム画面への追加と閲覧を確認し、ホーム画面から開いたAcervo内の「QRコードを読み取る」で、DBに登録していない同一サイトのUUIDv4形式テストQRを読み取ると404画面へ遷移した。これはテストQRの未登録による期待結果であり、本番データは変更していない。Android端末は手元になく、ホーム画面追加とHTTPS上のカメラ読取は未実施である。運用者の決定によりAndroid実機受入だけをMVP完成後へ移し、Android向けのPWA実装は残す。改訂後のMVP条件ではPhase 8を完了とするが、Androidでの動作確認済みとは扱わない。7C-LIVE-A、7C-LIVE-B、Phase 1全体も未完了のままとする。

## 2026-10-03 Phase 4 スマホ標本登録のローカル実装

未使用QRの`/q/<uuid>/`は、認可された利用者だけを登録入力画面へ遷移させる。入力値と再エンコード済みの一時写真はセッションに紐付け、確認画面の表示だけでは標本番号、QR状態、標本、履歴を変更しない。確定POSTではQR行をロックし、標本番号、標本、初回履歴、QR割当、写真レコードを同じトランザクションで確定する。競合して別の登録が先にQRを使った場合は409で失敗させ、標本番号とQRの二重利用を防ぐ。

写真はJPEG・PNG・WebPだけを実デコードし、1枚10MB、8,000万画素、標本あたり10枚を上限とした。2,000万画素を超える画像は縦横比を保って縮小し、EXIFを除去してランダム名のJPEGとして保存する。確認中の写真も同じ再エンコード済み一時領域へ置き、確定の成功・失敗時に削除する。確定途中の保存失敗時は保存済みの最終写真も補償削除する。写真はCaddyの公開URLへ置かず、ログインと`can_use_qr`の認可を通るDjangoの保護ビューからだけ返す。

変更ファイルは`config/settings/base.py`、`pyproject.toml`、`specimens/forms.py`、`specimens/services.py`、`specimens/urls.py`、`specimens/views.py`、`specimens/templates/specimens/register.html`、`specimens/templates/specimens/register_confirm.html`、`specimens/templates/specimens/registration_complete.html`、`specimens/tests/test_photo_processing.py`、`specimens/tests/test_qr.py`、`specimens/tests/test_sequence_concurrency.py`である。Pillow 12.3.0を、Django 5.2/Python 3.13で利用する直接依存として追加した。DBスキーマ変更はない。

ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が329件成功（PostgreSQL専用4件skip）、`ruff check .`、`ruff format --check .`、`python manage.py check --settings=config.settings.test`、`makemigrations --check --dry-run --settings=config.settings.test`、`git diff --check`が成功した。Phase 4専用では通常経路、確認時の採番なし、入力不正、権限不足、QR競合、写真の実形式・容量・画素数・枚数、EXIF除去、元ファイル名非使用、失敗時一時写真削除、保護写真の認証・認可を検証した。PostgreSQL上の同時QR登録テストはGitHub Actionsで未確認、本番Compose・VM200実ブラウザ受入も未実施である。コミット・push・VM200反映はGitHub Actions成功後にだけ行う。7C-LIVE-A、7C-LIVE-B、Phase 1全体はいずれも未完了とする。

コミット`f5e7481`のGitHub Actions run 37113053029では、PostgreSQL上の329テスト本体は成功したが、並行テストのワーカー接続が残り、テスト用DB削除時に失敗した。本番反映は行っていない。`specimens/tests/test_sequence_concurrency.py`の各ワーカーで接続を明示的に閉じる修正を加え、ローカル再検証後に再度CIへ送る予定である。

コミット`ffb0b7f`のGitHub Actions run 37113444348では、PostgreSQL 18上の329テスト、Ruff、Django check、マイグレーション、直接HTTPS／Cloudflare Tunnel Compose、暗号化バックアップと空環境復元を含む`test`・`production-container`が全成功した。先行runの失敗はテスト本体ではなくテストDB削除時の接続残りであり、このrunで解消を確認した。

2026-10-04、VM200のCloudflare Tunnel本番構成へ反映した。更新前にPostgreSQL 18の暗号化バックアップ`acervo-20261003T093926Z-bc8c5fc25f2e`を作成し、保持規則により古い1世代を削除した。`378a51f`から`ffb0b7f`へfast-forwardし、Cloudflare用Compose設定検証、webイメージの再ビルド、`up -d --build --wait`を成功させた。`db`、`web`、`proxy`、`tunnel`はhealthy、コンテナ内`check --deploy`は警告なし、webのUIDは10001、既存の`specimens.0001_initial`と`specimens.0002_qrbatch_qrlabel_and_more`は適用済み、VM200上の作業ツリーは空だった。Phase 4はDBスキーマ変更を含まない。実データ、実QR、実写真、スマートフォンの実機受入は行っておらず、Phase 5以降と7C-LIVE-Bへ残す。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-04 Phase 5 検索・詳細・履歴のローカル実装

標本番号、同定情報、学名・和名、採集地、採集者を対象にしたキーワード検索と状態による絞り込み、一覧、詳細画面を追加した。詳細・写真のURLにはDB連番IDや標本番号ではなく、標本固有のランダムUUIDv4だけを使う。割当済みQRは、閲覧を許可された利用者をその標本詳細へ遷移させる。

有効な卒業生memberも検索、詳細、保護写真を閲覧できる一方、編集、履歴追加、写真追加は現在在籍のmemberまたはadminだけに制限した。認可は全エンドポイントでサーバー側判定し、権限不足や推測したUUIDには404を返す。標本の編集では標本番号、詳細UUID、状態を変更できない。状態変更を伴う履歴は既存の行ロック・トランザクションサービスで記録し、同じ状態への重複遷移や不正遷移を拒否する。複数写真の追加は上限・実形式をすべて確認してから同じトランザクションで保存する。

変更ファイルは`templates/base.html`、`specimens/access.py`、`specimens/forms.py`、`specimens/services.py`、`specimens/urls.py`、`specimens/views.py`、`specimens/templates/specimens/list.html`、`specimens/templates/specimens/detail.html`、`specimens/templates/specimens/edit.html`、`specimens/templates/specimens/event.html`、`specimens/templates/specimens/photo_add.html`、`specimens/tests/test_qr.py`、`specimens/tests/test_views.py`である。ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が335件成功（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分確認、`git diff --check`が成功した。コミット`fc878f9`のGitHub Actions run 37133060241では、PostgreSQL 18上のテスト、Ruff、Django check、直接HTTPS／Cloudflare Tunnel Compose、暗号化バックアップと空環境復元を含む`test`・`production-container`が全成功した。2026-10-04、更新前バックアップ`acervo-20261004T090145Z-8942e3885f7d`（PostgreSQL 18）を作成し、保持規則により古い1世代を削除した。VM200を`ffb0b7f`から`fc878f9`へfast-forwardし、Cloudflare用Compose設定検証、webイメージの再ビルド、`up -d --build --wait`を成功させた。`db`、`web`、`proxy`、`tunnel`はhealthy、コンテナ内`check --deploy`は警告なし、webのUIDは10001、既存の`specimens.0001_initial`と`specimens.0002_qrbatch_qrlabel_and_more`は適用済み、VM200上の作業ツリーは空だった。実ブラウザ受入と実データによる検索・編集・履歴・写真追加は未実施であり、7C-LIVE-Bへ残す。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-04 Phase 6 分類候補検索・蝶類初期データのローカル実装

`TaxonDataset`、`TaxonDatasetRecord`、`TaxonDatasetRevision`を追加した。データセットは名称、版、ライセンス、保存版URL、取得日、画面・出力で使う出典表記を保持し、レコードはデータセットごとの科・属・種の階層、和名、学名、学名著者、原記載年、根拠URLを保持する。将来の訂正・新版は既存データを上書きせず別データセットと取込み履歴として保存できる。既存標本、QR、認証の構造は変更していない。

`import_japanese_butterfly_taxa`管理コマンドは、明示実行時だけWayback Machine 2021-05-05保存版の「日本産蝶類和名学名便覧」を取得し、写真・サイトデザインを扱わず、分類データだけを冪等に取り込む。5科・328種以外を検出した場合は保存せず中止する。保存時はデータ版`2010–2013`、CC BY 3.0、保存版URL、指定された出典表記を保存する。保存版の読取り検証では5科・328種を検出した。

分類候補画面はまずローカル分類を検索し、候補がない場合だけ環境設定`ACERVO_TAXON_EXTERNAL_SEARCH_ENABLED=true`でGBIFの候補を2秒上限で照会する。外部通信の停止・タイムアウト時も手入力登録を妨げない。外部候補を明示採用した場合だけ根拠URL、引用、確認日を`TaxonSource`へ保存する。分類検索・採用・手入力は現在在籍のmemberまたはadminに限定し、卒業生には404を返す。画面はデジタル庁デザインシステムの検索、フォーム、リスト、アクセシビリティ指針を参照して、ラベル、補助説明、エラー、意味のある状態表示を設けた。

変更ファイルは`.env.production.example`、`config/settings/base.py`、`specimens/forms.py`、`specimens/models.py`、`specimens/services.py`、`specimens/views.py`、`specimens/urls.py`、`specimens/management/commands/import_japanese_butterfly_taxa.py`、`specimens/migrations/0003_taxondataset_taxondatasetrecord_taxondatasetrevision.py`、分類画面テンプレート、テストである。ローカルSQLiteでは再試行修正後の全343テスト成功（PostgreSQL専用4件skip）、Ruff lint・format、Django check、migration差分確認、`git diff --check`が成功した。初回CI run 37199916776はPostgreSQLのテスト内で固定IDを仮定したため失敗したが、実装ではなくテストの連番依存を除去した。run 37200658624と再試行修正のrun 37201415140では、PostgreSQL 18上のテスト、Ruff、Django check、直接HTTPS／Cloudflare Tunnel Compose、暗号化バックアップと空環境復元を含む`test`・`production-container`が全成功した。

2026-10-04、VM200のCloudflare Tunnel本番構成へ反映した。更新前バックアップ`acervo-20261004T120716Z-c85888476c64`と、再試行修正前の更新前バックアップ`acervo-20261004T121934Z-e53839d3235b`（いずれもPostgreSQL 18）を作成し、それぞれ保持規則により古い1世代を削除した。VM200を`fc878f9`から`76ab114`、続けて`594114c`へfast-forwardし、Cloudflare用Compose設定検証、webイメージの再ビルド、`up -d --build --wait`を成功させた。`specimens.0003_taxondataset_taxondatasetrecord_taxondatasetrevision`まで適用済みで、`db`、`web`、`proxy`、`tunnel`はhealthy、`check --deploy`は警告なし、作業ツリーは空だった。初回取込み時にWayback Machineから一時的に接続拒否されたが、DB書込み前の失敗でデータは残らなかった。再試行対応後に取込みを成功させ、データセット1件、5科、328種、版`2010–2013`、ライセンス`CC BY 3.0`、取込み履歴1件を確認した。実ブラウザでの分類候補検索・外部候補採用・出典表示の受入は未実施であり、7C-LIVE-Bへ残す。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-04 Phase 7 PDF・CSVのローカル実装

標本詳細から、現在在籍のmemberまたはadminだけが70mm×35mmの標本ラベルPDFを取得できるようにした。ラベルには標本番号、分類または同定情報、採集日、採集地、採集者を収め、保護されたDjangoビューから添付として返す。割当済みQRの20mmラベルPDFも同じ権限に限定して再印刷でき、成功した再印刷だけが既存のQR token・割当を変えずに再印刷回数と時刻を記録する。卒業生memberは両PDFを取得できない。

管理ポータルにadmin限定の標本CSV出力を追加した。既存の中央MFAゲートを通し、生成したCSVはBOM付きUTF-8・添付・`nosniff`で返す。標本番号、分類、同定情報、状態、入手・採集・保管・備考・登録日の各列について、先頭または先頭空白後が`=`、`+`、`-`、`@`となる値へアポストロフィを付け、表計算ソフトの数式評価を防ぐ。出力成功時だけ既存の追記専用`AuditLog`へ、実行者と「標本CSV出力」の操作種別を記録する。監査ログにCSV本文や秘密値は保存しない。`audit`の小規模な選択肢追加migrationを含むが、標本・QR・認証の構造や不変条件は変更していない。

変更ファイルは`audit/models.py`、`audit/migrations/0004_specimen_csv_export_action.py`、`management_portal/views.py`、`management_portal/urls.py`、`management_portal/templates/management_portal/index.html`、`management_portal/tests/test_specimen_csv_export.py`、`specimens/services.py`、`specimens/views.py`、`specimens/urls.py`、`specimens/templates/specimens/detail.html`、`specimens/tests/test_views.py`である。デジタル庁デザインシステムは、既存の白・黒・グレー基調と、操作名が明確なボタン、ラベル・補助説明を保つための参考に留め、コードや資産は取り込んでいない。

ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が347件成功（PostgreSQL専用4件skip）、`ruff check .`、`ruff format --check .`、`python manage.py check --settings=config.settings.test`、`makemigrations --check --dry-run --settings=config.settings.test`、`git diff --check`が成功した。Phase 7専用では、標本ラベルPDF・QR再印刷PDFの応答形式と再印刷記録、卒業生のPDF拒否、memberのCSV拒否、CSV出力の監査記録、`=`・空白後`@`・`+`・`-`で始まるセルの無害化を確認した。コミット`f517f15`のGitHub Actions run 37202579808では、PostgreSQL 18上のテスト、Ruff、Django check、直接HTTPS／Cloudflare Tunnel Compose、暗号化バックアップと空環境復元を含む`test`・`production-container`が全成功した。

2026-10-05、VM200のCloudflare Tunnel本番構成へ反映した。更新前バックアップ`acervo-20261004T133905Z-c3a85e5c1fde`（PostgreSQL 18）を作成し、保持規則により古い1世代を削除した。VM200を`594114c`から`f517f15`へfast-forwardし、Cloudflare用Compose設定検証、webイメージの再ビルド、`up -d --build --wait`を成功させた。`audit.0004_specimen_csv_export_action`まで適用済みで、`db`、`web`、`proxy`、`tunnel`はhealthy、`check --deploy`は警告なし、webのUIDは10001、作業ツリーは空だった。実ブラウザでのPDF印刷・CSVダウンロード受入は未実施であり、7C-LIVE-Bへ残す。Phase 7の実装・PostgreSQL CI・本番Compose反映は完了とする。7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了のままとする。

## 2026-10-03 Phase 1D 残件のローカル実装

学校回生方式の管理画面に、現在在籍中の有効adminが0人のときの強い警告を追加した。年度切替日の60日前からは、次年度にも在籍する有効adminがいない場合に後継管理者の設定と引き継ぎを促す。`none`方式ではこれらの学校回生向け警告を表示しない。警告は`/management/`と`/management/users/`で、既存の中央管理アクセス判定を通過した管理者にだけ表示する。

`/management/audit-logs/`に最小AuditLog閲覧画面を追加した。管理者MFAゲートと`no-store`を適用し、直近100件を新しい順で表示する。日時、操作種別、実行者、対象、経路だけを表示し、一時パスワード、認証コード、MFA秘密などの秘密値を扱わない。利用者作成、role変更、有効状態変更、一時パスワード再発行、MFAリセットの既存記録を閲覧できる。

変更ファイルは`management_portal/admin_warnings.py`、`management_portal/views.py`、`management_portal/urls.py`、`management_portal/templates/management_portal/index.html`、`management_portal/templates/management_portal/user_list.html`、`management_portal/templates/management_portal/audit_log_list.html`、`management_portal/tests/test_admin_warnings.py`、`management_portal/tests/test_user_administration_ui.py`、`accounts/tests/test_user_administration_concurrency.py`、および先行して未コミットだったPhase 1D利用者管理一式である。

ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が290件成功（PostgreSQL専用1件skip）、Ruff lint・format、Django check、migration差分確認、`git diff --check`も成功した。GitHub Actionsではコミット`57b7890`に対する`test (push)`が50秒、`production-container (push)`が4分でいずれも成功した。前者はCIのPostgreSQL 18上でテストを実行するため、同時降格テストを含むPostgreSQL検証の成功根拠とする。後者はproduction Compose検証を含む。実ブラウザ受入は未実施である。したがってPhase 1D、7C-LIVE-A、7C-LIVE-B、Phase 1全体はいずれも未完了とする。次は本番相当の管理画面を実ブラウザで受入し、結果を追記する。

同日、VM200のCloudflare Tunnel本番構成で実ブラウザ受入を実施した。更新前に暗号化バックアップ`acervo-20261003T081532Z-8cfd9867a26e`（PostgreSQL 18）を作成し、保持整理では削除0件だった。作業ツリーが空であることを確認してコミット`36e9a19`から`afbd3ad`へfast-forwardし、Cloudflare用Compose設定検証、webイメージのbuild、`up -d --wait`を成功させた。`db`、`web`、`proxy`、`tunnel`はhealthy、コンテナ内`check --deploy`は警告なし、webのUIDは10001だった。

通常PCの実HTTPSブラウザで、既存の管理者アカウントによるMFA後の`/management/`表示、利用者管理一覧、監査ログ一覧、ログアウト後の`/management/`直接アクセスのログイン画面へのredirectを確認した。監査ログは空状態を正しく表示し、パスワード、認証コード、MFA秘密を表示しない案内を確認した。実利用者の作成・変更・一時パスワード再発行は行っていない。学校回生警告の実表示は、現在の本番データの状態を変更せず、単体テストで確認済みである。

VM200への保守アクセス確認中にSSHを一時起動したが、認証情報を使わずにゲストエージェント経由で作業を継続し、SSHは停止・自動起動無効の元状態へ復帰した。ProxmoxホストのSSHも同様に一時起動後、停止・自動起動無効へ復帰済みである。ディスク、DB、写真データの削除や初期化は行っていない。Phase 1Dの実装・自動テスト・PostgreSQL CI・production Compose・実ブラウザ受入は完了したが、7C-LIVE-A、7C-LIVE-B、Phase 1全体は未完了とする。

## 2026-10-03 Phase 2 標本データ中核の初期実装

設計責任者の承認後、`specimens`アプリを追加した。`SpecimenSequence`、`Specimen`、`Taxon`、`TaxonSource`、`StorageLocation`、`SpecimenEvent`、`SpecimenPhoto`の初回migrationを作成した。標本番号は環境変数`ACERVO_SPECIMEN_CODE_PREFIX`と6桁以上の連番から生成し、本番では接頭辞の未設定を起動時に拒否する。既存のUser・認証・DBデータを変更するmigrationは含めない。

サービス層では、行ロックと単一トランザクションにより標本作成時だけ番号を確定し、標本と初回履歴を同時に保存する。標本番号と詳細用UUIDv4はモデル上で変更不可とし、番号の再利用を防ぐ。貸出、返却、売却、廃棄、紛失、発見は状態と追記型の`SpecimenEvent`を同じトランザクションで変更し、不正な遷移と不正イベント種別を拒否する。未同定・採集日不明は許容する。

`specimens/tests/`に通常作成、未同定、採番失敗時のロールバック、UUIDv4、番号不再利用、イベント追記専用、不正状態遷移、不正入力、SQLiteのDB制約、PostgreSQL専用の同時採番テストを追加した。ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が303件成功（PostgreSQL専用2件skip）、Ruff lint・format、Django check、migration差分確認、`git diff --check`も成功した。

コミット`cf8cf72`に対するGitHub Actionsでは、PostgreSQL 18上の`test (push)`が53秒、`production-container (push)`が4分でいずれも成功した。同時採番テストを含むPostgreSQL検証と、本番コンテナ検証の成功を確認した。

同日、VM200のCloudflare Tunnel本番構成へ反映した。更新前に暗号化バックアップ`acervo-20261003T084353Z-1472371ecd81`（PostgreSQL 18）を作成し、保持整理では直前の1件を削除した。標本番号接頭辞は、既に確定していた`KDF-BIO`を`.env.production`へ値を表示せず1件だけ設定した。作業ツリーが空であることを確認して`afbd3ad`から`cf8cf72`へfast-forwardし、Cloudflare用Compose設定検証、webイメージのbuild、`up -d --build --wait`を成功させた。`db`、`web`、`proxy`、`tunnel`はhealthy、コンテナ内`check --deploy`は警告なし、`specimens.0001_initial`は適用済み、VM200上の作業ツリーは空だった。実データの標本は作成していない。Phase 2の中核ルールは、ローカル・PostgreSQL CI・本番Composeで確認済みとして完了とする。QR、登録画面、標本詳細、写真は未実装であり、7C-LIVE-B、7C-LIVE-A、Phase 1全体は引き続き未完了とする。次はPhase 3のQR基盤を実装する。

## 2026-10-03 Phase 3 QR基盤のローカル実装

設計責任者の承認後、`QRBatch`と`QRLabel`を追加した。`QRLabel`は暗号学的乱数で生成するUUIDv4 token、`unused`・`assigned`・`retired`の状態、標本への任意の1対1関連、再印刷回数・時刻を持つ。DBの一意制約、状態と標本関連のcheck制約、サービス層のトランザクションと行ロックにより、1枚のQRの二重割当を防ぐ。tokenは作成後変更できず、無効化後も既存の標本への割当履歴を保持する。QR発行自体は標本番号を消費しない。

`create_qr_batch`、`assign_qr_label`、`retire_qr_label`、`record_qr_reprint`を追加した。公開基底URLから`/q/<uuidv4>/`を生成し、`/q/<uuidv4>/`では未ログイン時に状態を明かさずログインへ戻す。現在在籍のmemberまたはadminだけがQRの次の操作へ進め、卒業生など権限のない利用者と不正UUIDには同じ404を返す。割当済み・無効QRから標本番号・同定情報などの標本内容は返さない。未使用QRの登録画面、割当済みQRの標本詳細画面は後続Phase 4・5で追加する。

20mmラベルと15mm試験ラベルのPDF生成を追加した。QR画像のみを正方形の1ページへ描き、標本番号・標本名・採集地をPDFへ含めない。PDF生成にはPython 3.13対応、BSDライセンスの`reportlab==5.0.1`を固定依存へ追加し、既存の`qrcode==8.2`も直接依存として固定した。

通常発行、UUIDの一意性・不変性、無効・不正入力、1標本へ複数QRの割当拒否、再印刷、PDFの形式・秘密値非記録、未ログイン、権限不足、不正UUID、割当済み・無効QRの情報非表示をテストした。PostgreSQL専用の同時割当テストも追加した。ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が315件成功（PostgreSQL専用3件skip）、Ruff lint・format、Django check、migration差分確認、`git diff --check`も成功した。コミット`378a51f`に対するGitHub Actionsでは、PostgreSQL 18上の`test (push)`が1分、`production-container (push)`が4分でいずれも成功した。

同日、VM200のCloudflare Tunnel本番構成へ反映した。更新前バックアップ`acervo-20261003T090608Z-43e4e0654a15`（PostgreSQL 18）を作成し、保持整理では直前の1件を削除した。更新前に設定ファイルのグループ読取権限が不足してバックアップが一度失敗したが、内容を表示せず、所有者root・バックアップコンテナのGID 10001・mode 640へ復旧した後のバックアップ作成は成功した。`cf8cf72`から`378a51f`へfast-forwardし、Cloudflare用Compose設定検証、webイメージbuild、`up -d --build --wait`を成功させた。`db`、`web`、`proxy`、`tunnel`はhealthy、`check --deploy`は警告なし、`specimens.0002_qrbatch_qrlabel_and_more`は適用済み、VM200上の作業ツリーは空だった。実データの標本・QRラベル、実HTTPSのQR読取、実印刷は未実施である。Phase 3の実装・PostgreSQL CI・本番Compose反映は完了とする。7C-LIVE-A、7C-LIVE-B、Phase 1全体は引き続き未完了とする。次はPhase 4のスマホ標本登録を実装する。

## 2026-09-30 7C-LIVE-A復元試験の続き

VM201で`acervo-restore`専用Compose projectのPostgreSQL 18.6を起動した。`up -d --wait db`は終了コード0で`acervo-restore-db-1`がhealthy、`docker ps`にはこの1コンテナだけが表示され、ホスト公開ポートはなかった。`5432/tcp`はコンテナ内ポートである。`docker volume ls`には`acervo-restore_postgres_data`だけがあり、写真ボリュームはまだなかった。PostgreSQLのpublic schemaの表数は`0`。`docker compose build restore`は終了コード0で成功した。

復元設定の空出力先を作成し、`allowed_signers`が空でないことを確認した。運用者は前回復号に成功した修正済みage復元鍵を、主ホストの非表示入力からVM201の一時ファイルへ渡した。鍵値はチャット・コマンド本文・出力へ表示していない。一時ファイルをコンテナUID10001所有・mode0400とし、`age-keygen -y`の出力を破棄して鍵形式を確認した。復元設定の出力先は空で、復元前のDockerボリュームは新規DB用1件だけだった。

`acervo-20260929T090008Z-7454c88b9a7b`をVM201の`acervo-restore` projectへ復元し、`restore_completed`と終了コード0を確認した。復元処理のコード上、署名付きmetadataと暗号化payloadのSHA-256を独立した`allowed_signers`で検証し、チェックサム、PostgreSQL major、空DB・空写真領域の判定を通過した後に復号・DB復元・写真展開・設定の別ディレクトリへのコピーを行う。個別の`signature=valid`行は今回の出力にはなかったため、署名検証の成功はこの制御フローと`restore_completed`から判断した。既存の`.env.production`は上書きしていない。復元した利用者数、ログイン・管理者MFA、再起動後の永続化はまだ未確認。一時age秘密鍵は削除手順を案内したが、完了結果は未確認。

運用者がVM201上の一時age秘密鍵ファイルを削除し、終了コード0を確認した。復元DBの`accounts_user`は1件。復元出力の`.env.production`とVM201で現在使っている`.env.production`の`cmp -s`は終了コード1で一致しなかった。差分の設定項目名だけを確認するまで、VM201のWebは起動しない。設定値は表示していない。ログイン・管理者MFA・永続化は未確認。

設定ファイルの差分を値を表示しないスクリプトで調べた。異なる項目名は`ACERVO_BACKUP_AGE_RECIPIENTS`、`ACERVO_DOMAIN`、`ACERVO_MFA_FERNET_KEYS`、`ACERVO_ORGANIZATION_NAME`、`ACERVO_PUBLIC_BASE_URL`、`ACERVO_SITE_NAME`、`CADDY_EMAIL`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`DJANGO_SECRET_KEY`、`POSTGRES_PASSWORD`。復元DBはVM201の現在のDBパスワードで初期化済みのため、認証受入では元のVM201設定を保存したうえで、復元した`DJANGO_SECRET_KEY`と`ACERVO_MFA_FERNET_KEYS`だけをVM201のWebへ一時適用する方針とした。元の設定へ戻せるまで、本番用の公開経路やTunnelは起動しない。値は表示していない。

VM201の既存`.env.production`は`root:root`・mode `600`。`acervo-restore` projectのWebイメージをビルドし、終了コード0で成功した。Webコンテナはまだ起動していない。元設定を退避する手順の結果を確認してから、一時設定と認証受入へ進む。

運用者はVM201の退避先にファイルがないことを確認したうえで、元の`.env.production`を`/root/acervo-vm201-env-before-acceptance`へ属性を保ってコピーした。コピーは終了コード0、退避ファイルは`root:root`・mode `600`。元設定の値は表示していない。復元した認証用鍵2項目の一時適用は結果待ち。

復元した`DJANGO_SECRET_KEY`と`ACERVO_MFA_FERNET_KEYS`の行だけを、VM201の試験用`.env.production`へ一時適用した。スクリプトは適用前に元ファイルと退避コピーのバイト一致、双方で対象項目が各1件であることを検査し、`ACCEPTANCE_ENV_READY`と終了コード0を返した。適用後に変更が2項目だけであること、ファイル権限、Compose設定は確認待ち。値は表示していない。

適用後の検証は`TWO_KEYS_ONLY_OK`と終了コード0で成功した。退避コピーとの変更行が認証用鍵2項目だけで、両項目が復元出力と一致することを値を表示せず確認した。その後、権限確認とCompose設定確認を行うコマンドが番号付きで同じ行に貼り付けられ、QEMU guest agentのタイムアウトになった。以後の`qm guest exec 201 -- true`と`qm agent 201 ping`は`QEMU guest agent is not running`で失敗した。一方、`qm status 201`は`running`、VM201のIPへのpingは2回とも成功した。VMは稼働しているがゲストエージェントが応答しない状態であり、原因は未確定。VM201コンソールからサービス状態の確認・再起動を案内する。適用後のファイル権限・Compose設定、Web起動、復元後ログイン・管理者MFA・永続化は未確認で、7C-LIVE-Aは未完了。

VM201コンソールの画面で`systemctl show qemu-guest-agent -p ActiveState -p SubState -p Result`の結果は`Result=success`、`ActiveState=active`、`SubState=running`だった。これはゲスト内サービスの稼働を示すが、主ホストからの通信回復はまだ確認していない。サービス再起動後に`qm agent 201 ping`で確認する。

VM201コンソールでのゲストエージェント再起動を案内した後、主ホストの`qm agent 201 ping`はエラーなく戻り、`qm guest exec 201 -- true`は終了コード0だった。再起動コマンド自体の結果は未受領だが、ゲストエージェント経由の操作は再開できる。直前のタイムアウト原因は未特定。認証用鍵2項目の一時適用後のファイル権限とCompose設定を次に確認する。

VM201の一時適用後`.env.production`は`root:root`・mode `600`を保持し、`acervo-restore` projectのCompose `config --quiet`は終了コード0だった。設定値は表示していない。Web起動と復元先の認証・MFA受入は未実施。

隔離した`acervo-restore` projectで`docker compose up -d --wait --no-recreate web`は終了コード0で成功した。既存DBは`Running`から`Healthy`、新規Webは`Started`から`Healthy`となり、試験用frontend networkとstatic volumeが作成された。proxyとTunnelは起動していない。`check --deploy`、公開ポート、復元後ログイン・管理者MFA・永続化はこれから確認する。

VM201のWebで`python manage.py check --deploy`は問題0件・終了コード0。`docker ps`には`acervo-restore-web-1`と`acervo-restore-db-1`の2件のみで、どちらもhealthy。表示はコンテナ内部の`8000/tcp`と`5432/tcp`だけで、ホストへのポート公開はなかった。復元後の管理者・MFA登録の件数、実ログイン、再起動後の永続化は未確認。

VM201の復元DBではadmin roleの利用者が1件、同roleのTOTP認証器が0件だった。これは復元時点のTOTP登録が存在しないことを示すが、他方式の認証器の有無は未確認。認証器の種類と管理者の状態を秘密値抜きで調べてから、復元先MFAの受入方法を決める。ログイン、MFA、永続化は未確認。

復元DBのadmin role利用者に紐づく認証器の種類は空リスト`[]`で、利用者は`is_active=True`・`must_change_password=True`だった。したがって2026-09-29 09:00 UTCのバックアップは、管理者の初回パスワード変更とMFA登録より前の状態を含んでおり、現在の管理者のパスワード・MFAによるログイン受入には使えない。VM200の現状態と2026-09-30の新しいバックアップの有無を確認する。VM201の現復元データは上書きせず維持している。

VM200の現DBではadmin role利用者は`is_active=True`・`must_change_password=False`で、認証器の種類は`totp`、`recovery_codes`、`webauthn`だった。VM200のバックアップ保存先には新しい`acervo-20260930T090018Z-3d7c28eabc85`が存在する。これが別ホストで保存確定・整合していることは未確認。旧VM201試験環境のDB・写真ボリュームは上書きせず、新しいバックアップは別の空Compose projectで受け入れる方針とする。

主ホストから別ホスト`192.168.11.202`へのSSHはポート22の接続タイムアウトだった。運用者は別ホストが現在電源オフと確認し、Wake-on-LANによる起動を提案した。別ホストの新バックアップの現地チェックサムは未確認。主ホストの既存起動unitを調べてからWake-on-LANを行う。

主ホストのtimer一覧には`acervo-backup-wake.timer`（毎日17:55 JST、当日17:55実行済み）と`acervo-backup-wol.timer`（毎日02:15 JST）が存在した。前者に対応する既存の`acervo-backup-wake.service`を手動起動し、別ホストの応答を確認する。

運用者が主ホストで`systemctl start acervo-backup-wake.service`を実行し、`Result=success`・`ExecMainStatus=0`を確認した。サービス成功は起動信号の送信までを示し、別ホストの起動を証明しない。45秒後の`192.168.11.202`へのpingは2回とも応答なし。サービスの実行内容と遅延起動の可能性を確認する。最初の`systemctl show`は行が途中で分割されて失敗したが、1行で再実行して正常結果を得た。

その後、運用者は保存用LXC110の`root@acervo-backup`コンソールでネットワーク設定を表示し、LXCの`eth0`に`192.168.11.22/24`が設定されていることを確認した。これはLXCへコンソールで到達できることを示すが、主ホストからの別物理ホスト`192.168.11.202`への疎通はまだ再確認していない。LXC内で新バックアップのチェックサムを直接確認する。

主ホストの`acervo-backup-wake.service`は、別ホスト用にLANブロードキャストのUDP 9へWake-on-LANを送る設定だった。送信先MACは運用識別情報として公開Statusに記載しない。設定確認後の`192.168.11.202`へのpingも2回とも応答なし。起動・疎通の原因は未確定。

保存用LXC110のコンソールで`acervo-20260930T090018Z-3d7c28eabc85`の`sha256sum -c checksums.sha256`を実行し、暗号化payloadとmetadataがともに`OK`だった。別ホストへの保存物のファイル整合性を確認したが、署名検証とVM201での復元は未実施。主ホストからLXCのIP`192.168.11.22`への直接通信を確認し、現時点で応答のない物理ホストIPを経由せず暗号化ファイルを取得できるか調べる。

主ホストから別物理ホストの`192.168.11.202`へのpingは引き続き応答なしだったが、保存用LXC110の`192.168.11.22`には2回とも応答した。LXCへの直接SSHで暗号化済みバックアップを取得できるか、公開ホスト鍵とSSH認証設定を確認する。

LXC110の`ssh`は`active`だが、実効設定は`permitrootlogin no`・`passwordauthentication no`だった。LXCのEd25519ホスト公開鍵指紋は確認したが、主ホストと照合・登録はしていない。root SSHを有効化せず、LXC側で検証済みのバックアップとVM200上の同backup IDがバイト一致することを確認したうえで、暗号化済み成果物をVM200から主ホストのメモリ経由でVM201へ転送する方法を検討する。これにより今回の新バックアップの物理的な取得経路はVM200となるため、別ホストからの実ファイル取得は未確認事項として明記する。

LXC110とVM200の`acervo-20260930T090018Z-3d7c28eabc85`で`checksums.sha256`自体のSHA-256が一致した。VM200側でも`sha256sum -c checksums.sha256`が暗号化payloadとmetadataの両方で`OK`、LXC側も既に両方`OK`だった。同一の署名付き暗号化成果物がVM200と別ホストに存在することをバイトレベルのハッシュで確認した。別ホストからの実ファイル取得は今回まだできていないため、新バックアップのVM201への搬入はVM200から行い、この経路差を受入記録に残す。

VM201の`/srv/acervo-backups/acervo-20260930T090018Z-3d7c28eabc85`が存在しないことを終了コード0で確認した。旧バックアップの保存ディレクトリや復元用DB・写真ボリュームは維持している。新バックアップの転送はこれから行う。

主ホスト上のPythonプロセスでVM200の暗号化済みバックアップディレクトリをtar化してQEMU guest agentの標準出力から受け取り、主ホストのメモリからVM201のguest agent標準入力へ渡して展開した。`ENCRYPTED_BACKUP_TRANSFER_OK`を確認し、主ホストのディスクにコピーを残していない。VM201側ファイルの件数・チェックサムはこれから確認する。別ホストの保存物とは前段でハッシュ一致を確認済みだが、転送元はVM200だった。

VM201上の新バックアップで`sha256sum -c checksums.sha256`は暗号化payloadとmetadataの両方が`OK`、終了コード0だった。旧`acervo-restore` projectのデータは削除せず、コンテナを停止して、新しい空のCompose projectで復元受入を続ける。署名検証・復号・新DB復元は未実施。

VM201上の新バックアップを復元コンテナUID/GID10001の所有に変更した。旧`acervo-restore` projectのWebとDBは停止し、既存のDB・写真・静的資産の3ボリュームは維持されている。新しい`/srv/acervo-restored-settings-20260930`を未存在確認後にUID/GID10001・mode0700で作成した。Dockerボリューム一覧に新project用のものはなく、新しいDB・写真領域はまだ作成していない。

新しい`acervo-acceptance` projectでPostgreSQL 18.6のDBコンテナを作成し、`up -d --wait db`は終了コード0・`Healthy`だった。DBのpublic schemaのテーブル数は復元前に`0`、終了コード0。次に署名検証用公開鍵、復元設定の空出力先、復号鍵の一時入力を確認して復元する。

VM201の署名検証用`allowed_signers`は空でなく、`/srv/acervo-restored-settings-20260930`は空だった。Dockerボリュームは新projectのPostgreSQL用1件と旧projectの3件だけで、新projectの写真ボリュームは未作成。`acervo-acceptance`用のrestoreイメージは終了コード0でビルドできた。復号鍵はまだ配置しておらず、新バックアップの署名検証・復元は未実施。

復元鍵用の一時ファイルが既に存在したため、未存在確認は終了コード1だった。それにもかかわらず、運用者は非表示入力で当該ファイルを更新した。鍵値は表示されず、UID/GID10001・mode0400への設定と`age-keygen -y`による形式検査は`IDENTITY_FORMAT_OK`・終了コード0で成功した。既存ファイルの由来は未確認だが、今回の入力で上書きされた。新バックアップの署名検証・復元と、直後の一時鍵削除は未実施。

運用者が一時鍵を先に削除してから復元コマンドを実行したため、復元は終了コード1・`restore_target_unavailable`で停止した。復元処理はidentity file、写真領域、設定出力先のいずれかが利用できない場合に、署名検証や復号より前でこのエラーを返す。今回はidentity fileを削除したことが原因である。失敗時に新projectの`media_data`ボリュームは作成されたが、DB・写真・設定の復元は実施されていない。復元先DB、写真ボリューム、設定出力先が空であることを再確認してから、鍵を再入力し、復元完了後に必ず削除する単一手順を案内する。

再確認では新projectのDBの表数は`0`、写真ボリュームは`MEDIA_EMPTY`だった。一方、鍵パス不存在と設定出力先空をまとめた検査は終了コード1だった。前回、存在しない鍵パスをDocker bind mountへ渡したため、Dockerが同パスに空ディレクトリを作成した可能性がある。対象のファイル種別と設定出力先を個別に調べてから、明示した空ディレクトリだけを削除して復元鍵を配置する。

鍵パス`/root/acervo-acceptance-identity-20260930.txt`はmode0755の空ディレクトリ、設定出力先は`SETTINGS_EMPTY`だった。Dockerがbind mountのために作成した空ディレクトリと判断できる。DBと写真ボリュームも空であることを確認済み。この空ディレクトリのみを`rmdir`で削除して、同じパスへ一時鍵ファイルを再配置する。

確認済みの空ディレクトリを`rmdir`で削除し、同パスが存在しないことを終了コード0で確認した。復元鍵の再入力、復元、鍵削除を順に連続実行する。

運用者は非表示入力でage復元鍵を一時ファイルへ渡し、UID/GID10001・mode0400を設定した。`acervo-acceptance` projectへの復元は`restore_completed backup_id=acervo-20260930T090018Z-3d7c28eabc85 postgres_major=18`・終了コード0で成功した。復元処理により、独立保管の`allowed_signers`を使う署名検証、チェックサム照合、PostgreSQL majorと空DB・空写真領域の確認、復号、DB・写真・設定の復元が完了した。一時age鍵は直後に削除し、終了コード0だった。復元先のログイン、管理者MFA、再起動後のDB・写真永続化は未確認。

復元設定の`DJANGO_SECRET_KEY`と`ACERVO_MFA_FERNET_KEYS`だけをVM201試験用`.env.production`へ一時適用し、`ACCEPTANCE_20260930_ENV_READY`・終了コード0を確認した。元のVM201設定は`/root/acervo-vm201-env-before-acceptance`へroot専用で退避済み。変更項目が2件だけであること、ファイル権限、Compose設定、Web起動、認証受入は未確認。

退避元との違いが`DJANGO_SECRET_KEY`と`ACERVO_MFA_FERNET_KEYS`の2項目だけであり、各値が9月30日復元設定と一致することを`TWO_KEYS_ONLY_OK`で確認した。`acervo-acceptance` projectのCompose `config --quiet`は終了コード0だった。Web起動、復元DBの管理者・MFA状態、ログイン、管理者MFA、永続化は未確認。

`acervo-acceptance` projectでWebイメージをビルドし、`up -d --wait --no-recreate web`は終了コード0で成功した。DBはhealthyを維持し、Webもhealthyになった。proxyとTunnelは起動していない。`check --deploy`、ホスト公開ポート、復元DBの管理者・MFA状態、ログイン、管理者MFA、永続化は未確認。

復元後Webで`python manage.py check --deploy`は問題0件・終了コード0。稼働中コンテナは`acervo-acceptance-web-1`と`acervo-acceptance-db-1`の2件のみで双方healthy、表示された`8000/tcp`と`5432/tcp`はコンテナ内部ポートでホストへの公開はない。復元DBのadmin role利用者は`is_active=True`・`must_change_password=False`で、認証器の種類は`recovery_codes`、`totp`、`webauthn`だった。認証用Fernet鍵で実際のTOTP記録を復号できるか、ログイン・MFA・管理画面への到達、再起動後の永続化は未確認。

復元DBのTOTP認証器を設定済みFernet鍵で復号できることを、秘密値を出さない`TOTP_DECRYPT_OK`・終了コード0で確認した。管理者の現在のパスワードと本人の認証アプリのコードを非表示入力で渡し、未ログイン拒否・パスワードログイン・TOTP認証・管理トップ到達・ログアウト後拒否をアプリの実ビューで確認する準備ができた。実行結果は未確認。

非表示入力による実ログイン試験は終了コード1・ラベルなしの`AssertionError`で中断した。コード上、最初のラベルなしassertは標準入力が2行であること、次が認証コードが6桁の数字であることの検査である。`PASSWORD_MISMATCH`以降の認証判定へ到達した証拠はなく、パスワードやMFAの成否は未確認。秘密値は出力されていない。まず非機密の2行で主ホストからVM201 Webへの標準入力転送を確認する。

主ホスト`pve`から`qm guest exec 201 --pass-stdin`を介してVM201のWebコンテナへ非機密の2行を渡す試験は、`out-data`が`2 [5, 6]`、`exitcode`が`0`で成功した。先の`AssertionError`は転送経路そのものの恒常的な不具合を示すものではない。実ログイン・TOTP・管理画面・ログアウト後拒否、再起動後のDBと写真ボリューム永続化は引き続き未確認。

非表示入力した管理者パスワードと認証アプリの6桁コードを用いるVM201のDjangoビュー試験では、`PASSWORD_CHECK_OK`、`BEFORE_LOGIN_DENIED`、`PASSWORD_LOGIN_STAGE_OK`まで確認した。TOTP送信後は`TOTP_STAGE_FAILED`・終了コード1。失敗ラベルはHTTP statusとredirect先をまとめて判定したもので、コードの期限切れ、入力違い、想定と異なる画面遷移のいずれかは未特定。管理画面到達とログアウト後拒否は未確認。秘密値は出力されていない。入力用シェル変数の削除も貼付ログが乱れており完了確認が必要。

運用者が主ホストで`unset`を実行し、両入力変数の不存在を`INPUT_VARIABLES_CLEARED`で確認した。新たに非表示入力したパスワードとTOTPコードで、VM201のDjangoビューによるログイン試験は終了コード0だった。`LOGIN 302 /accounts/mfa/authenticate/`、`MFA 302 /management/`、`MANAGEMENT 200`、`AFTER_LOGOUT 302 /accounts/login/`を確認した。これにより復元DBでのパスワード照合、TOTP通過、管理トップ到達、ログアウト後の拒否を確認した。PythonのDjangoテストクライアントによる内部ビュー試験であり、VM201からの実ブラウザ・公開HTTPS経路やCSRF送信の受入とは区別する。実行したシェル手順末尾で入力変数の`unset`を指定したが、変数不存在の独立確認は未実施。再起動後のDBと写真ボリューム永続化は未確認。

再起動前のVM201で、復元DBの有効・初回変更済みadmin role利用者1件と紐づく認証器3件を確認した。写真用`/app/media`ボリュームへ固定文言の試験用マーカー`.vm201-persistence-probe-20260930`を排他的に作成し、`DB_BASELINE_OK MEDIA_MARKER_CREATED`・終了コード0を確認した。マーカーは再起動後の永続化確認後に削除する。既存写真の表示は標本・写真機能未実装のため対象外。

運用者が主ホストで`qm reboot 201`を実行し、エラーなくプロンプトへ戻った。再起動後、`qm agent 201 ping`はエラーなし。VM201の`docker ps`では`acervo-acceptance-web-1`と`acervo-acceptance-db-1`がともにhealthyで、表示された`8000/tcp`と`5432/tcp`はコンテナ内部ポートのみ。DB状態と写真マーカーの再照合はこれから行う。

再起動後のVM201で、有効・初回パスワード変更済みadmin role利用者1件と紐づく認証器3件が維持され、写真用ボリュームの試験マーカー内容も一致した。`DB_PERSISTED MEDIA_VOLUME_PERSISTED`・終了コード0を確認した。これはDBと写真用ボリュームの再起動後永続化の受入であり、標本写真の表示・認可確認を意味しない。試験マーカーの削除、試験用コンテナ停止、元`.env.production`への復帰はこれから行う。

写真用ボリュームの試験マーカーは、内容一致と通常ファイル・非symlinkを確認してから削除し、`MEDIA_MARKER_REMOVED`・終了コード0だった。`acervo-acceptance`のWebとDBを`docker compose stop web db`で停止し、両コンテナの`Stopped`・終了コード0を確認した。DB・写真ボリュームは保持している。元`.env.production`への復帰は未実施。

停止後、現行`.env.production`とroot専用退避ファイルの所有者・mode0600・認証用鍵2項目以外の全行一致を検査したうえで、退避内容を一時ファイル経由で原子的に戻した。`ORIGINAL_ENV_RESTORED`・終了コード0。復帰後の独立したバイト一致確認とCompose設定検証はこれから行う。復元設定の別ディレクトリと退避コピーはまだ残っている。

元設定への復帰後、現行`.env.production`と退避ファイルの`cmp -s`によるバイト一致、現行ファイルのroot所有・mode0600、`acervo-acceptance`のCompose`config --quiet`を確認し、`RESTORED_ENV_VERIFIED`・終了コード0だった。試験用WebとDBは停止済みで、DB・写真ボリュームは保持している。復元設定出力の別ディレクトリと元設定の退避コピーは、不要な平文コピーとして整理する前に内容の種類を確認する。

復元設定の出力先`/srv/acervo-restored-settings-20260930`には通常ファイル`.env.production`だけがあると確認し、そのファイルと空になったディレクトリを削除した。`RESTORED_SETTINGS_COPY_REMOVED`・終了コード0。元設定の退避コピーは、現行`.env.production`とのバイト一致、現行ファイルのroot所有・mode0600を再確認したうえで削除し、`SAVED_ENV_COPY_REMOVED`・終了コード0だった。暗号化バックアップと復元済みDB・写真ボリュームは削除していない。最終的なコンテナ停止・一時鍵不存在・ボリューム保持は独立確認待ち。

最終確認は`VM201_ACCEPTANCE_CLEANUP_VERIFIED`・終了コード0で成功した。現行`.env.production`がroot所有・mode0600で残り、元設定の退避コピー、一時age復号鍵、2026-09-30復元設定の平文出力先はいずれも存在しない。VM201で稼働中のDockerコンテナはなく、暗号化バックアップと`acervo-acceptance`のPostgreSQL・写真用ボリュームは残っている。旧`acervo-restore` projectの停止済みデータも保持している。今回の写真用ボリューム確認は試験マーカーによるもので、マーカーは削除済み。標本モデル、QR、標本詳細、保護写真は未実装で、その復元後表示・認可は7C-LIVE-Bへ残す。VM201の実ブラウザ／HTTPS経路でのログイン・MFAは未確認。別ホストからVM201へ直接バックアップを取得した受入も未実施で、搬入元はハッシュ一致を確認したVM200だった。7C-LIVE-A、7C-LIVE-B、Phase 1全体は完了扱いにしない。

直接の別ホスト取得経路を調べるため、主ホスト`pve`から保存用LXC110の`192.168.11.22`へpingを2回ずつ2度実行し、いずれも2送信・2受信・損失0%だった。これはIP疎通の確認だけで、SSH認証、ファイル取得、復元経路の成立はまだ示さない。VM200・VM201・保存済みデータは変更していない。

保存用LXC110で実行する予定の権限確認`stat`が、誤って主ホスト`root@pve:~#`で実行され、対象パス不存在で失敗した。読み取り専用の確認で、主ホストやLXCのファイルは変更していない。LXC110のコンソールへ切り替えてから再実行する。

LXC110の`root@acervo-backup:~#`で同じ権限確認を実行した。`incoming`は`acervo-ingest:acervo-sftp`所有・mode0750、当該バックアップディレクトリは同所有・mode0770、暗号化payload・metadata・checksumsの3ファイルは同所有・mode0640だった。所有者・グループには読み取り権限があり、内容や秘密値は表示していない。2026-09-29には主ホストから`backup-pve`へ対話的SSHし、`pct exec 110`経由で旧バックアップをVM201へ搬入した記録がある。今回の新バックアップでも同経路が使えるか、主ホストから別物理ホストのSSH到達性を確認する。

主ホストで実行する予定のBatchMode・厳格ホスト鍵検証付きSSH確認が、誤って保存用LXC110の`root@acervo-backup:~#`で実行された。LXCには`192.168.11.202`のED25519ホスト鍵が未登録で、`Host key verification failed`・終了コード255で認証前に停止した。LXCの`known_hosts`は変更していない。主ホスト`pve`からのSSH到達性は未確認のまま。

主ホスト`root@pve:~#`で同じBatchMode・厳格ホスト鍵検証付きSSH確認を実行した。`Permission denied (publickey,password)`・終了コード255となり、ネットワーク接続と既存ホスト鍵の検証は通ったが、非対話認証はできなかった。2026-09-29に使った対話的SSHでLXC110の暗号化成果物を読み出せるか確認する。認証設定は変更していない。

主ホスト`pve`から別物理ホスト`backup-pve`へ厳格ホスト鍵検証付きの対話的SSHに成功し、その先の`pct exec 110`で新バックアップの暗号化payloadを読めることを`OFFSITE_READ_OK`で確認した。SSHパスワードは非表示入力で、チャット・コマンド引数に含めていない。ファイル内容は表示していない。次に保存先の3ファイルをVM201へストリームし、既存搬入物と一致するか照合する。

同じ対話的SSHと`pct exec 110`を使い、LXC110の`payload.tar.gz.age`、`metadata.json`、`checksums.sha256`をtarストリームで主ホストのディスクに保存せずVM201の標準入力へ渡した。VM201上の既存搬入物と各ファイルをバイト単位で照合し、3ファイルの集合も一致して`OFFSITE_READBACK_THREE_FILES_MATCH`・終了コード0だった。これは別ホストからVM201への直接読み出し経路と保存物の同一性を確認したもので、今回の復元処理に投入したファイルの元の搬入元がVM200だった事実は変わらない。DB、写真ボリューム、試験環境の設定は変更していない。

印刷したage鍵控えの照合を管理用Windows PCで開始した。修正済みデジタル控えのファイル存在だけを確認し、内容は表示していない。最初の`python -c`はPython本体が起動せず`Python`とだけ表示され、フルパスでのPython 3.13.14起動確認後の`-c`もPowerShellの引用符解釈で構文エラーとなった。どちらも非表示入力処理には到達せず、紙の鍵は入力していない。引用符の問題を避けるため、秘密値を含まない一時照合スクリプトを作成した。照合結果は未確認。

管理用PCの一時照合スクリプトで、紙に印刷されたage秘密鍵を非表示入力し、修正済みデジタル控えの鍵行と定数時間比較した。結果は`PRINTED_KEY_MISMATCH`。鍵の本文は表示・保存していない。この1回だけでは紙の誤記と入力ミスを区別できないため、紙の控えを復元可能な鍵として扱わず、非表示入力で再確認する。一時スクリプトは照合中のため残っている。

同じ紙の控えを再度非表示入力した結果、`PRINTED_KEY_MATCH`を確認した。少なくとも再入力された紙面の鍵行は、実バックアップ復号に成功した修正済みデジタル控えと一致する。初回不一致の原因は特定していない。鍵本文を表示・チャットへ貼付・ファイルへ保存せず、一時照合スクリプトは削除した。印刷物の保管状態や将来の四半期復元予定はこの照合では確認していない。

運用者に次回の四半期VM201復元試験予定を確認したところ、日付は未定との回答だった。今回の復元試験結果を定期実施の予定確定として扱わず、次回日付と担当者の決定を運用課題として残す。

## 2026-10-01 VM201実ブラウザー受入の省略と整理

運用者はVM201の実ブラウザ／HTTPS経路での認証受入を今回省略すると決定した。公開経路を作る準備として、Cloudflare上にVM201専用の`Acervo-vm201-restore-test` Tunnelを作成し、接続トークンをVM201の`/opt/acervo/.env.cloudflare`へroot所有・mode0600で一時配置した。トークン値はチャット、コマンド引数、VM201の出力へ表示していない。Compose設定検証は`VM201_TUNNEL_COMPOSE_CONFIG_OK`・終了コード0で成功した。公開hostnameのroute/DNSは設定しておらず、VM201のproxy、Tunnel、受入用コンテナは起動していないため、VM201は外部公開されていない。

省略決定後、運用者の明示承認によりCloudflare上の`Acervo-vm201-restore-test` Tunnelを削除した。CloudflareのTunnel一覧でVM200用`Acervo-vm200`だけが残ることを確認した。VM201の一時トークンファイルは所有者・mode・非symlinkを確認してから削除し、`VM201_TUNNEL_TOKEN_REMOVED`・終了コード0だった。さらに`VM201_BROWSER_ACCEPTANCE_NOT_CREATED`・終了コード0で、`.env.cloudflare`が残っていないこと、`acervo-browser-acceptance` projectのコンテナ・ボリュームが作成されていないことを確認した。既存の停止済み`acervo-acceptance`および`acervo-restore`のデータ、暗号化バックアップ、VM201の元`.env.production`には変更を加えていない。VM201の実ブラウザ／HTTPS経路での認証は未確認として残し、今回の省略を7C-LIVE-Aの完了根拠にはしない。

## 2026-10-01 Phase 1D 利用者管理の初期実装

運用者の次作業開始許可により、7C-LIVE-Aの未完了状態を変えずにPhase 1Dの最初の実装へ着手した。`accounts/user_administration.py`に、管理者による利用者の`role`と有効状態を変更するトランザクションサービスを追加した。操作対象と既存adminを行ロックし、更新後に有効adminが0人となる変更を拒否する。操作する管理者の有効状態、`role=admin`、初回パスワード変更済み、primary MFA登録も実行直前に再確認する。role変更と有効状態変更は、それぞれ秘密値を含まない追記専用`AuditLog`へ記録する。監査記録のaction追加には`audit` migration `0003_user_administration_actions`を加えた。

`/management/users/`の一覧と`/management/users/<id>/`の変更画面を追加した。中央の管理アクセスmiddlewareに加え、POST直前の再判定、TOTPまたはWebAuthnの直近MFA再認証、チェックボックス、対象ユーザー名の一致を要求する。role、有効状態、最後の有効admin保護、CSRF、memberの直接URL拒否、監査ログに秘密入力を出さないこと、監査書込み失敗時の更新ロールバックをテストで確認した。ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が276件すべて成功、Ruff lint・format、Django check、migration差分確認、`git diff --check`も成功した。PostgreSQL上の並行更新、production Compose、実ブラウザ受入は未実施である。ユーザー作成・パスワード再発行の監査、年度切替の後継警告、監査ログの閲覧画面などはPhase 1Dの残件であり、Phase 1D、7C-LIVE-A、7C-LIVE-B、Phase 1全体はいずれも未完了。

同日にPhase 1Dを続行し、`/management/users/new/`からの利用者作成と、`/management/users/<id>/password-reissue/`からの別利用者の一時パスワード再発行を追加した。いずれもPOST直前の管理アクセス再判定、TOTPまたはWebAuthnの直近MFA再認証、確認チェックを要求する。再発行では対象ユーザー名の一致を確認し、自分自身への再発行を拒否する。作成・再発行はトランザクション内で秘密値を含まない`AuditLog`を残す。監査書込みに失敗した場合は作成またはパスワード変更をロールバックする。一時パスワードは作成・再発行の直後の`no-store`応答でのみ表示し、監査ログ、メッセージ、DBの平文フィールドには保存しない。管理操作のうち利用者作成、role変更、有効状態変更、一時パスワード再発行を実装したが、年度切替の後継警告と監査ログ閲覧画面は未実装である。ローカルSQLiteでは`python manage.py test --settings=config.settings.test`が284件すべて成功、Ruff lint・format、Django check、migration差分確認、`git diff --check`も成功した。PostgreSQL上の並行更新、production Compose、実ブラウザ受入は未実施である。Phase 1D、7C-LIVE-A、7C-LIVE-B、Phase 1全体はいずれも未完了。

## 2026-09-29 7C-LIVE-Aの完了判定を訂正

前回、実ドメインで管理画面とログアウト後の拒否を確認した時点で7C-LIVE-Aを完了と記録した。しかし`docs/LIVE_PREFLIGHT.md`の7C-LIVE-A第5項には、署名付きバックアップを独立した空環境へ復元した後のログイン、管理者MFA、再起動後のDB・写真ボリューム永続化が含まれる。VM201で実施済みなのは利用者が0人だった時点の空データ復元と未認証画面の応答確認であり、ログイン・管理者MFAは実施できていない。したがって前回の完了判定を撤回し、7C-LIVE-AとPhase 1Dは未完了・未着手とする。既存の復元証跡は有効だが、現在の管理者を含む新しいバックアップで復元先認証を確認する必要がある。VM201の再使用は停止状態、対象ボリューム、鍵保管経路を確認してから行う。標本と写真の実データ受入は7C-LIVE-Bまで保留する。

運用者が主Proxmoxホストで`qm status 201`を実行し、VM201の停止を確認した。VM200の`/srv/acervo-backups`には9月27日、28日、29日のバックアップディレクトリがあり、最新候補は`acervo-20260929T090008Z-7454c88b9a7b`だった。別ホストのLXC110は`running`で、同backup IDの確定済みディレクトリにおける`sha256sum -c checksums.sha256`は`payload.tar.gz.age`と`metadata.json`の両方で`OK`だった。これは保存先のファイル整合性の確認であり、署名検証・復号・管理者データの有無・復元成功はまだ確認していない。VM201のコンテナ・ボリュームの現状確認を次に行う。

主ProxmoxホストでVM201を起動し、`qm status 201`は`running`だった。起動直後の`qm guest exec`はゲストエージェント未起動で失敗したが、再試行で応答した。VM201に`/opt/acervo/compose.production.yaml`と`/etc/acervo/backup-signing/allowed_signers`が存在し、Dockerコンテナとボリュームはそれぞれ0件だった。`/opt/acervo`のGit作業ツリーは`main...origin/main`で変更なし。`/srv/acervo-backups`は存在せず、最新バックアップはまだVM201へ搬入していない。復元操作、署名検証、ログイン、管理者MFA、再起動後の永続化は未実施である。

VM201の作業ツリーは当初`8a20529`で、`.env.production`の存在とLXC110（`192.168.11.22`）へのping成功を確認した。その後、運用者がVM201で`git merge --ff-only origin/main`を実行し、`8a20529`から`252824d`へfast-forwardした。`git log -1`でも`252824d`を確認した。コード更新後のCompose設定・イメージ・起動検証は未実施。暗号化バックアップのVM201への搬入方法を確認中である。

別ホストLXC110の`/srv/acervo-backup/sftp/incoming`は`acervo-ingest:acervo-sftp`の専用領域で、`ssh`は`active`。対象backup IDのディレクトリには`checksums.sha256`（165B）、`metadata.json`（1113B）、`payload.tar.gz.age`（9316B）の3ファイルがあり、所有者・グループに読み取り権限がある。`acervo-ingest`は通常シェルを持たない。運用者は前回の搬入方法を覚えていないため、主ホストと別ホスト間の既存SSH認証を確認して転送手順を選ぶ。ここまでバックアップの内容、鍵、`.env.production`の値は表示していない。

主Proxmoxホストから別Proxmoxホスト（`192.168.11.202`）への`BatchMode=yes`・厳格なホスト鍵検証付きSSHは、主ホストが相手のED25519ホスト鍵を未登録のため、認証前に`Host key verification failed`で停止した。接続・ファイル転送は成立していない。別ホストのコンソールとネットワーク経由で公開鍵指紋を照合してから信頼登録する。

別ホストのコンソールで表示したED25519ホスト公開鍵のSHA-256指紋と、主ホストから`ssh-keyscan`で取得した同アドレスの指紋は一致した。指紋そのものは秘密値ではないが、公開リポジトリには記載しない。SSH認証の可否とバックアップ搬入は続けて確認する。

指紋照合後、主ホストのroot用`known_hosts`に別ホストのED25519公開鍵を登録した。`BatchMode=yes`でのroot SSHは`Permission denied (publickey,password)`となり、無人用SSH認証は設定されていない。バックアップの転送や復元は未実施。運用者が対話的SSH認証を行えるか、秘密値を表示しない方法で確認する。

主ホストから別ホストへ、運用者がパスワードを画面で入力する対話的SSHは成功し、`hostname`が`backup-pve`を返した。パスワードはチャット・コマンド引数へ含めていない。LXC110からSSHとQEMUゲストエージェントのstdin経由で非機密文字列`transfer-ok`をVM201へ渡す試験も終了コード0で成功した。次に同じ経路で暗号化済みバックアップだけをVM201へ搬入し、転送後チェックサムを確認する。復号とDB復元は未実施。

VM201に`/srv/acervo-backups`を作成し、別ホストLXC110の確定済み`acervo-20260929T090008Z-7454c88b9a7b`を、主Proxmoxホストのディスクに保存せず、SSH・QEMUゲストエージェントのstdin経由でVM201へコピーした。VM201側の`tar`は終了コード0だった。転送後の3ファイル確認とチェックサム検証はこれから行う。暗号化payloadの内容・秘密値は表示していない。

VM201で対象ディレクトリ内の3ファイルがすべて通常ファイルとして存在し、`sha256sum -c checksums.sha256`は`payload.tar.gz.age`と`metadata.json`の両方で`OK`、終了コード0だった。これは転送後のファイル整合性までの結果であり、署名検証、復号、管理者データ、ログイン・MFA、永続化はまだ確認していない。

## 2026-09-28 7C-LIVE-Aの実機準備

設計責任者から、`docs/LIVE_PREFLIGHT.md`の責任者・バックアップ運用・受入端末はすべて確定・承認済みとの回答を受けた。具体的な担当・端末・秘密値は公開リポジトリへ記載しない。ローカル環境から主ProxmoxホストへのSSHはネットワーク制限を越えた試行でも認証拒否となり、Codexから直接実機操作はできなかった。運用者が`root@pve:~#`で`qm status 200`を実行し、VM200の`status: running`を確認した。`qm guest exec 200 -- systemctl show -p WorkingDirectory --value acervo-daily-backup.service`は終了コード0で空行を返したが、読み取り専用の検索で`/opt/acervo/compose.production.yaml`を確認した。VM200の`docker ps`には`tunnel`、`proxy`、`web`、`db`の4コンテナがあり、`proxy`、`web`、`db`はhealthyだった。表示されたポートはコンテナ内部の80/443/2019、8000、5432で、ホストへの転送表記はなかった。

VM200の`/opt/acervo`でCloudflare専用Composeの`config --quiet`は終了コード0で`COMPOSE_OK`、`web`の`python manage.py check --deploy`は問題0件、`proxy`の`caddy validate`は`Valid configuration`で終了コード0だった。これは設定・起動済みコンテナの確認であり、イメージの再ビルド、再起動、永続化は今回未確認。

運用者本人がCloudflareへサインインした後、管理画面で`Acervo-vm200` Tunnelの状態が正常、レプリカ1件、ルート0件であることを確認した。公開操作の最終確認を受けて、`specimens.kdf-biology.org`の公開アプリケーションルートを`http://proxy:8080`へ追加した。管理画面には追加成功、同hostnameのCNAME作成、ルート1件と表示された。Cloudflareのroute/DNS以外にVM200の設定・コンテナ、VM201、LXC110、`/dev/sda`は変更していない。

Codexブラウザからの公開URLへのアクセスは`ERR_BLOCKED_BY_CLIENT`となったが、同じ管理用PCの`curl.exe`では証明書検証結果0で`/health/`が200、`/accounts/login/`が200、`/admin/`が404、未ログインの`/management/`が302だった。後者の転送先は同一HTTPS Originの`/accounts/login/?next=/management/`。ログイン画面の応答ヘッダーではCSRF CookieのSecureとSameSite、HSTSの存在を値を出さずに確認した。実ブラウザでの管理者ログイン・MFA、セッションCookie、別OS・端末、バックアップの今回の再試験は未実施。

実ブラウザの管理者ログインを案内した後、運用者から管理者を作成した覚えがないとの指摘を受けた。VM200のDjango ORMで全ユーザー数とadmin数だけを読み取り、結果は`0 0`だった。初期管理者は未作成で、一時パスワードも未発行。ログイン・MFAの受入はこの段階では実施できない。初期管理者のユーザー名と回生番号を運用者へ確認中で、パスワード等の秘密値はチャットに出さない。

運用者指定の`kade6174`、33回生で`bootstrap_admin`を実行し、終了コード0で初期管理者を作成した。最初に表示された一時パスワードがチャットに貼られたため、直ちに使用停止とした。再発行時にも一時パスワードがチャットへ貼られたため、これも使用停止とした。最後に運用者が画面に表示されない値を入力する方式でパスワードを設定した。最初の試行は12文字未満のためDjangoのバリデーションで拒否され、パスワード変更は行われなかった。2回目は`password_updated`と終了コード0で成功し、`must_change_password=True`を維持した。値そのものは記録・表示していない。公開HTTPSでの初回パスワード変更、TOTPまたはパスキーのprimary MFA登録、Recovery Codes、管理者MFAゲートの実ブラウザ受入は未実施。

平文の`http://specimens.kdf-biology.org/health/`は当初200で、HTTPSへの転送がなかった。Cloudflareの対象hostnameだけに一致する`http://specimens.kdf-biology.org/*`から`https://specimens.kdf-biology.org/${1}`への308転送（クエリ保持）をフォームへ入力し、画面のルール検証は成功した。最初の「デプロイ」は自動承認審査で拒否された。理由は、公開ルートの承認だけでは追加の永続的な転送ルール変更への明示承認を確認できないため。運用者からこのルールへの明示承認を得てデプロイし、Cloudflare画面で同ルールがアクティブと表示された。管理用PCから`http://specimens.kdf-biology.org/health/?probe=1`は308で、転送先はパス・クエリを保つ同hostnameのHTTPS URLだった。HTTPSの`/health/`は200、証明書検証結果0を再確認した。

運用者は公開HTTPSで初回ログイン、パスワード変更、Recovery Codes生成、TOTP認証、パスキー登録を完了した。パスワードログイン後の第二要素としてのパスキーは成功した一方、ログイン画面からの直接ログインは失敗した。既存WebAuthn認証器について、秘密値・credential本体を出さずにpasswordless判定だけを読んだ結果は`[None]`だった。これは登録時の`credProps`結果が端末から返らない場合に、既存実装が直接ログイン不可として扱うためである。

作業ツリーで、パスキー登録開始時に選んだ方式をサーバー側のsession-bound challengeへ結び付け、成功時に認証器データへ方式だけを保存する修正を実装した。直接ログイン時は、このサーバー記録または既存の`credProps`の明示trueを要求する。選択と異なる送信、登録開始前の送信では認証器を作成しない。既存の`[None]`認証器を後から直接ログイン可能と分類しないため、本修正の本番反映後に、ログイン済みの設定画面で「パスキーとして登録する」を有効にした新規登録と直接ログイン受入が必要である。新しい直接ログインを確認するまで既存認証器を削除しない。ログイン画面では共通ナビゲーションの重複した「ログイン」リンクを隠し、入力欄下の送信ボタンだけを残す修正も実装した。

作業ツリーで`python manage.py test --settings=config.settings.test`は262件すべて成功、`ruff check .`、`ruff format --check .`、`python manage.py check --settings=config.settings.test`、`makemigrations --check --dry-run`、`git diff --check`は成功した。変更は未コミット・未pushであり、GitHub Actions、VM200でのCompose再ビルド・再起動、実ブラウザでの直接ログインおよび重複リンク解消は未確認である。

その後、修正を`36e9a19`としてコミットし、`3c9a3ad`とともにGitHubの`main`へpushした。VM200は未変更の作業ツリーで`8a20529`から`36e9a19`へfast-forwardし、Cloudflare用Composeでwebイメージを再ビルドして`up -d --wait`を実行した。終了コード0で、`db`、`web`、`proxy`、`tunnel`は稼働し、`db`、`web`、`proxy`はhealthyだった。更新後にコンテナ内の`python manage.py check --deploy`は問題0件で終了した。`/dev/sda`、VM201、LXC110は操作していない。

運用者は公開URLで、ログイン画面の重複リンクが消えたこと、登録し直したパスキーによる直接ログインが成功することを確認した。さらに、パスキー直接ログイン後の`/management/`管理トップ表示と、ログアウト後に同URLが同一Originのログイン画面へ戻ることを確認した。未認証管理URLのredirect、MFA未設定・未完了管理者の拒否、初回登録の不整合送信は自動テストで確認済みである。別OS・端末での受入は未実施である。

この時点では7C-LIVE-Aを完了と判断したが、復元先での認証受入が欠けていたため、上記のとおり2026-09-29に訂正した。Step 7C-LIVE全体とPhase 1全体は未完了である。

## 2026-09-28 チャット引継ぎとLIVE受入順序の整理

`AGENTS.md`、`PROJECT_SPEC.md`、`PLAN.md`、`STATUS.md`の順に確認し、`git status`は変更なしの`main...origin/main`、HEADは`fb78906`だった。関連URLを調べ、現在のルーティングに標本・QR・保護写真の経路がなく、Phase 2〜5のモデル・登録・詳細機能が未実装であることを確認した。既存変更はなかった。

設計責任者の回答により、Step 7C-LIVEの受入を7C-LIVE-A（公開基盤・認証・MFA・空データ復元）と7C-LIVE-B（標本実装後の標本・写真・実データ復元）に分けた。`PLAN.md`と`docs/LIVE_PREFLIGHT.md`の順序と確認項目を更新した。7C-LIVE-Aの成功後にPhase 1Dへ進めるが、一般利用開始とStep 7C-LIVE全体の完了は7C-LIVE-Bまで保留する。`PROJECT_SPEC.md`のMVP範囲・標本番号・QR・認可・バックアップ要件は変更していない。コード、DB、Compose、本番VM、Cloudflare route/DNSは変更していない。

ローカル仮想環境のPython 3.13.14でDjango system checkは0件、SQLiteの全259テストは成功、Ruff lintは成功、format checkは94ファイル成功した。通常の`python`ではDjangoが未導入のためcheck・testが`ModuleNotFoundError`で失敗したが、`.venv`で再実行して成功した。今回の文書変更に対するPostgreSQL、Compose、実ドメイン、端末、QR初回登録、標本詳細・写真の認可は未確認。後三者は機能自体が未実装であり、実装後に通常経路・権限不足・不正入力・競合を含む必須テストと実機受入を行う。次は7C-LIVE-Aの残る人による確定項目を確認し、承認後に公開基盤とMFAの実ドメイン受入を進める。

## 2026-09-28 標本番号・QR方式の設計確認

標本閲覧の認可設計を追加確認した。利用者の選択により、QR読取からの「未ログインならログイン→権限確認→詳細表示」と、ログイン後の検索からの閲覧を両立する。標本番号やDB連番IDを直入力するだけで詳細・写真・履歴を取得できる経路は設けず、検索結果からの詳細リンクにはQRとは別の標本詳細用ランダムUUIDv4を使い、各詳細リクエストでも閲覧権限を検査する。QR URL内のUUIDv4は推測困難なラベル識別子だが、URLの手入力と実際の読取は区別できず、UUIDv4自体を閲覧許可として扱わない。QR・標本関連のURLと認可は未実装であり、この安全性はまだ実機確認できていない。`PROJECT_SPEC.md`・`PLAN.md`・導入例に設計と必須テストを反映した。

生物班導入先の標本番号接頭辞を運用者が`KDF-BIO`に確定した。例は`KDF-BIO-000001`。標本番号の接頭辞は製品コードへ固定せず、登録確定時のみ採番・変更不可・削除後も再利用しないという`PROJECT_SPEC.md`の不変条件を維持する。導入例の公開hostnameを、運用者が選んだ`specimens.kdf-biology.org`へ更新した。

運用者は、QRにIDのみを記録する案とUUIDv7も検討し、初回登録で困らず端末標準のカメラでも使える「UUIDv4識別子を含むAcervoのURL」を選択した。QRは標本番号を含まず、未ログイン時はログイン後に同じQR判定へ戻す。`PROJECT_SPEC.md`と`PLAN.md`にUUIDv4形式と初回登録の必須確認を反映した。UUIDv7の時刻順序はQRには不要で、発行時刻を含まないUUIDv4を採用する。接頭辞の設定項目、SpecimenSequence、Specimen、QRLabel、QR読取は未実装であり、`PLAN.md`のPhase 2・3以降で扱う。Phase 1全体の完了条件が未達のため、アプリ実装・DB・外部公開設定は今回変更しない。今回の変更は文書のみで、実機の初回登録は未確認。

## 2026-09-28 署名付きバックアップの実機復元

VM200の署名秘密鍵をUID/GID 10001・mode 0600で配置し、VM201にはバックアップ保存先とは別経路で取得した`allowed_signers`を配置した。VM200で形式v2・`ssh-ed25519`署名付きのバックアップ`acervo-20260927T164402Z-b091646e79ee`を作成し、LXC110に転送して保存確定を確認した。保存先の`checksums.sha256`はpayloadとmetadataの両方で成功した。VM201に取得した3ファイルも同様に照合し、独立した公開鍵による署名検証は`signature=valid`だった。VM201の空DB・空写真領域へ復元し、`restore_completed`と終了コード0を確認した。

復元後のDBテーブル数はVM200／VM201とも15、写真ファイル数はともに0、復元設定とVM200の`.env.production`のSHA-256は一致した。これは写真・利用者データのない状態での復元試験であり、実データや画面表示の受入試験ではない。管理用PCのage秘密鍵ファイルには誤記があり、そのままでは解析できなかった。VM201上の一時的な修正候補で形式検査と実payloadの復号を確認し、管理用PCに元ファイルを上書きしない修正済みの控えを作成した。その控えをVM201へ転送して候補とバイト単位で一致することを確認した。秘密鍵本文・設定値は記録していない。

VM201では復元後の`db`・`web`・`proxy`がHealthy、`check --deploy`は0件、検証用の非公開Caddy設定で`/health/`が200、`/accounts/login/`が200、`/admin/`が404だった。3コンテナのホスト公開ポートは空だった。最初にCaddy設定を重ねずに8080番へ接続して拒否されたが、検証用の設定を明示して再試験した結果は成功した。試験用コンテナと5つのDockerボリュームを削除し、VM201の一時age鍵・SFTP鍵・known_hosts・バックアップコピー・復元設定コピーも対象を限定して削除した。別保管の公開鍵`allowed_signers`は次回の復元用に維持した。印刷した控えが修正済みの鍵と一致するかは未確認。一般公開用のCloudflare route/DNSと実利用者・実データの投入は未実施であり、Step 7C-LIVEとPhase 1全体は完了扱いにしない。

## 2026-09-28 バックアップ復元の真正性検証を強化（リリース前）

セキュリティ確認レポート（scan `84ca32bf-93bf-44b7-bf79-1ad0ba982281`）の唯一の指摘は、別ホスト保存先を書き換えられる攻撃者が、暗号化payload・metadata・checksumsを整合させて差し替えると復元を通過できる点だった。修正作業ツリーでは、バックアップ作成時に専用Ed25519秘密鍵でpayloadのSHA-256を含む正規化metadataへ署名し、復元時に保存先とは別の信頼できる保管場所からread-onlyで渡す`allowed_signers`だけを使って、復号・展開より前に検証するよう変更した。署名のない旧形式（format version 1）と不正署名は復元を拒否する。署名用秘密鍵は作成コンテナだけへ、公開鍵集合は復元コンテナだけへ渡し、どちらもコンテナ内ではread-onlyとする。

復元は保存先の3ファイルをprivateな一時領域へスナップショットしてから検証・復号する。検証後に保存先を再読込しないため、検証と復号の間の差替えを受け入れない。外側payloadと内側の写真archiveは展開前にパスを検査し、絶対パス、`..`、symlink、hardlink、デバイス、その他の非通常entry、重複entryを拒否する。保存先を同時に書き換えられる攻撃者は短いコピー競合により復元を失敗させ得るが、署名済みpayloadの任意差替えや任意ファイル書込みには至らない。DB復元後に写真または設定コピーが失敗した場合は空の復元先が部分復元状態になる既存の運用上の制約があり、再試行前に復元先を作り直す必要がある。

ローカルではバックアップ専用19件、Ruff lint／format、Django check、migration差分なし、全259件の回帰テスト、`git diff --check`が成功した。Docker CLIとbashがないため、Compose統合試験はローカル未実行である。mainのGitHub Actions run `36332469569`は`test`と`production-container`の全ジョブが成功した。後者では直接HTTPS構成、Tunnel専用構成、署名付きバックアップ作成、整合する3ファイルの改ざん拒否、空環境への復元までを確認した。実機への鍵配置・署名付きバックアップ作成・空環境復元は未完了。Cloudflareの公開route設定および一般公開は、実機復元受入を確認するまで進めない。

## 2026-09-27 初回定時実行の確認

運用者から主Proxmoxホストと本番候補VMの`systemctl list-timers`／`systemctl show`の実機出力を受領した。起動timerは17:55:20 JST、バックアップtimerは18:00:04 JSTに起動し、両serviceとも`Result=success`、`ExecMainStatus=0`だった。VM側serviceは18:00:07 JSTに終了した。両timerの次回は2026-09-28の17:55／18:00 JST。

VM側`journalctl`の当日分には、PostgreSQL 18を対象とする暗号化バックアップ作成、保持処理`deleted=0`、暗号化payload・metadata・checksumsのSFTP転送、`.ready`送信、`upload_complete`、`offsite_verified`、`shutdown_requested`、service正常終了が記録されていた。backup IDは`acervo-20260927T090005Z-04948a9e7b60`。別ホスト保存先の確定をスクリプトの検証ログで確認した。その後、主Proxmoxホストからバックアップ機のホストIPと保存用LXCのIPへ各2回pingし、どちらも応答0件だった。これは停止要求後の期待状態と整合するが、pingだけで物理的な電源断は断定できない。初回定時バックアップの作成・保存確定と停止要求、停止後のネットワーク非応答は確認済み。実データを使う復元受入は未実施。

同日にバックアップ機のLXC 110を実機確認した。LXCは`running`で、`ssh`と`acervo-finalize-incoming.path`はいずれも`active`だった。保存領域`/srv/acervo-backup`は629 GB中2.2 MB使用、597 GB空き。確定済み成果物は`/srv/acervo-backup/sftp/incoming/acervo-...`へ保存され、finalizeスクリプトは`.ready`、必須3ファイル、SHA-256を検証してからディレクトリを確定する。確認時には4世代が確定済みで、合計72 KBだった。別ホストの自動整理、容量監視、失敗通知は未整備であり、削除は行っていない。手動WOL送信は主Proxmoxホスト側で終了コード0だったが、直後のpingではバックアップ機から応答がなく、手動WOLからの起動成立は未確認である。

別ホスト向けに、確定済み成果物だけを日次14・週次8・月次12世代の和集合で保持するスクリプト、起動90秒後に整理と容量・必須unitを検査するsystemd unit、任意のDiscord Webhook失敗通知の導入用ファイルを追加した。保持スクリプトは既定で候補表示だけを行い、`--apply`がなければ削除しない。容量の初期しきい値は空き50 GiB未満または使用率85%以上である。Webhook URLはroot専用の設定ファイルにだけ置き、Git、ログ、コマンド引数には出さない。ローカルでは`python -m unittest core.tests.test_backup_tool core.tests.test_offsite_operations`が17件成功、Python構文確認と`git diff --check`が成功した。RuffはこのWindows環境に未導入のため未実行。実機への導入、dry-run結果の確認、Discord受信確認、実削除は未実施。

導入用ファイルをGitHubの`main`へ反映し、物理バックアップ機の作業用コピーがコミット`11115271bea6ca5a4449756432f95b1efa796dde`であることを確認した。LXC 110へ保持、容量監視、Discord通知、maintenance unitの各ファイルを配置してdaemon-reloadを実行した。保持処理のdry-runでは、`acervo-20260926T122342Z-ad9357417c17`だけが削除候補になった。同じ日付のより新しい世代があるため、日次14・週次8・月次12の保持規則では対象外となる。実削除とmaintenance timerの有効化は未実施。容量監視は`health_ok used_percent=0 free_gib=596`で成功した。Discord Webhookの作成・root専用設定ファイルへの保存・受信試験、VM200のバックアップservice失敗通知の導入は未実施。物理バックアップ機の`apt-get update`はEnterpriseリポジトリの401で非ゼロ終了したが、Debian公式リポジトリからのGit導入は成功した。Enterpriseリポジトリ設定は変更していない。

保持規則のdry-runで示した候補`acervo-20260926T122342Z-ad9357417c17`について、運用者の明示承認後に`--apply`を実行し、`retention_completed deleted=1`を確認した。確定済みの3世代は残った。`acervo-offsite-maintenance.timer`を`enabled`にし、次回のバックアップ機起動時から起動90秒後に実行されるよう設定した。timer有効化直後の`NEXT`は`-`だったため、maintenance serviceを手動で1回実行した。終了コード0、`retention_completed deleted=0`、`health_ok used_percent=0 free_gib=596`を確認した。Discord Webhookのroot専用設定ファイル作成・受信試験、VM200のバックアップservice失敗通知の導入は未実施。

Discord WebhookをLXC 110のroot専用`0600`ファイルに設定し、通知serviceを試験したがHTTP 403で失敗した。Webhook URLはログ・チャットに表示していない。同じURLを使い、明示的な`User-Agent: Acervo-Backup/1.0`付きGETはHTTP 200、テスト通知POSTはHTTP 204だったため、Python標準の通信識別名が403の原因と判断した。通知スクリプトに成功した識別名を追加し、モックでPOSTとヘッダーを確認するテストを追加した。ローカルで`python -m unittest core.tests.test_offsite_operations`は9件成功、Python構文確認と`git diff --check`も成功。修正版のGitHub反映、LXC配布、systemd経由の受信再試験、VM200側の失敗通知設定は未実施。

修正版`d4babc8`をGitHubへ反映し、物理バックアップ機の作業用コピーを同コミットへ更新して、通知スクリプトをLXC 110に再配置した。`acervo-discord-notify@notification-test.service`の再試験は`Result=success`、`ExecMainStatus=0`、最新ログは`discord_notification_sent unit=notification-test`となり、運用者がDiscordへの着信も確認した。VM200の日次バックアップserviceの失敗通知はまだ未導入。

VM200も`d4babc8`へ更新し、`acervo-discord-notify`、通知用systemd template、`acervo-daily-backup.service`の`OnFailure` drop-inを配置してdaemon-reloadした。Webhook URLは主Proxmoxホストから`qm guest exec --pass-stdin`で渡し、画面、コマンド履歴、ログへ表示せずにVMのroot専用`/etc/acervo/discord-webhook.url`（`root:root 0600`）へ保存した。VM上の`acervo-discord-notify@notification-test.service`は`Result=success`、`ExecMainStatus=0`で終了し、運用者がDiscordへの着信も確認した。

GitHub Actionsの品質確認は、別ホスト運用テスト4か所の100文字超過（E501）で失敗した。テストの意味を変えずに改行して修正し、ローカルの`python -m unittest core.tests.test_offsite_operations`は9件成功、`git diff --check`も成功した。このWindows環境にRuffは未導入のため、Ruffの最終確認はGitHub Actionsで行う。

初回修正後のGitHub ActionsではRuffの構文検査は成功し、formatterが既存の別ホスト運用ファイル2件とテスト1件の整形差分を検出した。Ruff出力どおりに整形し、運用テスト9件、`git diff --check`、対象3ファイルの100文字超過なしを再確認した。修正コミット`81d91d7`のGitHub Actions run `36317255882`では、品質確認、PostgreSQLテスト、直接HTTPS構成、Tunnel専用構成、暗号化バックアップから空環境復元まで全て成功した。

## 2026-09-26 実機バックアップ作業の引継ぎ

以下は運用者からの引継ぎ報告であり、この作業ツリーから実機のログや設定を読み返した結果ではない。導入先固有のアドレス、認証情報、秘密鍵の値は記録しない。

- 本番候補VMでPostgreSQLの`db`は稼働中。Web、Caddy、Tunnelの稼働と一般公開は未確認。`age`で暗号化したDB・写真・必要設定のバックアップをVMの永続領域へ作成し、別物理ホスト上のSFTP保存先へ転送した。保存先では`.ready`を契機に必要ファイルとSHA-256を照合して保存を確定する。
- 別VMの空のDB・写真領域へ別ホストから取得したバックアップを復元した。元と復元先のDBテーブル数・写真ファイル数はいずれも0で一致し、復元設定ファイルのSHA-256も一致した。試験に使った一時秘密鍵・設定ファイル・Dockerボリュームは試験VMから削除した。これは空データの復元確認であり、実データ・ログイン・標本詳細・写真表示の受入ではない。
- 日次バックアップスクリプトの手動実行は終了コード0で完了し、作成、転送、保存確定の確認、バックアップ機の停止まで進んだ。失敗時は停止要求へ進まない構成との報告を受けた。バックアップ機の起動は本番候補VMからのWOLでは失敗し、主ProxmoxホストからのWOLで成功した。
- 主Proxmoxホストに毎日17:55 JSTの起動timer、本番候補VMに毎日18:00 JSTのバックアップtimerを設定した。service・timerの内容は運用者が読み返した。VM側は`Persistent=false`であり、停止中に逃した実行は自動で追いかけない。2026-09-26に`list-timers --all`の実機出力を受領し、両timerの次回が2026-09-27の17:55／18:00 JST、`LAST`がともに`-`、VM側確認コマンドの終了コードが0であることを確認した。両timerの`systemctl is-enabled`も`enabled`（VM側確認コマンドは終了コード0）で、再起動後も有効化される設定を確認した。翌日の初回起動結果は上記に記録する。
- バックアップ機の非特権LXCはsystemd起動時にmount単位3件が失敗した。`nesting=1`設定後の再起動で失敗単位0件、`ssh`と保存確定用path単位は`active`と報告された。nestingによりホストの`/proc`・`/sys`がより見える運用上の注意がある。
- 別ホスト保存先の旧世代の自動整理、失敗通知、容量監視は未整備。保存先容量は約640 GB。保持・削除ルールが確定するまで過去の成果物を削除しない。

この時点で未確認だった初回定時実行の結果は、翌日の記録に記載する。公開設定と受入は`docs/LIVE_PREFLIGHT.md`の承認事項を満たしてから進める。

## Completed

- 設計責任者の承認により、バックアップ暗号化のrecipient要件を「2本以上」から「1本以上」へ変更した。1本運用では秘密鍵を紛失・破損すると既存バックアップを復元できない。このリスクを承認した導入先だけが選択でき、後継者の公開鍵を追加した後は、新規バックアップを複数recipientへ暗号化する。実装、単体テスト、導入例、公開前確認、非公開運用台帳テンプレートを整合した。`python -m unittest core.tests.test_backup_tool`は10件成功、Python構文確認と`git diff --check`も成功した。このWindows環境にはDjangoとRuffが未導入のため、全Djangoテスト、Django check、Ruffは未実行である。Dockerも未導入のため、単一recipientによるComposeバックアップ・復元統合確認はCIで実行する。
- Phase 10Aの実装・検証結果を受入れた。`age`の各秘密鍵は単独で復号できる完全な鍵であり、複数recipientは二者承認ではなく管理者喪失に備えた可用性対策として扱う。最低2本を2名以上の担当者または相互に独立した保管場所へ分離し、秘密鍵と暗号化バックアップを同一障害領域へ置かない。鍵紛失・漏えい・担当者交代時は新recipient群で新規バックアップを作成し、既存成果物の再暗号化または安全な廃棄を別途判断する。秘密分散、Shamir方式、二者承認機構はMVPに追加しない。
- Step 7C-LIVEの承認パッケージを`docs/LIVE_PREFLIGHT.md`へ確定待ちとして明記した。その後、導入先でバックアップの実機設定と空データ復元試験が進んだ。公開設定、責任者、バックアップ運用、受入端末の確定・承認と、公開前・限定運用後の各受入はなお必要である。第1・第2段階が成功し、秘密値なしで結果を記録するまでStep 7C-LIVEを完了扱いにしない。

- Step 7C-LIVE事前確認として、汎用設定と生物班の導入例が分離され、`acervo.kdf-biology.org`、`school_cohort`、4月1日、2026年度、33回生、運用責任者がアプリコードや汎用の本番例へ固定されていないことを静的確認した。直接HTTPSは`proxy`だけが80/tcp・443/tcp・443/udpを公開し、Tunnel専用は`proxy`、`web`、`db`、`tunnel`にホスト公開ポートがなく、Compose内部の`http://proxy:8080`をTunnelオリジンとする。両方式を同時に指定せず、直接HTTPSはTunnel資格情報を必要としない。CaddyはTunnel専用でACMEを起動せず、Gunicorn・PostgreSQL・保護写真を公開しない。
- `docs/LIVE_PREFLIGHT.md`へ、秘密値を含まない承認前の確定チェックリスト、承認後の実行順序と期待結果、中止条件を追加した。公開hostnameとWebAuthn RP ID、Host／CSRF Origin一致、Django秘密鍵とMFA Fernet鍵の別管理、担当者・バックアップ暗号化・復元試験先・対象端末の確定を必須にした。外部環境の操作は行っていない。
- Phase 10Aとして、固定版`age` 1.3.2と2本以上の異なる公開鍵を用いる、PostgreSQL論理ダンプ・保護写真・非公開設定を一単位にした暗号化バックアップを追加した。復号用identityは成果物・リポジトリ・ログへ保存せず、生成後に印刷して別々の管理者または保管場所へ分配する。成果物は暗号化payload、秘密値を含まないmetadata・checksumだけを公開し、未完了成果物は採用しない。日次14・週次8・月次12世代は設定で変更できる。
- 復元は空のPostgreSQL 18検証環境だけを対象とし、確認文字列、チェックサム、形式・PostgreSQLメジャー一致、空DB・空写真の確認を必須にする。既存データ、既存写真、実行中の設定を暗黙に上書きしない。復元設定は別出力先へ復元する。DB障害、写真読取・暗号化障害、破損・欠落成果物、誤った復元先、保持境界、秘密値非出力を含む10件の単体テストを追加した。
- 実装コミット`de51033da6960e7385dc1edbf3e57e2f39f8b473`およびCI修正コミット`bd3bc90`、`27e11ad`、`c042181`、`4e0ea92`により、GitHub Actions run `35359748083`でPostgreSQL 18全241件、直接HTTPS／Tunnel専用の本番コンテナ検証、暗号化バックアップから独立した空環境への復元、`check --deploy`、DB・写真・設定の復元確認が全成功した。ローカルではRuff lint／format、Django check、migration差分なし、SQLite全241件、ランダムな一時値での`check --deploy`、Markdownリンク、`git diff --check`が成功。Docker CLIとCaddy CLIはこのWindows環境にないため、コンテナ統合検証はCIで実行した。Phase 10全体とStep 7C-LIVEは完了扱いにしない。
- Step 7C-LIVE事前確認のローカル検証では、Markdownローカルリンク、旧回生変数が移行・拒否説明だけに残ること、文書内に具体的な秘密値がないこと、`git diff --check`、Ruff lint／format、Django check、migration差分なし、ランダムな一時値を使う本番相当`check --deploy`、SQLite全231件が成功した（231件、19.127秒）。Docker CLIとCaddy CLIがこのWindows環境にないためCompose設定解決・Caddy adapt／validate・コンテナ起動はローカル未実行である。コード、設定、Compose、Caddy、CIの差分はなく、実装HEAD `a0cd67190a0f938f8027a392c5476908e489c816`のGitHub Actions run `35353377279`でPostgreSQL 18全231件と直接HTTPS／Tunnel専用の本番コンテナ検証が全成功している。
- Step 7C-DOCとして、汎用ソフトウェア向けの`docs/DEPLOYMENT.md`、生物班への一導入例である`docs/examples/KDF_BIOLOGY.md`、公開リポジトリに実値を書かない`docs/templates/PRIVATE_OPERATIONS_RUNBOOK.md`を追加した。READMEの詳細な本番手順は汎用導入マニュアルへ集約し、公開方式、MFA復旧、在籍ポリシー、引継ぎの説明を重複させない。
- Step 7C-DOC-Rとして、ライセンス採用前の文書表現と非公開運用台帳の記録範囲を整合した。公開台帳テンプレートには実値を書かず、アクセス制限された非公開コピーには引継ぎに必要な最小限の担当者・連絡先・管理アカウント識別子・内部接続先を記録可能とした。一方、パスワード、token、秘密鍵、Recovery Codesは非公開コピーにも直接記載せず、安全な保管場所への参照だけを残す。Markdownリンクと`git diff --check`を確認し、実装コミット`4b0c8690ba09dd5ce9ceb1c1c962e6fb215e699a`のGitHub Actions run `35349448683`は`test`と`production-container`の全ジョブ成功。コード、Compose、Caddy、CI、DNS、Tunnel、token、本番ホストおよび本番公開の外部状態は変更していない。
- Step 7C-LICENSEとして、kade_6174が権利を有するAcervo固有のコード、文書、設定例へApache License 2.0を適用した。`LICENSE`は公式本文との行単位一致、`NOTICE`は`Copyright 2026 kade_6174`、`THIRD_PARTY_NOTICES.md`はBootstrap 5.3.8（MIT）とhtmx 2.0.10（0BSD）の同梱ライセンスと配布元を記録する。PEP 639の`license = "Apache-2.0"`、`authors = [{ name = "kade_6174" }]`、ライセンス関連ファイルの`license-files`を設定し、隔離wheelで`License-Expression: Apache-2.0`、Author、LICENSE・NOTICE・第三者通知・同梱ライセンスの収録を確認した。ローカルではRuff lint／format、Django check、migration差分なし、Markdownリンク、`git diff --check`が成功。SQLite全231件は初回に既存TOTP統合テスト1件が一時失敗したが、同一テストの単独再実行と全231件の再実行はいずれも成功した。ローカルの`build`／setuptoolsは未導入のためsdistは未検証。実装コミット`41e3b8fb9d996a700869fb614b7525894fd5b6b7`のGitHub Actions run `35353015064`は`test`（PostgreSQL 18を含む）と`production-container`（直接HTTPS／Tunnel専用）の全ジョブ成功。第三者のコード、静的資産、依存パッケージ、コンテナ基盤は再ライセンスせず、公開Dockerイメージまたは配布済みアーカイブを正式提供する前の完全な依存物・ライセンス・SBOM確認は別タスクとする。コード、migration、Compose、Caddy、CI、DNS、Tunnel、token、本番ホストおよび本番公開の外部状態は変更していない。
- 生物班の例は`school_cohort`の1年生基準（2026年度33回生）とTunnel専用構成を記録するが、サイト名・組織名、VM、Tunnel名、token、バックアップ先、利用端末は未確定または非公開情報として推測・記載していない。外部状態は変更していない。DNS、Tunnel作成・token配置、本番ホスト、本番Compose起動、実HTTPS受入、本番公開はStep 7C-LIVEへ残る。

- Step 7A-R2として、学校回生方式の基準を「基準年度の1年生回生」へ変更した。`ACERVO_BASE_SCHOOL_YEAR=2026`と`ACERVO_BASE_FIRST_YEAR_COHORT=33`では、2026年度に33・32・31回生を順に1・2・3年生、2027年度に34・33・32回生を順に1・2・3年生として扱う。既存の`cohort_number`、DB schema、管理MFA、ログイン、MFAリセット、session、AuditLogは変更していない。
- 本番で旧`ACERVO_BASE_THIRD_YEAR_COHORT`を検出した場合は、値を表示せず新しい`ACERVO_BASE_FIRST_YEAR_COHORT`への移行を案内してfail-fastで拒否する。旧変数だけでも新旧同時指定でも拒否し、`none`ポリシーの動作は維持する。当時のStep 7A／7A-Rは3年生基準だったが、現在はStep 7A-R2の1年生基準が正とする。migrationは追加していない。
- ローカルでは在籍判定・ポリシー・本番設定の専用42件、およびSQLite全231件が成功した。Ruff lint／format、Django check、migration差分なし、`git diff --check`、ランダムな一時設定値を用いる本番相当`check --deploy`も成功した。GitHub Actions run 35304262014は全成功し、PostgreSQL 18全231件、Ruff、Django check、migration差分なし、直接HTTPS／Tunnel専用のCompose・Caddy・本番イメージ・healthy・UID 10001・`check --deploy`・IP信頼境界・公開ポート・DB／写真永続化の既存回帰を確認した。このWindows環境ではDocker CLIが利用できないため、コンテナ起動はローカル未実行である。

- Step 7BのCSRF 403診断・補正として、Caddy経由ログインPOSTにCookieとform tokenをSimpleCookieで正しく組み合わせ、公開Origin https://acervo.localhost のOriginとRefererを送るCI検証へ更新した。Cookie、token、パスワード等の値はログへ出さず、名前の有無、token長、HTTP status、Location有無だけを確認する。django.security.csrfには拒否記録がなく、CI限定の安全なサーバーログで実際の原因がallauthのUnable to determine client IP addressであることを確認した。
- 原因はCaddyの専用IPヘッダーを削除してから再設定する経路で、Djangoへヘッダーが届かなかったことだった。直接HTTPSではCaddy接続元、Tunnel専用では信頼済みCF-Connecting-IPからのIPを、いずれも単一の上書き設定でDjangoへ渡すよう修正した。外部入力のX-Acervo-Client-IP、X-Forwarded-For、CF-Connecting-IPは直接HTTPSで採用されず、Tunnel専用では正規化済みCF-Connecting-IPだけが採用される。CSRF、Secure Cookie、Origin検証、レート制限を緩和していない。
- CI失敗時だけweb・proxyの直近ログを出し、終了コードを保ったまま必ずComposeを後片付けする。CI専用の診断設定は、CSRF理由または専用IPヘッダーの有無・IP形式だけを記録し、Cookie、CSRF token、パスワード、秘密鍵、Tunnel token、環境変数値を出力しない。通常の本番環境では無効である。
- Step 7B実装検証HEAD `1ebf6f8` はGitHub Actions run 35221822741で全成功。PostgreSQL 18の全228件、Ruff lint／format、Django check、migration差分なしが成功した。直接HTTPSとTunnel専用を別々に、Compose設定、Caddy adapt／validate、本番イメージ、db・web・proxy healthy、UID 10001、check --deploy、ログインPOSTのCSRF／同一Origin、health、静的ファイル、admin 404、管理画面redirect、IP信頼境界、公開ポート、DB・写真永続化まで確認した。Tunnel専用ではproxy・web・db・tunnelのホスト公開ポートなし、直接HTTPSではproxyだけが80/tcp・443/tcp・443/udpを公開し、web:8000・db:5432は非公開である。
- 最終整理HEAD `f9556e9` はGitHub Actions run 35222634638で全成功。本整合修正の開始時の実HEADは `f9556e9cff0426cd41ed9f902ebfbeb9dea52268` である。
- ローカルDocker CLIとPython開発依存はこのWindows環境で利用できないため、今回のローカルSQLite全テスト、Ruff、Django check、Compose起動は未実行である。CIのPostgreSQL 18全228件と本番コンテナ検証で確認した。migrationは追加・変更していない。
- Step 7Bの変更ファイル: compose.production.yaml、compose.direct.yaml、compose.cloudflare.yaml、deploy/Caddyfile.direct、deploy/Caddyfile.cloudflare、deploy/Caddyfile.common、削除した旧deploy/Caddyfile、.github/scripts/verify-production-compose.sh、.github/workflows/ci.yml、PROJECT_SPEC.md、README.md、PLAN.md、STATUS.md、accounts/adapters.py、accounts/tests/test_deployment_config.py、config/settings/production.py。

- Step 7A-Rとして、`school_cohort`を選ぶ本番では年度開始月・日、基準年度、基準回生をすべて明示必須にし、欠落・空値・非整数・不正日付・範囲外年度・0以下回生を秘密値を含めずfail-fastで拒否するよう補強した。`none`は学校方式の4変数なしで成立し、空白だけの`ACERVO_SITE_NAME`も本番で拒否する。`.env.example`と`.env.production.example`へ一致する設定例と学校方式の説明を追加した。Compose、Caddy、Cloudflare、DNS、Tunnel、本番環境は変更していない。
- Step 7A-Rのローカル検証では、SQLite全228件、Ruff lint／format、Django check、migration差分なし、`git diff --check`、ランダムな一時設定値を用いる本番相当`check --deploy`が成功した。既存のnone／school_cohort、nullable migration、同期・非同期manager、`bootstrap_admin`、管理MFA、MFAリセット、認証、パスキー回帰を含む。ローカルDocker CLIがないためコンテナ検証は未実行で、最終HEADのGitHub ActionsでPostgreSQL 18と既存本番コンテナ検証を確認する。
- GitHub Actions run 35191673164は全成功。PostgreSQL 18全228件と、変更していない既存本番／Cloudflare Compose・Caddy・本番イメージ・healthy・UID 10001・IP信頼境界・非公開ポート・DB／写真永続化検証が成功した。
- Step 7Aとして、Userの保存値`member`／`admin`を維持しつつ表示名を「利用者」へ変更し、`cohort_number`をNULL・blank許可へ移行した。DB制約はNULLまたは正数とし、既存の非NULL回生値を変更しないmigrationと、NULLがある場合の逆migration拒否（バックアップ復元または全回生設定を要求）を追加した。
- `ACERVO_ENROLLMENT_POLICY`は`none`／`school_cohort`だけを許可し、本番では明示必須とした。`school_cohort`は年度開始月・日、基準年度、基準回生を環境変数から読み、回生欠損・未来回生を拒否する。`none`は回生を要求せず、保存済み回生も認可へ使わない。`school_cohort`から`none`への切替は卒業済み利用者の書込み可否を変え得るため、運用上の権限変更として事前確認が必要である。
- Step 7Aで`ACERVO_SITE_NAME`、`ACERVO_ORGANIZATION_NAME`を追加し、導入先サイト名をヘッダー、WebAuthn RP表示名、TOTP issuerへ適用した。RP IDは従来どおり`ACERVO_PUBLIC_BASE_URL`のhostnameだけから安全に導出し、別RP ID設定は追加していない。hostname変更時は既存パスキーの再登録が必要だが、サイト表示名変更だけでは不要である。
- 変更ファイルは`.env.production.example`、`accounts/adapters.py`、`accounts/enrollment.py`、`accounts/models.py`、`accounts/security.py`、`accounts/services.py`、`accounts/management/commands/bootstrap_admin.py`、migration、設定、表示context、テスト、文書。Compose、Caddy、DNS、Cloudflare Tunnel、本番公開は変更していない。実装コミットは`c399eee`。
- Step 7A最終検証はGitHub Actions run 35101803167で全成功。PostgreSQL 18の全225件、Ruff、Django check、migration差分なし、本番／Cloudflare Compose設定、Caddy、イメージ、全サービスhealthy、UID 10001、`check --deploy`、クライアントIP信頼境界、Web・DBポート非公開、DB・写真永続化を確認した。次の7B開始条件は、この検証済みHEADを基準にTunnel専用の公開境界だけを分離し、DNS・実Tunnel・本番公開を混在させないことである。
- Step 7A-SPECとして、Acervoを1インスタンス＝1組織の汎用セルフホスト型標本管理システムとして文書上明確化した。学校・生物班の回生／年度方式、`kdf-biology.org`、Cloudflare Tunnel、Tailscaleは導入例へ分離し、マルチテナント、Symbiota連携、公式サイト・Wiki・メール運用を現在要件から除外した。コード、migration、設定、Compose、Caddy、CI、認証処理は変更していない。
- Step 7A-SPECの文書コミットは`8eededc122661b98de352cc7ac2145841380fd84`。ローカルでRuff、Django check、migration差分なし、SQLite全214件、Markdownリンク、`git diff --check`が成功し、GitHub Actions run 35099967154でPostgreSQL 18全214件と既存の本番／Cloudflare Compose・Caddy・イメージ・healthy・UID 10001・信頼境界・非公開ポート・永続化検証が全成功した。実ドメイン、Tunnel専用構成、同期パスキー、Chrome以外の実運用対象ブラウザは未確認のまま維持する。
- Step 7A-SPECで、現行Userの`cohort_number` NULL不可・正数DB制約、2026年度／31回生／4月1日固定の在籍判定、作成サービス・`bootstrap_admin`・関連テストへの依存を確認した。これらを在籍判定なしと学校回生方式から選べるようにする実装は、既存データ移行・後方互換性・管理者影響を伴う未着手のStep 7Aへ分離した。
- 生物班環境の確定事実として、`kdf-biology.org`はXserverドメインで登録しCloudflare Free DNSはActiveだが、公開サービス用DNSレコードは未設定。Dell Precision 3630（Xeon E-2186G）上のProxmox VEをTailscale経由で管理しており、Acervoの候補URLは`https://acervo.kdf-biology.org`だが最終確定・公開は未実施。SymbiotaはDebian 12／Apache／MariaDB／PHPで管理者ログインまで確認した非稼働検証環境で、Acervoと共有DB・認証・session・ファイル領域を持たない。
- Step 6C-Rとして、`STATUS.md`の現在状態と過去時点の履歴を整合し、READMEの緊急コマンド例をシェル安全な`ADMIN_USERNAME`プレースホルダーへ変更した。コマンド後に既存パスワードでログインし、MFA未登録では管理画面を拒否し、新TOTP再認証後だけ管理画面を許可する実フローを追加した。監査失敗時のsessionロールバック、`must_change_password`・password hash等の不変性、秘密値非混入も補強した。
- Step 6C-Rでコマンド専用テストを8件へ拡張し、Step 6関連62件、SQLite全214件、PostgreSQL 18全214件が成功した。GitHub Actions run 35089008341では、本番イメージ内の`python manage.py help reset_admin_mfa`が非破壊で成功し、username位置引数と緊急用途を確認した。本番／Cloudflare Compose、Caddy、本番イメージ、全サービスhealthy、UID 10001、非公開ポート、IP信頼境界、`/health/`・静的ファイル、`/admin/`遮断、DB・写真永続化も成功した。
- Step 6Cとして、緊急復旧専用の`python manage.py reset_admin_mfa <username>`とHTTP非依存サービスを追加した。対象は有効なadminかつAuthenticator保持者に限り、別の有効・初回変更済み・primary MFA保持adminがいる場合は通常の管理画面を案内して拒否する。確認文字列`RESET <username>`の一致、空入力・EOF拒否を必須とし、無確認実行経路は提供しない。
- コマンド用サービスはadmin行を主キー順でロックし、対象Authenticator・対象session削除、`mfa_reset_at`更新、actor NULL／`server-operator`スナップショットのコマンド用AuditLog一件作成を同一トランザクションで実行する。パスワード、role、有効状態、初回変更フラグ、新しい秘密・Recovery Codesは変更・出力・監査しない。AuditLog actionは`command_mfa_reset`へ正式化した。
- Step 6C専用6件を追加し、最後のadminの成功、全Authenticator・session削除、確認不一致・EOF、対象拒否、別admin条件、二重実行、監査失敗ロールバックを確認した。SQLite全212件、PostgreSQL 18全212件、Ruff、Django check、migration差分なし、本番相当`check --deploy`、本番／Cloudflare Compose、Caddy adapt／validate、本番イメージ、全サービスhealthy、UID 10001、非公開ポート、IP信頼境界、Caddy経由`/health/`・静的ファイル、`/admin/`遮断、DB・写真永続化がGitHub Actions run 35086332954で成功した。Step 7、role変更、無効化、最後の管理者の降格・無効化保護、監査ログ閲覧は未着手である。
- Step 6B-Rとして、MFAリセット検索・確認画面専用の共通messages partialを追加し、成功・fail-closedエラーを日本語で一回だけ表示するよう補正した。`aria-live`、HTML escape、既存の白・黒・グレー中心の表示を維持し、base全体や他のMFA画面には波及させていない。
- Step 6B-Rではallauthの実TOTP再認証view・フォーム・session・認証記録を通す成功／失敗テストと、WebAuthn再認証view・form・session・redirectを通す限定mock成功／失敗テストを追加した。再認証後は確認GETへ戻るだけで本文を再送せず、改めてPOSTした場合だけサービス層を実行する。実フローで判明したallauthのWebAuthn再認証method ID（`mfa_reauthenticate:webauthn`）を許可するよう補正した。
- Step 6B関連テストは22件、SQLite全206件、PostgreSQL 18全206件が成功。Ruff、Django check、migration差分なし、本番相当`check --deploy`、本番／Cloudflare Compose、Caddy、本番イメージ、全サービスhealthy、UID 10001、非公開ポート、クライアントIP信頼境界、DB・写真永続化をGitHub Actionsで確認した。当時はStep 6Cのサーバー管理コマンドが未着手だったが、現在はStep 6Cまで完了している。role変更、無効化、最後の管理者保護、監査ログ閲覧、その他の管理操作は引き続き未着手である。
- Step 6Bとして、`/management/mfa-reset/`のusername完全一致検索と`/management/users/<user_id>/mfa-reset/`の確認・実行画面を追加した。中央管理MFAゲートに加え、実行POST直前にTOTPまたはWebAuthnの直近再認証を必須とし、古いPOST本文を保存・再送せず、固定した内部確認GETへ戻す。確認チェックとPOST時点のusername完全一致も必須とした。
- UIは認証器の一般種別だけを表示し、秘密値、credential、challenge、session、パスワード等を表示・保存しない。実行はStep 6Aの`reset_user_mfa_by_admin()`だけを経由し、対象sessionの無効化、`mfa_reset_at`更新、監査ログ1件作成をサービス層のトランザクションへ委譲する。二重POSTは対象MFAなしの安全な業務エラーとなり、監査ログを増やさない。
- Step 6B専用テスト16件を追加し、管理ゲート、完全一致検索、CSRF、確認不備、username変更、自己対象、TOTP／WebAuthn再認証、外部nextを受け取らない固定遷移、fail-closed、対象sessionだけの無効化、監査ログ一回性、対象属性、実行直前のactor状態再検査、秘密値非表示を確認した。当時はStep 6Cのサーバー管理コマンドが未着手だったが、現在はStep 6Cまで完了している。role変更、無効化、最後の管理者保護、監査ログ閲覧、その他の管理操作は引き続き未着手である。
- Step 6B実装コミット `9a699959151b4e1e3ad6d7a7da3555fd2287ed65` はGitHub Actions run 34976164456で全成功した。PostgreSQL 18の全200テスト、Ruff、Django check、migration差分なし、本番`check --deploy`、本番／Cloudflare Compose、Caddy adapt／validate、本番イメージ、`db`・`web`・`proxy` healthy、Web UID 10001、Caddy経由応答、専用クライアントIP信頼境界、Web 8000番・DB 5432番のホスト非公開、DB・写真永続化を確認した。
- Step 6Aとして、`mfa_reset_at` nullable日時フィールドとmigration、追記専用の`audit.AuditLog`、HTTP非依存の別管理者MFAリセットサービスを追加した。サービスはactor／targetを主キー順で行ロックし、actorの有効状態・Acervo admin role・初回パスワード変更・primary MFA・本人以外を再検証してから、対象の全Authenticator削除、時刻更新、対象Django session無効化、監査記録1件を同一トランザクションで実行する。
- AuditLogは発生日時、操作種別、実行経路、actor／target FKとusernameスナップショットだけを持ち、秘密値・credential・challenge・session／Cookie・任意本文・汎用JSONを保存しない。通常のinstance更新・削除は拒否し、Django `/admin/`へは登録していない。
- Step 5のセッションMFA判定は`mfa_reset_at`以前の記録、欠損・bool・不正・無限大・未来の時刻をfail closedで拒否するよう補強した。リセット後に新たなprimary MFAを登録しても旧記録は再利用できず、リセット後に正当に作成されたMFA記録は許可する。session削除だけへ安全性を依存しない。
- Step 6A関連17件、SQLite全184件、PostgreSQL 18全184件、Ruff、Django check、migration差分なし、本番`check --deploy`、本番／Cloudflare Compose、Caddy、本番イメージ、全サービスhealthy、UID 10001、非公開ポート、クライアントIP信頼境界、Caddy経由応答、DB・写真永続化が成功した。当時はStep 6Bのリセット画面・直近再認証および6Cの最後の管理者向け管理コマンドは未着手だったが、現在はStep 6まで完了している。
- Step 5Cとして、実際のallauthログインステージ、MFAフォーム、再認証、session、Authenticator DB、Step 5Aポリシー、Step 5B中央ゲートを通す専用統合テスト13件を追加した。TOTP、未使用Recovery Code、WebAuthn第二要素、passwordlessパスキー、TOTP／WebAuthn再認証の成功から`/management/`までを確認し、WebAuthnは既存方針どおりブラウザ認証器の暗号検証境界だけを限定mockした。
- Recovery Codeの一回消費と再利用拒否、Recovery Codesだけのadmin拒否、パスワードのみの未完了セッション、MFA失敗・中止・レート制限、ログアウト・新規セッション・Cookie消失、role降格・無効化・初回パスワード変更要求・最後のprimary MFA削除の次リクエスト反映を統合確認した。`is_staff`／`is_superuser`のmemberと卒業生memberは拒否し、既存方針どおり卒業生adminは必要条件を満たせば許可した。
- allauth adapterが利用可能なMFA再認証方法を返さない場合も500にせず、入力本文や外部`next`を保存・再送せず、日本語案内付きMFA設定画面へfail closedで戻すよう中央ゲートを補強した。既存の全HTTP method、未作成管理URL、内部`next`、キャッシュ禁止のテストと合わせて管理経路の迂回不能を確認した。
- Step 5CのSQLite全174件、PostgreSQL 18全174件、Ruff、Django check、migration差分なし、本番`check --deploy`、本番／Cloudflare Compose、Caddy、本番イメージ、全サービスhealthy、UID 10001、非公開ポート、クライアントIP信頼境界、Caddy経由応答、DB・写真永続化が成功した。Step 5完了時点ではStep 6は未着手だったが、現在はStep 6Aまで完了している。
- Step 5Bとして、`/management`、`/management/`、`/management/`配下の全HTTP methodへStep 5Aの`evaluate_management_access()`を適用する中央middlewareを追加した。許可時を含む管理応答にはキャッシュ禁止を付与し、role・active・初回パスワード・primary MFA・現在セッションのMFAをリクエストごとに再評価する。独自の管理許可フラグや拒否POSTの保存・再送は行わない。
- 未認証は内部`next`付きログイン、member／inactiveは詳細を出さない日本語403、初回パスワード変更未完了は既存変更画面、primary MFA未設定は日本語案内付きMFA設定、セッションMFA未完了は利用可能なallauth MFA再認証へ誘導する。TOTPまたはRecovery Code入力とWebAuthnだけの構成を区別し、パスワード再認証へ落ちるループを避けた。
- `/management/`へusername、将来追加予定の案内、MFA設定、通常画面、POSTログアウトだけを持つ最小トップを追加した。全ログイン利用者に「セキュリティ設定」、`role=admin`には利便性の「管理」リンクを追加したが、認可は中央ゲートのみが担う。Django `/admin/`へのリンクや管理操作本体は追加していない。
- Step 5B単体の完了時点では中央ゲートと最小入口までで、Step 5Cの統合検証は後続として未着手だった。現在はStep 5Cまで完了しているが、role変更、無効化、最後の管理者保護、管理者MFAリセット、監査ログ、ユーザー管理は未実装で、一般memberのMFAは引き続き任意である。
- Step 5Aとして、管理アクセスの許可条件（認証済み、有効、`role=admin`、初回パスワード変更済み、TOTPまたはWebAuthnのprimary MFAを保持、現在セッションでMFA認証済み）と、各拒否理由を再利用可能なサーバー側ポリシーとして実装した。`is_staff`、`is_superuser`、独自セッションフラグには依存しない。
- primary MFAは現在のAuthenticator DBを判定ごとに参照し、Recovery Codesだけでは設定済みとしない。セッションMFAはallauth標準の認証記録を参照し、TOTP、WebAuthn第二要素、passwordlessパスキー、Recovery Code、MFA/WebAuthn再認証を受理する。パスワードのみ、不明・欠損・signup用の記録は拒否する。
- Step 5Aは判定ポリシーだけを実装し、redirect、403、middleware、案内画面、`/management/`への強制適用をStep 5Bへ分離した。中央適用と案内は現在Step 5Bで完了しているが、role変更、最後の管理者保護、管理者MFAリセット、監査ログは後続作業であり、一般memberの任意MFA運用は変更していない。
- Sub-step 4Dとして、Windows Hello と実ブラウザで、パスキー登録（端末内パスキー）、パスワードレスログイン、パスワード後のWebAuthn第二要素、パスキー再認証、リカバリーコード一回性・再生成・保存確認・離脱警告、端末名変更、削除確認・削除、削除済みパスキーのログイン拒否を受入確認した。リカバリーコード、credential、challenge、パスワードは記録していない。
- 実ブラウザで `localhost` のパスキーが `127.0.0.1` から使用できず一般エラーとなること、再認証の安全な内部 `next` は `/health/` へ遷移し、外部 `next` はホームへフォールバックすることを確認した。
- ローカル開発ではCaddyを経由しないため `ALLAUTH_TRUSTED_CLIENT_IP_HEADER` を無効化し、直接ログインPOSTが403にならないことを統合テストで固定した。本番の専用IPヘッダー信頼境界は変更していない。
- パスキーログインボタンをWebAuthnフォームに関連付け、Windows Helloが起動するよう修正。WebAuthnの中止・失敗表示を「パスキーまたはセキュリティキー」に統一し、認証コード・認証器という不適切な用語を避けた。ブラウザの旧静的資産を読み込まないよう、WebAuthn UIスクリプトのURLにリビジョン指定を付与した。
- Recovery Codes画面では、保存確認前にリンクで離脱しようとした場合も確認ダイアログを表示するよう補強した。タブを閉じる・再読み込みする場合の `beforeunload` 警告は維持している。
- 受入後、利用者がダウンロード済みの使い捨てリカバリーコードファイルとWindows上のテスト用パスキーを削除したことを確認した。開発サーバーを停止し、使い捨てユーザーのみを含むローカルSQLite DB、受入専用ローカル設定、検証ログを削除した。既存ユーザーと既存開発DBは変更していない。

- Sub-step 4Cとして、`mfa_login_webauthn`だけを明示公開。パスキー専用ログイン画面入口、標準allauth JavaScript、never-cache、passwordless credential用途確認を追加。signup／Trust browserは非公開のまま維持

- Sub-step 4C-Testとして、`accounts/tests/test_mfa_passkey_login.py` を追加。固定RP ID・user verification必須のrequest options、専用IPに基づく共有レート制限、passwordless用途のTrue/False/None、userHandle・inactive user・safe next・初回パスワード変更ゲート、認証記録、TOTP/Recovery Codes/パスワードログインの回帰をHTTP統合テストで確認した。ローカルSQLiteのaccountsテスト135件、全体138件が成功した。
- Sub-step 4C-Testの実装コミット `1b0af8c3389aa07660cbea7e5082b51640a2510b` はGitHub Actions run 34834929920で全成功。PostgreSQL 18の全138テスト、Ruff、Django check、migration差分なし、およびproduction／Cloudflare Compose、Caddy、イメージ、healthy、UID 10001、非公開ポート、DB・写真永続化を確認した。これをもってSub-step 4Cを完了とする。
- `AcervoLoginWebAuthnForm` の独自オーケストレーションでも、allauth標準の失敗回数消費後に返る `too_many_login_attempts` を既存の日本語 `rate_limited` へ正規化する共通ヘルパーを適用。用途外credential（False/None）は失敗回数を解除しない。
- ログイン画面はパスキーログインPOST後の一般的な日本語エラーを表示し、credential JSONは再表示しない。パスキーボタンも既存の二重操作防止対象へ加えた。

- Sub-step 4Bとして、allauth 65.19.3の個別WebAuthn viewだけを明示的に公開し、一覧・追加・名称変更・削除・WebAuthn再認証・ログイン時第二要素を追加。passwordless login、signup、Trust browser URLは非公開のまま維持
- 4B-R2として`accounts/tests/test_mfa_webauthn.py`を8件へ拡張。challenge stateの保存、成功時消去、再利用拒否、passwordless/第二要素のregistration option、WebAuthn再認証の通常MFA記録・外部next拒否を追加確認
- 4B-R3AとしてWebAuthn専用フォームを追加し、allauth標準の検証・レート制限を変更せず、認証失敗だけを既存の日本語一般エラー／`rate_limited`表示へ正規化。第二要素失敗時にcredential hidden fieldを再表示しないこと、never-cache、未ログイン維持を統合テストで確認
- 4B-R3Bとして認証challenge stateの成功時消去・再利用拒否・現在ユーザーのAuthenticator解決を追加確認。WebAuthn第二要素の共有レート制限と専用IP境界も確認し、失敗／制限応答にcredential JSONを再表示しない`SensitiveCredentialInput`を追加
- 自動テストのWebAuthn成功経路では、ブラウザ認証器が出力するattestation/assertionのparse・署名検証とFido2Server完了境界だけを`autospec`付きでmockし、allauth view・フォーム・login stage・session・Authenticator DB・Recovery Codes連携・MFA認証記録は実行。補助的に無効な保存credentialを解析しないため`get_credentials`と表示用`Authenticator.wrap`を限定mockする。4B時点で4Dへ残した実ブラウザの署名とOrigin/RP不一致確認は、現在は`localhost`で受入済み
- パスキー登録の日本語UI、標準WebAuthn JavaScript、機能検出・一般的なaria-liveエラー、二重送信防止、全WebAuthn管理画面のnever-cacheを追加。秘密鍵、生体情報、challenge、credential JSONを独自に保存・表示しない
- `MFA_SUPPORTED_TYPES`へ`webauthn`を追加。登録用のpasswordless選択肢を有効にする設定は追加したが、パスワードレスログインURLはallowlist外のためStep 4Cまで利用できない

- Sub-step 4Aとして、`ACERVO_PUBLIC_BASE_URL`を唯一の情報源にして小文字のhostnameをWebAuthn RP IDへ固定し、RP表示名を`Acervo`へ固定。リクエストの`Host`、`X-Forwarded-Host`、`X-Forwarded-For`はRP IDの決定に使わない
- 本番起動時に公開URLのHTTPS、DNS hostname、認証情報・query・fragment・subpath不在、IP／localhost拒否、`DJANGO_ALLOWED_HOSTS`完全一致、`DJANGO_CSRF_TRUSTED_ORIGINS`完全Origin一致をfail-fastで検証。allauth／python-fido2標準のOrigin検証は緩和していない
- `MFA_PASSKEY_SIGNUP_ENABLED=False`を明示し、`MFA_SUPPORTED_TYPES=["recovery_codes", "totp"]`、`MFA_PASSKEY_LOGIN_ENABLED=False`、WebAuthn URL非公開、Trust browser無効を維持
- `accounts/tests/test_deployment_config.py`へ、RP IDのport除外・header偽装非依存・表示名、開発用localhost、本番公開Origin設定の失敗経路を追加。既存TOTP／Recovery Codes／ログイン時MFAの回帰テストも実行
- Sub-step 3Dレビュー指摘対応として、MFAログインステージの制限到達時に利用者へ一般的な日本語メッセージと `rate_limited` エラーコードを返す表示契約を追加。allauth標準の制限消費・解除・照合は変更していない
- `accounts/tests/test_mfa_authenticate.py` を補強し、同一専用IPでX-Forwarded-Forだけを変えてもMFA制限を回避できないこと、入力コードとRecovery Codeがレスポンス・セッション・DBへ残らないこと、正しいMFA成功後にallauth標準の失敗回数解除が働くことを検証
- `mfa_authenticate` だけを明示的allowlistへ追加し、django-allauth標準のログインステージでTOTPまたは未使用Recovery Codeを検証してからログインを確立する縦断フローを実装
- 日本語の認証画面、CSRF付きPOST中止、一般的な不正コードメッセージ、入力済み認証コードをエラー応答へ再表示しない入力欄を追加。照合・使用済み更新・レート制限・ログインステージはallauth標準実装を維持
- Step 4までの一時的機能ゲートとして `MFA_SUPPORTED_TYPES` から `webauthn` を除外し、`MFA_PASSKEY_LOGIN_ENABLED=False` を設定。`mfa_trust` と全WebAuthn URLは引き続きNoReverseMatch/404
- `accounts/tests/test_mfa_authenticate.py` でMFA未登録・Recovery Codesのみの通常ログイン、TOTP/Recovery Code成功・失敗・一回性、safe/external next、キャンセル、CSRF、never_cache、専用クライアントIP境界、無効ユーザー、初回パスワード変更順序、認証記録をHTTP統合テストで確認
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

- 7C-LIVE-AのVM201復元受入の残件整理。VM201の試験用コンテナは停止済みで、元設定へ復帰した。7C-LIVE-Aは未完了。

## Remaining

- 本番公開hostnameは`specimens.kdf-biology.org`。Cloudflare route/DNS、HTTPS応答、HTTPからHTTPSへの転送、管理者のパスキー直接ログインと管理トップ表示は確認済み。対象外の端末・ブラウザ、同期パスキーの受入範囲は未確認である。
- 公開設定、責任者、バックアップ運用、受入端末は運用者が確定・承認済み。担当者・秘密値・端末の詳細は公開リポジトリに記録しない。
- 署名付き暗号化バックアップの別ホスト保存とVM201への独立した空環境復元は成功した。別ホストの保持規則・容量監視・Discord失敗通知も手動で動作確認済み。VM201の復元データを用いたDjangoビューのパスワードログイン・TOTP・管理トップ・ログアウト後拒否、再起動後のDB・写真用ボリューム永続化は確認済み。別ホストの保存物3ファイルをVM201へ直接ストリームして復元済み搬入物とのバイト一致も確認したが、元の復元入力はVM200から搬入した。印刷したage秘密鍵控えと修正済みデジタル控えは非表示入力で一致を確認した。VM201の実ブラウザ／HTTPS経路での認証と四半期ごとの定期復元試験予定は未確認。標本・保護写真の実データ復元受入は機能実装後の7C-LIVE-Bに残る。
- 公開HTTPSではRecovery Codes生成、TOTP認証、パスキー登録と直接ログインを確認済み。「すべてコピー」、ローカルBlob保存、保存確認前の離脱警告、パスキー削除、同期パスキーとChrome以外の実運用対象ブラウザは未確認（`localhost`のWindows＋Chrome＋Windows Hello受入は完了）。
- Phase 1Dの利用者作成、role変更、有効状態変更、最後の有効admin保護、一時パスワード再発行と最小監査はローカル実装済み。年度切替の後継警告、監査ログ閲覧、PostgreSQL上の並行更新、production Compose、実ブラウザ受入は未実施。7C-LIVE-A、7C-LIVE-B、Phase 1全体はいずれも未完了。

## Tests

### ローカル

- Step 7A実装後: `python manage.py test --settings=config.settings.test`: 成功（SQLite、225件全成功）。在籍ポリシー（none／school_cohort）、同期・非同期manager、作成サービス、`bootstrap_admin`、設定fail-fast、既存回生保持とNULLデータがある逆migration拒否を追加確認した。Ruff lint／format、Django check、migration差分なし、`git diff --check`、ランダムな一時設定値を用いる本番相当`check --deploy`は成功。ローカルDocker CLIはないためCompose・Caddy・コンテナ検証は未実行で、push後の既存CIで確認する。
- Step 6A実装／本番修正後: `python manage.py test accounts.tests.test_mfa_reset accounts.tests.test_management_access --settings=config.settings.test`: 成功（関連17件全成功）。`python manage.py test --settings=config.settings.test`: 成功（SQLite、184件全成功）。`ruff check .`、`ruff format --check .`、`git diff --check`、`python manage.py check --settings=config.settings.test`、`python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功。実行用の一時本番設定による`python manage.py check --deploy`: 成功（警告なし、0 silenced）。ローカルDocker検証はDocker CLIが存在しないため実行せず、GitHub Actionsで確認した。
- Step 5C実装コミット: `python manage.py test management_portal --settings=config.settings.test`: 成功（Step 5C専用13件を含む25件全成功）。`python manage.py test --settings=config.settings.test`: 成功（SQLite、174件全成功）。
- Step 5C実装コミット: `ruff check .`、`ruff format --check .`、`git diff --check`、`python manage.py check --settings=config.settings.test`: 成功。`python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（migration差分なし）。本番相当設定の`python manage.py check --deploy`: 成功（警告なし、0 silenced）。ローカルDocker検証はDocker CLIが存在しないため実行せず、同一実装HEADのGitHub Actionsで完了した。
- Step 5B作業ツリー: `python manage.py test management_portal --settings=config.settings.test`: 成功（専用12件全成功）。`python manage.py test accounts.tests.test_management_access --settings=config.settings.test`: 成功（Step 5A専用7件全成功）。`python manage.py test accounts --settings=config.settings.test`: 成功（accounts 146件全成功）。`python manage.py test --settings=config.settings.test`: 成功（SQLite、161件全成功）。
- Step 5B作業ツリー: `ruff check .`、`ruff format --check .`、`git diff --check`、`python manage.py check --settings=config.settings.test`: 成功。`python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（migration差分なし）。本番相当設定の`python manage.py check --deploy`: 成功（警告なし、0 silenced）。
- Step 5A作業ツリー: `python manage.py test accounts.tests.test_management_access --settings=config.settings.test`: 成功（専用7件全成功）。`python manage.py test accounts --settings=config.settings.test`: 成功（accounts 146件全成功）。`python manage.py test --settings=config.settings.test`: 成功（SQLite、149件全成功）。
- Step 5A作業ツリー: `ruff check .`、`ruff format --check .`、`git diff --check`、`python manage.py check --settings=config.settings.test`: 成功。`python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（migration差分なし）。本番相当設定の`python manage.py check --deploy`: 成功（警告なし、0 silenced）。
- `ruff check .`: 成功
- `ruff format --check .`: 成功（53ファイル）
- `python manage.py check --settings=config.settings.test`: 成功
- `python manage.py makemigrations --check --dry-run --settings=config.settings.test`: 成功（差分なし）
- `python manage.py test accounts.tests.test_mfa_urls --settings=config.settings.test`: 成功（11件全成功）
- `python manage.py test accounts.tests.test_mfa_totp --settings=config.settings.test`: 成功（12件全成功）
- `python manage.py test accounts.tests.test_mfa_recovery_codes --settings=config.settings.test`: 成功（6件全成功）
- `python manage.py test accounts.tests.test_mfa_authenticate --settings=config.settings.test`: 成功（12件全成功）
- `python manage.py test accounts.tests --settings=config.settings.test`: 成功（112件全成功）
- `python manage.py test --settings=config.settings.test`: 成功（SQLite、119件全成功）
- Sub-step 4D最終作業ツリー: `python manage.py test --settings=config.settings.test`: 成功（SQLite、142件全成功）。`ruff check .`、`ruff format --check .`、`git diff --check` も成功。WebAuthn失敗表示・直接開発ログイン・パスキーボタンフォーム関連付け・Recovery Codes離脱警告の追加テストを含む。
- Step 4B作業ツリー: `python manage.py test --settings=config.settings.test`: 成功（SQLite、119件全成功）、`ruff check .`／`ruff format --check .`／`python manage.py check --settings=config.settings.test`／`makemigrations --check --dry-run`: 成功。production設定の`check --deploy`: 警告なしで成功
- Step 4BのPostgreSQL 18、本番Compose・Cloudflare追加Compose、Caddy、本番イメージ・コンテナ検証: このローカル環境ではDocker CLIが利用できないため未実行。push後のGitHub Actionsで確認予定
- 本番相当設定での `python manage.py check --deploy`: 成功（警告なし、0 silenced）
- ローカルDocker検証: 未実行（このWindows環境にDocker CLIが存在しないため）。Sub-step 4A HEADのGitHub Actionsで本番コンテナ検証を実行し、全項目成功

### GitHub Actions

- Phase 1C Step 6B実装HEAD `9a699959151b4e1e3ad6d7a7da3555fd2287ed65`: run 34976164456（`test`、`production-container` 全成功）。PostgreSQL 18の全200テスト、Ruff、Django check、migration差分なし、本番／Cloudflare Compose、Caddy adapt／validate、本番イメージ、`db`・`web`・`proxy` healthy、Web UID 10001、`check --deploy`、Caddy経由応答、専用クライアントIP信頼境界、Web 8000番・DB 5432番のホスト非公開、DB・写真永続化を確認
- Phase 1C Step 6A本番修正HEAD `e9e4172e76272e86bf2e6c144fc7630a1cedb6b6`: run 34974094232（`test`、`production-container` 全成功）。PostgreSQL 18の全184テスト、Ruff、Django check、migration差分なし、本番／Cloudflare Compose、Caddy adapt／validate、本番イメージ、`db`・`web`・`proxy` healthy、Web UID 10001、`check --deploy`、Caddy経由の`/health/`・静的ファイル200、`/admin/` 404、未認証`/management/`の同一Originログインredirect、専用クライアントIP信頼境界、Web 8000番・DB 5432番のホスト非公開、DB・写真永続化を確認
- Phase 1C Step 5C実装HEAD `af7b20e908445e2839ca226b3769a8b36564642c`: run 34962199834（`test`、`production-container` 全成功）。PostgreSQL 18の全174テスト、Ruff、Django check、migration差分なし、本番／Cloudflare Compose、Caddy adapt／validate、本番イメージ、`db`・`web`・`proxy` healthy、Web UID 10001、`check --deploy`、Caddy経由の`/health/`・静的ファイル200、`/admin/` 404、未認証`/management/`の同一Originログインredirect、専用クライアントIP信頼境界、Web 8000番・DB 5432番のホスト非公開、DB・写真永続化を確認
- Phase 1C Step 5B実装HEAD `237fbdf5bea32e5f4488403d7f3d2d7a5a7f9ce0`: run 34868855403（`test`、`production-container` 全成功）。PostgreSQL 18の全161テスト、Ruff、Django check、migration差分なし、本番／Cloudflare Compose、Caddy、本番イメージ、全サービスhealthy、UID 10001、Caddy経由の未認証`/management/`同一Originログインredirect、`/admin/` 404、非公開ポート、DB・写真永続化を確認
- Phase 1C Step 5A実装HEAD `0c05ceecf6a0b0ad78a4a317799baa2e4842c1fc`: run 34867040961（`test`、`production-container` 全成功）。PostgreSQL 18.6の全149テスト、Ruff、Django check、migration差分なし、本番Compose／Cloudflare追加Compose、Caddy、本番イメージ、全サービスhealthy、非root実行、`check --deploy`、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Phase 1C Step 4最終HEAD `ff33741f8a3a26a097ac4069f792bba6cfe8c514`: run 34864967629（`test`、`production-container` 全成功）。PostgreSQL 18の全テスト、Ruff、Django check、migration差分なし、本番Compose／Cloudflare追加Compose、Caddy、本番イメージ、全サービスhealthy、非root実行、`check --deploy`、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Phase 1C Sub-step 4B（HEAD: `63e8a86bec1a553621dbf72277c6ccf31c6049b5`）: run 34771093567（`test`、`production-container` 全成功）。PostgreSQL 18上の全119テスト、Ruff、Django check、migration差分なし、本番Compose／Cloudflare追加Compose、Caddy adapt・validate、本番イメージ、全サービスhealthy、UID 10001、`check --deploy`、Caddy経由確認、IP境界、ポート非公開、DB・写真永続化を確認

- Phase 1C Sub-step 4A（HEAD: `dac1fd15c9e65ee8c393775cd4bf3b9a33c8b12c`）: run 34770046419（全ジョブ成功）
- `test` job: PostgreSQL 18.6上で全119テスト、Ruff lint・format、Django system check、migration差分なしを確認
- `production-container` job: 本番ComposeとCloudflare追加Compose、Caddy adapt・validate、本番イメージ、全サービスhealthy、非root・`check --deploy`、Caddy経由のMFA認証URL安全リダイレクト、共有cache table、クライアントIP境界、ポート非公開、DB・写真永続化を確認
- Phase 1C Sub-step 3D（HEAD: `0a48c1faf51f343826d8b89c45bc91af51a86cdc`）: run 34768590542（全ジョブ成功）
- `test` job: PostgreSQL 18.6上で全114テスト、Ruff lint・format、Django system check、migration差分なしを確認
- `production-container` job: 本番ComposeとCloudflare追加Compose、Caddy adapt・validate、本番イメージ、全サービスhealthy、非root・`check --deploy`、Caddy経由でログインステージなしの `/accounts/mfa/authenticate/` が `/accounts/login/` へ302、共有cache table、クライアントIP境界、ポート非公開、DB・写真永続化を確認
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

- run 34973856152: Step 6Aで追加した`audit`アプリをDockerfileへコピーしておらず、本番webが`ModuleNotFoundError`でunhealthyになった。`Dockerfile`へ`COPY audit ./audit`を追加し、run 34974094232で全ジョブ成功。
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
- TOTP、Recovery Codes、WebAuthn第二要素、パスキー登録・管理・パスワードレスログイン、管理アクセス判定、`/management/`中央ゲートと統合・本番相当検証、MFAリセットのサービス層・最小AuditLog、リセット画面・直近再認証、最後の管理者向け管理コマンドは現在すべて完了し、`localhost`のWindows＋Chrome＋Windows Hello実機受入も完了している。実運用HTTPSドメイン等の受入、Step 7、管理操作本体、role変更・最後の管理者保護は未完了。

## Change history

- `accounts/mfa_reset.py`, `accounts/models.py`, `accounts/management_access.py`, `accounts/migrations/0002_user_mfa_reset_at.py`, `audit/`, `Dockerfile`, `accounts/tests/test_mfa_reset.py`, `accounts/tests/test_management_access.py`, `PROJECT_SPEC.md`, `README.md`, `PLAN.md`, `STATUS.md`: Step 6AのMFAリセットサービス、追記専用AuditLog、旧MFA記録失効、本番イメージへの監査アプリ追加、文書整合を追加
- `management_portal/middleware.py`, `management_portal/tests/test_integration.py`, `README.md`, `PLAN.md`, `STATUS.md`: Step 5Cのallauth実フロー統合テスト、再認証方法欠落時のfail-closed補強、Step 5完了実績を追加
- `management_portal/`, `config/settings/base.py`, `config/urls.py`, `templates/base.html`, `templates/mfa/index.html`, `Dockerfile`, `pyproject.toml`, `.github/workflows/ci.yml`, `README.md`, `PLAN.md`, `STATUS.md`: Step 5Bの中央管理ゲート、最小管理トップ、ナビゲーション、理由別応答、キャッシュ禁止、専用テスト、本番Caddy経由redirect検証を追加
- `accounts/management_access.py`, `accounts/tests/test_management_access.py`, `PLAN.md`, `STATUS.md`: Step 5を5A〜5Cへ分割し、Step 5Aの管理アクセス判定ポリシーと専用テストを追加
- `README.md`, `STATUS.md`, `PLAN.md`: Step 4完了、Step 5未着手、実装済みMFA範囲、`localhost`実機受入、実運用HTTPS等の未確認事項を現在状態へ整合
- `PROJECT_SPEC.md`: 白・黒・グレーを基本とする配色、意味のある状態色、フォーカス・コントラスト、Specify 7を参考に留めること、外部デザイン非複製、個人開発で保守しやすいUI方針を追加
- `config/settings/development.py`: 直接開発サーバーではCaddy専用クライアントIPヘッダーを要求しない設定を追加
- `accounts/forms.py`: WebAuthn失敗時だけをパスキー／セキュリティキー用の一般エラーへ正規化
- `templates/account/login.html`, `templates/mfa/authenticate.html`, `templates/mfa/webauthn/reauthenticate.html`, `templates/mfa/webauthn/edit_form.html`, `static/js/webauthn-ui.js`: パスキーボタンのフォーム関連付け、エラー文言の統一、静的資産リビジョン指定を追加
- `templates/mfa/recovery_codes/index.html`: 保存確認前のリンク離脱にも確認ダイアログを追加
- `accounts/tests/test_authentication.py`, `accounts/tests/test_deployment_config.py`, `accounts/tests/test_mfa_passkey_login.py`, `accounts/tests/test_mfa_recovery_codes.py`, `accounts/tests/test_mfa_webauthn.py`: Step 4Dで判明した開発直結・WebAuthn失敗表示・フォーム関連付け・離脱警告の回帰テストを追加

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
