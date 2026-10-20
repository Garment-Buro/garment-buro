from app.modules.identity.models import User, UserStatus
from app.modules.partners.models import (
    PartnerLanding,
    PartnerLandingStatus,
    PartnerProfile,
    PartnerStatus,
)


def public_landing_conditions():
    """Apply after joining the landing, its partner profile and its owning user."""
    return (
        PartnerLanding.status == PartnerLandingStatus.PUBLISHED.value,
        PartnerProfile.status == PartnerStatus.ACTIVE.value,
        User.status == UserStatus.ACTIVE.value,
    )
