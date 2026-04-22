from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class PromotionResponse(BaseModel):
    id: str
    bank: str
    source_id: str
    source_url: str
    title: str
    description: str
    image_url: str | None
    card_types: list | dict | None
    category: str | None
    merchant_name: str | None
    discount_type: str | None
    discount_value: str | None
    minimum_spend: float | None
    start_date: date | None
    end_date: date | None
    terms_and_conditions: str | None
    checksum: str
    is_active: bool
    scraped_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromotionListResponse(BaseModel):
    items: list[PromotionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ScrapeRunResponse(BaseModel):
    id: str
    bank: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    promotions_found: int
    promotions_new: int
    promotions_updated: int
    error_message: str | None

    model_config = {"from_attributes": True}


class ScrapeRunListResponse(BaseModel):
    items: list[ScrapeRunResponse]
    total: int
    page: int
    page_size: int
    pages: int


class StatsResponse(BaseModel):
    bank: str
    total: int
    active: int


class HealthResponse(BaseModel):
    status: str
    version: str
    adapters: list[str]


class FilterOptionsResponse(BaseModel):
    banks: list[str]
    categories: list[str]
    discount_types: list[str]
    card_types: list[str]
    merchant_names: list[str]


class ScrapeTriggerRequest(BaseModel):
    bank: str | None = None


class ScrapeTriggerResponse(BaseModel):
    message: str
    banks: list[str]


class RunningScrapesResponse(BaseModel):
    banks: list[str]


class ScheduleEntry(BaseModel):
    bank: str
    interval_hours: int
    rate_limit_seconds: float


class ScheduleInfoResponse(BaseModel):
    schedules: list[ScheduleEntry]
