"""QR公開URLの安全な入口。"""

import uuid

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from .access import can_edit_specimens, can_use_qr, can_view_specimens
from .forms import (
    SpecimenEditForm,
    SpecimenEventForm,
    SpecimenPhotoForm,
    SpecimenRegistrationForm,
    TaxonManualForm,
    TaxonSearchForm,
)
from .models import QRLabel, Specimen, SpecimenPhoto, StorageLocation, TaxonDataset
from .services import (
    SpecimenServiceError,
    TaxonCandidate,
    TemporaryPhoto,
    add_specimen_photos,
    adopt_external_taxon_candidate,
    discard_temporary_photos,
    record_specimen_event,
    register_specimen_from_qr,
    save_temporary_photos,
    search_taxon_candidates,
)


def _session_key(token) -> str:
    return f"specimen-registration-{token}"


def _session_photos(data) -> tuple[TemporaryPhoto, ...]:
    return tuple(TemporaryPhoto(**photo) for photo in data.get("photos", []))


def _specimen_or_404(detail_uuid):
    specimen = (
        Specimen.objects.select_related("taxon", "storage_location", "created_by")
        .filter(detail_uuid=detail_uuid)
        .first()
    )
    if specimen is None:
        raise Http404
    return specimen


@never_cache
@login_required
def specimen_list(request):
    if not can_view_specimens(request.user):
        raise Http404
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    specimens = Specimen.objects.select_related("taxon", "storage_location")
    if query:
        specimens = specimens.filter(
            Q(specimen_code__icontains=query)
            | Q(identification_text__icontains=query)
            | Q(taxon__scientific_name__icontains=query)
            | Q(taxon__japanese_name__icontains=query)
            | Q(collected_place__icontains=query)
            | Q(collector__icontains=query)
        )
    if status in Specimen.Status.values:
        specimens = specimens.filter(status=status)
    page = Paginator(specimens, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "specimens/list.html",
        {"page": page, "query": query, "status": status, "status_choices": Specimen.Status.choices},
    )


@never_cache
@login_required
def taxon_search(request):
    if not can_edit_specimens(request.user):
        raise Http404
    form = TaxonSearchForm(request.GET or None)
    local_candidates = ()
    external_candidates = ()
    candidate_keys = {}
    if form.is_valid() and form.cleaned_data["query"]:
        local_candidates, external_candidates = search_taxon_candidates(form.cleaned_data["query"])
        if external_candidates:
            stored = {}
            for candidate in external_candidates:
                key = uuid.uuid4().hex
                candidate_keys[key] = candidate
                stored[key] = {
                    "scientific_name": candidate.scientific_name,
                    "japanese_name": candidate.japanese_name,
                    "rank": candidate.rank,
                    "source_url": candidate.source_url,
                    "citation": candidate.citation,
                }
            request.session["external-taxon-candidates"] = stored
    return render(
        request,
        "specimens/taxon_search.html",
        {
            "form": form,
            "local_candidates": local_candidates,
            "external_candidates": [(key, candidate) for key, candidate in candidate_keys.items()],
            "datasets": TaxonDataset.objects.all(),
        },
    )


@never_cache
@login_required
def taxon_adopt_external(request):
    if not can_edit_specimens(request.user) or request.method != "POST":
        raise Http404
    stored = request.session.get("external-taxon-candidates", {})
    payload = stored.get(request.POST.get("candidate_key", ""))
    if not payload:
        raise Http404
    candidate = TaxonCandidate(external=True, **payload)
    taxon = adopt_external_taxon_candidate(candidate)
    request.session.pop("external-taxon-candidates", None)
    return redirect(f"{reverse('specimens:taxon_search')}?created={taxon.pk}")


@never_cache
@login_required
def taxon_manual_create(request):
    if not can_edit_specimens(request.user):
        raise Http404
    form = TaxonManualForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        taxon = form.save()
        return redirect(f"{reverse('specimens:taxon_search')}?created={taxon.pk}")
    return render(request, "specimens/taxon_manual.html", {"form": form})


