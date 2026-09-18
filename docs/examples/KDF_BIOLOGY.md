# 生物班向け導入・運用例

これはAcervoの必須仕様ではなく、生物班への**一導入例**です。Acervo本体は任意の組織・公開URLで運用でき、Cloudflare Tunnelを使わない直接HTTPS構成も引き続き選択できます。

DNS、Tunnel、token、本番ホスト、本番Compose起動、実HTTPS受入は、この文書だけでは実施しません。これらはStep 7C-LIVEとして別途承認された作業です。

## 確定したアプリ設定

本番ホスト上の権限制限された`.env.production`へ、次の値を設定します。Gitへコミットしません。

```ini
ACERVO_PUBLIC_BASE_URL=https://acervo.kdf-biology.org
DJANGO_ALLOWED_HOSTS=acervo.kdf-biology.org
DJANGO_CSRF_TRUSTED_ORIGINS=https://acervo.kdf-biology.org

ACERVO_ENROLLMENT_POLICY=school_cohort
ACERVO_SCHOOL_YEAR_START_MONTH=4
ACERVO_SCHOOL_YEAR_START_DAY=1
ACERVO_BASE_SCHOOL_YEAR=2026
ACERVO_BASE_FIRST_YEAR_COHORT=33
```

`ACERVO_SITE_NAME`と`ACERVO_ORGANIZATION_NAME`は未確定のため、この文書で推測して設定しません。旧`ACERVO_BASE_THIRD_YEAR_COHORT`は使いません。

学校年度は4月1日に切り替わります。

- 2026年度: 33回生＝1年生、32回生＝2年生、31回生＝3年生
- 2027年度: 34回生＝1年生、33回生＝2年生、32回生＝3年生

## 公開方式

この導入例ではCloudflare Tunnel専用構成を採用します。自宅ルーターの受信ポートは開放しません。Tunnelのオリジンは`http://proxy:8080`です。

- `proxy`、`web`、`db`、`tunnel`にホスト公開ポートを持たせない
- Proxmox、SSH、PostgreSQL、Gunicornを一般公開しない
- Cloudflare Accessを必須にせず、Acervo側のログイン・MFAを置き換えない
- Tunnelの名前、token、VMのOS・容量・アドレス、バックアップ保存先は未確定または非公開情報であり、この文書へ記載しない

Tunnel tokenは必要時だけ本番ホスト上の権限制限された`.env.cloudflare`で管理します。token自体をGit、ログ、コマンド履歴、運用台帳へ記載しません。

## 運用と引継ぎ

- 通常利用はスマートフォン、管理はPCを想定する。
- 当面の管理者は1名とし、アカウントを共有しない。
- TOTP、Recovery Codes、パスキー、および本番ホストからの緊急MFAリセット経路を失わない。
- 使い捨て試験adminは作らない。
- 引継ぎ時は後輩用の別管理者アカウントを作る。後継者のMFA登録と復旧確認が終わるまで、現管理者を削除・降格しない。
- ドメイン契約はサービス継続中、現責任者が維持する。DNS、Tunnel、本番ホスト、秘密鍵、バックアップの担当を次年度へ明示的に引き継ぐ。

担当と保管場所は、公開リポジトリへ実値を書かず、[非公開運用台帳テンプレート](../templates/PRIVATE_OPERATIONS_RUNBOOK.md)から作成するアクセス制限済みの台帳で管理します。

## パスキー受入

実HTTPSでの受入はまだ未実施です。実際に採用するスマートフォンOS、PC OS、ブラウザは未確定です。受入時は、端末内パスキーと同期パスキーを区別して確認します。

- iPhone／Apple環境ではiCloudキーチェーンが同期パスキー候補
- Android／Google環境ではGoogle Password Managerが同期パスキー候補
- 対応Windows環境では同期可能な資格情報管理機能が候補
- パスキーだけに依存せず、TOTPとRecovery Codesを維持する

公開hostnameは最初のパスキー登録前に確定します。hostname変更時には既存パスキーの再登録が必要になり得ます。
