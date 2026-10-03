"""標本・QR操作の最小認可判定。"""

from django.utils import timezone

from accounts.enrollment import EnrollmentStatus
from accounts.models import User


def can_use_qr(user) -> bool:
    """QR読取・登録へ進める利用者だけを許可する。"""

    if not user.is_authenticated or not user.is_active:
        return False
    if user.role == User.Role.ADMIN:
        return True
    return user.cohort_standing_on(timezone.localdate()).status in {
        EnrollmentStatus.ENROLLED,
        EnrollmentStatus.NOT_APPLICABLE,
    }
