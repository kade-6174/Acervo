from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from specimens.management.commands.import_japanese_butterfly_taxa import _fetch, _SpeciesListParser
from specimens.models import Taxon, TaxonSource
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
        response = self.client.post(
            reverse("specimens:taxon_manual_create"),
            {"scientific_name": "Papilio xuthus", "japanese_name": "アゲハ", "rank": "species"},
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
