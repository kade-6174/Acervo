from io import BytesIO

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import User
from specimens.models import Specimen
from specimens.services import (
    SpecimenServiceError,
    add_specimen_photo,
    create_specimen,
    discard_temporary_photos,
    register_specimen_from_qr,
    save_temporary_photos,
)


class PhotoProcessingTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="photo-user", cohort_number=33)
        self.specimen = create_specimen(
            created_by=user,
            identification_text="写真テスト",
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
        )

    def upload(self, size=(100, 80), image_format="PNG"):
        output = BytesIO()
        Image.new("RGB", size, "red").save(output, image_format)
        return SimpleUploadedFile("test.png", output.getvalue(), content_type="image/png")

    @override_settings(ACERVO_PHOTO_MAX_STORED_PIXELS=1_000)
    def test_oversized_photo_is_downscaled_and_reencoded_without_original_name(self):
        photo = add_specimen_photo(specimen_id=self.specimen.pk, upload=self.upload((100, 80)))

        self.assertLessEqual(photo.width * photo.height, 1_000)
        self.assertEqual(photo.content_type, "image/jpeg")
        self.assertTrue(photo.file_path.endswith(".jpg"))
        self.assertNotIn("test.png", photo.file_path)

    def test_invalid_photo_is_rejected(self):
        upload = SimpleUploadedFile("bad.svg", b"<svg/>", content_type="image/svg+xml")
        with self.assertRaisesRegex(SpecimenServiceError, "invalid_photo"):
            add_specimen_photo(specimen_id=self.specimen.pk, upload=upload)

    @override_settings(ACERVO_PHOTO_MAX_UPLOAD_BYTES=10)
    def test_oversized_upload_is_rejected_before_storage(self):
        with self.assertRaisesRegex(SpecimenServiceError, "photo_too_large"):
            add_specimen_photo(specimen_id=self.specimen.pk, upload=self.upload())

    @override_settings(ACERVO_PHOTO_MAX_SOURCE_PIXELS=1_000)
    def test_excessive_source_pixels_are_rejected(self):
        with self.assertRaisesRegex(SpecimenServiceError, "photo_too_many_pixels"):
            add_specimen_photo(specimen_id=self.specimen.pk, upload=self.upload((40, 30)))

    def test_temporary_photos_are_reencoded_and_discarded(self):
        temporary = save_temporary_photos([self.upload()])

        self.assertEqual(len(temporary), 1)
        self.assertTrue(default_storage.exists(temporary[0].path))
        self.assertTrue(temporary[0].path.endswith(".jpg"))

        discard_temporary_photos([temporary[0].path])
        self.assertFalse(default_storage.exists(temporary[0].path))

    def test_photo_limit_is_enforced(self):
        for _ in range(10):
            add_specimen_photo(specimen_id=self.specimen.pk, upload=self.upload())

        with self.assertRaisesRegex(SpecimenServiceError, "photo_limit_reached"):
            add_specimen_photo(specimen_id=self.specimen.pk, upload=self.upload())

    def test_reencoded_photo_does_not_retain_exif_or_original_filename(self):
        output = BytesIO()
        exif = Image.Exif()
        exif[270] = "non-public-photo-note"
        Image.new("RGB", (20, 20), "green").save(output, "JPEG", exif=exif)
        upload = SimpleUploadedFile("original-secret-name.jpg", output.getvalue())

        photo = add_specimen_photo(specimen_id=self.specimen.pk, upload=upload)
        with default_storage.open(photo.file_path, "rb") as stored:
            content = stored.read()

        self.assertNotIn(b"non-public-photo-note", content)
        self.assertNotIn("original-secret-name.jpg", photo.file_path)

    def test_registration_failure_removes_temporary_photo(self):
        temporary = save_temporary_photos([self.upload()])

        with self.assertRaisesRegex(SpecimenServiceError, "qr_label_not_found"):
            register_specimen_from_qr(
                token="00000000-0000-0000-0000-000000000000",
                created_by=self.specimen.created_by,
                acquisition_method=Specimen.AcquisitionMethod.OTHER,
                identification_text="失敗する登録",
                temporary_photos=temporary,
            )

        self.assertFalse(default_storage.exists(temporary[0].path))
