"""画面に依存しない標本採番と状態遷移。"""

import json
import uuid
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import (
    QRBatch,
    QRLabel,
    Specimen,
    SpecimenEvent,
    SpecimenPhoto,
    SpecimenSequence,
    Taxon,
    TaxonSource,
)


class SpecimenServiceErrorCode(StrEnum):
    SPECIMEN_NOT_FOUND = "specimen_not_found"
    INVALID_EVENT_TYPE = "invalid_event_type"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    INVALID_QR_BATCH_SIZE = "invalid_qr_batch_size"
    QR_LABEL_NOT_FOUND = "qr_label_not_found"
    QR_LABEL_NOT_UNUSED = "qr_label_not_unused"
    SPECIMEN_ALREADY_HAS_QR_LABEL = "specimen_already_has_qr_label"
    INVALID_PHOTO = "invalid_photo"
    PHOTO_TOO_LARGE = "photo_too_large"
    PHOTO_TOO_MANY_PIXELS = "photo_too_many_pixels"
    PHOTO_LIMIT_REACHED = "photo_limit_reached"


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


@dataclass(frozen=True, slots=True)
class SpecimenRegistrationResult:
    specimen_id: int
    specimen_code: str
    qr_label_id: int


@dataclass(frozen=True, slots=True)
class TemporaryPhoto:
    """確認画面までだけ保持する、再エンコード済み画像。"""

    path: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class TaxonCandidate:
    """ローカルまたは外部照会で得た、採用前の分類候補。"""

    scientific_name: str
    japanese_name: str
    rank: str
    source_url: str = ""
    citation: str = ""
    external: bool = False


def search_taxon_candidates(query: str) -> tuple[tuple[Taxon, ...], tuple[TaxonCandidate, ...]]:
    """ローカルを優先し、必要時だけGBIF候補を短時間照会する。"""

    normalized = query.strip()
    if not normalized:
        return (), ()
    local = tuple(
        Taxon.objects.filter(
            models.Q(scientific_name__icontains=normalized)
            | models.Q(japanese_name__icontains=normalized)
        )[:20]
    )
    if local or not settings.ACERVO_TAXON_EXTERNAL_SEARCH_ENABLED:
        return local, ()
    return (), _search_gbif_taxa(normalized)


def _search_gbif_taxa(query: str) -> tuple[TaxonCandidate, ...]:
    """GBIF Species APIの候補だけを取得する。外部障害は空結果へフォールバックする。"""

    endpoint = "https://api.gbif.org/v1/species/search?" + urlencode({"q": query, "limit": 10})
    request = Request(endpoint, headers={"User-Agent": "Acervo/0.1 taxon lookup"})
    try:
        with urlopen(request, timeout=2) as response:  # noqa: S310 - 固定したGBIF HTTPS URLのみ
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeDecodeError):
        return ()

    candidates = []
    for item in payload.get("results", []):
        scientific_name = str(item.get("scientificName") or item.get("canonicalName") or "").strip()
        if not scientific_name:
            continue
        key = item.get("key")
        source_url = f"https://www.gbif.org/species/{key}" if isinstance(key, int) else ""
        candidates.append(
            TaxonCandidate(
                scientific_name=scientific_name,
                japanese_name="",
                rank=str(item.get("rank") or "").strip(),
                source_url=source_url,
                citation="GBIF Backbone Taxonomy",
                external=True,
            )
        )
    return tuple(candidates)


@transaction.atomic
def adopt_external_taxon_candidate(candidate: TaxonCandidate) -> Taxon:
    """利用者が明示採用した外部候補だけをローカル分類と根拠へ保存する。"""

    if not candidate.external or not candidate.scientific_name:
        raise ValueError("外部候補だけを採用できます。")
    taxon = Taxon.objects.create(
        scientific_name=candidate.scientific_name,
        japanese_name=candidate.japanese_name,
        rank=candidate.rank,
    )
    TaxonSource.objects.create(
        taxon=taxon,
        source_url=candidate.source_url,
        citation=candidate.citation,
        checked_on=timezone.localdate(),
    )
    return taxon


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
    *, specimen_id: int, event_type: str, created_by, note: str = "", occurred_on=None
) -> StateChangeResult:
    """状態と連動する履歴を原子的に追加する。"""

    if event_type not in SpecimenEvent.Type.values:
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_EVENT_TYPE)
    specimen = Specimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_NOT_FOUND)
    next_status = _STATE_FOR_EVENT.get(event_type, specimen.status)
    if event_type in _STATE_FOR_EVENT and (
        next_status == specimen.status or next_status not in _ALLOWED_TRANSITIONS[specimen.status]
    ):
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_STATE_TRANSITION)
    event = SpecimenEvent.objects.create(
        specimen=specimen,
        event_type=event_type,
        note=note,
        occurred_on=occurred_on or timezone.localdate(),
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
def register_specimen_from_qr(
    *, token, created_by, photo_uploads=(), temporary_photos=(), **fields
):
    """未使用QRだけで、標本・番号・QR割当・写真を確定する。"""
    temporary_paths = [photo.path for photo in temporary_photos]
    saved_paths: list[str] = []
    try:
        label = QRLabel.objects.select_for_update().filter(token=token).first()
        if label is None:
            raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_FOUND)
        if label.status != QRLabel.Status.UNUSED or label.specimen_id is not None:
            raise SpecimenServiceError(SpecimenServiceErrorCode.QR_LABEL_NOT_UNUSED)
        specimen = create_specimen(created_by=created_by, **fields)
        label.specimen = specimen
        label.status = QRLabel.Status.ASSIGNED
        label.full_clean()
        label.save(update_fields=["specimen", "status"])
        for upload in photo_uploads:
            photo = add_specimen_photo(specimen_id=specimen.pk, upload=upload)
            saved_paths.append(photo.file_path)
        for temporary_photo in temporary_photos:
            with default_storage.open(temporary_photo.path, "rb") as upload:
                photo = _add_normalized_photo(
                    specimen=specimen,
                    image_bytes=upload.read(),
                    width=temporary_photo.width,
                    height=temporary_photo.height,
                )
                saved_paths.append(photo.file_path)
        return SpecimenRegistrationResult(specimen.pk, specimen.specimen_code, label.pk)
    except Exception:
        for path in saved_paths:
            default_storage.delete(path)
        raise
    finally:
        discard_temporary_photos(temporary_paths)


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


