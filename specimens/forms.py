import unicodedata
from itertools import groupby

from django import forms
from django.forms.models import ModelChoiceIterator

from .models import (
    Specimen,
    SpecimenEvent,
    StorageLocation,
    Taxon,
    TaxonDataset,
    TaxonDatasetRecord,
)

JAPANESE_BUTTERFLY_DATASET_SLUG = "japanese-butterflies-ja-328"
LEGACY_BUTTERFLY_DATASET_SLUG = "japanese-butterflies-binran-2010-2013"
SMALL_KANA = str.maketrans("ァィゥェォャュョッヮヵヶ", "アイウエオヤユヨツワカケ")
RANK_ORDER = {rank: index for index, (rank, _) in enumerate(TaxonDatasetRecord.Rank.choices)}
RANK_LABELS = dict(TaxonDatasetRecord.Rank.choices)


def _japanese_sort_key(name):
    normalized = unicodedata.normalize("NFKC", name)
    katakana = "".join(
        chr(ord(character) + 0x60) if "ぁ" <= character <= "ゖ" else character
        for character in normalized
    )
    return katakana.translate(SMALL_KANA).casefold(), katakana.casefold()


class JapaneseNameChoiceIterator(ModelChoiceIterator):
    """和名優先で五十音順に選択肢を描画する。"""

    def __iter__(self):
        if self.field.empty_label is not None:
            yield "", self.field.empty_label
        records = sorted(
            self.queryset,
            key=lambda record: (
                not bool(record.japanese_name),
                _japanese_sort_key(record.japanese_name or record.scientific_name),
                record.pk,
            ),
        )
        for record in records:
            yield self.choice(record)


class GroupedTaxonChoiceIterator(ModelChoiceIterator):
    """和名分類以外のローカル分類を階級ごとに表示する。"""

    def __iter__(self):
        if self.field.empty_label is not None:
            yield "", self.field.empty_label
        taxa = sorted(
            self.queryset,
            key=lambda taxon: (
                RANK_ORDER.get(taxon.rank, len(RANK_ORDER)),
                taxon.rank,
                not bool(taxon.japanese_name),
                _japanese_sort_key(taxon.japanese_name or taxon.scientific_name),
                taxon.pk,
            ),
        )
        for rank, group in groupby(taxa, key=lambda taxon: taxon.rank):
            label = RANK_LABELS.get(rank, "その他" if rank else "階級未設定")
            yield label, [self.choice(taxon) for taxon in group]


class TaxonChoiceField(forms.ModelChoiceField):
    """和名を優先して表示する分類選択欄。"""

    def label_from_instance(self, obj):
        if obj.japanese_name and obj.scientific_name:
            return f"{obj.japanese_name}（{obj.scientific_name}）"
        return obj.japanese_name or obj.scientific_name or f"分類 {obj.pk}"


class GroupedTaxonChoiceField(TaxonChoiceField):
    iterator = GroupedTaxonChoiceIterator


class TaxonDatasetRecordChoiceField(forms.ModelChoiceField):
    """指定JSONの和名分類を表示する選択欄。"""

    iterator = JapaneseNameChoiceIterator

    def label_from_instance(self, obj):
        if obj.japanese_name and obj.scientific_name:
            return f"{obj.japanese_name}（{obj.scientific_name}）"
        return obj.japanese_name or obj.scientific_name


class TaxonHierarchySelect(forms.Select):
    """祖先レコードのIDをoptionへ渡し、空欄の中間階級を許容する。"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            ancestor_ids = []
            parent = instance.parent
            while parent is not None:
                ancestor_ids.append(str(parent.pk))
                parent = parent.parent
            option["attrs"]["data-ancestor-ids"] = ",".join(ancestor_ids)
        return option


class TaxonParentSelect(forms.Select):
    """分類階級をoptionへ渡し、上位分類候補を画面で絞り込む。"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-taxon-rank"] = instance.rank
        return option


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if not data:
            return []
        return [single_file_clean(item, initial) for item in data]


