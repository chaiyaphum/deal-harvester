from __future__ import annotations

import structlog
from sqlalchemy import select

from card_retrieval.core.models import Promotion, ScrapeRun
from card_retrieval.storage.database import get_session
from card_retrieval.storage.orm_models import Base, PromotionRow, ScrapeRunRow

logger = structlog.get_logger()


class PromotionRepository:
    def __init__(self, session=None):
        self._session = session

    @property
    def session(self):
        if self._session is None:
            self._session = get_session()
        return self._session

    def ensure_tables(self):
        from card_retrieval.storage.database import engine

        Base.metadata.create_all(engine)

    def upsert_promotions(self, promotions: list[Promotion]) -> tuple[int, int]:
        new_count = 0
        updated_count = 0

        for promo in promotions:
            existing = self.session.execute(
                select(PromotionRow).where(
                    PromotionRow.bank == promo.bank,
                    PromotionRow.source_id == promo.source_id,
                )
            ).scalar_one_or_none()

            if existing is None:
                row = PromotionRow(
                    id=promo.id,
                    bank=promo.bank,
                    source_id=promo.source_id,
                    source_url=promo.source_url,
                    title=promo.title,
                    description=promo.description,
                    image_url=promo.image_url,
                    card_types=promo.card_types,
                    category=promo.category,
                    merchant_name=promo.merchant_name,
                    discount_type=promo.discount_type,
                    discount_value=promo.discount_value,
                    minimum_spend=promo.minimum_spend,
                    start_date=promo.start_date,
                    end_date=promo.end_date,
                    terms_and_conditions=promo.terms_and_conditions,
                    raw_data=promo.raw_data,
                    checksum=promo.checksum,
                    scraped_at=promo.scraped_at,
                )
                self.session.add(row)
                new_count += 1
            elif existing.checksum != promo.checksum:
                existing.title = promo.title
                existing.description = promo.description
                existing.image_url = promo.image_url
                existing.card_types = promo.card_types
                existing.category = promo.category
                existing.merchant_name = promo.merchant_name
                existing.discount_type = promo.discount_type
                existing.discount_value = promo.discount_value
                existing.minimum_spend = promo.minimum_spend
                existing.start_date = promo.start_date
                existing.end_date = promo.end_date
                existing.terms_and_conditions = promo.terms_and_conditions
                existing.raw_data = promo.raw_data
                existing.checksum = promo.checksum
                existing.scraped_at = promo.scraped_at
                existing.source_url = promo.source_url
                updated_count += 1

        self.session.commit()
        return new_count, updated_count

    def save_scrape_run(self, run: ScrapeRun):
        row = ScrapeRunRow(
            id=run.id,
            bank=run.bank,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            promotions_found=run.promotions_found,
            promotions_new=run.promotions_new,
            promotions_updated=run.promotions_updated,
            error_message=run.error_message,
        )
        self.session.add(row)
        self.session.commit()

    def get_promotions(self, bank: str | None = None, active_only: bool = True) -> list[PromotionRow]:
        stmt = select(PromotionRow)
        if bank:
            stmt = stmt.where(PromotionRow.bank == bank)
        if active_only:
            stmt = stmt.where(PromotionRow.is_active.is_(True))
        stmt = stmt.order_by(PromotionRow.scraped_at.desc())
        return list(self.session.execute(stmt).scalars().all())

    def get_scrape_runs(self, bank: str | None = None, limit: int = 20) -> list[ScrapeRunRow]:
        stmt = select(ScrapeRunRow)
        if bank:
            stmt = stmt.where(ScrapeRunRow.bank == bank)
        stmt = stmt.order_by(ScrapeRunRow.started_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def close(self):
        if self._session:
            self._session.close()
