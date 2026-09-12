from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from django.core.exceptions import ValidationError

BASE_SCHOOL_YEAR = 2026
BASE_THIRD_YEAR_COHORT = 31


class EnrollmentStatus(StrEnum):
    ENROLLED = "enrolled"
    GRADUATED = "graduated"
    NOT_YET_ENROLLED = "not_yet_enrolled"


@dataclass(frozen=True)
class CohortStanding:
    status: EnrollmentStatus
    grade: int | None


def school_year_on(on_date: date) -> int:
    """4月1日を境界として、指定日の学校年度を返す。"""
    return on_date.year if on_date.month >= 4 else on_date.year - 1


def third_year_cohort_for_school_year(school_year: int) -> int:
    """指定学校年度の3年生回生を返す。"""
    return BASE_THIRD_YEAR_COHORT + (school_year - BASE_SCHOOL_YEAR)


def cohort_standing_on(cohort_number: int, on_date: date) -> CohortStanding:
    """指定日における回生の在籍状態と学年を算出する。"""
    third_year_cohort = third_year_cohort_for_school_year(school_year_on(on_date))
    cohort_offset = cohort_number - third_year_cohort

    if cohort_offset < 0:
        return CohortStanding(EnrollmentStatus.GRADUATED, None)
    if cohort_offset <= 2:
        return CohortStanding(EnrollmentStatus.ENROLLED, 3 - cohort_offset)
    return CohortStanding(EnrollmentStatus.NOT_YET_ENROLLED, None)


def validate_cohort_for_date(cohort_number: int, on_date: date) -> None:
    """指定日時点で未入学相当となる未来回生を拒否する。"""
    if cohort_standing_on(cohort_number, on_date).status is EnrollmentStatus.NOT_YET_ENROLLED:
        raise ValidationError("未入学相当の回生は登録できません。")
