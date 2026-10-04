"""日本産蝶類和名学名便覧の分類データだけを、明示実行で取り込む。"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from specimens.models import Taxon, TaxonDataset, TaxonDatasetRecord, TaxonDatasetRevision

ARCHIVE_URL = "https://web.archive.org/web/20210505224155/https://binran.lepimages.jp/"
DATASET_SLUG = "japanese-butterflies-binran-2010-2013"
ATTRIBUTION = (
    "出典：猪又敏男・植村好延・矢後勝也・神保宇嗣・上田恭一郎（2010–2013）"
    "『日本産蝶類和名学名便覧』。CC BY 3.0。Wayback Machine 2021-05-05保存版を"
    "Acervo用に分類階層・データ形式を整形して利用。"
)


@dataclass(frozen=True)
class SpeciesEntry:
    source_key: str
    scientific_name: str
    japanese_name: str
    scientific_author: str
    original_publication_year: int | None
    source_url: str


class _SpeciesListParser(HTMLParser):
    """保存版の種一覧から、最上位の種リストだけを読み取る最小パーサー。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ol_depth = 0
        self.ul_depth = 0
        self._current: dict | None = None
        self.entries: list[SpeciesEntry] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "ol":
            self.ol_depth += 1
        elif tag == "ul":
            self.ul_depth += 1
        elif tag == "li" and self.ol_depth and not self.ul_depth:
            self._finish_current()
            self._current = {"text": [], "italics": [], "source_key": ""}
        elif tag == "i" and self._current is not None:
            self._current["in_italic"] = True
        elif tag == "a" and self._current is not None:
            self._current["in_link"] = True
            match = re.search(r"/species/(\d+)", attributes.get("href", ""))
            if match:
                self._current["source_key"] = f"species-{match.group(1)}"

    def handle_endtag(self, tag):
        if tag == "i" and self._current is not None:
            self._current["in_italic"] = False
        elif tag == "a" and self._current is not None:
            self._current["in_link"] = False
        elif tag == "li":
            self._finish_current()
        elif tag == "ul":
            self.ul_depth = max(0, self.ul_depth - 1)
        elif tag == "ol":
            self.ol_depth = max(0, self.ol_depth - 1)

    def handle_data(self, data):
        if self._current is None:
            return
        text = " ".join(data.split())
        if not text or self._current.get("in_link"):
            return
        self._current["text"].append(text)
        if self._current.get("in_italic"):
            self._current["italics"].append(text)

    def _finish_current(self):
        if self._current is None:
            return
        entry = _entry_from_parts(
            self._current["source_key"], self._current["italics"], self._current["text"]
        )
        if entry:
            self.entries.append(entry)
        self._current = None


def _entry_from_parts(source_key, italics, text_parts):
    if not source_key or len(italics) < 2:
        return None
    scientific_name = " ".join(italics[:2])
    full_text = " ".join(text_parts)
    remainder = full_text.replace(scientific_name, "", 1).strip()
    japanese_start = re.search(r"[\u3040-\u30ff\u3400-\u9fff]", remainder)
    author_part = remainder[: japanese_start.start()].strip() if japanese_start else remainder
    japanese_name = remainder[japanese_start.start() :].strip() if japanese_start else ""
    year_match = re.search(r"(?:\[)?(1[5-9]\d{2}|20\d{2})(?:\])?", author_part)
    year = int(year_match.group(1)) if year_match else None
    author = re.sub(r"(?:,?\s*\[?(?:1[5-9]\d{2}|20\d{2})\]?)", "", author_part).strip()
    return SpeciesEntry(source_key, scientific_name, japanese_name, author, year, "")


