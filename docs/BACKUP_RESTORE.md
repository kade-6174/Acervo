# 暗号化バックアップと空環境復元

この手順は、AcervoのDB、保護写真、復元に必要な設定を、公開鍵暗号`age`で暗号化し、作成元専用の署名鍵で真正性を確認してから**空の検証環境だけ**へ復元するためのものです。本番データ、DNS、Tunnel、実アカウントは操作しません。

## 方式と鍵の管理

バックアップ用コンテナには固定版`age 1.3.2`とOpenSSHを含めます。少なくとも1人の管理責任者の公開鍵へ暗号化します。サーバーと`.env.production`には公開鍵だけを置き、復号用の秘密鍵は置きません。公開鍵を1本だけにする場合、対応する秘密鍵を紛失・破損すると既存バックアップを復元できません。このリスクを承認した導入先だけが1本運用を選びます。

秘密鍵は、管理者の安全な端末で生成後ただちに印刷し、責任者が封緘して保管します。共有プリンタ、印刷履歴、スプール、Git、チャット、メール、バックアップ保存先へ秘密鍵を残してはいけません。非公開運用台帳には秘密鍵そのものではなく、保管責任者と保管場所への参照だけを記録します。後継者が決まったら、その公開鍵を追加して以降の新規バックアップを複数recipientへ暗号化します。

`age-keygen`は秘密鍵をファイルへ出力し、標準出力には公開鍵だけを出力します。管理用端末で、権限制限された一時ファイルへ生成してください。公開鍵を`ACERVO_BACKUP_AGE_RECIPIENTS`へ1本以上設定します。

暗号化用とは別に、バックアップ作成VMだけが読めるEd25519署名秘密鍵を`/etc/acervo/backup-signing/private`へ置きます。秘密鍵を`.env.production`、payload、バックアップ保存先、SFTP保存先へ置きません。復元環境では、この秘密鍵ではなく、別経路で保管した公開鍵から作る`/etc/acervo/backup-signing/allowed_signers`だけを使います。署名鍵を失った場合に備え、公開鍵と保管場所を非公開運用台帳へ記録します。

```ini
ACERVO_BACKUP_AGE_RECIPIENTS=age1BACKUP_CUSTODIAN_PUBLIC_KEY
ACERVO_BACKUP_RETENTION_DAILY=14
ACERVO_BACKUP_RETENTION_WEEKLY=8
ACERVO_BACKUP_RETENTION_MONTHLY=12
```

## 含むものと含まないもの

1回のバックアップは、同じUTC時刻とbackup IDを持つ次を含みます。

- PostgreSQL 18のcustom形式論理dump
- `media_data`内の写真等
- `.env.production`の復元用コピー

公開状態で読める`metadata.json`と`checksums.sha256`には、backup ID、UTC実行時刻、形式バージョン、PostgreSQL major、暗号化payloadのSHA-256だけを含めます。`metadata.json`には上記を対象とする署名を含めます。秘密値、設定値、写真内容は含めません。暗号化されたpayload内部には構成要素のSHA-256 manifestを保持します。

次は意図的に含めません。

- `postgres_data`の物理ボリューム、Dockerイメージ、静的資産、ホストOS
- Caddyの証明書・状態（直接HTTPSでは再取得する）
- `.env.cloudflare`、Tunnel token、age秘密鍵、Recovery Codes

Tunnel tokenとage秘密鍵は別保管し、復元後に必要なら運用者が別経路で提供します。

## 作成

バックアップ保存先はホスト上の永続領域に作成し、コンテナの一時領域だけに置きません。実行ユーザーとバックアップコンテナUID 10001だけが読めるようにします。`.env.production`をコンテナへ読み取り専用で渡すため、同ファイルもUIDまたはグループ10001が読める必要があります。

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /srv/acervo-backups
sudo chgrp 10001 .env.production
sudo chmod 0640 .env.production
# 署名秘密鍵はbackupコンテナUIDだけが読める専用ファイルとして作る。
sudo install -d -m 0750 -o root -g 10001 /etc/acervo/backup-signing
sudo ssh-keygen -q -t ed25519 -N '' -f /etc/acervo/backup-signing/private
sudo chown 10001:10001 /etc/acervo/backup-signing/private
sudo chmod 0600 /etc/acervo/backup-signing/private
sudo sh -c 'printf "acervo-backup "; cat /etc/acervo/backup-signing/private.pub' \
  > /secure-offline-location/allowed_signers

