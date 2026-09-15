from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AuditLog(models.Model):
    """秘密値を持たない、アプリケーション上の追記専用監査記録。"""

    class Action(models.TextChoices):
        ADMIN_MFA_RESET = "admin_mfa_reset", "別管理者によるMFAリセット"
        COMMAND_MFA_RESET_RESERVED = "command_mfa_reset_reserved", "管理コマンドMFAリセット予約"

    class Channel(models.TextChoices):
        MANAGEMENT_UI = "management_ui", "管理画面"
        MANAGEMENT_COMMAND = "management_command", "サーバー管理コマンド"

    occurred_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    channel = models.CharField(max_length=32, choices=Channel.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs_as_actor",
    )
    actor_username = models.CharField(max_length=150)
    target = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs_as_target",
    )
    target_username = models.CharField(max_length=150)

    class Meta:
        ordering = ["-occurred_at", "-pk"]

    def __str__(self):
        return f"{self.action}:{self.pk}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("監査記録は更新できません。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("監査記録は削除できません。")
