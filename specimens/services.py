"""画面に依存しない標本採番と状態遷移。"""

from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO

import qrcode
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import QRBatch, QRLabel, Specimen, SpecimenEvent, SpecimenSequence


class SpecimenServiceErrorCode(StrEnum):
    SPECIMEN_NOT_FOUND = "specimen_not_found"
    INVALID_EVENT_TYPE = "invalid_event_type"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    INVALID_QR_BATCH_SIZE = "invalid_qr_batch_size"
    QR_LABEL_NOT_FOUND = "qr_label_not_found"
    QR_LABEL_NOT_UNUSED = "qr_label_not_unused"
    SPECIMEN_ALREADY_HAS_QR_LABEL = "specimen_already_has_qr_label"


class SpecimenServiceError(Exception):
    def __init__(self, code: SpecimenServiceErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class StateChangeResult:
    specimen_id: int
    event_id: int
    previous_status: str
    current_status: str


@dataclass(frozen=True, slots=True)
class QRBatchResult:
    batch_id: int
    label_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class QRLabelAssignmentResult:
    label_id: int
    specimen_id: int


def _specimen_code(number: int) -> str:
    return f"{settings.ACERVO_SPECIMEN_CODE_PREFIX}-{number:06d}"


def _next_sequence_number() -> int:
    sequence = SpecimenSequence.objects.select_for_update().filter(pk=1).first()
    if sequence is None:
        sequence, _ = SpecimenSequence.objects.get_or_create(pk=1, defaults={"next_number": 1})
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    return number


@transaction.atomic
def create_specimen(*, created_by, **fields) -> Specimen:
    """確定時だけ採番し、標本と初回履歴を同一トランザクションで保存する。"""

    number = _next_sequence_number()
    specimen = Specimen(specimen_code=_specimen_code(number), created_by=created_by, **fields)
    specimen.full_clean()
    specimen.save()
    SpecimenEvent.objects.create(
        specimen=specimen,
        event_type={
            Specimen.AcquisitionMethod.COLLECTED: SpecimenEvent.Type.COLLECTION,
            Specimen.AcquisitionMethod.PURCHASED: SpecimenEvent.Type.PURCHASE,
            Specimen.AcquisitionMethod.DONATED: SpecimenEvent.Type.DONATION,
            Specimen.AcquisitionMethod.OTHER: SpecimenEvent.Type.OTHER,
        }[specimen.acquisition_method],
        occurred_on=specimen.collected_on or timezone.localdate(),
        created_by=created_by,
    )
    return specimen


_STATE_FOR_EVENT = {
    SpecimenEvent.Type.LOAN: Specimen.Status.ON_LOAN,
    SpecimenEvent.Type.RETURN: Specimen.Status.IN_COLLECTION,
    SpecimenEvent.Type.SALE: Specimen.Status.SOLD,
    SpecimenEvent.Type.DISPOSAL: Specimen.Status.DISPOSED,
    SpecimenEvent.Type.LOSS: Specimen.Status.LOST,
    SpecimenEvent.Type.FOUND: Specimen.Status.IN_COLLECTION,
}

_ALLOWED_TRANSITIONS = {
    Specimen.Status.IN_COLLECTION: {
        Specimen.Status.ON_LOAN,
        Specimen.Status.SOLD,
        Specimen.Status.DISPOSED,
        Specimen.Status.LOST,
    },
    Specimen.Status.ON_LOAN: {Specimen.Status.IN_COLLECTION},
    Specimen.Status.LOST: {Specimen.Status.IN_COLLECTION},
    Specimen.Status.SOLD: set(),
    Specimen.Status.DISPOSED: set(),
}


@transaction.atomic
def record_specimen_event(
    *, specimen_id: int, event_type: str, created_by, note: str = ""
) -> StateChangeResult:
    """状態と連動する履歴を原子的に追加する。"""

    if event_type not in SpecimenEvent.Type.values:
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_EVENT_TYPE)
    specimen = Specimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_NOT_FOUND)
    next_status = _STATE_FOR_EVENT.get(event_type, specimen.status)
    if next_status != specimen.status and next_status not in _ALLOWED_TRANSITIONS[specimen.status]:
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_STATE_TRANSITION)
    event = SpecimenEvent.objects.create(
        specimen=specimen,
        event_type=event_type,
        note=note,
        created_by=created_by,
    )
    previous_status = specimen.status
    if next_status != previous_status:
        specimen.status = next_status
        specimen.save(update_fields=["status"])
    return StateChangeResult(specimen.pk, event.pk, previous_status, specimen.status)