docker compose -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml \
  run --rm -v /srv/acervo-backups:/backups backup create
```

Tunnel専用では`compose.direct.yaml`を`compose.cloudflare.yaml`へ置き換えます。公開方式overlayを同時に指定しません。

成功時だけ`acervo-...`ディレクトリを公開します。途中失敗は`.failed-acervo-...`として残り、正常バックアップに数えません。成功・失敗の出力はbackup ID、構成要素名、PostgreSQL major、失敗理由コードだけで、DBパスワード、Fernet鍵、Django秘密鍵、Tunnel token、秘密鍵を含みません。

保持処理は日次14、週次8、月次12の最新世代の和集合を残します。実削除前に候補を確認するには次を使います。

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml \
  run --rm -v /srv/acervo-backups:/backups backup retention --dry-run
```

通常の`create`後に保持処理も実行されます。保持処理が失敗した場合、作成済みbackupは残して処理全体を失敗終了にします。運用者は候補・ディスク容量・権限を確認してから再実行します。

サーバー外への複製先と方法は運用者が選びます。複製先には暗号化済み`acervo-...`ディレクトリだけをコピーし、age秘密鍵は同じ場所へ置きません。毎日実行する場合は、秘密値をコマンド引数へ書かないroot以外のsystemd timer等を使用し、終了コードと安全なログを監視します。

既存の形式v1バックアップには署名がないため、新しい復元処理は受け入れません。更新後に署名付き形式v2のバックアップを作成し、空の検証環境で復元できることを確認してから、v1を運用上の復元候補から外します。v1の保存や削除は、保持規則と必要な監査上の保存期間に従います。

## 定時実行の受入と日々の確認

導入先で起動用ホストとバックアップ実行VMを分けた場合、両方のtimerを**それぞれのホスト**で確認します。主ホストのバックアップ機起動timerと、VM内のバックアップtimerは別のsystemd管理下です。`systemctl list-timers --all --no-pager <unit名>`で次回時刻とunit名を読み、設定した現地時刻と一致することを確認します。VMが停止中に予定時刻を逃したときの扱いは`Persistent`設定で決まるため、設定値も確認します。

初回は手動実行の成功と区別して、予定時刻を過ぎた後に次を順に確認し、実行日時・結果・確認担当を非公開運用台帳へ記録します。

1. バックアップ実行VMでserviceの`Result`と終了コード、該当時刻のjournalを確認する。ログを共有する前に秘密値が含まれないことを確認し、秘密値をチャットや運用記録へ転記しない。
2. 別ホストの保存先で、同じbackup IDの暗号化成果物が`.ready`処理を経て確定し、必要ファイルとSHA-256の検証に成功したことを確認する。転送しただけでは成功扱いにしない。
3. バックアップ機が予定どおり停止したことを、バックアップ機を管理する物理ホストから確認する。保存先コンテナと物理ホストの宛先を混同しない。
4. バックアップ実行VMが停止して予定時刻を逃した場合は、当日の成果物が存在するかを確認する。`Persistent=false`なら自動追いかけ実行を期待しない。

別ホスト保存先の自動削除は、日次・週次・月次の保持規則、必要容量、復元可能性を確認してから導入します。規則が未確定の間は過去の成果物を削除しません。失敗通知と空き容量の監視も、日々の運用開始前に担当者と確認頻度を決めます。

## 別ホストの保持・容量監視・Discord通知

別ホストの保持処理も、初期値で日次14世代、週次8世代、月次12世代を残します。`deploy/offsite/acervo_offsite_retention.py`は、確定済みの`acervo-YYYYMMDDTHHMMSSZ-<hex>`ディレクトリだけを対象にします。既定では削除候補を表示するだけで、`--apply`が明示されたときだけ候補を削除します。`.ready`と`.incoming`は対象にしません。

バックアップ機は転送後に停止するため、保持処理と容量監視は起動直後に実行します。`acervo-offsite-maintenance.timer`は起動90秒後に実行し、整理後に、保存先の空き容量、`ssh.service`、`acervo-finalize-incoming.path`を確認します。初期しきい値は空き50 GiB未満または使用率85%以上です。導入先はroot専用の`/etc/acervo/offsite-maintenance.env`で、次の範囲だけ調整できます。

