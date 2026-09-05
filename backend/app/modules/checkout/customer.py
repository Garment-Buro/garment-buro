"""Prepare a cabinet without treating checkout contact entry as authentication."""

from app.db.session import DatabaseManager
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.security import normalize_email


async def prepare_checkout_customer(database: DatabaseManager, email: str) -> None:
    email, normalized = normalize_email(email)
    async with database.session() as session:
        # Never overwrite an existing customer's profile from an anonymous checkout,
        # mark the email verified, issue a session, or grant access by phone alone.
        await IdentityRepository().get_or_create_customer(
            session,
            email=email,
            email_normalized=normalized,
        )
        await session.commit()
