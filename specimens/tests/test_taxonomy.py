from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from specimens.forms import SpecimenRegistrationForm, TaxonManualForm
from specimens.models import QRLabel, Specimen, Taxon, TaxonDataset, TaxonDatasetRecord, TaxonSource
from specimens.services import (
    TaxonCandidate,
    adopt_external_taxon_candidate,
    create_qr_batch,
    search_taxon_candidates,
)


class TaxonomyServiceTests(TestCase):
    def test_local_taxon_is_preferred_without_external_request(self):
        local = Taxon.objects.create(scientific_name="Papilio xuthus", japanese_name="アゲハ")

        with (
            override_settings(ACERVO_TAXON_EXTERNAL_SEARCH_ENABLED=True),
            patch("specimens.services.urlopen") as mocked_open,
        ):
            local_candidates, external_candidates = search_taxon_candidates("xuthus")

        self.assertEqual(local_candidates, (local,))
        self.assertEqual(external_candidates, ())
        mocked_open.assert_not_called()

    @override_settings(ACERVO_TAXON_EXTERNAL_SEARCH_ENABLED=True)
    def test_external_timeout_returns_empty_candidates_so_manual_entry_remains_possible(self):
        with patch("specimens.services.urlopen", side_effect=TimeoutError):
            local_candidates, external_candidates = search_taxon_candidates("unknown butterfly")

        self.assertEqual(local_candidates, ())
        self.assertEqual(external_candidates, ())

    def test_adopting_external_candidate_records_source_and_checked_date(self):
        candidate = TaxonCandidate(
            scientific_name="Papilio xuthus",
            japanese_name="",
            rank="SPECIES",
            source_url="https://www.gbif.org/species/1",
            citation="GBIF Backbone Taxonomy",
            external=True,
        )

        taxon = adopt_external_taxon_candidate(candidate)

        source = TaxonSource.objects.get(taxon=taxon)
        self.assertEqual(source.source_url, candidate.source_url)
        self.assertEqual(source.citation, candidate.citation)
        self.assertIsNotNone(source.checked_on)


class TaxonomyViewsTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="taxonomy-member", cohort_number=33)
        self.graduate = User.objects.create_user(username="taxonomy-graduate", cohort_number=30)

    def test_graduate_cannot_search_or_create_taxa(self):
        self.client.force_login(self.graduate)

        self.assertEqual(self.client.get(reverse("specimens:taxon_search")).status_code, 404)
        self.assertEqual(self.client.get(reverse("specimens:taxon_manual_create")).status_code, 404)

    def test_external_failure_does_not_block_manual_taxon_registration(self):
        self.client.force_login(self.member)
        with patch("specimens.views.search_taxon_candidates", return_value=((), ())):
            response = self.client.get(reverse("specimens:taxon_search"), {"query": "候補なし"})

        self.assertContains(response, "手入力で登録")
        family = Taxon.objects.create(scientific_name="Papilionidae", rank="family")
        genus = Taxon.objects.create(scientific_name="Papilio", rank="genus", parent=family)
        response = self.client.post(
            reverse("specimens:taxon_manual_create"),
            {
                "scientific_name": "Papilio xuthus",
                "japanese_name": "アゲハ",
                "rank": "species",
                "parent": genus.pk,
            },
        )
        taxon = Taxon.objects.get(scientific_name="Papilio xuthus")
        self.assertRedirects(response, f"{reverse('specimens:taxon_search')}?created={taxon.pk}")

    def test_external_candidate_adoption_uses_server_side_session_data(self):
        self.client.force_login(self.member)
        candidate = TaxonCandidate(
            scientific_name="Papilio xuthus",
            japanese_name="",
            rank="SPECIES",
            source_url="https://www.gbif.org/species/1",
            citation="GBIF Backbone Taxonomy",
            external=True,
        )
        with patch("specimens.views.search_taxon_candidates", return_value=((), (candidate,))):
            response = self.client.get(reverse("specimens:taxon_search"), {"query": "xuthus"})
        key, _ = response.context["external_candidates"][0]

        response = self.client.post(
            reverse("specimens:taxon_adopt_external"),
            {"candidate_key": key},
        )

        taxon = Taxon.objects.get(scientific_name="Papilio xuthus")
        self.assertRedirects(response, f"{reverse('specimens:taxon_search')}?created={taxon.pk}")
        self.assertEqual(TaxonSource.objects.get().citation, "GBIF Backbone Taxonomy")


