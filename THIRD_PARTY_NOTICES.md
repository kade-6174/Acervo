# 第三者ライセンスと通知

この文書は、Acervoリポジトリへ同梱していることを確認した第三者資産の通知です。別途記載があるものを除き、kade_6174が権利を有するAcervo固有のコード、文書、設定例は[Apache License 2.0](LICENSE)です。第三者資産、依存パッケージ、コンテナ基盤はAcervoのApache-2.0へ再ライセンスされず、それぞれの元のライセンスが適用されます。

## age

- 用途: バックアップpayloadの公開鍵暗号化
- 固定版: 1.3.2
- ライセンス: BSD 3-Clause License
- 公式配布元: https://github.com/FiloSottile/age
- 取り扱い: 専用バックアップコンテナのビルド時に公式release archiveをSHA-256検証して取得する。Acervo固有部分のApache-2.0へ再ライセンスしない。

## 同梱静的資産

| 資産 | 確認したバージョン | ライセンス | 公式配布元 | リポジトリ内のライセンス |
|---|---:|---|---|---|
| Bootstrap | 5.3.8 | MIT | [twbs/bootstrap v5.3.8](https://github.com/twbs/bootstrap/releases/tag/v5.3.8) | [static/vendor/bootstrap/LICENSE](static/vendor/bootstrap/LICENSE) |
| htmx | 2.0.10 | 0BSD | [bigskysoftware/htmx v2.0.10](https://github.com/bigskysoftware/htmx/releases/tag/v2.0.10) | [static/vendor/htmx/LICENSE](static/vendor/htmx/LICENSE) |
| jsQR | 1.4.0 | Apache-2.0 | [cozmo/jsQR](https://github.com/cozmo/jsQR) | [static/vendor/jsqr/LICENSE](static/vendor/jsqr/LICENSE) |

上記のライセンスファイルは変更・削除しません。

## Python依存パッケージとコンテナ基盤

`pyproject.toml`のPython依存パッケージ、およびDockerfile・Composeが参照するPython、Caddy、PostgreSQL、cloudflaredの各イメージは、各配布元のライセンスに従います。この通知は、これらをAcervo固有部分と同じApache-2.0であると主張するものではありません。

公開Dockerイメージまたは配布済みアーカイブを正式に提供する前に、含まれる完全な依存物、ライセンス本文、著作権表示、SBOMおよび再配布条件を別タスクで確認します。この文書はその完全な棚卸しではありません。