class SpecimenRegistrationForm(forms.Form):
    butterfly_family = TaxonDatasetRecordChoiceField(
        label="科",
        queryset=TaxonDatasetRecord.objects.none(),
        required=False,
        widget=TaxonHierarchySelect(attrs={"class": "form-select", "data-taxon-rank": "family"}),
    )
    butterfly_subfamily = TaxonDatasetRecordChoiceField(
        label="亜科",
        queryset=TaxonDatasetRecord.objects.none(),
        required=False,
        widget=TaxonHierarchySelect(attrs={"class": "form-select", "data-taxon-rank": "subfamily"}),
    )
    butterfly_tribe = TaxonDatasetRecordChoiceField(
        label="族",
        queryset=TaxonDatasetRecord.objects.none(),
        required=False,
        widget=TaxonHierarchySelect(attrs={"class": "form-select", "data-taxon-rank": "tribe"}),
    )
    butterfly_genus = TaxonDatasetRecordChoiceField(
        label="属",
        queryset=TaxonDatasetRecord.objects.none(),
        required=False,
        widget=TaxonHierarchySelect(attrs={"class": "form-select", "data-taxon-rank": "genus"}),
    )
    butterfly_species = TaxonDatasetRecordChoiceField(
        label="種",
        queryset=TaxonDatasetRecord.objects.none(),
        required=False,
        widget=TaxonHierarchySelect(attrs={"class": "form-select", "data-taxon-rank": "species"}),
    )
    taxon = GroupedTaxonChoiceField(
        label="登録済みの分類", queryset=Taxon.objects.none(), required=False, empty_label="未選択"
    )
    identification_text = forms.CharField(label="同定情報", max_length=500, required=False)
    acquisition_method = forms.ChoiceField(label="入手方法", choices=Specimen.AcquisitionMethod)
    collected_on = forms.DateField(
        label="採集日", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    collected_place = forms.CharField(label="採集地", max_length=500, required=False)
    collector = forms.CharField(label="採集者", max_length=255, required=False)
    storage_location = forms.ModelChoiceField(
        label="保管場所", queryset=StorageLocation.objects.all(), required=False
    )
    note = forms.CharField(label="備考", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    photos = MultipleFileField(
        label="写真",
        required=False,
        widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["taxon"].queryset = Taxon.objects.exclude(
            taxondatasetrecord__dataset__slug__in=(
                JAPANESE_BUTTERFLY_DATASET_SLUG,
                LEGACY_BUTTERFLY_DATASET_SLUG,
            )
        ).distinct()
        dataset = TaxonDataset.objects.filter(slug=JAPANESE_BUTTERFLY_DATASET_SLUG).first()
        self.butterfly_dataset_available = dataset is not None
        for field_name, rank in (
            ("butterfly_family", TaxonDatasetRecord.Rank.FAMILY),
            ("butterfly_subfamily", TaxonDatasetRecord.Rank.SUBFAMILY),
            ("butterfly_tribe", TaxonDatasetRecord.Rank.TRIBE),
            ("butterfly_genus", TaxonDatasetRecord.Rank.GENUS),
            ("butterfly_species", TaxonDatasetRecord.Rank.SPECIES),
        ):
            field = self.fields[field_name]
            field.queryset = (
                TaxonDatasetRecord.objects.filter(dataset=dataset, rank=rank).select_related(
                    "taxon", "parent__parent__parent__parent__parent__parent__parent__parent"
                )
                if dataset
                else TaxonDatasetRecord.objects.none()
            )

    def clean(self):
        cleaned_data = super().clean()
        family = cleaned_data.get("butterfly_family")
        subfamily = cleaned_data.get("butterfly_subfamily")
        tribe = cleaned_data.get("butterfly_tribe")
        genus = cleaned_data.get("butterfly_genus")
        species = cleaned_data.get("butterfly_species")
        selected_record = species or genus or tribe or subfamily or family

        if selected_record:
            selected_field_name = next(
                field_name
                for field_name, record in (
                    ("butterfly_species", species),
                    ("butterfly_genus", genus),
                    ("butterfly_tribe", tribe),
                    ("butterfly_subfamily", subfamily),
                    ("butterfly_family", family),
                )
                if record
            )
            ancestor_ids = set()
            parent = selected_record.parent
            while parent is not None:
                ancestor_ids.add(parent.pk)
                parent = parent.parent
            if any(
                record and record.pk != selected_record.pk and record.pk not in ancestor_ids
                for record in (family, subfamily, tribe, genus)
            ):
                self.add_error(selected_field_name, "選択した上位分類の系統と一致しません。")
            if cleaned_data.get("taxon"):
                self.add_error("taxon", "和名分類と他の分類は同時に選択できません。")
            if not selected_record.taxon_id:
                raise forms.ValidationError("選択した分類を標本へ関連付けられません。")
            cleaned_data["taxon"] = selected_record.taxon

        for field_name in (
            "butterfly_family",
            "butterfly_subfamily",
            "butterfly_tribe",
            "butterfly_genus",
            "butterfly_species",
        ):
            cleaned_data.pop(field_name, None)
        return cleaned_data


class SpecimenEditForm(forms.ModelForm):
    class Meta:
        model = Specimen
        fields = [
            "taxon",
            "identification_text",
            "acquisition_method",
            "collected_on",
            "collected_place",
            "collector",
            "storage_location",
            "note",
        ]
        widgets = {
            "collected_on": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class SpecimenEventForm(forms.Form):
    event_type = forms.ChoiceField(
        label="履歴種別",
        choices=[
            choice
            for choice in SpecimenEvent.Type.choices
            if choice[0]
            not in {
                SpecimenEvent.Type.COLLECTION,
                SpecimenEvent.Type.PURCHASE,
                SpecimenEvent.Type.DONATION,
            }
        ],
    )
    occurred_on = forms.DateField(
        label="日付", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    note = forms.CharField(label="備考", required=False, widget=forms.Textarea(attrs={"rows": 3}))


class SpecimenPhotoForm(forms.Form):
    photos = MultipleFileField(
        label="追加する写真",
        widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )


class TaxonSearchForm(forms.Form):
    query = forms.CharField(label="分類名", max_length=255, required=False)


class TaxonManualForm(forms.ModelForm):
    rank = forms.ChoiceField(
        label="分類階級",
        choices=(
            ("", "選択してください"),
            (TaxonDatasetRecord.Rank.FAMILY, "科"),
            (TaxonDatasetRecord.Rank.GENUS, "属"),
            (TaxonDatasetRecord.Rank.SPECIES, "種"),
            ("other", "その他"),
        ),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "data-manual-taxon-rank": ""}),
    )
    parent = TaxonChoiceField(
        label="上位分類",
        queryset=Taxon.objects.all(),
        required=False,
        widget=TaxonParentSelect(attrs={"class": "form-select", "data-manual-taxon-parent": ""}),
    )

    class Meta:
        model = Taxon
        fields = ["scientific_name", "japanese_name", "rank", "parent"]

    def clean(self):
        cleaned_data = super().clean()
        if not (
            (cleaned_data.get("scientific_name") or "").strip()
            or (cleaned_data.get("japanese_name") or "").strip()
        ):
            raise forms.ValidationError("学名または和名を入力してください。")
        rank = cleaned_data.get("rank")
        parent = cleaned_data.get("parent")
        expected_parent_rank = {
            TaxonDatasetRecord.Rank.GENUS: TaxonDatasetRecord.Rank.FAMILY,
            TaxonDatasetRecord.Rank.SPECIES: TaxonDatasetRecord.Rank.GENUS,
        }.get(rank)
        if expected_parent_rank and parent is None:
            self.add_error("parent", "上位分類を選択してください。")
        if parent and expected_parent_rank and parent.rank != expected_parent_rank:
            self.add_error("parent", "選択した分類階級に合う上位分類を選んでください。")
        if rank == TaxonDatasetRecord.Rank.FAMILY and parent:
            self.add_error("parent", "科を登録するときは上位分類を選択しません。")
        return cleaned_data
