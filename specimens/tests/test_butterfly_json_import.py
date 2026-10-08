"""ローカル和名分類JSONだけを使う取込みの検証。"""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from specimens.management.commands.import_japanese_butterfly_taxa import (
    DATASET_SLUG,
    DEFAULT_SOURCE,
    _validated_source,
)
from specimens.models import Specimen, Taxon, TaxonDataset, TaxonDatasetRecord


class JapaneseButterflyJsonImportTests(TestCase):
    def setUp(self):
        self.source_file = Path("butterflies.json")
        self.payload = {
            "title": "テスト用和名分類",
            "source": {
                "title": "テスト用出典",
                "url": "https://example.invalid/taxa",
                "license": "CC BY 3.0 Unported",
            },
            "count": 328,
            "taxa": [
                {
                    "界": "動物界",
                    "門": "節足動物門",
                    "綱": "昆虫綱",
                    "目": "チョウ目",
                    "科": "テストチョウ科",
                    "亜科": "テストチョウ亜科",
                    "族": "テストチョウ族" if index % 2 else None,
                    "属": "テストチョウ属" if index % 2 else "別テストチョウ属",
                    "種": f"テスト種{index:03d}",
                }
                for index in range(328)
            ],
        }

    def _call_import(self, **kwargs):
        raw = json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
        with patch.object(Path, "read_bytes", return_value=raw):
            return call_command(
                "import_japanese_butterfly_taxa", source_file=self.source_file, **kwargs
            )

    def test_bundled_source_is_the_approved_328_species_file(self):
        payload, raw, nodes = _validated_source(DEFAULT_SOURCE)
        self.assertEqual(len(payload["taxa"]), 328)
        self.assertEqual(len(nodes), 557)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "1c9fb5a46cf825cc5e1a0ab04806571e502505e441a8edc6ed4b9406ac4cfa33",
        )

    def test_bundled_source_creates_the_expected_hierarchy(self):
        call_command("import_japanese_butterfly_taxa", verbosity=0)
        records = TaxonDatasetRecord.objects.filter(dataset__slug=DATASET_SLUG)
        self.assertEqual(records.count(), 557)
        self.assertEqual(records.filter(rank="family").count(), 5)
        self.assertEqual(records.filter(rank="subfamily").count(), 21)
        self.assertEqual(records.filter(rank="tribe").count(), 31)
        self.assertEqual(records.filter(rank="genus").count(), 168)
        self.assertEqual(records.filter(rank="species").count(), 328)
        self.assertFalse(records.exclude(scientific_name="").exists())

    def test_import_is_atomic_idempotent_and_preserves_existing_taxa(self):
        old_dataset = TaxonDataset.objects.create(
            slug="japanese-butterflies-binran-2010-2013",
            title="従来の分類",
            version="旧版",
            license_name="CC BY 3.0",
            source_url="https://example.invalid/old",
            retrieved_on=timezone.localdate(),
            attribution="従来データ",
        )
        old_taxon = Taxon.objects.create(
            scientific_name="Papilio xuthus", japanese_name="アゲハ", rank="species"
        )
        owner = User.objects.create_user(username="historic-owner", cohort_number=33)
        specimen = Specimen.objects.create(
            specimen_code="HIST-000001",
            taxon=old_taxon,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            created_by=owner,
        )
        self._call_import(verbosity=0)

        dataset = TaxonDataset.objects.get(slug=DATASET_SLUG)
        self.assertEqual(dataset.records.filter(rank="species").count(), 328)
        self.assertEqual(dataset.records.filter(rank="tribe").count(), 1)
        self.assertEqual(dataset.records.count(), 337)
        species = dataset.records.get(japanese_name="テスト種001")
        self.assertEqual(species.scientific_name, "")
        self.assertEqual(species.parent.rank, "genus")
        self.assertEqual(species.parent.parent.rank, "tribe")
        self.assertEqual(dataset.revisions.count(), 1)
        self.assertTrue(TaxonDataset.objects.filter(pk=old_dataset.pk).exists())
        self.assertTrue(Taxon.objects.filter(pk=old_taxon.pk).exists())
        specimen.refresh_from_db()
        self.assertEqual(specimen.taxon_id, old_taxon.pk)

        self._call_import(verbosity=0)
        self.assertEqual(dataset.records.count(), 337)
        self.assertEqual(dataset.revisions.count(), 1)

    def test_bad_source_and_changed_version_cannot_modify_existing_dataset(self):
        self.payload["count"] = 327
        with self.assertRaises(CommandError):
            self._call_import()
        self.assertFalse(TaxonDataset.objects.exists())

        self.payload["count"] = 328
        self._call_import(verbosity=0)
        self.payload["taxa"][0]["種"] = "変更された種"
        with self.assertRaises(CommandError):
            self._call_import()
        self.assertEqual(TaxonDatasetRecord.objects.filter(rank="species").count(), 328)
        self.assertFalse(TaxonDatasetRecord.objects.filter(japanese_name="変更された種").exists())

    def test_duplicate_path_is_rejected_before_database_write(self):
        self.payload["taxa"][1] = self.payload["taxa"][0].copy()
        with self.assertRaises(CommandError):
            self._call_import()
        self.assertFalse(TaxonDataset.objects.exists())