@never_cache
@login_required
def specimen_detail(request, detail_uuid):
    if not can_view_specimens(request.user):
        raise Http404
    specimen = _specimen_or_404(detail_uuid)
    return render(
        request,
        "specimens/detail.html",
        {
            "specimen": specimen,
            "events": specimen.events.select_related("created_by").all(),
            "photos": specimen.photos.all(),
            "can_edit": can_edit_specimens(request.user),
        },
    )


@never_cache
@login_required
def specimen_edit(request, detail_uuid):
    if not can_edit_specimens(request.user):
        raise Http404
    specimen = _specimen_or_404(detail_uuid)
    form = SpecimenEditForm(request.POST or None, instance=specimen)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("specimens:detail", detail_uuid=specimen.detail_uuid)
    return render(request, "specimens/edit.html", {"form": form, "specimen": specimen})


@never_cache
@login_required
def specimen_event(request, detail_uuid):
    if not can_edit_specimens(request.user):
        raise Http404
    specimen = _specimen_or_404(detail_uuid)
    form = SpecimenEventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            record_specimen_event(
                specimen_id=specimen.pk, created_by=request.user, **form.cleaned_data
            )
        except SpecimenServiceError as error:
            form.add_error("event_type", _event_error_message(error))
        else:
            return redirect("specimens:detail", detail_uuid=specimen.detail_uuid)
    return render(request, "specimens/event.html", {"form": form, "specimen": specimen})


@never_cache
@login_required
def specimen_photo_add(request, detail_uuid):
    if not can_edit_specimens(request.user):
        raise Http404
    specimen = _specimen_or_404(detail_uuid)
    form = SpecimenPhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_specimen_photos(specimen_id=specimen.pk, uploads=form.cleaned_data["photos"])
        except SpecimenServiceError as error:
            form.add_error("photos", _photo_error_message(error))
        else:
            return redirect("specimens:detail", detail_uuid=specimen.detail_uuid)
    return render(request, "specimens/photo_add.html", {"form": form, "specimen": specimen})


@never_cache
@login_required
def qr_resolve(request, token):
    """認可済み利用者だけに、QRの次の操作を案内する。

    標本の内容や標本番号はPhase 5までここから返さない。
    """

    if not can_view_specimens(request.user):
        raise Http404
    label = QRLabel.objects.select_related("specimen").filter(token=token).first()
    if label is None:
        raise Http404
    if label.status == QRLabel.Status.RETIRED:
        return render(request, "specimens/qr_unavailable.html", status=410)
    if label.status == QRLabel.Status.UNUSED:
        if not can_edit_specimens(request.user):
            raise Http404
        return redirect("specimens:register", token=token)
    return redirect("specimens:detail", detail_uuid=label.specimen.detail_uuid)


@never_cache
@login_required
def register(request, token):
    if not can_use_qr(request.user):
        raise Http404
    label = QRLabel.objects.filter(token=token, status=QRLabel.Status.UNUSED).first()
    if label is None:
        raise Http404
    if request.method == "POST":
        form = SpecimenRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            session_key = _session_key(token)
            previous = request.session.get(session_key, {})
            try:
                photos = save_temporary_photos(form.cleaned_data.pop("photos"))
            except SpecimenServiceError as error:
                form.add_error("photos", _photo_error_message(error))
            else:
                discard_temporary_photos(photo["path"] for photo in previous.get("photos", []))
                request.session[session_key] = {
                    "fields": {
                        key: _session_value(value) for key, value in form.cleaned_data.items()
                    },
                    "photos": [
                        {"path": photo.path, "width": photo.width, "height": photo.height}
                        for photo in photos
                    ],
                }
                return redirect("specimens:register_confirm", token=token)
    else:
        form = SpecimenRegistrationForm(initial={"taxon": request.GET.get("taxon")})
    return render(request, "specimens/register.html", {"form": form, "token": token})


