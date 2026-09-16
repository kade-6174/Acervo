from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from accounts.models import User
from accounts.services import create_user_with_temporary_password


class Command(BaseCommand):
    help = "最初のAcervo管理者を一度だけ作成します。"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--cohort-number", type=int)

    def handle(self, *args, **options):
        username = options["username"]
        cohort_number = options["cohort_number"]

        try:
            with transaction.atomic():
                if User.objects.select_for_update().filter(username=username).exists():
                    raise CommandError("同じユーザー名が既に存在します。")
                if (
                    User.objects.select_for_update()
                    .filter(role=User.Role.ADMIN, is_active=True)
                    .exists()
                ):
                    raise CommandError("有効な管理者が既に存在します。")
                result = create_user_with_temporary_password(
                    username=username,
                    cohort_number=cohort_number,
                    role=User.Role.ADMIN,
                )
        except (IntegrityError, ValidationError) as error:
            raise CommandError("管理者を作成できませんでした。") from error

        self.stdout.write(f"一時パスワード: {result.temporary_password}")
