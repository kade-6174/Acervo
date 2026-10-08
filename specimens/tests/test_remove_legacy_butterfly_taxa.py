from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from specimens.forms import SpecimenRegistrationForm
from specimens.management.commands.remove_legacy_butterfly_taxa import LEGACY_DATASET_SLUG
from specimens.models import (
    Specimen,
    Taxon,
    TaxonDataset,
    TaxonDatasetRecord,
    TaxonDatasetRevision,
)


class RemoveLegacyButterflyTaxaTests(TestCase):
    def setUp(self):
        self.dataset = TaxonDataset.objects.create(
            slug=LEGACY_DATASET_SLUG,
            title="旧便覧版",
            version="2010-2013",
            license_name="CC BY 3.0",
            source_url="https://example.invalid/old",
            retrieved_on=timezone.localdate(),
            attribution="旧分類",
        )
        self.family_taxon = Taxon.objects.create(japanese_name="旧科", rank="family")
        self.species_taxon = Taxon.objects.create(
            japanese_name="旧種", rank="species", parent=self.family_taxon
        )
        self.family_record = TaxonDatasetRecord.objects.create(
            dataset=self.dataset,
            source_key="family",
            rank="family",
            japanese_name="旧科",
            taxon=self.family_taxon,
        )
        TaxonDatasetRecord.objects.create(
            dataset=self.dataset,
            source_key="species",
            parent=self.family_record,
            rank="species",
            japanese_name="旧種",
            taxon=self.species_taxon,
        )
        TaxonDatasetRevision.objects.create(dataset=self.dataset, note="旧版の取込み")

    def test_preview_and_apply_remove_only_legacy_dataset(self):
        other_taxon = Taxon.objects.create(japanese_name="手入力の種", rank="species")
        output = StringIO()
        call_command("remove_legacy_butterfly_taxa", stdout=output)
        self.assertIn("LEGACY_READY records=2 taxa=2 revisions=1", output.getvalue())
        self.assertTrue(TaxonDataset.objects.filter(pk=self.dataset.pk).exists())
        self.assertNotIn(self.species_taxon, SpecimenRegistrationForm().fields["taxon"].queryset)

        output = StringIO()
        call_command("remove_legacy_butterfly_taxa", apply=True, stdout=output)
        self.assertIn("LEGACY_REMOVED records=2 taxa=2 revisions=1", output.getvalue())
        self.assertFalse(TaxonDataset.objects.filter(pk=self.dataset.pk).exists())
        self.assertFalse(Taxon.objects.filter(pk=self.family_taxon.pk).exists())
        self.assertFalse(Taxon.objects.filter(pk=self.species_taxon.pk).exists())
        self.assertTrue(Taxon.objects.filter(pk=other_taxon.pk).exists())

    def test_specimen_reference_aborts_without_deleting_anything(self):
        owner = User.objects.create_user(username="legacy-owner", cohort_number=33)
        Specimen.objects.create(
            specimen_code="LEGACY-000001",
            taxon=self.species_taxon,
            acquisition_method=Specimen.AcquisitionMethod.OTHER,
            created_by=owner,
        )

        with self.assertRaisesMessage(CommandError, "旧分類を参照する標本"):
            call_command("remove_legacy_butterfly_taxa", apply=True)

        self.assertEqual(self.dataset.records.count(), 2)
        self.assertTrue(Taxon.objects.filter(pk=self.species_taxon.pk).exists())

    def test_manually_added_child_aborts(self):
        child = Taxon.objects.create(japanese_name="手入力の下位分類", parent=self.family_taxon)

        with self.assertRaisesMessage(CommandError, "手入力等の分類"):
            call_command("remove_legacy_butterfly_taxa", apply=True)

        self.assertTrue(Taxon.objects.filter(pk=child.pk).exists())
        self.assertTrue(TaxonDataset.objects.filter(pk=self.dataset.pk).exists())
