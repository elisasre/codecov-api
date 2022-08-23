import operator
from functools import reduce
from typing import Iterable

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F, Func, Q, QuerySet
from shared.license import get_current_license

from codecov_auth.models import Owner
from services import ServiceException
from utils.config import get_config


class LicenseException(ServiceException):
    pass


def admin_owners() -> QuerySet:
    """
    Returns a queryset of admin owners based on the YAML config:

        setup:
          admins:
            - service: <provider>
              username: <username>
            - ...
    """
    admins = get_config("setup", "admins", default=[])

    filters = [
        Q(service=admin["service"], username=admin["username"])
        for admin in admins
        if "service" in admin and "username" in admin
    ]

    return Owner.objects.filter(reduce(operator.or_, filters))


def activated_owners() -> QuerySet:
    """
    Returns all owners that are activated in ANY org's `plan_activated_users`
    across the entire instance.
    """
    owner_ids = (
        Owner.objects.annotate(
            plan_activated_owner_ids=Func(
                F("plan_activated_users"),
                function="unnest",
            )
        )
        .values_list("plan_activated_owner_ids", flat=True)
        .distinct()
    )

    return Owner.objects.filter(pk__in=owner_ids)


def license_seats() -> int:
    """
    Max number of seats allowed by the current license.
    """
    license = get_current_license()
    return license.number_allowed_users or 0


@transaction.atomic
def activate_owner(owner: Owner):
    """
    Activate the given owner in ALL orgs that the owner is a part of.
    """
    if not settings.IS_ENTERPRISE:
        raise Exception("activate_owner is only available in self-hosted environments")

    if activated_owners().count() >= license_seats():
        raise LicenseException(
            "No seats remaining. Please contact Codecov support or deactivate users."
        )

    Owner.objects.filter(pk__in=owner.organizations).update(
        plan_activated_users=Func(
            owner.pk,
            function="array_append_unique",
            template="%(function)s(plan_activated_users, %(expressions)s)",
        )
    )


def deactivate_owner(owner: Owner):
    """
    Deactivate the given owner across ALL orgs.
    """
    if not settings.IS_ENTERPRISE:
        raise Exception(
            "deactivate_owner is only available in self-hosted environments"
        )

    Owner.objects.filter(
        plan_activated_users__contains=Func(
            owner.pk,
            function="array",
            template="%(function)s[%(expressions)s]",
        )
    ).update(
        plan_activated_users=Func(
            owner.pk,
            function="array_remove",
            template="%(function)s(plan_activated_users, %(expressions)s)",
        )
    )