# Project Status

最終更新: 2026-09-27

## Current Task

Phase 1C Step 6、Step 7A-SPEC、Step 7A、Step 7A-R2、Step 7B、Step 7C-DOC、Step 7C-DOC-R、Step 7C-LICENSE、Phase 10A（バックアップ・復元の先行部分）を完了。導入先ではバックアップの実機設定、空データ復元試験、初回timer起動、暗号化バックアップ作成・別ホスト保存確定、停止要求後のバックアップ機へのネットワーク非応答を確認した。Step 7C-LIVEの承認パッケージと実ドメイン受入、Phase 1全体は未完了。

## 2026-09-27 初回定時実行の確認

運用者から主Proxmoxホストと本番候補VMの`systemctl list-timers`／`systemctl show`の実機出力を受領した。起動timerは17:55:20 JST、バックアップtimerは18:00:04 JSTに起動し、両serviceとも`Result=success`、`ExecMainStatus=0`だった。VM側serviceは18:00:07 JSTに終了した。両timerの次回は2026-09-28の17:55／18:00 JST。

VM側`journalctl`の当日分には、PostgreSQL 18を対象とする暗号化バックアップ作成、保持処理`deleted=0`、暗号化payload・metadata・checksumsのSFTP転送、`.ready`送信、`upload_complete`、`offsite_verified`、`shutdown_requested`、service正常終了が記録されていた。backup IDは`acervo-20260927T090005Z-04948a9e7b60`。別ホスト保存先の確定をスクリプトの検証ログで確認した。その後、主Proxmoxホストからバックアップ機のホストIPと保存用LXCのIPへ各2回pingし、どちらも応答0件だった。これは停止要求後の期待状態と整合するが、pingだけで物理的な電源断は断定できない。初回定時バックアップの作成・保存確定と停止要求、停止後のネットワーク非応答は確認済み。実データを使う復元受入は未実施。

同日にバックアップ機のLXC 110を実機確認した。LXCは`running`で、`ssh`と`acervo-finalize-incoming.path`はいずれも`active`だった。保存領域`/srv/acervo-backup`は629 GB中2.2 MB使用、597 GB空き。確定済み成果物は`/srv/acervo-backup/sftp/incoming/acervo-...`へ保存され、finalizeスクリプトは`.ready`、必須3ファイル、SHA-256を検証してからディレクトリを確定する。確認時には4世代が確定済みで、合計72 KBだった。別ホストの自動整理、容量監視、失敗通知は未整備であり、削除は行っていない。手動WOL送信は主Proxmoxホスト側で終了コード0だったが、直後のpingではバックアップ機から応答がなく、手動WOLからの起動成立は未確認である。

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

- なし

## Remaining

- Acervo本番ホスト名は候補の`acervo.kdf-biology.org`であり、最終確定後にDNS変更、実Tunnel接続または直接HTTPSの証明書取得を手動確認する。現時点で公開サービス用DNSレコードはない。
- 本番ホストと管理経路、公開方式、`ACERVO_SITE_NAME`、`ACERVO_ORGANIZATION_NAME`、初期・継続管理者、DNS・Cloudflare・サーバー・バックアップの責任者、バックアップ暗号化・保存先、空環境の復元試験先、実運用対象の端末・OS・ブラウザ・同期パスキープロバイダーは、設計責任者が確定する必要がある。
- Phase 10Aの実装・CI復元試験に加え、導入先ではサーバー外保管、空データ復元試験、手動バックアップと初回定時バックアップの作成・保存確定が確認された。復号identityの保管体制・recipient本数の承認状態、実データを使う復元受入、四半期ごとの定期復元試験は未確認または未実施である。別ホスト保存先の保持・削除ルール、失敗通知、容量監視も未整備である。
- 公開環境を用意した後、実運用HTTPSドメインでRecovery Codes初回表示の「すべてコピー」、ローカルBlobによるファイル保存、保存確認前の離脱警告、端末内・同期パスキーの登録・ログイン・削除を確認する。同期パスキーとChrome以外の実運用対象ブラウザも未確認（`localhost`のWindows＋Chrome＋Windows Hello受入は完了）。
- 後続Phaseのrole変更、最後の管理者の降格・無効化保護、管理操作本体、監査ログ閲覧は未着手。Step 7CのDNS変更、実Tunnel作成・token投入、実ドメイン公開、実証明書・実HTTPS受入も未着手。

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
