import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ResortSettingsCreateRequest(BaseModel):
    resort_name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    timezone: str = "UTC"
    currency: str = "USD"
    default_language: str = "en"
    check_in_time: str | None = None
    check_out_time: str | None = None
    logo_url: str | None = None
    primary_brand_color: str | None = None
    secondary_brand_color: str | None = None
    website_url: str | None = None
    settings_metadata: dict = Field(default_factory=dict)


class ResortSettingsUpdateRequest(BaseModel):
    resort_name: str | None = None
    legal_name: str | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    timezone: str | None = None
    currency: str | None = None
    default_language: str | None = None
    check_in_time: str | None = None
    check_out_time: str | None = None
    logo_url: str | None = None
    primary_brand_color: str | None = None
    secondary_brand_color: str | None = None
    website_url: str | None = None
    settings_metadata: dict | None = None


class ResortSettingsOut(BaseModel):
    id: uuid.UUID
    resort_name: str
    legal_name: str | None
    description: str | None
    address: str | None
    city: str | None
    state: str | None
    country: str | None
    postal_code: str | None
    phone: str | None
    email: str | None
    whatsapp: str | None
    timezone: str
    currency: str
    default_language: str
    check_in_time: str | None
    check_out_time: str | None
    logo_url: str | None
    primary_brand_color: str | None
    secondary_brand_color: str | None
    website_url: str | None
    settings_metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
