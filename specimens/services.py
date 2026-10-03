"""画面に依存しない標本採番と状態遷移。"""

from dataclasses import dataclass
from enum import StrEnum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Specimen, SpecimenEvent, SpecimenSequence


class SpecimenServiceErrorCode(StrEnum):
    SPECIMEN_NOT_FOUND = "specimen_not_found"
    INVALID_EVENT_TYPE = "invalid_event_type"
    INVALID_STATE_TRANSITION = "invalid_state_transition"


class SpecimenServiceError(Exception):
    def __init__(self, code: SpecimenServiceErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class StateChangeResult:
    specimen_id: int
    event_id: int
    previous_status: str
    current_status: str


def _specimen_code(number: int) -> str:
    return f"{settings.ACERVO_SPECIMEN_CODE_PREFIX}-{number:06d}"


def _next_sequence_number() -> int:
    sequence = SpecimenSequence.objects.select_for_update().filter(pk=1).first()
    if sequence is None:
        sequence, _ = SpecimenSequence.objects.get_or_create(pk=1, defaults={"next_number": 1})
    number = sequence.next_number
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    return number


@transaction.atomic
def create_specimen(*, created_by, **fields) -> Specimen:
    """確定時だけ採番し、標本と初回履歴を同一トランザクションで保存する。"""

    number = _next_sequence_number()
    specimen = Specimen(specimen_code=_specimen_code(number), created_by=created_by, **fields)
    specimen.full_clean()
    specimen.save()
    SpecimenEvent.objects.create(
        specimen=specimen,
        event_type={
            Specimen.AcquisitionMethod.COLLECTED: SpecimenEvent.Type.COLLECTION,
            Specimen.AcquisitionMethod.PURCHASED: SpecimenEvent.Type.PURCHASE,
            Specimen.AcquisitionMethod.DONATED: SpecimenEvent.Type.DONATION,
            Specimen.AcquisitionMethod.OTHER: SpecimenEvent.Type.OTHER,
        }[specimen.acquisition_method],
        occurred_on=specimen.collected_on or timezone.localdate(),
        created_by=created_by,
    )
    return specimen


_STATE_FOR_EVENT = {
    SpecimenEvent.Type.LOAN: Specimen.Status.ON_LOAN,
    SpecimenEvent.Type.RETURN: Specimen.Status.IN_COLLECTION,
    SpecimenEvent.Type.SALE: Specimen.Status.SOLD,
    SpecimenEvent.Type.DISPOSAL: Specimen.Status.DISPOSED,
    SpecimenEvent.Type.LOSS: Specimen.Status.LOST,
    SpecimenEvent.Type.FOUND: Specimen.Status.IN_COLLECTION,
}

_ALLOWED_TRANSITIONS = {
    Specimen.Status.IN_COLLECTION: {
        Specimen.Status.ON_LOAN,
        Specimen.Status.SOLD,
        Specimen.Status.DISPOSED,
        Specimen.Status.LOST,
    },
    Specimen.Status.ON_LOAN: {Specimen.Status.IN_COLLECTION},
    Specimen.Status.LOST: {Specimen.Status.IN_COLLECTION},
    Specimen.Status.SOLD: set(),
    Specimen.Status.DISPOSED: set(),
}


@transaction.atomic
def record_specimen_event(
    *, specimen_id: int, event_type: str, created_by, note: str = ""
) -> StateChangeResult:
    """状態と連動する履歴を原子的に追加する。"""

    if event_type not in SpecimenEvent.Type.values:
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_EVENT_TYPE)
    specimen = Specimen.objects.select_for_update().filter(pk=specimen_id).first()
    if specimen is None:
        raise SpecimenServiceError(SpecimenServiceErrorCode.SPECIMEN_NOT_FOUND)
    next_status = _STATE_FOR_EVENT.get(event_type, specimen.status)
    if next_status != specimen.status and next_status not in _ALLOWED_TRANSITIONS[specimen.status]:
        raise SpecimenServiceError(SpecimenServiceErrorCode.INVALID_STATE_TRANSITION)
    event = SpecimenEvent.objects.create(
        specimen=specimen,
        event_type=event_type,
        note=note,
        created_by=created_by,
    )
    previous_status = specimen.status
    if next_status != previous_status:
        specimen.status = next_status
        specimen.save(update_fields=["status"])
    return StateChangeResult(specimen.pk, event.pk, previous_status, specimen.status)