def qr_url(token) -> str:
    """導入先設定の公開基底URLから、QRに入れるURLだけを作る。"""

    return f"{settings.ACERVO_PUBLIC_BASE_URL.rstrip('/')}/q/{token}/"


@transaction.atomic
def create_qr_batch(*, requested_count: int, created_by, note: str = "") -> QRBatchResult:
    """未使用QRをまとめて発行する。標本番号は消費しない。"""

    if (
        not isinstance(requested_count, int)
        or isinstance(requested_count, bool)
        or requested_count < 1
    ):
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_QR_BATCH_SIZE)
    batch = QRBatch(requested_count=requested_count, created_by=created_by, note=note)
    batch.full_clean()
    batch.save()
    labels = [QRLabel(batch=batch) for _ in range(requested_count)]
    QRLabel.objects.bulk_create(labels)
    return QRBatchResult(batch_id=batch.pk, label_ids=tuple(label.pk for label in labels))


@transaction.atomic
def assign_qr_label(*, token, specimen_id: int) -> QRLabelAssignmentResult:
    """未使用QRと標本を同時にロックし、二重割当を防ぐ。"""

    label = QRLabel.objects.select_for_update().filter(token=token).first()
    if label is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_FOUND)
    if label.status != QRLabel.Status.UNUSED or label.specimen_id is not None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_UNUSED)
    specimen = Specimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_NOT_FOUND)
    if QRLabel.objects.select_for_update().filter(specimen=specimen).exists():
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_ALREADY_HAS_QR_LABEL)
    label.specimen = specimen
    label.status = QRLabel.Status.ASSIGNED
    label.full_clean()
    label.save(update_fields=["specimen", "status"])
    return QRLabelAssignmentResult(label_id=label.pk, specimen_id=specimen.pk)


@transaction.atomic
def retire_qr_label(*, token) -> QRLabel:
    """ラベルを無効化する。既存の標本への割当履歴は保持する。"""

    label = QRLabel.objects.select_for_update().filter(token=token).first()
    if label is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_FOUND)
    if label.status == QRLabel.Status.RETIRED:
        raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_UNUSED)
    label.status = QRLabel.Status.RETIRED
    label.retired_at = timezone.now()
    label.full_clean()
    label.save(update_fields=["status", "retired_at"])
    return label


@transaction.atomic
def record_qr_reprint(*, token) -> QRLabel:
    """再印刷回数を記録する。QR識別子や割当は変更しない。"""

    label = QRLabel.objects.select_for_update().filter(token=token).first()
    if label is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_FOUND)
    label.print_count += 1
    label.last_printed_at = timezone.now()
    label.save(update_fields=["print_count", "last_printed_at"])
    return label


def build_qr_labels_pdf(*, labels, size_mm: int) -> bytes:
    """1ページ1枚、QR情報だけを含む正方形ラベルPDFを生成する。"""

    if size_mm not in {15, 20}:
        raise ValueError("QRラベル寸法は15mmまたは20mmです。")
    output = BytesIO()
    side = size_mm * mm
    document = canvas.Canvas(output, pagesize=(side, side), pageCompression=1)
    for label in labels:
        image = qrcode.make(qr_url(label.token)).get_image()
        document.drawImage(ImageReader(image), 0, 0, width=side, height=side, mask="auto")
        document.showPage()
    document.save()
    return output.getvalue()