```ini
ACERVO_BACKUP_RETENTION_DAILY=14
ACERVO_BACKUP_RETENTION_WEEKLY=8
ACERVO_BACKUP_RETENTION_MONTHLY=12
ACERVO_OFFSITE_MIN_FREE_GIB=50
ACERVO_OFFSITE_MAX_USED_PERCENT=85
```

Discord通知は任意です。Webhook URLは投稿先チャンネルへの送信権限を持つ秘密情報なので、Git、チャット、ログ、コマンド引数へ書きません。`/etc/acervo/discord-webhook.url`にURLだけを保存し、root所有・`0600`にします。`acervo-discord-notify@.service`は失敗したsystemd unit名だけを通知し、設定値、保存先のファイル名、バックアップ内容を送信しません。VM側の`acervo-daily-backup.service`とLXC側のmaintenance serviceの`OnFailure`から呼び出します。

導入前は、保持スクリプトを`--apply`なしで実行し、削除候補が想定どおりであることを確認します。容量監視とDiscord通知も、テスト専用の失敗unitを使うか、復旧可能な検証環境で通知受信を確認します。実データの成果物を使った通知試験や削除を、初回導入確認へ混ぜません。

## 空環境への復元

復元は本番環境へ実行しません。対象Compose projectのDBにpublic schemaのテーブルがなく、`media_data`が空である場合だけ許可します。`RESTORE_EMPTY_TARGET`の完全一致確認が必要です。復元前に、バックアップ保存先からは取得しない`allowed_signers`で署名を確認します。署名なし、署名不正、形式v1のバックアップは復元しません。PostgreSQL majorがbackup metadataと対象DBで一致しない場合は拒否します。PostgreSQL major更新は通常復元と混ぜず、別途移行・復元試験を行います。

復元設定は稼働中の`.env.production`を上書きせず、指定した空ディレクトリへ`.env.production`として出力します。運用者が内容と接続先を確認してから、対象環境へ安全に配置します。

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /srv/acervo-restored-settings
# backup作成VMの署名秘密鍵から独立した保管物を使い、公開鍵だけを配置する。
sudo install -d -m 0755 -o root -g root /etc/acervo/backup-signing
sudo install -m 0644 -o root -g root /path/from-trusted-key-store/allowed_signers /etc/acervo/backup-signing/allowed_signers

docker compose -p acervo-restore -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml \
  run --rm \
  -v /srv/acervo-backups:/backups:ro \
  -v /secure/offline-location/printed-key-copy.txt:/run/identity/identity.txt:ro \
  -v /srv/acervo-restored-settings:/restored-settings \
  restore restore --backup-id acervo-UTC_TIMESTAMP-ID --identity-file /run/identity/identity.txt \
  --confirm RESTORE_EMPTY_TARGET
```

秘密鍵の実パスや内容をシェル履歴へ残さないよう、権限制限された管理手段でmount元を指定します。上の秘密鍵パスは説明用の例であり、実在値ではありません。

復元後は対象環境でmigration、`python manage.py check --deploy`、healthcheck、ログイン、管理者MFAゲート、再起動後のDB・写真永続化を確認します。CIの空環境復元テストには非機密の試験標本・履歴・QR・写真を含め、標本番号・詳細UUID・QR割当・採番元の保持、詳細表示、認証済み写真表示、未ログイン時の詳細・QR・写真拒否、写真バイトの一致を検査します。復元先のDB・webコンテナを再作成した後も同じ検査を行います。Caddyが`/media/`を公開しないことは本番ComposeのCIで検査します。

この自動検査は利用者セッションをテスト用に作成してビューを検証します。実ブラウザでのパスワード・パスキー・TOTP認証や、別ホスト保存した実データの復元受入を代替しません。四半期ごとの実復元試験では、実際のログイン・MFA、代表的な標本詳細と保護写真の表示・未認証拒否、ホスト再起動後の永続化を必須確認します。7C-LIVE-A・7C-LIVE-Bの未確認項目は`STATUS.md`に残します。

ディスク不足、DB接続失敗、写真読取失敗、暗号化失敗、署名不正、checksum不一致、構成要素不足、危険なアーカイブentry、空でない復元先、PostgreSQL major不一致はすべて失敗として扱います。アーカイブは通常ファイルとディレクトリ以外を拒否し、symlink、hardlink、絶対パス、親ディレクトリ参照を展開しません。四半期に1回以上、空の検証環境でこの復元受入を実施してください。
