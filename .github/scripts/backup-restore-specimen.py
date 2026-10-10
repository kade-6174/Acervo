"""CI専用の非機密標本を作成し、空環境復元後の認可・データ保持を検証する。"""

# ruff: noqa: E402 -- Django初期化後にモデルを読み込む独立実行スクリプト。

import hashlib
import json
import os
import sys
from io import BytesIO

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.enrollment import first_year_cohort_for_school_year, school_year_on
from accounts.models import User
from specimens.models import QRLabel, Specimen, SpecimenEvent, SpecimenSequence
from specimens.services import create_qr_batch, record_specimen_event, register_specimen_from_qr

MANIFEST = "ci-backup-specimen.json"
USERNAME = "ci-backup-member"


def seed():
    cohort = None
    if settings.ACERVO_ENROLLMENT_POLICY == "school_cohort":
        cohort = first_year_cohort_for_school_year(school_year_on(timezone.localdate()))
    user = User.objects.create_user(username=USERNAME, cohort_number=cohort)
    batch = create_qr_batch(requested_count=1, created_by=user)
    label = QRLabel.objects.get(pk=batch.label_ids[0])
    image = BytesIO()
    Image.new("RGB", (12, 8), "green").save(image, "PNG")
    result = register_specimen_from_qr(
        token=label.token,
        created_by=user,
        acquisition_method=Specimen.AcquisitionMethod.OTHER,
        identification_text="復元確認専用の試験標本",
        photo_uploads=[SimpleUploadedFile("synthetic.png", image.getvalue(), "image/png")],
    )
    specimen = Specimen.objects.get(pk=result.specimen_id)
    record_specimen_event(
        specimen_id=specimen.pk, created_by=user, event_type=SpecimenEvent.Type.LOAN
    )
    photo = specimen.photos.get()
    with default_storage.open(photo.file_path, "rb") as stored:
        digest = hashlib.sha256(stored.read()).hexdigest()
    manifest = {
        "specimen_code": specimen.specimen_code,
        "detail_uuid": str(specimen.detail_uuid),
        "qr_token": str(label.token),
        "photo_path": photo.file_path,
        "photo_sha256": digest,
        "next_number": SpecimenSequence.objects.get().next_number,
    }
    with default_storage.open(MANIFEST, "w") as stored:
        json.dump(manifest, stored)
    print("backup_fixture=created")


def verify():
    with default_storage.open(MANIFEST) as stored:
        manifest = json.load(stored)
    specimen = Specimen.objects.get(detail_uuid=manifest["detail_uuid"])
    assert specimen.specimen_code == manifest["specimen_code"]
    assert specimen.status == Specimen.Status.ON_LOAN
    assert list(specimen.events.values_list("event_type", flat=True)) == [
        SpecimenEvent.Type.OTHER,
        SpecimenEvent.Type.LOAN,
    ]
    assert SpecimenSequence.objects.get().next_number == manifest["next_number"]
    label = QRLabel.objects.get(token=manifest["qr_token"])
    assert label.status == QRLabel.Status.ASSIGNED and label.specimen_id == specimen.pk
    photo = specimen.photos.get()
    assert photo.file_path == manifest["photo_path"]
    assert (photo.width, photo.height, photo.content_type) == (12, 8, "image/jpeg")
    host = "acervo.localhost"
    detail_url = reverse("specimens:detail", args=[specimen.detail_uuid])
    photo_url = reverse("specimens:photo", args=[specimen.detail_uuid, photo.pk])
    qr_url = reverse("specimens:qr_resolve", args=[label.token])
    anonymous = Client(HTTP_HOST=host)
    for url in (detail_url, photo_url, qr_url):
        response = anonymous.get(url, secure=True)
        assert response.status_code == 302
        assert response["Location"].startswith(reverse("account_login"))
        assert "no-store" in response["Cache-Control"]
    authenticated = Client(HTTP_HOST=host)
    authenticated.force_login(User.objects.get(username=USERNAME))
    detail = authenticated.get(detail_url, secure=True)
    assert detail.status_code == 200 and specimen.specimen_code.encode() in detail.content
    qr = authenticated.get(qr_url, secure=True)
    assert qr.status_code == 302 and qr["Location"] == detail_url
    response = authenticated.get(photo_url, secure=True)
    assert response.status_code == 200 and response["Content-Type"] == "image/jpeg"
    assert "no-store" in response["Cache-Control"]
    try:
        content = b"".join(response.streaming_content)
    finally:
        response.close()
    assert hashlib.sha256(content).hexdigest() == manifest["photo_sha256"]
    with Image.open(BytesIO(content)) as image:
        image.load()
        assert image.size == (12, 8) and image.format == "JPEG"
    print("restored_specimen=verified protected_photo=verified anonymous=denied")


if sys.argv[1] == "seed":
    seed()
elif sys.argv[1] == "verify":
    verify()
else:
    raise ValueError("seedまたはverifyを指定してください。")
