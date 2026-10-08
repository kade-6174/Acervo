"""指定されたローカルJSONだけから日本産蝶類の和名階層を取り込む。"""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from specimens.models import Taxon, TaxonDataset, TaxonDatasetRecord, TaxonDatasetRevision

DATASET_SLUG = "japanese-butterflies-ja-328"
RANKS = (
    ("界", TaxonDatasetRecord.Rank.KINGDOM),
    ("門", TaxonDatasetRecord.Rank.PHYLUM),
    ("綱", TaxonDatasetRecord.Rank.CLASS),
    ("目", TaxonDatasetRecord.Rank.ORDER),
    ("科", TaxonDatasetRecord.Rank.FAMILY),
    ("亜科", TaxonDatasetRecord.Rank.SUBFAMILY),
    ("族", TaxonDatasetRecord.Rank.TRIBE),
    ("属", TaxonDatasetRecord.Rank.GENUS),
    ("種", TaxonDatasetRecord.Rank.SPECIES),
)
DEFAULT_SOURCE = Path(settings.BASE_DIR) / "specimens" / "data" / "japanese_butterflies_ja_328.json"


def _validated_source(source_file):
    try:
        raw = source_file.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CommandError("分類JSONを読み取れません。取込みを中止します。") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("source"), dict):
        raise CommandError("分類JSONの出典情報が不正です。")
    source = payload["source"]
    if not all(
        isinstance(source.get(key), str) and source[key] for key in ("title", "url", "license")
    ):
        raise CommandError("分類JSONの出典・利用条件を確認できません。")
    rows = payload.get("taxa")
    if payload.get("count") != 328 or not isinstance(rows, list) or len(rows) != 328:
        raise CommandError("分類JSONは328種でなければなりません。")
    paths = set()
    nodes = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {key for key, _ in RANKS}:
            raise CommandError("分類JSONの階級が不正です。")
        if any(
            not isinstance(row[key], str) or not row[key].strip() for key, _ in RANKS if key != "族"
        ):
            raise CommandError("分類JSONに空の必須階級があります。")
        if row["族"] is not None and (not isinstance(row["族"], str) or not row["族"].strip()):
            raise CommandError("分類JSONの族が不正です。")
        path = tuple(row[key].strip() if row[key] is not None else None for key, _ in RANKS)
        if path in paths:
            raise CommandError("分類JSONに重複した種があります。")
        paths.add(path)
        current = ()
        for value in path:
            if value is not None:
                current += (value,)
                nodes.add(current)
    return payload, raw, nodes


class Command(BaseCommand):
    help = "指定されたローカルJSONだけから日本産蝶類328種の和名分類を取り込む"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="保存せず件数を検証する")
        parser.add_argument(
            "--source-file", type=Path, default=DEFAULT_SOURCE, help="分類JSONのローカルパス"
        )

    def handle(self, *args, **options):
        payload, raw, nodes = _validated_source(options["source_file"])
        version = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"検証成功: 328種、{len(nodes)}階層項目。"))
            return

        source = payload["source"]
        attribution = (
            f"出典：{source['title']}。{source['license']}。"
            f"{source['url']}。指定JSONから和名分類階層のみを取り込んだ。"
        )
        with transaction.atomic():
            dataset, created = TaxonDataset.objects.get_or_create(
                slug=DATASET_SLUG,
                defaults={
                    "title": payload.get("title") or source["title"],
                    "version": version,
                    "license_name": source["license"],
                    "source_url": source["url"],
                    "retrieved_on": timezone.localdate(),
                    "attribution": attribution,
                },
            )
            if not created:
                if dataset.version != version or dataset.records.count() != len(nodes):
                    raise CommandError(
                        "既存の分類版と一致しません。既存データを上書きせず中止します。"
                    )
                self.stdout.write(self.style.SUCCESS("取込み済み: 分類版は変更されていません。"))
                return

            records = {}
            taxa = {}
            for row in payload["taxa"]:
                parent_path = ()
                for key, rank in RANKS:
                    name = row[key]
                    if name is None:
                        continue
                    path = (*parent_path, name.strip())
                    if path not in records:
                        parent_taxon = taxa.get(parent_path)
                        taxon = Taxon.objects.create(
                            scientific_name="",
                            japanese_name=name.strip(),
                            rank=rank,
                            parent=parent_taxon,
                        )
                        path_json = json.dumps(path, ensure_ascii=False).encode("utf-8")
                        source_key = f"{rank}-{hashlib.sha256(path_json).hexdigest()}"
                        record = TaxonDatasetRecord.objects.create(
                            dataset=dataset,
                            source_key=source_key,
                            parent=records.get(parent_path),
                            rank=rank,
                            scientific_name="",
                            japanese_name=name.strip(),
                            source_url=source["url"],
                            taxon=taxon,
                        )
                        records[path] = record
                        taxa[path] = taxon
                    parent_path = path
            TaxonDatasetRevision.objects.create(
                dataset=dataset, note="指定された和名分類JSONを初回取込み"
            )
        self.stdout.write(self.style.SUCCESS("取込み成功: 328種の和名分類を保存しました。"))