@never_cache
@login_required
def register_confirm(request, token):
    if not can_use_qr(request.user):
        raise Http404
    session_key = _session_key(token)
    data = request.session.get(session_key)
    if not data:
        return redirect("specimens:register", token=token)
    if request.method == "POST":
        form = SpecimenRegistrationForm(data["fields"])
        if not form.is_valid():
            raise Http404
        form.cleaned_data.pop("photos")
        try:
            result = register_specimen_from_qr(
                token=token,
                created_by=request.user,
                temporary_photos=_session_photos(data),
                **form.cleaned_data,
            )
        except SpecimenServiceError as error:
            request.session.pop(session_key, None)
            return render(
                request,
                "specimens/register_confirm.html",
                {
                    "summary": _registration_summary(data["fields"]),
                    "token": token,
                    "error": _registration_error_message(error),
                },
                status=409,
            )
        request.session.pop(session_key, None)
        return render(
            request, "specimens/registration_complete.html", {"specimen_code": result.specimen_code}
        )
    return render(
        request,
        "specimens/register_confirm.html",
        {
            "summary": _registration_summary(data["fields"]),
            "token": token,
            "photos": range(len(data.get("photos", []))),
        },
    )


@never_cache
@login_required
def temporary_photo(request, token, index):
    if not can_use_qr(request.user):
        raise Http404
    data = request.session.get(_session_key(token))
    if not data:
        raise Http404
    photos = _session_photos(data)
    if index < 0 or index >= len(photos):
        raise Http404
    from django.core.files.storage import default_storage

    try:
        return FileResponse(
            default_storage.open(photos[index].path, "rb"), content_type="image/jpeg"
        )
    except OSError:
        raise Http404 from None


@never_cache
@login_required
def photo(request, detail_uuid, photo_id):
    if not can_view_specimens(request.user):
        raise Http404
    item = SpecimenPhoto.objects.filter(pk=photo_id, specimen__detail_uuid=detail_uuid).first()
    if item is None:
        raise Http404
    from django.core.files.storage import default_storage

    try:
        return FileResponse(
            default_storage.open(item.file_path, "rb"), content_type=item.content_type
        )
    except OSError:
        raise Http404 from None


def _photo_error_message(error):
    return {
        "invalid_photo": "JPEG、PNG、WebPの画像ファイルを選んでください。",
        "photo_too_large": "写真は1枚10MB以下にしてください。",
        "photo_too_many_pixels": "写真は8,000万画素以下にしてください。",
        "photo_limit_reached": "写真は10枚までです。",
    }.get(error.code, "写真を処理できませんでした。")


def _registration_error_message(error):
    if error.code == "qr_label_not_unused":
        return "このQRコードは、ほかの登録で使用済みになりました。最初からやり直してください。"
    return "登録を確定できませんでした。最初からやり直してください。"


def _event_error_message(error):
    if error.code == "invalid_state_transition":
        return "この標本の現在の状態では、その履歴を追加できません。"
    return "履歴を追加できませんでした。"


def _session_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "pk"):
        return value.pk
    return value


def _registration_summary(fields):
    labels = {
        "taxon": "分類",
        "identification_text": "同定情報",
        "acquisition_method": "入手方法",
        "collected_on": "採集日",
        "collected_place": "採集地",
        "collector": "採集者",
        "storage_location": "保管場所",
        "note": "備考",
    }
    choices = dict(SpecimenRegistrationForm.base_fields["acquisition_method"].choices)
    values = dict(fields)
    if values.get("acquisition_method"):
        values["acquisition_method"] = choices.get(values["acquisition_method"], "—")
    if values.get("storage_location"):
        values["storage_location"] = (
            StorageLocation.objects.filter(pk=values["storage_location"])
            .values_list("name", flat=True)
            .first()
            or "—"
        )
    return [(label, values.get(name) or "—") for name, label in labels.items()]
