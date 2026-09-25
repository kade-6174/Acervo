# 暗号化バックアップと空環境復元

この手順は、AcervoのDB、保護写真、復元に必要な設定を、公開鍵暗号`age`で暗号化して保存し、**空の検証環境だけ**へ復元するためのものです。本番データ、DNS、Tunnel、実アカウントは操作しません。

## 方式と鍵の管理

バックアップ用コンテナには固定版`age 1.3.2`を含めます。少なくとも1人の管理責任者の公開鍵へ暗号化します。サーバーと`.env.production`には公開鍵だけを置き、復号用の秘密鍵は置きません。公開鍵を1本だけにする場合、対応する秘密鍵を紛失・破損すると既存バックアップを復元できません。このリスクを承認した導入先だけが1本運用を選びます。

秘密鍵は、管理者の安全な端末で生成後ただちに印刷し、責任者が封緘して保管します。共有プリンタ、印刷履歴、スプール、Git、チャット、メール、バックアップ保存先へ秘密鍵を残してはいけません。非公開運用台帳には秘密鍵そのものではなく、保管責任者と保管場所への参照だけを記録します。後継者が決まったら、その公開鍵を追加して以降の新規バックアップを複数recipientへ暗号化します。

`age-keygen`は秘密鍵をファイルへ出力し、標準出力には公開鍵だけを出力します。管理用端末で、権限制限された一時ファイルへ生成してください。公開鍵を`ACERVO_BACKUP_AGE_RECIPIENTS`へ1本以上設定します。

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

公開状態で読める`metadata.json`と`checksums.sha256`には、backup ID、UTC実行時刻、形式バージョン、PostgreSQL major、暗号化payloadのSHA-256だけを含めます。秘密値、設定値、写真内容は含めません。暗号化されたpayload内部には構成要素のSHA-256 manifestを保持します。

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

## 空環境への復元

復元は本番環境へ実行しません。対象Compose projectのDBにpublic schemaのテーブルがなく、`media_data`が空である場合だけ許可します。`RESTORE_EMPTY_TARGET`の完全一致確認が必要です。PostgreSQL majorがbackup metadataと対象DBで一致しない場合は拒否します。PostgreSQL major更新は通常復元と混ぜず、別途移行・復元試験を行います。

復元設定は稼働中の`.env.production`を上書きせず、指定した空ディレクトリへ`.env.production`として出力します。運用者が内容と接続先を確認してから、対象環境へ安全に配置します。

```bash
sudo install -d -m 0700 -o 10001 -g 10001 /srv/acervo-restored-settings

docker compose -p acervo-restore -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml \
  run --rm \
  -v /srv/acervo-backups:/backups:ro \
  -v /secure/offline-location/printed-key-copy.txt:/run/identity/identity.txt:ro \
  -v /srv/acervo-restored-settings:/restored-settings \
  restore restore --backup-id acervo-UTC_TIMESTAMP-ID --identity-file /run/identity/identity.txt \
  --confirm RESTORE_EMPTY_TARGET
```

秘密鍵の実パスや内容をシェル履歴へ残さないよう、権限制限された管理手段でmount元を指定します。上の秘密鍵パスは説明用の例であり、実在値ではありません。

復元後は対象環境でmigration、`python manage.py check --deploy`、healthcheck、ログイン、管理者MFAゲート、再起動後のDB・写真永続化を確認します。現在は標本詳細・保護写真配信の機能本体が未実装のため、CIではDB、`media_data`、設定の往復と、Caddyが`/media/`を公開しないことを最小確認とします。標本詳細表示、認可済み写真表示、未認証写真拒否は該当機能を実装後、四半期ごとの実復元試験で必須確認します。

ディスク不足、DB接続失敗、写真読取失敗、暗号化失敗、checksum不一致、構成要素不足、空でない復元先、PostgreSQL major不一致はすべて失敗として扱います。四半期に1回以上、空の検証環境でこの復元受入を実施してください。
