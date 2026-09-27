#!/usr/bin/env bash
set -euo pipefail

source_compose=(docker compose -p acervo-ci-backup-source -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml)
target_compose=(docker compose -p acervo-ci-backup-target -f compose.production.yaml -f compose.direct.yaml -f compose.backup.yaml)
work_directory="$(mktemp -d)"

cleanup() {
  local status=$?
  "${source_compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  "${target_compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  # コンテナ内の非root UIDが作成した一時ファイルも確実に削除する。
  sudo rm -rf "$work_directory"
  return "$status"
}
trap cleanup EXIT

mkdir -p "$work_directory/archives" "$work_directory/keys" "$work_directory/restored-settings"
ssh-keygen -q -t ed25519 -N '' -f "$work_directory/keys/signing"
printf 'acervo-backup ' > "$work_directory/keys/allowed_signers"
cat "$work_directory/keys/signing.pub" >> "$work_directory/keys/allowed_signers"
# ホスト側は公開鍵と検証結果を書き、コンテナには必要な作業用ディレクトリだけを渡す。
sudo chown -R 10001:10001 "$work_directory/archives" "$work_directory/keys" "$work_directory/restored-settings"

"${source_compose[@]}" config --quiet
"${source_compose[@]}" build backup
"${source_compose[@]}" up --detach --wait db web proxy
"${source_compose[@]}" exec -T web sh -c 'printf %s restored-photo > /app/media/backup-restore-check.txt'

ACERVO_BACKUP_SIGNING_PRIVATE_KEY_FILE="$work_directory/keys/signing" "${source_compose[@]}" run --rm --no-deps \
  --entrypoint sh backup -ceu '
    printf test > /tmp/signing-input
    ssh-keygen -Y sign -f /run/acervo-backup-signing/private -n acervo-backup /tmp/signing-input >/dev/null
    test -s /tmp/signing-input.sig
  '
ACERVO_BACKUP_SIGNING_PRIVATE_KEY_FILE="$work_directory/keys/signing" "${source_compose[@]}" run --rm --no-deps -v "$work_directory/keys:/keys" --entrypoint age-keygen backup -o /keys/first.txt 2> "$work_directory/first.public"
first_recipient="$(sed -n 's/^Public key: //p' "$work_directory/first.public")"
test -n "$first_recipient"
recipients="$first_recipient"

ACERVO_BACKUP_SIGNING_PRIVATE_KEY_FILE="$work_directory/keys/signing" "${source_compose[@]}" run --rm --no-deps \
  -v "$work_directory/archives:/backups" \
  -e "ACERVO_BACKUP_AGE_RECIPIENTS=$recipients" \
  backup create

backup_id="$(find "$work_directory/archives" -mindepth 1 -maxdepth 1 -type d -name 'acervo-*' -printf '%f\n')"
test -n "$backup_id"
# 成果物はバックアップ用UIDだけが読める。CIではsudoで存在だけを検査し、内容は出力しない。
sudo test -f "$work_directory/archives/$backup_id/payload.tar.gz.age"
sudo test -f "$work_directory/archives/$backup_id/metadata.json"
sudo test -f "$work_directory/archives/$backup_id/checksums.sha256"
sudo test ! -e "$work_directory/archives/$backup_id/database.dump"
sudo test ! -e "$work_directory/archives/$backup_id/photos.tar"

# 保存先の書込み権限だけで整合する3ファイルを置換しても、署名検証より先へ進まない。
tampered_id="acervo-tampered"
sudo cp -a "$work_directory/archives/$backup_id" "$work_directory/archives/$tampered_id"
sudo python3 - "$work_directory/archives/$tampered_id" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
payload = directory / "payload.tar.gz.age"
payload.write_bytes(b"attacker replacement")
metadata_path = directory / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
metadata["encrypted_payload_sha256"] = hashlib.sha256(payload.read_bytes()).hexdigest()
metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
(directory / "checksums.sha256").write_text(
    f"{hashlib.sha256(payload.read_bytes()).hexdigest()}  payload.tar.gz.age\n"
    f"{hashlib.sha256(metadata_path.read_bytes()).hexdigest()}  metadata.json\n",
    encoding="ascii",
)
PY

"${source_compose[@]}" down --volumes --remove-orphans
"${target_compose[@]}" up --detach --wait db
if ACERVO_BACKUP_ALLOWED_SIGNERS_FILE="$work_directory/keys/allowed_signers" "${target_compose[@]}" run --rm --no-deps \
  -v "$work_directory/archives:/backups:ro" \
  -v "$work_directory/keys/first.txt:/run/identity/identity.txt:ro" \
  -v "$work_directory/restored-settings:/restored-settings" \
  restore restore --backup-id "$tampered_id" --identity-file /run/identity/identity.txt \
  --confirm RESTORE_EMPTY_TARGET; then
  echo "tampered_backup_was_accepted" >&2
  exit 1
fi
ACERVO_BACKUP_ALLOWED_SIGNERS_FILE="$work_directory/keys/allowed_signers" "${target_compose[@]}" run --rm --no-deps \
  -v "$work_directory/archives:/backups:ro" \
  -v "$work_directory/keys/first.txt:/run/identity/identity.txt:ro" \
  -v "$work_directory/restored-settings:/restored-settings" \
  restore restore --backup-id "$backup_id" --identity-file /run/identity/identity.txt \
  --confirm RESTORE_EMPTY_TARGET

sudo cmp --silent .env.production "$work_directory/restored-settings/.env.production"
"${target_compose[@]}" run --rm --no-deps --entrypoint sh restore -c 'test "$(cat /target-media/backup-restore-check.txt)" = restored-photo'
"${target_compose[@]}" up --detach --wait web proxy
"${target_compose[@]}" exec -T web python manage.py check --deploy
"${target_compose[@]}" exec -T web python -c "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/health/', headers={'Host': 'acervo.localhost', 'X-Forwarded-Proto': 'https'}); assert urllib.request.urlopen(request, timeout=5).status == 200"

echo "backup_restore_ci=success"
