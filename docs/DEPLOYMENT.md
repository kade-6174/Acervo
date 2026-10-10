# Acervo 導入マニュアル

この文書は、任意の組織がAcervoを自分たちのLinuxホストへ導入するための汎用手順です。別途記載があるものを除き、kade_6174が権利を有するAcervo固有のコード、文書、設定例は[Apache License 2.0](../LICENSE)で公開します。第三者のコード、静的資産、依存パッケージ、コンテナ基盤には各元のライセンスが適用されるため、[第三者ライセンスと通知](../THIRD_PARTY_NOTICES.md)も確認してください。MVPでは**1インスタンスを1組織**が運用します。複数組織を同居させるマルチテナント機能は対象外です。

具体的な導入例は[生物班向け導入・運用例](examples/KDF_BIOLOGY.md)を参照してください。これは製品要件ではありません。

## 前提条件

- x86-64またはARM64のLinuxホスト、Docker Engine、Docker Compose
- 導入者が管理する公開URL。例: `https://acervo.example.org`
- 直接HTTPSを選ぶ場合は、公開URLのDNSをホストへ向け、80/tcp・443/tcp・443/udpをCaddyへ到達可能にする手段
- Cloudflare Tunnelを選ぶ場合は、導入者自身のCloudflareアカウントとTunnel。CloudflareとTailscaleはいずれもAcervoの必須依存ではありません。

パスキーのWebAuthn RP IDは`ACERVO_PUBLIC_BASE_URL`のhostnameから導出されます。公開hostnameは最初のパスキー登録前に確定してください。hostnameを変更すると既存パスキーの再登録が必要になり得ます。サイト表示名の変更だけでは不要です。

## 設定ファイル

`.env.production.example`をコピーして、ホスト上だけに`.env.production`を作成します。運用ユーザー以外が読めない権限にしてください。

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

次の値は導入先ごとに設定します。公開URL、許可Host、CSRF Originのhostname／Originは一致させます。直接HTTPSでは`ACERVO_DOMAIN`も同じhostnameにします。

```ini
ACERVO_PUBLIC_BASE_URL=https://acervo.example.org
DJANGO_ALLOWED_HOSTS=acervo.example.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://acervo.example.org
ACERVO_DOMAIN=acervo.example.org

ACERVO_SITE_NAME=導入先サイト表示名
ACERVO_ORGANIZATION_NAME=導入先組織名
```

`DJANGO_SECRET_KEY`、`POSTGRES_PASSWORD`、`ACERVO_MFA_FERNET_KEYS`には、インスタンスごとに生成した長いランダム値を設定します。これら、Tunnel token、管理者パスワード、Recovery CodesをGit、ログ、コマンド履歴、公開チケットへ残してはいけません。

### 在籍ポリシー

一般組織・研究団体・個人利用など、学校回生を使わない導入先は次を選びます。

```ini
ACERVO_ENROLLMENT_POLICY=none
```

学校回生方式は`school_cohort`です。基準年度に1年生である回生を指定します。3年生基準へ読み替える設計はありません。

```ini
ACERVO_ENROLLMENT_POLICY=school_cohort
ACERVO_SCHOOL_YEAR_START_MONTH=4
ACERVO_SCHOOL_YEAR_START_DAY=1
ACERVO_BASE_SCHOOL_YEAR=2026
ACERVO_BASE_FIRST_YEAR_COHORT=33
```

旧`ACERVO_BASE_THIRD_YEAR_COHORT`は禁止されています。本番環境に残すと起動時に拒否されるため、削除して`ACERVO_BASE_FIRST_YEAR_COHORT`へ移行してください。`school_cohort`では4つの学校方式変数がすべて必須です。

## 公開方式を一つ選ぶ

`compose.production.yaml`はホスト公開ポートを持たない共通基盤で、**単独では起動しません**。以下のoverlayを一つだけ重ねます。同時指定はしません。

### 直接HTTPS（標準）

直接HTTPSはCloudflare資格情報を必要としません。Caddyだけが80/tcp、443/tcp、443/udpをホストへ公開し、証明書を取得・更新します。`web:8000`と`db:5432`はCompose内部だけで利用します。

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml config --quiet
docker compose -f compose.production.yaml -f compose.direct.yaml build
docker compose -f compose.production.yaml -f compose.direct.yaml up -d
docker compose -f compose.production.yaml -f compose.direct.yaml ps
```

### Cloudflare Tunnel専用（任意）

Tunnel専用では、`proxy`、`web`、`db`、`tunnel`のいずれもホスト公開ポートを持ちません。TunnelのオリジンはCompose内部の`http://proxy:8080`です。Caddyはこの構成で公開証明書やACMEを起動しません。

