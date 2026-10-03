"""QR公開URLの安全な入口。"""

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .access import can_use_qr
from .forms import SpecimenRegistrationForm
from .models import QRLabel, SpecimenPhoto, StorageLocation
from .services import (
    SpecimenServiceError,
    TemporaryPhoto,
    discard_temporary_photos,
    register_specimen_from_qr,
    save_temporary_photos,
)


def _session_key(token) -> str:
    return f"specimen-registration-{token}"


def _session_photos(data) -> tuple[TemporaryPhoto, ...]:
    return tuple(TemporaryPhoto(**photo) for photo in data.get("photos", []))


@never_cache
@login_required
def qr_resolve(request, token):
    """認可済み利用者だけに、QRの次の操作を案内する。

    標本の内容や標本番号はPhase 5までここから返さない。
    """

    if not can_use_qr(request.user):
        raise Http404
    label = QRLabel.objects.filter(token=token).only("status").first()
    if label is None:
        raise Http404
    if label.status == QRLabel.Status.RETIRED:
        return render(request, "specimens/qr_unavailable.html", status=410)
    if label.status == QRLabel.Status.UNUSED:
        return redirect("specimens:register", token=token)
    return render(request, "specimens/qr_assigned.html")


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
        form = SpecimenRegistrationForm()
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
    if not can_use_qr(request.user):
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


def _session_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "pk"):
        return value.pk
    return value


def _registration_summary(fields):
    labels = {
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
