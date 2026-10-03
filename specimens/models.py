"""標本データの中核モデル。"""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SpecimenSequence(models.Model):
    """単一組織内で標本番号を再利用せず発行する採番元。"""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_number = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="specimens_sequence_singleton"),
            models.CheckConstraint(
                condition=models.Q(next_number__gt=0),
                name="specimens_sequence_next_number_positive",
            ),
        ]

    def __str__(self):
        return f"next={self.next_number}"


class Taxon(models.Model):
    scientific_name = models.CharField("学名", max_length=255, blank=True)
    japanese_name = models.CharField("和名", max_length=255, blank=True)
    rank = models.CharField("分類階級", max_length=64, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("pk")),
                name="specimens_taxon_not_own_parent",
            )
        ]
        ordering = ["scientific_name", "japanese_name", "pk"]

    def __str__(self):
        return self.scientific_name or self.japanese_name or f"Taxon {self.pk}"


class TaxonSource(models.Model):
    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="sources")
    source_url = models.URLField("根拠URL", blank=True)
    citation = models.TextField("引用", blank=True)
    checked_on = models.DateField("確認日", null=True, blank=True)

    def __str__(self):
        return self.citation or self.source_url or f"TaxonSource {self.pk}"


class StorageLocation(models.Model):
    name = models.CharField("名称", max_length=255)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    note = models.TextField("備考", blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"], name="specimens_storage_location_unique"
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("pk")),
                name="specimens_storage_not_own_parent",
            ),
        ]
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class QRBatch(models.Model):
    """同時に発行したQRラベルのまとまり。"""

    requested_count = models.PositiveIntegerField("発行枚数")
    note = models.TextField("備考", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(requested_count__gt=0),
                name="specimens_qr_batch_requested_count_positive",
            )
        ]
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"QR batch {self.pk} ({self.requested_count})"


class Specimen(models.Model):
    class Status(models.TextChoices):
        IN_COLLECTION = "in_collection", "所蔵中"
        ON_LOAN = "on_loan", "貸出中"
        SOLD = "sold", "売却済み"
        DISPOSED = "disposed", "廃棄"
        LOST = "lost", "紛失"

    class AcquisitionMethod(models.TextChoices):
        COLLECTED = "collected", "採集"
        PURCHASED = "purchased", "購入"
        DONATED = "donated", "寄贈"
        OTHER = "other", "その他"

    specimen_code = models.CharField("標本番号", max_length=96, unique=True, editable=False)
    detail_uuid = models.UUIDField(
        "詳細用識別子", default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    taxon = models.ForeignKey(Taxon, null=True, blank=True, on_delete=models.PROTECT)
    identification_text = models.CharField("同定情報", max_length=500, blank=True)
    acquisition_method = models.CharField(max_length=16, choices=AcquisitionMethod)
    collected_on = models.DateField("採集日", null=True, blank=True)
    collected_place = models.CharField("採集地", max_length=500, blank=True)
    collector = models.CharField("採集者", max_length=255, blank=True)
    storage_location = models.ForeignKey(
        StorageLocation, null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.IN_COLLECTION)
    note = models.TextField("備考", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_specimens"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["specimen_code"]

    def __str__(self):
        return self.specimen_code

    def save(self, *args, **kwargs):
        if self.pk:
            original = (
                type(self).objects.filter(pk=self.pk).values("specimen_code", "detail_uuid").first()
            )
            if original and (
                original["specimen_code"] != self.specimen_code
                or original["detail_uuid"] != self.detail_uuid
            ):
                raise ValidationError("標本番号と詳細用識別子は変更できません。")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.taxon_id and not self.identification_text.strip():
            raise ValidationError({"identification_text": "Taxon未指定時は同定情報が必要です。"})


class QRLabel(models.Model):
    """QRラベル1枚。tokenは公開URLの識別子であり、認可情報ではない。"""

    class Status(models.TextChoices):
        UNUSED = "unused", "未使用"
        ASSIGNED = "assigned", "割当済み"
        RETIRED = "retired", "無効"

    batch = models.ForeignKey(QRBatch, on_delete=models.PROTECT, related_name="labels")
    token = models.UUIDField(
        "QR識別子", default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.UNUSED)
    specimen = models.OneToOneField(
        Specimen,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="qr_label",
    )
    print_count = models.PositiveIntegerField(default=0)
    last_printed_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(status="unused", specimen__isnull=True)
                    | models.Q(status="assigned", specimen__isnull=False)
                    | models.Q(status="retired")
                ),
                name="specimens_qr_label_status_specimen_consistent",
            )
        ]
        ordering = ["pk"]

    def __str__(self):
        return str(self.token)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values("token").first()
            if original and original["token"] != self.token:
                raise ValidationError("QR識別子は変更できません。")
        return super().save(*args, **kwargs)


class SpecimenEvent(models.Model):
    class Type(models.TextChoices):
        COLLECTION = "collection", "採集"
        PURCHASE = "purchase", "購入"
        DONATION = "donation", "寄贈"
        MOVE = "move", "移動"
        LOAN = "loan", "貸出"
        RETURN = "return", "返却"
        SALE = "sale", "売却"
        DISPOSAL = "disposal", "廃棄"
        LOSS = "loss", "紛失"
        FOUND = "found", "発見"
        OTHER = "other", "その他"

    specimen = models.ForeignKey(Specimen, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=16, choices=Type)
    occurred_on = models.DateField(default=timezone.localdate)
    note = models.TextField("備考", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_on", "pk"]

    def __str__(self):
        return f"{self.specimen}: {self.event_type}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("標本履歴は更新できません。")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("標本履歴は削除できません。")


class SpecimenPhoto(models.Model):
    specimen = models.ForeignKey(Specimen, on_delete=models.PROTECT, related_name="photos")
    file_path = models.CharField("保存相対パス", max_length=500, unique=True)
    content_type = models.CharField("形式", max_length=100)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_path
