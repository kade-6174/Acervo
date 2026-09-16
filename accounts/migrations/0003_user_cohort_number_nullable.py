import django.core.validators
from django.db import migrations, models


def prevent_unsafe_reverse(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    if User.objects.filter(cohort_number__isnull=True).exists():
        raise RuntimeError(
            "NULLの回生データがあるため戻せません。バックアップから復元するか、"
            "すべての利用者へ回生を設定してから逆変換してください。"
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_user_mfa_reset_at")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("member", "利用者"), ("admin", "管理者")],
                default="member",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="cohort_number",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.RemoveConstraint(model_name="user", name="accounts_user_cohort_number_positive"),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(("cohort_number__isnull", True))
                | models.Q(("cohort_number__gt", 0)),
                name="accounts_user_cohort_number_positive",
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, prevent_unsafe_reverse),
    ]