class ButterflyHierarchyFormTests(TestCase):
    def setUp(self):
        dataset = TaxonDataset.objects.create(
            slug="japanese-butterflies-ja-328",
            title="日本産蝶類和名学名便覧",
            version="2010–2013",
            license_name="CC BY 3.0",
            source_url="https://example.invalid/butterflies",
            retrieved_on=timezone.localdate(),
            attribution="テスト用の出典表記",
        )
        self.family_taxon = Taxon.objects.create(
            scientific_name="Papilionidae", japanese_name="アゲハチョウ科", rank="family"
        )
        self.genus_taxon = Taxon.objects.create(
            scientific_name="Papilio", rank="genus", parent=self.family_taxon
        )
        self.subfamily_taxon = Taxon.objects.create(
            japanese_name="アゲハチョウ亜科", rank="subfamily", parent=self.family_taxon
        )
        self.genus_taxon.parent = self.subfamily_taxon
        self.genus_taxon.save(update_fields=["parent"])
        self.species_taxon = Taxon.objects.create(
            scientific_name="Papilio xuthus",
            japanese_name="アゲハ",
            rank="species",
            parent=self.genus_taxon,
        )
        self.family = TaxonDatasetRecord.objects.create(
            dataset=dataset,
            source_key="family-Papilionidae",
            rank=TaxonDatasetRecord.Rank.FAMILY,
            scientific_name="Papilionidae",
            japanese_name="アゲハチョウ科",
            taxon=self.family_taxon,
        )
        self.genus = TaxonDatasetRecord.objects.create(
            dataset=dataset,
            source_key="genus-Papilionidae-Papilio",
            parent=None,
            rank=TaxonDatasetRecord.Rank.GENUS,
            scientific_name="Papilio",
            taxon=self.genus_taxon,
        )
        self.subfamily = TaxonDatasetRecord.objects.create(
            dataset=dataset,
            source_key="subfamily-Papilioninae",
            parent=self.family,
            rank=TaxonDatasetRecord.Rank.SUBFAMILY,
            japanese_name="アゲハチョウ亜科",
            taxon=self.subfamily_taxon,
        )
        self.genus.parent = self.subfamily
        self.genus.save(update_fields=["parent"])
        self.species = TaxonDatasetRecord.objects.create(
            dataset=dataset,
            source_key="species-100",
            parent=self.genus,
            rank=TaxonDatasetRecord.Rank.SPECIES,
            scientific_name="Papilio xuthus",
            japanese_name="アゲハ",
            taxon=self.species_taxon,
        )

    def test_registration_uses_the_deepest_selected_japanese_butterfly_taxon(self):
        form = SpecimenRegistrationForm(
            {
                "butterfly_family": self.family.pk,
                "butterfly_subfamily": self.subfamily.pk,
                "butterfly_genus": self.genus.pk,
                "butterfly_species": self.species.pk,
                "acquisition_method": "other",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["taxon"], self.species_taxon)
        self.assertNotIn("butterfly_species", form.cleaned_data)
        family_labels = [str(label) for _, label in form.fields["butterfly_family"].choices]
        self.assertIn("アゲハチョウ科（Papilionidae）", family_labels)

    def test_registration_renders_dataset_options_in_each_hierarchy_select(self):
        form = SpecimenRegistrationForm()

        for field_name, record in (
            ("butterfly_family", self.family),
            ("butterfly_subfamily", self.subfamily),
            ("butterfly_genus", self.genus),
            ("butterfly_species", self.species),
        ):
            self.assertIn(f'value="{record.pk}"', str(form[field_name]))
        self.assertIn(
            f'data-ancestor-ids="{self.genus.pk},{self.subfamily.pk},{self.family.pk}"',
            str(form["butterfly_species"]),
        )

    def test_registration_accepts_lower_ranks_without_selecting_upper_ranks(self):
        for selections in (
            {"butterfly_species": self.species.pk},
            {"butterfly_genus": self.genus.pk},
            {"butterfly_family": self.family.pk, "butterfly_species": self.species.pk},
        ):
            with self.subTest(selections=selections):
                form = SpecimenRegistrationForm({**selections, "acquisition_method": "other"})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(
                    form.cleaned_data["taxon"],
                    self.species_taxon if "butterfly_species" in selections else self.genus_taxon,
                )

    def test_registration_does_not_render_another_classification_list(self):
        Taxon.objects.create(japanese_name="手入力の種", rank="species")
        form = SpecimenRegistrationForm()
        html = str(form["taxon"])
        self.assertIn('type="hidden"', html)
        self.assertNotIn("<select", html)
        self.assertNotIn("手入力の種", html)
        self.assertFalse(
            SpecimenRegistrationForm(
                {"taxon": self.species_taxon.pk, "acquisition_method": "other"}
            ).is_valid()
        )
        saved = SpecimenRegistrationForm(
            {"taxon": self.species_taxon.pk, "acquisition_method": "other"},
            allow_saved_taxon=True,
        )
        self.assertTrue(saved.is_valid(), saved.errors)

    def test_japanese_classification_survives_qr_confirmation(self):
        member = User.objects.create_user(username="butterfly-member", cohort_number=33)
        label = QRLabel.objects.get(
            pk=create_qr_batch(requested_count=1, created_by=member).label_ids[0]
        )
        register_url = reverse("specimens:register", kwargs={"token": label.token})
        confirm_url = reverse("specimens:register_confirm", kwargs={"token": label.token})
        self.client.force_login(member)

        self.assertNotContains(self.client.get(register_url), "別の分類を選択する")
        response = self.client.post(
            register_url,
            {"butterfly_species": self.species.pk, "acquisition_method": "other"},
        )
        self.assertRedirects(response, confirm_url, fetch_redirect_response=False)
        self.assertContains(self.client.get(confirm_url), "アゲハ")
        response = self.client.post(confirm_url)

        self.assertEqual(response.status_code, 200)
        specimen = Specimen.objects.get()
        self.assertEqual(specimen.taxon_id, self.species_taxon.pk)
        label.refresh_from_db()
        self.assertEqual(label.specimen_id, specimen.pk)
        self.assertContains(
            self.client.get(reverse("specimens:edit", args=[specimen.detail_uuid])),
            "分類候補を検索・登録する",
        )

    def test_registration_rejects_a_species_outside_the_selected_genus(self):
        other_genus_taxon = Taxon.objects.create(
            scientific_name="Graphium", rank="genus", parent=self.subfamily_taxon
        )
        other_genus = TaxonDatasetRecord.objects.create(
            dataset=self.family.dataset,
            source_key="genus-Papilionidae-Graphium",
            parent=self.subfamily,
            rank=TaxonDatasetRecord.Rank.GENUS,
            scientific_name="Graphium",
            taxon=other_genus_taxon,
        )
        form = SpecimenRegistrationForm(
            {
                "butterfly_family": self.family.pk,
                "butterfly_subfamily": self.subfamily.pk,
                "butterfly_genus": other_genus.pk,
                "butterfly_species": self.species.pk,
                "acquisition_method": "other",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("butterfly_species", form.errors)

        other_family_taxon = Taxon.objects.create(japanese_name="別の科", rank="family")
        other_family = TaxonDatasetRecord.objects.create(
            dataset=self.family.dataset,
            source_key="family-other",
            rank=TaxonDatasetRecord.Rank.FAMILY,
            japanese_name="別の科",
            taxon=other_family_taxon,
        )
        mismatched = SpecimenRegistrationForm(
            {
                "butterfly_family": other_family.pk,
                "butterfly_species": self.species.pk,
                "acquisition_method": "other",
            }
        )
        self.assertFalse(mismatched.is_valid())
        self.assertIn("butterfly_species", mismatched.errors)

    def test_registration_allows_skipped_tribe_but_rejects_a_different_tribe(self):
        tribe_taxon = Taxon.objects.create(
            japanese_name="アゲハチョウ族", rank="tribe", parent=self.subfamily_taxon
        )
        tribe = TaxonDatasetRecord.objects.create(
            dataset=self.family.dataset,
            source_key="tribe-Papilionini",
            parent=self.subfamily,
            rank=TaxonDatasetRecord.Rank.TRIBE,
            japanese_name="アゲハチョウ族",
            taxon=tribe_taxon,
        )
        self.genus.parent = tribe
        self.genus.save(update_fields=["parent"])
        base = {
            "butterfly_family": self.family.pk,
            "butterfly_subfamily": self.subfamily.pk,
            "butterfly_genus": self.genus.pk,
            "butterfly_species": self.species.pk,
            "acquisition_method": "other",
        }
        without_tribe = SpecimenRegistrationForm(base)
        self.assertTrue(without_tribe.is_valid(), without_tribe.errors)
        valid = SpecimenRegistrationForm({**base, "butterfly_tribe": tribe.pk})
        self.assertTrue(valid.is_valid(), valid.errors)

        another_tribe_taxon = Taxon.objects.create(japanese_name="別の族", rank="tribe")
        another_tribe = TaxonDatasetRecord.objects.create(
            dataset=self.family.dataset,
            source_key="tribe-other",
            parent=self.subfamily,
            rank=TaxonDatasetRecord.Rank.TRIBE,
            japanese_name="別の族",
            taxon=another_tribe_taxon,
        )
        mismatched = SpecimenRegistrationForm({**base, "butterfly_tribe": another_tribe.pk})
        self.assertFalse(mismatched.is_valid())
        self.assertIn("butterfly_species", mismatched.errors)

        skipped = SpecimenRegistrationForm(
            {
                "butterfly_family": self.family.pk,
                "butterfly_genus": self.genus.pk,
                "butterfly_species": self.species.pk,
                "acquisition_method": "other",
            }
        )
        self.assertTrue(skipped.is_valid(), skipped.errors)

    def test_manual_form_uses_japanese_rank_labels_and_validates_the_parent_rank(self):
        form = TaxonManualForm(
            {
                "scientific_name": "Papilio bianor",
                "japanese_name": "カラスアゲハ",
                "rank": "species",
                "parent": self.genus_taxon.pk,
            }
        )

        self.assertEqual(form.fields["rank"].choices[1], ("family", "科"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().rank, "species")

        invalid = TaxonManualForm(
            {
                "scientific_name": "Papilio maackii",
                "japanese_name": "ミヤマカラスアゲハ",
                "rank": "species",
                "parent": self.family_taxon.pk,
            }
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("parent", invalid.errors)

    def test_manual_form_marks_parent_candidates_with_their_rank(self):
        html = TaxonManualForm().as_p()

        self.assertIn('data-taxon-rank="family"', html)
        self.assertIn("data-manual-taxon-rank", html)
