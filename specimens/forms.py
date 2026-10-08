from django import forms

from .models import (
    Specimen,
    SpecimenEvent,
    StorageLocation,
    Taxon,
    TaxonDataset,
    TaxonDatasetRecord,
)

JAPANESE_BUTTERFLY_DATASET_SLUG = "japanese-butterflies-ja-328"


class TaxonChoiceField(forms.ModelChoiceField):
    """和名を優先して表示する分類選択欄。"""

    def label_from_instance(self, obj):
        if obj.japanese_name and obj.scientific_name:
            return f"{obj.japanese_name}（{obj.scientific_name}）"
        return obj.japanese_name or obj.scientific_name or f"分類 {obj.pk}"


class TaxonDatasetRecordChoiceField(forms.ModelChoiceField):
    """指定JSONの和名分類を表示する選択欄。"""

    def label_from_instance(self, obj):
        if obj.japanese_name and obj.scientific_name:
            return f"{obj.japanese_name}（{obj.scientific_name}）"
        return obj.japanese_name or obj.scientific_name


class TaxonHierarchySelect(forms.Select):
    """親レコードのIDをoptionへ渡し、ブラウザ側で下位候補を絞り込む。"""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-parent-id"] = str(instance.parent_id or "")
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
        label="科", queryset=TaxonDatasetRecord.objects.none(), required=False
    )
    butterfly_subfamily = TaxonDatasetRecordChoiceField(
        label="亜科", queryset=TaxonDatasetRecord.objects.none(), required=False
    )
    butterfly_tribe = TaxonDatasetRecordChoiceField(
        label="族", queryset=TaxonDatasetRecord.objects.none(), required=False
    )
    butterfly_genus = TaxonDatasetRecordChoiceField(
        label="属", queryset=TaxonDatasetRecord.objects.none(), required=False
    )
    butterfly_species = TaxonDatasetRecordChoiceField(
        label="種", queryset=TaxonDatasetRecord.objects.none(), required=False
    )
    taxon = TaxonChoiceField(
        label="分類", queryset=Taxon.objects.all(), required=False, empty_label="未選択"
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
                    "taxon", "parent"
                )
                if dataset
                else TaxonDatasetRecord.objects.none()
            )
            field.widget = TaxonHierarchySelect(
                attrs={"class": "form-select", "data-taxon-rank": rank}
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
            if subfamily and not family:
                self.add_error("butterfly_family", "科を選択してください。")
            if subfamily and family and subfamily.parent_id != family.pk:
                self.add_error("butterfly_subfamily", "選択した科に属する亜科を選んでください。")
            if tribe and not subfamily:
                self.add_error("butterfly_subfamily", "亜科を選択してください。")
            if tribe and subfamily and tribe.parent_id != subfamily.pk:
                self.add_error("butterfly_tribe", "選択した亜科に属する族を選んでください。")
            if genus and not subfamily:
                self.add_error("butterfly_subfamily", "亜科を選択してください。")
            if species and not genus:
                self.add_error("butterfly_genus", "属を選択してください。")
            if genus and subfamily and genus.parent_id != (tribe.pk if tribe else subfamily.pk):
                self.add_error("butterfly_genus", "選択した亜科・族に属する属を選んでください。")
            if species and genus and species.parent_id != genus.pk:
                self.add_error("butterfly_species", "選択した属に属する種を選んでください。")
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
