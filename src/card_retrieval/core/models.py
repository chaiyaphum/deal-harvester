import hashlib
import json
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field


class Promotion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bank: str
    source_id: str
    source_url: str
    title: str
    description: str = ""
    image_url: str | None = None
    card_types: list[str] = Field(default_factory=list)
    category: str | None = None
    merchant_name: str | None = None
    discount_type: str | None = None
    discount_value: str | None = None
    minimum_spend: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    terms_and_conditions: str | None = None
    raw_data: dict = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def checksum(self) -> str:
        content = json.dumps(
            {
                "bank": self.bank,
                "source_id": self.source_id,
                "title": self.title,
                "description": self.description,
                "discount_type": self.discount_type,
                "discount_value": self.discount_value,
                "start_date": str(self.start_date) if self.start_date else None,
                "end_date": str(self.end_date) if self.end_date else None,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(content.encode()).hexdigest()


class ScrapeRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bank: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    status: str = "running"  # running, success, failed
    promotions_found: int = 0
    promotions_new: int = 0
    promotions_updated: int = 0
    error_message: str | None = None
