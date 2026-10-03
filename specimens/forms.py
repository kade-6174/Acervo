from django import forms

from .models import Specimen, StorageLocation


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if not data:
            return []
        return [single_file_clean(item, initial) for item in data]


class SpecimenRegistrationForm(forms.Form):
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
