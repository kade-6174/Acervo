from django.core.management.base import BaseCommand, CommandError

from accounts.mfa_reset import MFAResetError, MFAResetErrorCode, reset_admin_mfa_by_command


class Command(BaseCommand):
    help = "最後の有効な管理者のMFAを緊急リセットします。"

    def add_arguments(self, parser):
        parser.add_argument("username", help="対象の管理者username")

    def handle(self, *args, **options):
        username = options["username"]
        expected = f"RESET {username}"
        self.stdout.write(
            "警告: MFAを削除し、既存ログインsessionを無効化します。この操作は取り消せません。"
        )
        self.stdout.write(f"実行するには `{expected}` を入力してください。")
        try:
            confirmation = input()
        except EOFError:
            confirmation = ""
        if confirmation != expected:
            raise CommandError("確認文字列が一致しないため、変更していません。")
        try:
            result = reset_admin_mfa_by_command(target_username=username)
        except MFAResetError as error:
            if error.code is MFAResetErrorCode.COMMAND_OTHER_ADMIN_AVAILABLE:
                raise CommandError(
                    "別の復旧可能な管理者がいます。通常の管理画面からMFAをリセットしてください。"
                ) from None
            raise CommandError(
                "MFAリセットを実行できません。対象と復旧条件を確認してください。"
            ) from None
        self.stdout.write(
            self.style.SUCCESS(
                f"{username} のMFAをリセットしました"
                f"（削除した認証器: {result.deleted_authenticator_count}件）。"
                "再ログイン後にMFAの再登録が必要です。"
            )
        )
