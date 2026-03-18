from __future__ import annotations

import structlog
from sqlalchemy import String, func, select, update

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

    def deactivate_missing(self, bank: str, active_source_ids: list[str]) -> int:
        """Set is_active=False for promotions not in the current scrape."""
        stmt = (
            update(PromotionRow)
            .where(
                PromotionRow.bank == bank,
                PromotionRow.is_active.is_(True),
                PromotionRow.source_id.notin_(active_source_ids),
            )
            .values(is_active=False)
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount

    def get_promotions(
        self, bank: str | None = None, active_only: bool = True,
    ) -> list[PromotionRow]:
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

    def query_promotions(
        self,
        filters: dict,
        sort_by: str = "scraped_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PromotionRow], int]:
        stmt = select(PromotionRow)

        if filters.get("bank"):
            stmt = stmt.where(PromotionRow.bank == filters["bank"])
        if filters.get("category"):
            stmt = stmt.where(PromotionRow.category == filters["category"])
        if filters.get("merchant_name"):
            stmt = stmt.where(PromotionRow.merchant_name.ilike(f"%{filters['merchant_name']}%"))
        if filters.get("discount_type"):
            stmt = stmt.where(PromotionRow.discount_type == filters["discount_type"])
        if filters.get("card_type"):
            stmt = stmt.where(
                PromotionRow.card_types.cast(String).ilike(f"%{filters['card_type']}%")
            )
        if filters.get("search"):
            term = f"%{filters['search']}%"
            stmt = stmt.where(
                PromotionRow.title.ilike(term) | PromotionRow.description.ilike(term)
            )
        if "is_active" in filters and filters["is_active"] is not None:
            stmt = stmt.where(PromotionRow.is_active.is_(filters["is_active"]))
        if filters.get("start_date_from"):
            stmt = stmt.where(PromotionRow.start_date >= filters["start_date_from"])
        if filters.get("start_date_to"):
            stmt = stmt.where(PromotionRow.start_date <= filters["start_date_to"])
        if filters.get("end_date_from"):
            stmt = stmt.where(PromotionRow.end_date >= filters["end_date_from"])
        if filters.get("end_date_to"):
            stmt = stmt.where(PromotionRow.end_date <= filters["end_date_to"])
        if filters.get("min_spend_min") is not None:
            stmt = stmt.where(PromotionRow.minimum_spend >= filters["min_spend_min"])
        if filters.get("min_spend_max") is not None:
            stmt = stmt.where(PromotionRow.minimum_spend <= filters["min_spend_max"])

        # Count total before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar_one()

        # Sort
        allowed_sort = {"scraped_at", "title", "end_date", "created_at"}
        sort_col = getattr(PromotionRow, sort_by if sort_by in allowed_sort else "scraped_at")
        stmt = stmt.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items = list(self.session.execute(stmt).scalars().all())
        return items, total

    def get_promotion_by_id(self, promotion_id: str) -> PromotionRow | None:
        stmt = select(PromotionRow).where(PromotionRow.id == promotion_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_stats(self) -> list[dict]:
        stmt = (
            select(
                PromotionRow.bank,
                func.count().label("total"),
                func.count().filter(PromotionRow.is_active.is_(True)).label("active"),
            )
            .group_by(PromotionRow.bank)
            .order_by(PromotionRow.bank)
        )
        rows = self.session.execute(stmt).all()
        return [{"bank": r.bank, "total": r.total, "active": r.active} for r in rows]

    def get_filter_options(self) -> dict:
        banks = [
            r[0]
            for r in self.session.execute(
                select(PromotionRow.bank).distinct().order_by(PromotionRow.bank)
            ).all()
        ]
        categories = [
            r[0]
            for r in self.session.execute(
                select(PromotionRow.category)
                .where(PromotionRow.category.isnot(None))
                .distinct()
                .order_by(PromotionRow.category)
            ).all()
        ]
        discount_types = [
            r[0]
            for r in self.session.execute(
                select(PromotionRow.discount_type)
                .where(PromotionRow.discount_type.isnot(None))
                .distinct()
                .order_by(PromotionRow.discount_type)
            ).all()
        ]
        merchant_names = [
            r[0]
            for r in self.session.execute(
                select(PromotionRow.merchant_name)
                .where(PromotionRow.merchant_name.isnot(None))
                .distinct()
                .order_by(PromotionRow.merchant_name)
            ).all()
        ]
        # card_types is JSON — collect distinct values across all rows
        all_card_types: set[str] = set()
        rows = self.session.execute(
            select(PromotionRow.card_types).where(PromotionRow.card_types.isnot(None))
        ).all()
        for (ct,) in rows:
            if isinstance(ct, list):
                all_card_types.update(str(v) for v in ct if v)

        return {
            "banks": banks,
            "categories": categories,
            "discount_types": discount_types,
            "card_types": sorted(all_card_types),
            "merchant_names": merchant_names,
        }

    def query_scrape_runs(
        self,
        filters: dict,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ScrapeRunRow], int]:
        stmt = select(ScrapeRunRow)

        if filters.get("bank"):
            stmt = stmt.where(ScrapeRunRow.bank == filters["bank"])
        if filters.get("status"):
            stmt = stmt.where(ScrapeRunRow.status == filters["status"])
        if filters.get("from_date"):
            stmt = stmt.where(ScrapeRunRow.started_at >= filters["from_date"])
        if filters.get("to_date"):
            stmt = stmt.where(ScrapeRunRow.started_at <= filters["to_date"])

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.session.execute(count_stmt).scalar_one()

        stmt = stmt.order_by(ScrapeRunRow.started_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items = list(self.session.execute(stmt).scalars().all())
        return items, total

    def close(self):
        if self._session:
            self._session.close()
