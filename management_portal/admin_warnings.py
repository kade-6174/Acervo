"""学校回生方式における管理者引き継ぎの表示用判定。"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.conf import settings

from accounts.enrollment import EnrollmentStatus, cohort_standing_on
from accounts.models import User


@dataclass(frozen=True, slots=True)
class AdministratorWarnings:
    """秘密値を含まない、管理画面に出す注意事項。"""

    no_current_enrolled_admin: bool = False
    successor_required: bool = False


def _next_school_year_start(on_date: date) -> date:
    start_this_year = date(
        on_date.year,
        settings.ACERVO_SCHOOL_YEAR_START_MONTH,
        settings.ACERVO_SCHOOL_YEAR_START_DAY,
    )
    if on_date < start_this_year:
        return start_this_year
    return date(
        on_date.year + 1,
        settings.ACERVO_SCHOOL_YEAR_START_MONTH,
        settings.ACERVO_SCHOOL_YEAR_START_DAY,
    )


def get_administrator_warnings(*, on_date: date) -> AdministratorWarnings:
    """現役admin不足と年度切替前の後継未設定を判定する。"""

    if settings.ACERVO_ENROLLMENT_POLICY != "school_cohort":
        return AdministratorWarnings()

    active_admin_cohorts = User.objects.filter(role=User.Role.ADMIN, is_active=True).values_list(
        "cohort_number", flat=True
    )
    current_enrolled = any(
        cohort_standing_on(cohort_number, on_date).status is EnrollmentStatus.ENROLLED
        for cohort_number in active_admin_cohorts
    )
    next_boundary = _next_school_year_start(on_date)
    in_handover_window = next_boundary - timedelta(days=60) <= on_date < next_boundary
    successor_enrolled = any(
        cohort_standing_on(cohort_number, next_boundary).status is EnrollmentStatus.ENROLLED
        for cohort_number in active_admin_cohorts
    )
    return AdministratorWarnings(
        no_current_enrolled_admin=not current_enrolled,
        successor_required=in_handover_window and not successor_enrolled,
    )
