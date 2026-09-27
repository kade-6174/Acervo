# セキュリティ修正の引継ぎ

最終更新: 2026-09-28

## 目的と一次情報

セキュリティ確認レポート scan `84ca32bf-93bf-44b7-bf79-1ad0ba982281` の唯一の指摘
`backup.restore-authenticity`（Medium、CWE-345/CWE-22）を修正する。

指摘は、別ホスト保存先への書込み権限を持つ攻撃者が、暗号化payload、metadata、checksumsを整合させて差し替えると、復元が真正なバックアップとして受け入れる点だった。レポートはローカルCodex Securityの完了scanに保存されている。外部公開経路、Cloudflare route/DNS、実機の鍵保管とホスト設定は、このコード検査の対象外である。

## 対応状況

| 指摘 | 状態 | 実装・確認 |
| --- | --- | --- |
| 保存先改ざん済みバックアップを復元できる | 修正済み、リリース前 | 専用Ed25519鍵で正規化metadataとencrypted payload SHA-256を署名し、復号前に信頼済み`allowed_signers`で検証する。未署名format version 1、不正署名、未知の公開鍵は拒否する。 |
| 検証後に保存先を差し替える競合 | 修正済み、リリース前 | `snapshot_backup()`が必須3ファイルをprivateな作業領域に固定し、以降は保存先を再読込しない。 |
| archiveによるパス脱出・リンク展開 | 修正済み、リリース前 | 手動展開前に絶対パス、`..`、symlink、hardlink、デバイス、非通常entry、重複entryを拒否する。 |

公開鍵集合はバックアップ保存先と別の信頼できる保管場所から復元コンテナへread-onlyで渡す。署名秘密鍵は作成コンテナだけへread-onlyで渡し、復元側へは渡さない。秘密鍵・Webhook・age identity・本番`.env`の値は記録、ログ、Gitに含めない。

## 変更ファイル

- `deploy/backup/acervo_backup.py`: 署名、復元前認証、snapshot、安全なtar展開。
- `compose.backup.yaml`: 作成用秘密鍵と復元用`allowed_signers`を別々にread-only mount。
- `deploy/backup/Dockerfile`: OpenSSHの署名検証機能を追加。
- `core/tests/test_backup_tool.py`: 署名成功・改ざん・未署名・不正署名・未知鍵・危険なarchive・snapshotの試験。
- `.github/scripts/verify-backup-restore.sh`: CIで整合する3ファイルの差替えが復元失敗になることを検証。
- `docs/BACKUP_RESTORE.md`: 鍵配置、旧形式拒否、復元手順、安全なarchiveの説明。
- `STATUS.md`: 実装状態と公開停止条件。

## レビュー

最初のレビューで、署名検証後に保存先payloadを再度開くTOCTOUが指摘された。`snapshot_backup()`により修正済み。

最終レビューでは、保存先だけを書き換えられる攻撃者が署名済みpayloadを復号・展開まで到達させる具体的な迂回は見つからなかった。残る可用性上の限定事項は、コピー開始直前の保存先置換で復元を失敗させ得ることだけであり、署名検証を通る任意payloadの受入れにはならない。

## 検証状況

2026-09-28に、`core.tests.test_backup_tool` 19件、Ruff lint／format、Django check、migration差分確認、全Djangoテスト259件、`git diff --check`が成功した。

このWindows環境にはDockerとbashがないため、Composeの署名付き作成→復元試験とshell構文検査は未実行である。`.github/scripts/verify-backup-restore.sh`を含むGitHub Actionsの`production-container`で確認する。

## 次に行うこと

1. 差分を最終確認して日本語コミットを作成し、mainへpushする。
2. GitHub Actionsの`test`と`production-container`の成功を確認する。
3. VM200に署名秘密鍵を安全な権限で配置し、VM201などの復元環境に別保管の`allowed_signers`を配置する。実値はチャットやログへ出さない。
4. 署名付きformat version 2バックアップを作り、別ホスト保存確定後に空の復元環境で復元する。DB、写真、設定、ログイン、標本詳細、写真表示を受入確認する。
5. 上記が成功するまでCloudflareのpublic hostname route設定と一般公開を進めない。

## 残る制約

- 旧format version 1バックアップは安全側で復元拒否する。新しい署名付きバックアップの復元受入が済むまで、旧成果物を削除しない。
- DBの復元後、写真展開または設定コピーに失敗すると復元先が部分状態になる。復元を再試行する前に、対象の空DB・写真領域・復元設定出力先を作り直す。
