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
sudo chown -R 10001:10001 "$work_directory"

"${source_compose[@]}" config --quiet
"${source_compose[@]}" build backup
"${source_compose[@]}" up --detach --wait db web proxy
"${source_compose[@]}" exec -T web sh -c 'printf %s restored-photo > /app/media/backup-restore-check.txt'

"${source_compose[@]}" run --rm --no-deps -v "$work_directory/keys:/keys" --entrypoint age-keygen backup -o /keys/first.txt > "$work_directory/first.public"
"${source_compose[@]}" run --rm --no-deps -v "$work_directory/keys:/keys" --entrypoint age-keygen backup -o /keys/second.txt > "$work_directory/second.public"
sudo chown -R 10001:10001 "$work_directory/keys"
recipients="$(tr -d '\n' < "$work_directory/first.public"),$(tr -d '\n' < "$work_directory/second.public")"

"${source_compose[@]}" run --rm --no-deps \
  -v "$work_directory/archives:/backups" \
  -e "ACERVO_BACKUP_AGE_RECIPIENTS=$recipients" \
  backup create

backup_id="$(find "$work_directory/archives" -mindepth 1 -maxdepth 1 -type d -name 'acervo-*' -printf '%f\n')"
test -n "$backup_id"
test -f "$work_directory/archives/$backup_id/payload.tar.gz.age"
test -f "$work_directory/archives/$backup_id/metadata.json"
test -f "$work_directory/archives/$backup_id/checksums.sha256"
test ! -e "$work_directory/archives/$backup_id/database.dump"
test ! -e "$work_directory/archives/$backup_id/photos.tar"

"${source_compose[@]}" down --volumes --remove-orphans
"${target_compose[@]}" up --detach --wait db
"${target_compose[@]}" run --rm --no-deps \
  -v "$work_directory/archives:/backups:ro" \
  -v "$work_directory/keys/first.txt:/run/identity/identity.txt:ro" \
  -v "$work_directory/restored-settings:/restored-settings" \
  restore restore --backup-id "$backup_id" --identity-file /run/identity/identity.txt \
  --confirm RESTORE_EMPTY_TARGET

cmp --silent .env.production "$work_directory/restored-settings/.env.production"
"${target_compose[@]}" run --rm --no-deps --entrypoint sh restore -c 'test "$(cat /target-media/backup-restore-check.txt)" = restored-photo'
"${target_compose[@]}" up --detach --wait web proxy
"${target_compose[@]}" exec -T web python manage.py check --deploy
"${target_compose[@]}" exec -T web python -c "import urllib.request; request=urllib.request.Request('http://127.0.0.1:8000/health/', headers={'Host': 'acervo.localhost', 'X-Forwarded-Proto': 'https'}); assert urllib.request.urlopen(request, timeout=5).status == 200"

echo "backup_restore_ci=success"
