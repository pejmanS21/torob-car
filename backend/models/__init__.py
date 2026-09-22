"""Import every model so `Base.metadata` is complete for Alembic."""

from models.admin_audit import AdminAudit
from models.anonymous_chat_quota import AnonymousChatQuota
from models.chat import Chat, ChatMessage
from models.city import City
from models.listing import Listing
from models.price_alert import PriceAlert
from models.saved_listing import SavedListing
from models.user import User
from models.vehicle_catalog import VehicleCatalog

__all__ = [
    "AdminAudit",
    "AnonymousChatQuota",
    "Chat",
    "ChatMessage",
    "City",
    "Listing",
    "PriceAlert",
    "SavedListing",
    "User",
    "VehicleCatalog",
]