Tunnelを使う場合だけ、`.env.cloudflare.example`から`.env.cloudflare`を作り、権限を制限します。`TUNNEL_TOKEN`は対話的または権限制限された編集手段で設定し、シェルの履歴やログに出さないでください。

```bash
cp .env.cloudflare.example .env.cloudflare
chmod 600 .env.cloudflare
docker compose -f compose.production.yaml -f compose.cloudflare.yaml config --quiet
docker compose -f compose.production.yaml -f compose.cloudflare.yaml build
docker compose -f compose.production.yaml -f compose.cloudflare.yaml up -d
docker compose -f compose.production.yaml -f compose.cloudflare.yaml ps
```

厳格なホストファイアウォールを使う場合は、`cloudflared`からCloudflareへの7844/TCP・7844/UDP送信が必要です。Cloudflare AccessはAcervoのログインや管理者MFAを置き換えず、必須要件でもありません。

## 起動後の確認と停止

選んだ公開方式と同じComposeファイルの組合せを、確認・停止・管理コマンドにも常に使います。

- `web`、`db`、`proxy`のhealthcheckがhealthyであること
- `web`がUID 10001で動作すること
- コンテナ内で`python manage.py check --deploy`が警告なしで成功すること
- `/health/`、ログイン、静的ファイルを確認すること
- `/admin/`が公開経路で404であること
- 直接HTTPSではCaddyだけが80/tcp・443/tcp・443/udpを公開し、Tunnel専用ではホスト公開ポートがないこと

停止は次のようにします。通常の停止で永続ボリュームを削除しないでください。

```bash
# 選択したoverlayに合わせてdirectまたはcloudflareを使う
docker compose -f compose.production.yaml -f compose.direct.yaml down
```

## 初期管理者とMFA

初期管理者は本番ホスト上で`bootstrap_admin`を使って一度だけ作成します。`school_cohort`では`--cohort-number`が必要で、`none`では不要です。一時パスワードは一度だけ標準出力へ表示されるため、安全な手段で利用者へ渡し、端末履歴やログに残さないでください。

```bash
# school_cohortでは末尾に --cohort-number COHORT_NUMBER を追加する
docker compose -f compose.production.yaml -f compose.direct.yaml exec web python manage.py bootstrap_admin --username INITIAL_ADMIN_USERNAME
```

Tunnel専用構成では、上記の`compose.direct.yaml`を`compose.cloudflare.yaml`へ置き換えます。

初期管理者は初回パスワード変更、TOTPまたはパスキーのprimary MFA登録、Recovery Codesの安全な保管を完了するまで管理機能を利用できません。Recovery Codesは一度だけ表示され、各コードは一度だけ使用できます。

通常のMFA喪失は、別の復旧可能な管理者が`/management/`のMFAリセット画面から対応します。最後の有効adminだけが対象となる緊急時には、選択したCompose構成で次を実行します。

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml exec web python manage.py reset_admin_mfa ADMIN_USERNAME
```

`ADMIN_USERNAME`を実際の対象usernameへ置き換え、対話確認で`RESET 実際のusername`を完全一致で入力します。このコマンドは対象の既存MFAとログインsessionを無効化しますが、パスワード、role、有効状態を変更せず、新しい秘密やRecovery Codesを出力しません。

## バックアップ・復元

管理画面で行う標本の無効化・完全削除と、失敗した写真削除の再試行は[標本管理の運用手順](SPECIMEN_MANAGEMENT.md)を参照してください。

DB、写真、復元に必要な非公開設定は、1人以上の管理責任者の`age`公開鍵で暗号化して保存します。公開鍵を1本だけにする導入先は、対応する秘密鍵を紛失・破損すると既存バックアップを復元できないリスクを承認します。後継者の公開鍵を追加した後は、新規バックアップを複数recipientへ暗号化します。空環境だけへ安全に復元する手順、保持世代、定期実行、失敗時の扱いは[暗号化バックアップと空環境復元](BACKUP_RESTORE.md)を参照してください。標本詳細と保護写真配信は実装済みですが、別ホスト保存した実データの復元後に認証・表示・永続化を確認する受入は残っています。Phase 10全体やStep 7C-LIVEをCIやこの手順だけで完了扱いにはしません。

実運用環境を操作する前の承認項目、受入順序、中止条件は[Step 7C-LIVE 実施前確認](LIVE_PREFLIGHT.md)にまとめています。

通常更新、失敗時の対応、巻戻しの判断、ディスク確認、管理者交代・移行、リリース前の受入項目は[更新・障害対応・リリース確認](OPERATIONS.md)を参照してください。
