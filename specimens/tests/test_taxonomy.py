from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from specimens.forms import SpecimenRegistrationForm, TaxonManualForm
from specimens.management.commands.import_japanese_butterfly_taxa import _fetch, _SpeciesListParser
from specimens.models import Taxon, TaxonDataset, TaxonDatasetRecord, TaxonSource
from specimens.services import (
    TaxonCandidate,
    adopt_external_taxon_candidate,
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
            slug="japanese-butterflies-binran-2010-2013",
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
            parent=self.family,
            rank=TaxonDatasetRecord.Rank.GENUS,
            scientific_name="Papilio",
            taxon=self.genus_taxon,
        )
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

    def test_registration_rejects_a_species_outside_the_selected_genus(self):
        other_genus_taxon = Taxon.objects.create(
            scientific_name="Graphium", rank="genus", parent=self.family_taxon
        )
        other_genus = TaxonDatasetRecord.objects.create(
            dataset=self.family.dataset,
            source_key="genus-Papilionidae-Graphium",
            parent=self.family,
            rank=TaxonDatasetRecord.Rank.GENUS,
            scientific_name="Graphium",
            taxon=other_genus_taxon,
        )
        form = SpecimenRegistrationForm(
            {
                "butterfly_family": self.family.pk,
                "butterfly_genus": other_genus.pk,
                "butterfly_species": self.species.pk,
                "acquisition_method": "other",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("butterfly_species", form.errors)

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


class JapaneseButterflyParserTests(TestCase):
    def test_parser_keeps_species_author_year_and_omits_nested_subspecies(self):
        parser = _SpeciesListParser()
        parser.feed(
            "<ol><li><i>Papilio</i> <i>xuthus</i> Linnaeus, 1767 アゲハ"
            '<a href="/species/100">詳細</a></li><ul><li><i>Papilio</i> <i>xuthus</i>'
            '<i>formosana</i> Fruhstorfer, 1908 アゲハ亜種 <a href="/species/101">詳細</a>'
            "</li></ul></ol>"
        )

        self.assertEqual(len(parser.entries), 1)
        entry = parser.entries[0]
        self.assertEqual(entry.scientific_name, "Papilio xuthus")
        self.assertEqual(entry.scientific_author, "Linnaeus")
        self.assertEqual(entry.original_publication_year, 1767)
        self.assertEqual(entry.japanese_name, "アゲハ")
        self.assertEqual(entry.source_key, "species-100")

    def test_fetch_retries_transient_connection_failure(self):
        response = MagicMock()
        response.read.return_value = b"<html></html>"
        response.__enter__.return_value = response
        with (
            patch(
                "specimens.management.commands.import_japanese_butterfly_taxa.urlopen",
                side_effect=[OSError("temporary"), response],
            ) as mocked_open,
            patch(
                "specimens.management.commands.import_japanese_butterfly_taxa.time.sleep"
            ) as mocked_sleep,
        ):
            result = _fetch(
                "https://web.archive.org/web/20210505224155/https://binran.lepimages.jp/"
            )

        self.assertEqual(result, "<html></html>")
        self.assertEqual(mocked_open.call_count, 2)
        mocked_sleep.assert_called_once_with(1)
