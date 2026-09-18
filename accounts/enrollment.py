from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from django.conf import settings
from django.core.exceptions import ValidationError


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    GRADUATED = "graduated"
    NOT_YET_ENROLLED = "not_yet_enrolled"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class CohortStanding:
    status: EnrollmentStatus
    grade: int | None


def school_year_on(on_date: date) -> int:
    """導入先設定の年度開始日を境界として、指定日の学校年度を返す。"""
    start = (settings.ACERVO_SCHOOL_YEAR_START_MONTH, settings.ACERVO_SCHOOL_YEAR_START_DAY)
    return on_date.year if (on_date.month, on_date.day) >= start else on_date.year - 1


def first_year_cohort_for_school_year(school_year: int) -> int:
    """指定学校年度の1年生回生を返す。"""
    return settings.ACERVO_BASE_FIRST_YEAR_COHORT + (school_year - settings.ACERVO_BASE_SCHOOL_YEAR)


def cohort_standing_on(cohort_number: int | None, on_date: date) -> CohortStanding:
    """指定日における回生の在籍状態と学年を算出する。"""
    if settings.ACERVO_ENROLLMENT_POLICY == "none":
        return CohortStanding(EnrollmentStatus.NOT_APPLICABLE, None)
    if cohort_number is None:
        raise ValidationError("school_cohort方式では回生が必要です。")
    first_year_cohort = first_year_cohort_for_school_year(school_year_on(on_date))
    cohort_offset = first_year_cohort - cohort_number

    if cohort_offset < 0:
        return CohortStanding(EnrollmentStatus.NOT_YET_ENROLLED, None)
    if cohort_offset <= 2:
        return CohortStanding(EnrollmentStatus.ENROLLED, cohort_offset + 1)
    return CohortStanding(EnrollmentStatus.GRADUATED, None)


def validate_cohort_for_date(cohort_number: int | None, on_date: date) -> None:
    """指定日時点で未入学相当となる未来回生を拒否する。"""
    if settings.ACERVO_ENROLLMENT_POLICY == "none":
        return
    if cohort_number is None:
        raise ValidationError("school_cohort方式では回生が必要です。")
    if cohort_standing_on(cohort_number, on_date).status is EnrollmentStatus.NOT_YET_ENROLLED:
        raise ValidationError("未入学相当の回生は登録できません。")
