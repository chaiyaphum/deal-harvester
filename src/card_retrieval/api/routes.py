from __future__ import annotations

import math
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from card_retrieval.api.auth import require_api_key
from card_retrieval.api.schemas import (
    FilterOptionsResponse,
    HealthResponse,
    PromotionListResponse,
    PromotionResponse,
    ScrapeRunListResponse,
    StatsResponse,
)
from card_retrieval.storage.repository import PromotionRepository

router = APIRouter(prefix="/api/v1")


def _get_repo() -> PromotionRepository:
    return PromotionRepository()


# --- Health (public) ---


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health():
    import card_retrieval.adapters  # noqa: F401
    from card_retrieval.core.registry import list_adapters

    return HealthResponse(
        status="ok",
        version="0.1.0",
        adapters=list(list_adapters().keys()),
    )


# --- Promotions ---


@router.get(
    "/promotions",
    response_model=PromotionListResponse,
    tags=["promotions"],
    dependencies=[Depends(require_api_key)],
)
def list_promotions(
    bank: str | None = Query(None, description="Filter by bank"),
    category: str | None = Query(None, description="Filter by category slug"),
    merchant_name: str | None = Query(None, description="Partial match on merchant name"),
    discount_type: str | None = Query(None, description="Filter by discount type"),
    card_type: str | None = Query(None, description="Filter promotions containing this card type"),
    search: str | None = Query(None, description="Search title and description"),
    is_active: bool = Query(True, description="Filter by active status"),
    start_date_from: date | None = Query(None, description="Promotions starting on or after"),
    start_date_to: date | None = Query(None, description="Promotions starting on or before"),
    end_date_from: date | None = Query(None, description="Promotions ending on or after"),
    end_date_to: date | None = Query(None, description="Promotions ending on or before"),
    min_spend_min: float | None = Query(None, description="Minimum spend >= value"),
    min_spend_max: float | None = Query(None, description="Minimum spend <= value"),
    sort_by: str = Query("scraped_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    repo = _get_repo()
    try:
        filters = {
            "bank": bank,
            "category": category,
            "merchant_name": merchant_name,
            "discount_type": discount_type,
            "card_type": card_type,
            "search": search,
            "is_active": is_active,
            "start_date_from": start_date_from,
            "start_date_to": start_date_to,
            "end_date_from": end_date_from,
            "end_date_to": end_date_to,
            "min_spend_min": min_spend_min,
            "min_spend_max": min_spend_max,
        }
        items, total = repo.query_promotions(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
        pages = math.ceil(total / page_size) if total > 0 else 0
        return PromotionListResponse(
            items=[PromotionResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
    finally:
        repo.close()


@router.get(
    "/promotions/{promotion_id}",
    response_model=PromotionResponse,
    tags=["promotions"],
    dependencies=[Depends(require_api_key)],
)
def get_promotion(promotion_id: str):
    repo = _get_repo()
    try:
        row = repo.get_promotion_by_id(promotion_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Promotion {promotion_id} not found",
            )
        return PromotionResponse.model_validate(row)
    finally:
        repo.close()


# --- Scrape Runs ---


@router.get(
    "/scrape-runs",
    response_model=ScrapeRunListResponse,
    tags=["scrape-runs"],
    dependencies=[Depends(require_api_key)],
)
def list_scrape_runs(
    bank: str | None = Query(None, description="Filter by bank"),
    run_status: str | None = Query(None, alias="status", description="Filter by status"),
    from_date: datetime | None = Query(None, description="Runs started after"),
    to_date: datetime | None = Query(None, description="Runs started before"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    repo = _get_repo()
    try:
        filters = {
            "bank": bank,
            "status": run_status,
            "from_date": from_date,
            "to_date": to_date,
        }
        from card_retrieval.api.schemas import ScrapeRunResponse

        items, total = repo.query_scrape_runs(
            filters=filters,
            page=page,
            page_size=page_size,
        )
        pages = math.ceil(total / page_size) if total > 0 else 0
        return ScrapeRunListResponse(
            items=[ScrapeRunResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
    finally:
        repo.close()


# --- Stats ---


@router.get(
    "/stats",
    response_model=list[StatsResponse],
    tags=["stats"],
    dependencies=[Depends(require_api_key)],
)
def get_stats():
    repo = _get_repo()
    try:
        rows = repo.get_stats()
        return [StatsResponse(**r) for r in rows]
    finally:
        repo.close()


# --- Filters ---


@router.get(
    "/filters",
    response_model=FilterOptionsResponse,
    tags=["filters"],
    dependencies=[Depends(require_api_key)],
)
def get_filters():
    repo = _get_repo()
    try:
        options = repo.get_filter_options()
        return FilterOptionsResponse(**options)
    finally:
        repo.close()