def normalize_photo(upload) -> tuple[bytes, int, int]:
    """許可画像を実デコードし、必要なら縮小してEXIFなしJPEGにする。"""
    if upload.size > settings.ACERVO_PHOTO_MAX_UPLOAD_BYTES:
        raise SpecimenServiceError(SpecimenServiceErrorCode.PHOTO_TOO_LARGE)
    try:
        with Image.open(upload) as source:
            source.load()
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_PHOTO)
            width, height = source.size
            pixels = width * height
            if pixels > settings.ACERVO_PHOTO_MAX_SOURCE_PIXELS:
                raise SpecimenServiceError(SpecimenServiceErrorCode.PHOTO_TOO_MANY_PIXELS)
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_PHOTO) from None
    if pixels > settings.ACERVO_PHOTO_MAX_STORED_PIXELS:
        scale = (settings.ACERVO_PHOTO_MAX_STORED_PIXELS / pixels) ** 0.5
        width, height = max(1, int(width * scale)), max(1, int(height * scale))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue(), width, height


def save_temporary_photos(uploads) -> tuple[TemporaryPhoto, ...]:
    """確認前の画像を、安全な一時領域へ再エンコードして保存する。"""
    uploads = tuple(uploads)
    if len(uploads) > settings.ACERVO_PHOTO_MAX_PER_SPECIMEN:
        raise SpecimenServiceError(SpecimenServiceErrorCode.PHOTO_LIMIT_REACHED)
    normalized = [normalize_photo(upload) for upload in uploads]
    temporary_paths: list[str] = []
    try:
        results = []
        for image_bytes, width, height in normalized:
            path = f"registration-tmp/{uuid.uuid4()}.jpg"
            default_storage.save(path, ContentFile(image_bytes))
            temporary_paths.append(path)
            results.append(TemporaryPhoto(path=path, width=width, height=height))
        return tuple(results)
    except Exception:
        discard_temporary_photos(temporary_paths)
        raise


def discard_temporary_photos(paths) -> None:
    """確認中止・失敗時の一時画像を削除する。"""
    for path in paths:
        if isinstance(path, str) and path.startswith("registration-tmp/"):
            default_storage.delete(path)


@transaction.atomic
def add_specimen_photo(*, specimen_id: int, upload) -> SpecimenPhoto:
    return add_specimen_photos(specimen_id=specimen_id, uploads=[upload])[0]


@transaction.atomic
def add_specimen_photos(*, specimen_id: int, uploads) -> tuple[SpecimenPhoto, ...]:
    """複数写真を、上限確認からDB記録までまとめて追加する。"""
    specimen = Specimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_NOT_FOUND)
    uploads = tuple(uploads)
    if specimen.photos.count() + len(uploads) > settings.ACERVO_PHOTO_MAX_PER_SPECIMEN:
        raise SpecimenServiceError(SpecimenServiceErrorCode.PHOTO_LIMIT_REACHED)
    normalized = [normalize_photo(upload) for upload in uploads]
    saved_paths: list[str] = []
    try:
        photos = []
        for image_bytes, width, height in normalized:
            photo = _add_normalized_photo(
                specimen=specimen, image_bytes=image_bytes, width=width, height=height
            )
            saved_paths.append(photo.file_path)
            photos.append(photo)
        return tuple(photos)
    except Exception:
        for path in saved_paths:
            default_storage.delete(path)
        raise


def _add_normalized_photo(
    *, specimen: Specimen, image_bytes: bytes, width: int, height: int
) -> SpecimenPhoto:
    path = f"specimens/{specimen.detail_uuid}/{uuid.uuid4()}.jpg"
    default_storage.save(path, ContentFile(image_bytes))
    try:
        return SpecimenPhoto.objects.create(
            specimen=specimen, file_path=path, content_type="image/jpeg", width=width, height=height
        )
    except Exception:
        default_storage.delete(path)
        raise
