"""参照されていない旧便覧版の分類だけを明示実行で削除する。"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from specimens.models import (
    Specimen,
    Taxon,
    TaxonDataset,
    TaxonDatasetRecord,
    TaxonDatasetRevision,
    TaxonSource,
)

LEGACY_DATASET_SLUG = "japanese-butterflies-binran-2010-2013"


def _delete_leaves_first(model, ids):
    remaining = set(ids)
    while remaining:
        parent_ids = set(
            model.objects.filter(pk__in=remaining, parent_id__in=remaining).values_list(
                "parent_id", flat=True
            )
        )
        leaves = remaining - parent_ids
        if not leaves:
            raise CommandError("旧分類の階層に循環があります。削除を中止します。")
        model.objects.filter(pk__in=leaves).delete()
        remaining -= leaves


class Command(BaseCommand):
    help = "既存標本等が参照しない旧便覧版の分類を削除する"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="確認後に削除を実行する")

    @transaction.atomic
    def handle(self, *args, **options):
        dataset = TaxonDataset.objects.select_for_update().filter(slug=LEGACY_DATASET_SLUG).first()
        if dataset is None:
            self.stdout.write("LEGACY_ABSENT")
            return

        records = list(
            TaxonDatasetRecord.objects.select_for_update()
            .filter(dataset=dataset)
            .values_list("pk", "taxon_id")
        )
        record_ids = {record_id for record_id, _ in records}
        taxon_ids = {taxon_id for _, taxon_id in records if taxon_id is not None}
        if len(taxon_ids) != len(records):
            raise CommandError("旧分類レコードと分類の対応が一対一ではありません。")
        locked_taxon_ids = set(
            Taxon.objects.select_for_update().filter(pk__in=taxon_ids).values_list("pk", flat=True)
        )
        if locked_taxon_ids != taxon_ids:
            raise CommandError("旧分類の参照先が存在しません。")

        if Specimen.objects.filter(taxon_id__in=taxon_ids).exists():
            raise CommandError("旧分類を参照する標本があります。削除を中止します。")
        if (
            TaxonDatasetRecord.objects.exclude(dataset=dataset)
            .filter(taxon_id__in=taxon_ids)
            .exists()
        ):
            raise CommandError("別の分類版と共有する分類があります。削除を中止します。")
        if (
            TaxonDatasetRecord.objects.exclude(dataset=dataset)
            .filter(parent_id__in=record_ids)
            .exists()
        ):
            raise CommandError("別の分類版から参照する下位分類があります。")
        if Taxon.objects.exclude(pk__in=taxon_ids).filter(parent_id__in=taxon_ids).exists():
            raise CommandError("手入力等の分類から参照する下位分類があります。")
        if TaxonSource.objects.filter(taxon_id__in=taxon_ids).exists():
            raise CommandError("旧分類に追加された出典があります。削除を中止します。")

        revision_count = TaxonDatasetRevision.objects.filter(dataset=dataset).count()
        counts = f"records={len(records)} taxa={len(taxon_ids)} revisions={revision_count}"
        if not options["apply"]:
            self.stdout.write(f"LEGACY_READY {counts}")
            return

        TaxonDatasetRevision.objects.filter(dataset=dataset).delete()
        _delete_leaves_first(TaxonDatasetRecord, record_ids)
        dataset.delete()
        _delete_leaves_first(Taxon, taxon_ids)
        self.stdout.write(f"LEGACY_REMOVED {counts}")
