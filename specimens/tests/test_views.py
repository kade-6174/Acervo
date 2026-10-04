from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from specimens.models import QRLabel, Specimen
from specimens.services import add_specimen_photo, assign_qr_label, create_qr_batch, create_specimen


class SpecimenViewTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="current-member", cohort_number=33)
        self.graduate = User.objects.create_user(username="graduate-viewer", cohort_number=30)
        self.specimen = create_specimen(
            created_by=self.member,
            identification_text="アカネズミ",
            acquisition_method=Specimen.AcquisitionMethod.COLLECTED,
            collected_place="校庭",
            collector="記録者",
        )
        self.photo = add_specimen_photo(specimen_id=self.specimen.pk, upload=_image_upload())

    def detail_url(self):
        return reverse("specimens:detail", kwargs={"detail_uuid": self.specimen.detail_uuid})

    def test_unauthenticated_search_redirects_without_disclosing_results(self):
        response = self.client.get(reverse("specimens:list"), {"q": "アカネズミ"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/accounts/login/?next="))

    def test_search_and_detail_use_random_uuid_not_database_id(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("specimens:list"), {"q": "アカネズミ"})
        self.assertContains(response, self.specimen.specimen_code)
        self.assertContains(response, self.detail_url())
        self.assertEqual(self.client.get(f"/specimens/{self.specimen.pk}/").status_code, 404)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 200)

    def test_graduate_can_view_detail_and_photo_but_cannot_write(self):
        self.client.force_login(self.graduate)
        photo_url = reverse(
            "specimens:photo",
            kwargs={"detail_uuid": self.specimen.detail_uuid, "photo_id": self.photo.pk},
        )

        self.assertEqual(self.client.get(reverse("specimens:list")).status_code, 200)
        self.assertEqual(self.client.get(self.detail_url()).status_code, 200)
        self.assertEqual(self.client.get(photo_url).status_code, 200)
        self.assertEqual(
            self.client.post(
                reverse("specimens:edit", kwargs={"detail_uuid": self.specimen.detail_uuid}),
                {
                    "identification_text": "改変",
                    "acquisition_method": Specimen.AcquisitionMethod.OTHER,
                },
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("specimens:event", kwargs={"detail_uuid": self.specimen.detail_uuid}),
                {"event_type": "loan"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("specimens:photo_add", kwargs={"detail_uuid": self.specimen.detail_uuid}),
                {"photos": _image_upload()},
            ).status_code,
            404,
        )

    def test_member_can_edit_and_add_state_changing_event(self):
        self.client.force_login(self.member)
        edit_url = reverse("specimens:edit", kwargs={"detail_uuid": self.specimen.detail_uuid})
        response = self.client.post(
            edit_url,
            {
                "identification_text": "編集後の同定情報",
                "acquisition_method": Specimen.AcquisitionMethod.OTHER,
                "collected_place": "校庭",
                "collector": "記録者",
            },
        )
        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.specimen.refresh_from_db()
        self.assertEqual(self.specimen.identification_text, "編集後の同定情報")

        response = self.client.post(
            reverse("specimens:event", kwargs={"detail_uuid": self.specimen.detail_uuid}),
            {"event_type": "loan", "occurred_on": "2026-10-04", "note": "貸出記録"},
        )
        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.specimen.refresh_from_db()
        self.assertEqual(self.specimen.status, Specimen.Status.ON_LOAN)
        event = self.specimen.events.latest("pk")
        self.assertEqual(str(event.occurred_on), "2026-10-04")

    def test_current_member_can_get_specimen_and_qr_label_pdfs(self):
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=self.member).label_ids[0]
        )
        assign_qr_label(token=label.token, specimen_id=self.specimen.pk)
        self.client.force_login(self.member)

        label_response = self.client.get(
            reverse("specimens:label_pdf", kwargs={"detail_uuid": self.specimen.detail_uuid})
        )
        self.assertEqual(label_response.status_code, 200)
        self.assertEqual(label_response["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(label_response.streaming_content).startswith(b"%PDF"))

        qr_response = self.client.get(
            reverse("specimens:qr_label_pdf", kwargs={"detail_uuid": self.specimen.detail_uuid})
        )
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(qr_response.streaming_content).startswith(b"%PDF"))
        label.refresh_from_db()
        self.assertEqual(label.print_count, 1)
        self.assertIsNotNone(label.last_printed_at)

    def test_graduate_cannot_get_label_pdfs(self):
        self.client.force_login(self.graduate)

        self.assertEqual(
            self.client.get(
                reverse("specimens:label_pdf", kwargs={"detail_uuid": self.specimen.detail_uuid})
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("specimens:qr_label_pdf", kwargs={"detail_uuid": self.specimen.detail_uuid})
            ).status_code,
            404,
        )

    def test_member_can_add_photos_but_invalid_upload_does_not_add_any(self):
        self.client.force_login(self.member)
        photo_add_url = reverse(
            "specimens:photo_add", kwargs={"detail_uuid": self.specimen.detail_uuid}
        )
        response = self.client.post(photo_add_url, {"photos": _image_upload()})
        self.assertRedirects(response, self.detail_url(), fetch_redirect_response=False)
        self.assertEqual(self.specimen.photos.count(), 2)

        response = self.client.post(
            photo_add_url,
            {
                "photos": [
                    _image_upload(),
                    SimpleUploadedFile("bad.svg", b"<svg/>", content_type="image/svg+xml"),
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JPEG、PNG、WebP")
        self.assertEqual(self.specimen.photos.count(), 2)

    def test_invalid_state_transition_is_rejected_without_new_event(self):
        self.client.force_login(self.member)
        event_url = reverse("specimens:event", kwargs={"detail_uuid": self.specimen.detail_uuid})
        first = self.client.post(event_url, {"event_type": "loan"})
        self.assertRedirects(first, self.detail_url(), fetch_redirect_response=False)
        self.specimen.refresh_from_db()
        self.assertEqual(self.specimen.status, Specimen.Status.ON_LOAN)
        event_count = self.specimen.events.count()

        response = self.client.post(event_url, {"event_type": "loan"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "現在の状態では")
        self.assertEqual(self.specimen.events.count(), event_count)


def _image_upload():
    output = BytesIO()
    Image.new("RGB", (10, 10), "green").save(output, "PNG")
    return SimpleUploadedFile("photo.png", output.getvalue(), content_type="image/png")
