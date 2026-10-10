# 更新・障害対応・リリース確認

対象はアプリを配置したLinuxホストです。Proxmoxを使う導入先は、対象VMの操作経路を非公開運用台帳で確認します。VM内のアプリ操作と物理ホストのディスク操作を混同しません。以下の例は直接HTTPS構成です。Tunnel専用では`compose.direct.yaml`を`compose.cloudflare.yaml`に置き換えます。

## 更新前

1. 対象ホスト、配置場所、現在のGit HEAD、反映するコミットを確認します。反映対象のCIが成功していることを確認します。
2. 配置場所で`git status --short`を確認します。変更があれば更新を止め、作成者と扱いを確認します。
3. [バックアップ手順](BACKUP_RESTORE.md)で更新前バックアップを作成し、終了コード0と暗号化成果物3ファイルを確認します。別ホストの最新保存物と独立した空環境での復元試験日時も確認します。
4. DB migrationが含まれる場合は逆変換の可否、旧アプリとの互換性、データを戻す場合の損失を確認します。PostgreSQL major更新は通常更新へ混ぜません。
5. ビルド用領域、DB、写真、バックアップの空き容量を確認します。

**対象ホスト:** アプリのLinuxホスト。**確認ポイント:** 配置場所・永続領域の空き容量とinodeが不足していないこと。1行ずつ実行します。

```bash
df -h . /var/lib/docker /srv/acervo-backups
```

```bash
df -i . /var/lib/docker /srv/acervo-backups
```

例のパスを使っていない導入先は、台帳に記載した実際の保存先で確認します。容量不足時は更新を止めます。`docker system prune --volumes`やDB・写真ボリューム削除を容量確保に使いません。

## アプリ更新

**対象ホスト:** アプリのLinuxホスト。アプリ配置場所で1行ずつ実行します。複数の変更は反映する最終コミットのCI成功後にまとめられます。

```bash
git fetch origin
```

反映対象と`origin/main`が一致することを確認してから進めます。

```bash
git merge --ff-only origin/main
```

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml config --quiet
```

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml up -d --build --wait
```

この構成ではweb起動時にmigrationを実行します。起動成功後、次を確認します。

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml exec -T web python manage.py check --deploy
```

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml exec -T web python manage.py migrate --check
```

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml ps
```

```bash
docker compose -f compose.production.yaml -f compose.direct.yaml exec -T web id -u
```

**確認ポイント:** 各終了コード0、Djangoの問題0件、未適用migrationなし、db・web・proxyのhealthy、UID`10001`。Tunnel専用ではtunnelの稼働も確認します。最後にGit作業ツリーが清潔でHEADが反映対象と一致することを確認し、日時・バックアップID・結果を記録します。文書だけの更新はコンテナへの再反映を必要としません。

## 失敗した場合

| 症状 | 最初の対応 | 再開条件 |
| --- | --- | --- |
| ビルド失敗 | 直前の稼働状態と容量・通信・エラー箇所を確認 | 原因解消後に同じ反映対象でビルド成功 |
| migration失敗 | 後続を止め、適用済みmigrationとDB状態を確認 | データ保全と再実行または復旧方法を確認 |
| webがhealthyにならない | webの限定した直近ログと設定検証を確認 | 起動・health・Django検査成功 |
| DB・写真取得失敗 | 永続領域、接続、権限、容量を確認 | 元のデータ保持と認証済み閲覧の回復 |
| バックアップ・転送失敗 | 失敗扱いにし、既存の正常成果物を保持 | 新しい成果物・整合性・転送先確定を確認 |
| 写真削除待ち | [標本管理手順](SPECIMEN_MANAGEMENT.md)で再試行 | 成功、または担当者が残件の理由を把握 |

ログを共有する場合は秘密情報や実データを含む箇所を除きます。`.env.production`の内容、コンテナ環境変数一覧、秘密鍵、認証コードを診断結果として表示しません。

### 戻す場合

コードを前のコミットへ戻してもDBは戻りません。現在のschemaと互換性がある旧アプリへ戻せるかを先に確認し、反映先コミットを確定します。互換性を確認できない場合はGitだけの巻戻しを行いません。

DB復旧が必要な場合は、停止時間、復旧時点以降のデータ損失、写真との整合性を運用責任者が確認します。既存の本番DBへ復元処理を流し込まず、[空環境への復元](BACKUP_RESTORE.md)で独立した復旧環境を構築し、認証・標本・写真を確認してから公開先を切り替えます。旧環境のボリュームや設定を削除する作業は別途判断します。

## リリース前の受入表

各行に日時、確認者、対象コミット、結果、未実施理由を記録します。自動テスト成功だけで手動確認の行を完了にしません。

| 確認項目 | 実施先・方法 |
| --- | --- |
| PostgreSQL必須テスト・競合・本番Compose・復元CI | 反映対象のGitHub Actions |
| 公開HTTPS、管理者MFA、初回パスワード変更、権限不足拒否 | 実運用の対象ブラウザ |
| QR初回登録、再読取、写真追加、検索・詳細・履歴 | 非機密の試験標本を実サイトで登録 |
| 和名分類の上位による絞込み・上位未選択・五十音順 | 標本登録画面 |
| 無効化・完全削除、再確認、QR・番号の不再利用 | [標本管理手順](SPECIMEN_MANAGEMENT.md)の試験標本 |
| iPhoneのホーム画面追加、カメラ、本番発行QRの写真読取 | Safariとホーム画面アプリ |
| QRの実印刷・読取、PDF・管理者CSV | 使用予定の用紙・プリンター、対象権限 |
| 日次バックアップ・失敗検知・別ホスト保存 | 予定時刻の結果と保存先の確定済み成果物 |
| 別ホスト保存物から標本・写真・認証を復元 | 独立した空環境、実ブラウザ／HTTPS |
| ホスト再起動後のDB・写真保持 | 再起動前後で代表標本・保護写真を比較 |
| 管理者交代・端末喪失復旧・鍵の引き継ぎ | 後継者の認証・MFAと復元鍵の安全な保管 |
| 一般利用開始の承認 | 未確認項目・制約を運用責任者が確認 |

Android向け実装はMVPに含めます。Android実機受入だけをMVP完成後に行い、それまでは動作確認済みと扱いません。7C-LIVE-A・7C-LIVE-B、Phase 1・Phase 9・Phase 10の全体完了は、それぞれ`PLAN.md`の条件と`STATUS.md`の記録に従います。

## 管理者交代・サーバー移行

現在の管理者が操作できる間に後継者のアカウント・MFAを設定し、管理画面へ入れることを確認します。最後の有効管理者を失う操作は行いません。backup recipient追加、秘密鍵の別保管、署名検証公開鍵、復元試験日時、日次実行・障害時の担当を[非公開運用台帳](templates/PRIVATE_OPERATIONS_RUNBOOK.md)へ引き継ぎます。

別ホストへの移行は、新ホストを空環境として復元し、復元設定の接続先・公開方式・写真保存先を確認します。必要なTunnel資格情報等は別経路で配置します。MFA・標本・写真・未認証拒否・永続化を確認してから公開先を変更し、移行中の書込みが分岐しないよう運用責任者が停止時間と切替時刻を決めます。
