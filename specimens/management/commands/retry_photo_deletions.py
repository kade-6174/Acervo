"""完全削除後に残った写真の削除を再試行する。"""

from django.core.management.base import BaseCommand, CommandError

from specimens.services import retry_pending_photo_deletions


class Command(BaseCommand):
    help = "標本の完全削除後に保留された写真ファイルの削除を再試行する"

    def handle(self, *args, **options):
        removed, failed = retry_pending_photo_deletions()
        self.stdout.write(f"写真削除の再試行: 完了={removed} 保留={failed}")
        if failed:
            raise CommandError("写真ファイルの削除が完了していません。")