def _fetch(url):
    request = Request(url, headers={"User-Agent": "Acervo/0.1 butterfly taxonomy importer"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - command receives an HTTPS archive URL
        return response.read().decode("utf-8")


def _family_urls(index_html, archive_url):
    identifiers = sorted(set(re.findall(r"/taxa/family/([A-Za-z]+)/species", index_html)))
    if len(identifiers) != 5:
        raise CommandError("保存版から蝶類5科の一覧を確認できませんでした。取込みを中止します。")
    base = archive_url.rstrip("/")
    return [(identifier, f"{base}/taxa/family/{identifier}/species") for identifier in identifiers]


class Command(BaseCommand):
    help = "Wayback Machine保存版の日本産蝶類328種を、出典情報付きで冪等に取り込む"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="保存せず解析件数だけ確認する")
        parser.add_argument("--source-url", default=ARCHIVE_URL, help="Wayback Machine保存版のURL")

    def handle(self, *args, **options):
        source_url = options["source_url"]
        if not source_url.startswith("https://web.archive.org/web/20210505224155/"):
            raise CommandError("許可された2021-05-05のWayback Machine保存版だけを指定できます。")

        index_html = _fetch(source_url)
        families = _family_urls(index_html, source_url)
        parsed = []
        for family_name, family_url in families:
            parser = _SpeciesListParser()
            parser.feed(_fetch(family_url))
            if not parser.entries:
                raise CommandError(
                    f"{family_name}の種一覧を解析できませんでした。取込みを中止します。"
                )
            parsed.append((family_name, family_url, parser.entries))
        species_count = sum(len(entries) for _, _, entries in parsed)
        if species_count != 328:
            raise CommandError(
                f"328種ではなく{species_count}件を検出したため、取込みを中止します。"
            )
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("検証成功: 5科、328種を検出しました。"))
            return

        with transaction.atomic():
            dataset, _ = TaxonDataset.objects.get_or_create(
                slug=DATASET_SLUG,
                defaults={
                    "title": "日本産蝶類和名学名便覧",
                    "version": "2010–2013",
                    "license_name": "CC BY 3.0",
                    "source_url": source_url,
                    "retrieved_on": timezone.localdate(),
                    "attribution": ATTRIBUTION,
                },
            )
            for family_name, family_url, entries in parsed:
                family_taxon, _ = Taxon.objects.get_or_create(
                    scientific_name=family_name, defaults={"rank": "family"}
                )
                family_record, _ = TaxonDatasetRecord.objects.update_or_create(
                    dataset=dataset,
                    source_key=f"family-{family_name}",
                    defaults={
                        "rank": TaxonDatasetRecord.Rank.FAMILY,
                        "scientific_name": family_name,
                        "source_url": family_url,
                        "taxon": family_taxon,
                    },
                )
                genera = {}
                for entry in entries:
                    genus_name = entry.scientific_name.split(" ", 1)[0]
                    if genus_name not in genera:
                        genus_taxon, _ = Taxon.objects.get_or_create(
                            scientific_name=genus_name,
                            parent=family_taxon,
                            defaults={"rank": "genus"},
                        )
                        genera[genus_name], _ = TaxonDatasetRecord.objects.update_or_create(
                            dataset=dataset,
                            source_key=f"genus-{family_name}-{genus_name}",
                            defaults={
                                "parent": family_record,
                                "rank": TaxonDatasetRecord.Rank.GENUS,
                                "scientific_name": genus_name,
                                "source_url": family_url,
                                "taxon": genus_taxon,
                            },
                        )
                    species_taxon, _ = Taxon.objects.get_or_create(
                        scientific_name=entry.scientific_name,
                        parent=genera[genus_name].taxon,
                        defaults={"japanese_name": entry.japanese_name, "rank": "species"},
                    )
                    TaxonDatasetRecord.objects.update_or_create(
                        dataset=dataset,
                        source_key=entry.source_key,
                        defaults={
                            "parent": genera[genus_name],
                            "rank": TaxonDatasetRecord.Rank.SPECIES,
                            "scientific_name": entry.scientific_name,
                            "japanese_name": entry.japanese_name,
                            "scientific_author": entry.scientific_author,
                            "original_publication_year": entry.original_publication_year,
                            "source_url": family_url,
                            "taxon": species_taxon,
                        },
                    )
            TaxonDatasetRevision.objects.create(
                dataset=dataset, note="Wayback Machine 2021-05-05保存版から初期取込みを実行"
            )
        self.stdout.write(self.style.SUCCESS("取込み成功: 5科、328種を保存しました。"))
