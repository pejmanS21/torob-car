"""Import every model so `Base.metadata` is complete for Alembic."""

from models.city import City
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog

__all__ = ["City", "Listing", "VehicleCatalog"]
