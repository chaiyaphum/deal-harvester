# Card Data Retrieval

ระบบดึงข้อมูลโปรโมชันบัตรเครดิตจากเว็บไซต์ธนาคารไทยแบบอัตโนมัติ รองรับ 3 ธนาคาร (KTC, CardX, Kasikorn) พร้อมสถาปัตยกรรมแบบ Plugin ที่เพิ่มธนาคารใหม่ได้ง่าย

---

## สารบัญ

- [ภาพรวมระบบ](#ภาพรวมระบบ)
- [สถาปัตยกรรม](#สถาปัตยกรรม)
- [โครงสร้างโปรเจกต์](#โครงสร้างโปรเจกต์)
- [การติดตั้ง](#การติดตั้ง)
- [วิธีใช้งาน (CLI)](#วิธีใช้งาน-cli)
- [Configuration](#configuration)
- [อธิบาย Component ทุกตัว](#อธิบาย-component-ทุกตัว)
  - [Core Layer](#1-core-layer)
  - [Adapters (ตัวดึงข้อมูลแต่ละธนาคาร)](#2-adapters-ตัวดึงข้อมูลแต่ละธนาคาร)
  - [Fetchers (ตัวดึง HTML/API)](#3-fetchers-ตัวดึง-htmlapi)
  - [Storage Layer](#4-storage-layer)
  - [Scheduling](#5-scheduling)
  - [Utilities](#6-utilities)
- [Data Schema](#data-schema)
- [Database](#database)
- [วิธีเพิ่มธนาคารใหม่](#วิธีเพิ่มธนาคารใหม่)
- [การทดสอบ](#การทดสอบ)
- [Deployment](#deployment)

---

## ภาพรวมระบบ

ระบบนี้ทำหน้าที่:

1. **ดึงข้อมูลโปรโมชัน** จากเว็บไซต์ธนาคาร 3 แห่ง โดยแต่ละเว็บใช้เทคนิคที่ต่างกันตามความยากของเว็บ
2. **แปลงข้อมูล** (parse) ให้เป็น schema เดียวกันทุกธนาคาร
3. **บันทึกลง Database** พร้อมระบบ deduplication ด้วย checksum (รันซ้ำกี่รอบก็ไม่มี duplicate)
4. **ตั้งเวลารันอัตโนมัติ** ด้วย scheduler
5. **บันทึก audit log** ทุกครั้งที่รัน (scrape_runs)

| ธนาคาร | เว็บไซต์ | ความยาก | วิธีดึงข้อมูล |
|---------|----------|---------|---------------|
| **KTC** | ktc.co.th/promotion | ง่าย-ปานกลาง | HTTP request + อ่าน `__NEXT_DATA__` JSON (Next.js SSR) |
| **CardX** | cardx.co.th/credit-card/promotion | ยาก | Playwright เปิด browser แล้วดักจับ API response (Flutter SPA) |
| **Kasikorn** | kasikornbank.com | ยากมาก | Playwright แบบ stealth (บล็อก bot, ต้องปลอมตัวเป็นคน) |

---

## สถาปัตยกรรม

```
                ┌─────────────┐
                │  CLI (typer) │
                │  / Scheduler │
                └──────┬──────┘
                       │
                       v
              ┌────────────────┐
              │   Pipeline     │   <-- orchestrator: fetch -> parse -> validate -> store
              │  (pipeline.py) │
              └────────┬───────┘
                       │
          ┌────────────┼────────────┐
          v            v            v
   ┌────────────┐ ┌──────────┐ ┌───────────┐
   │ KTC        │ │ CardX    │ │ Kasikorn  │   <-- แต่ละตัว = Adapter (Strategy Pattern)
   │ Adapter    │ │ Adapter  │ │ Adapter   │
   └─────┬──────┘ └────┬─────┘ └─────┬─────┘
         │              │              │
         v              v              v
   ┌──────────┐  ┌───────────┐  ┌────────────┐
   │ HTTP     │  │ Browser   │  │ Stealth    │   <-- Fetcher แยกตามเทคนิค
   │ Fetcher  │  │ Fetcher   │  │ Fetcher    │
   │ (httpx)  │  │(Playwright│  │(Playwright │
   │          │  │+intercept)│  │+anti-detect│
   └──────────┘  └───────────┘  └────────────┘
                       │
                       v
              ┌────────────────┐
              │   Repository   │   <-- upsert + dedup + audit log
              │  (SQLAlchemy)  │
              └────────┬───────┘
                       │
                       v
              ┌────────────────┐
              │   SQLite DB    │   <-- Phase 1 (เปลี่ยนเป็น PostgreSQL ได้ง่ายภายหลัง)
              └────────────────┘
```

### Design Patterns ที่ใช้

| Pattern | ใช้ตรงไหน | ทำไม |
|---------|-----------|------|
| **Registry** | `core/registry.py` | Adapter ลงทะเบียนตัวเองผ่าน decorator `@register("bank_name")` ไม่ต้องแก้ไข pipeline เลย |
| **Strategy** | แต่ละ Adapter | แต่ละธนาคารมีวิธี scrape ต่างกัน แต่ interface เดียวกัน |
| **Template Method** | `BaseAdapter` | กำหนดโครงสร้างที่ Adapter ทุกตัวต้อง implement |
| **Repository** | `storage/repository.py` | แยก business logic ออกจาก database access |
| **Pipeline** | `core/pipeline.py` | จัดลำดับ: fetch -> parse -> normalize -> validate -> store |

---

## โครงสร้างโปรเจกต์

```
card-data-retrieval/
├── pyproject.toml                          # Project metadata + dependencies
├── alembic.ini                             # Alembic migration config
├── alembic/
│   ├── env.py                              # Alembic environment setup
│   ├── script.py.mako                      # Migration template
│   └── versions/                           # Migration files (auto-generated)
│
├── src/card_retrieval/
│   ├── __init__.py
│   ├── main.py                             # CLI entry point (typer)
│   ├── config.py                           # Settings จาก environment variables
│   │
│   ├── core/                               # Business logic หลัก
│   │   ├── base_adapter.py                 # Abstract base class สำหรับ Adapter
│   │   ├── registry.py                     # ระบบลงทะเบียน Adapter
│   │   ├── models.py                       # Pydantic schemas (Promotion, ScrapeRun)
│   │   ├── pipeline.py                     # Orchestrator (รัน adapter -> เก็บ DB)
│   │   └── exceptions.py                   # Custom exceptions
│   │
│   ├── adapters/                           # Adapter แต่ละธนาคาร
│   │   ├── __init__.py                     # Import ทุก adapter เพื่อ trigger registration
│   │   ├── ktc/
│   │   │   ├── adapter.py                  # KtcAdapter class
│   │   │   ├── parser.py                   # แปลง HTML/JSON -> Promotion
│   │   │   └── constants.py                # URLs, rate limits, categories
│   │   ├── cardx/
│   │   │   ├── adapter.py                  # CardxAdapter class
│   │   │   ├── parser.py                   # แปลง intercepted JSON -> Promotion
│   │   │   └── constants.py                # URLs, API patterns
│   │   └── kasikorn/
│   │       ├── adapter.py                  # KasikornAdapter class
│   │       ├── parser.py                   # แปลง rendered HTML -> Promotion
│   │       └── constants.py                # URLs, CSS selectors
│   │
│   ├── fetchers/                           # ตัวดึงข้อมูลจากเว็บ
│   │   ├── http_fetcher.py                 # httpx (async HTTP/2) + retry
│   │   ├── browser_fetcher.py              # Playwright (JS rendering + API intercept)
│   │   └── stealth_fetcher.py              # Playwright + anti-bot (human-like behavior)
│   │
│   ├── storage/                            # Database layer
│   │   ├── database.py                     # SQLAlchemy engine + session
│   │   ├── orm_models.py                   # Table definitions (PromotionRow, ScrapeRunRow)
│   │   └── repository.py                   # CRUD + upsert + dedup logic
│   │
│   ├── scheduling/
│   │   └── scheduler.py                    # APScheduler cron jobs
│   │
│   └── utils/
│       ├── text.py                         # Thai text normalization + discount extraction
│       └── rate_limiter.py                 # Per-domain rate limiting
│
├── tests/
│   ├── conftest.py                         # Pytest fixtures (in-memory DB)
│   ├── test_models.py                      # Promotion checksum tests
│   ├── test_registry.py                    # Adapter registration tests
│   ├── test_repository.py                  # Upsert + dedup tests
│   ├── test_text_utils.py                  # Thai text parsing tests
│   ├── adapters/
│   │   ├── test_ktc_parser.py              # KTC parser tests (against fixtures)
│   │   ├── test_cardx_parser.py            # CardX parser tests
│   │   └── test_kasikorn_parser.py         # Kasikorn parser tests
│   └── fixtures/
│       ├── ktc_next_data.json              # Sample KTC __NEXT_DATA__
│       ├── ktc_promotion_page.html         # Sample KTC HTML page
│       ├── cardx_api_response.json         # Sample CardX API response
│       └── kasikorn_promotions.html        # Sample Kasikorn HTML page
│
└── data/
    └── promotions.db                       # SQLite database (auto-created)
```

---

## การติดตั้ง

### ขั้นตอนที่ 1: ติดตั้ง uv (package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

### ขั้นตอนที่ 2: สร้าง virtual environment + ติดตั้ง dependencies

```bash
cd card-data-retrieval

# สร้าง venv ด้วย Python 3.11
uv venv --python 3.11

# ติดตั้ง project + dev dependencies
uv pip install -e ".[dev]"
```

### ขั้นตอนที่ 3: ติดตั้ง Playwright browsers (จำเป็นสำหรับ CardX + Kasikorn)

```bash
.venv/bin/playwright install chromium
```

### ขั้นตอนที่ 4: สร้าง database

```bash
.venv/bin/python -m card_retrieval.main init-db
```

---

## วิธีใช้งาน (CLI)

ทุกคำสั่งรันผ่าน:

```bash
.venv/bin/python -m card_retrieval.main <command>
```

หรือถ้า install แล้ว:

```bash
card-retrieval <command>
```

### คำสั่งทั้งหมด

#### `run` - รัน scraper

```bash
# รันทุกธนาคาร
card-retrieval run

# รันเฉพาะ KTC
card-retrieval run --bank ktc

# รันเฉพาะ CardX
card-retrieval run --bank cardx

# รันเฉพาะ Kasikorn
card-retrieval run --bank kasikorn
```

ผลลัพธ์:
```
Starting scrape for all banks...
  ktc: success | found=45 new=45 updated=0
  cardx: success | found=22 new=22 updated=0
  kasikorn: success | found=18 new=18 updated=0
```

#### `list-adapters` - ดู adapter ที่ลงทะเบียนแล้ว

```bash
card-retrieval list-adapters
```

```
         Registered Adapters
┌──────────┬─────────────────┬─────────────────────────────────┐
│ Bank     │ Class           │ Source URL                      │
├──────────┼─────────────────┼─────────────────────────────────┤
│ ktc      │ KtcAdapter      │ https://www.ktc.co.th/promotion │
│ cardx    │ CardxAdapter    │ https://www.cardx.co.th/...     │
│ kasikorn │ KasikornAdapter │ https://www.kasikornbank.com/...│
└──────────┴─────────────────┴─────────────────────────────────┘
```

#### `show` - ดูโปรโมชันที่เก็บไว้

```bash
# ดูทั้งหมด (default 20 รายการ)
card-retrieval show

# ดูเฉพาะ KTC, 50 รายการ
card-retrieval show --bank ktc --limit 50
```

#### `history` - ดูประวัติการรัน

```bash
card-retrieval history
card-retrieval history --bank ktc --limit 5
```

#### `schedule` - เปิด scheduler รันอัตโนมัติ

```bash
card-retrieval schedule
```

```
Starting scheduler...
  KTC: every 6h
  CardX: every 12h
  Kasikorn: every 24h
```

กด `Ctrl+C` เพื่อหยุด

#### `init-db` - สร้างตาราง database

```bash
card-retrieval init-db
```

---

## Configuration

ตั้งค่าทั้งหมดผ่าน **environment variables** ด้วย prefix `CARD_RETRIEVAL_`:

| Variable | ค่าเริ่มต้น | คำอธิบาย |
|----------|-------------|----------|
| `CARD_RETRIEVAL_DATABASE_URL` | `sqlite:///data/promotions.db` | Database connection string |
| `CARD_RETRIEVAL_LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `CARD_RETRIEVAL_LOG_JSON` | `false` | เปิด JSON logging (เหมาะสำหรับ production) |
| `CARD_RETRIEVAL_RATE_LIMIT_KTC` | `2.0` | วินาทีระหว่าง request ของ KTC |
| `CARD_RETRIEVAL_RATE_LIMIT_CARDX` | `5.0` | วินาทีระหว่าง request ของ CardX |
| `CARD_RETRIEVAL_RATE_LIMIT_KASIKORN` | `10.0` | วินาทีระหว่าง request ของ Kasikorn |
| `CARD_RETRIEVAL_SCHEDULE_KTC` | `6` | ชั่วโมงระหว่างรอบ scrape ของ KTC |
| `CARD_RETRIEVAL_SCHEDULE_CARDX` | `12` | ชั่วโมงระหว่างรอบ scrape ของ CardX |
| `CARD_RETRIEVAL_SCHEDULE_KASIKORN` | `24` | ชั่วโมงระหว่างรอบ scrape ของ Kasikorn |
| `CARD_RETRIEVAL_BROWSER_HEADLESS` | `true` | เปิด browser แบบ headless (ไม่แสดง GUI) |
| `CARD_RETRIEVAL_BROWSER_TIMEOUT` | `30000` | timeout ของ browser (ms) |

ตัวอย่างการใช้:

```bash
# ใช้ PostgreSQL แทน SQLite
export CARD_RETRIEVAL_DATABASE_URL="postgresql://user:pass@localhost:5432/card_promo"

# เปิด debug log
export CARD_RETRIEVAL_LOG_LEVEL="DEBUG"

# เปิด browser mode ให้เห็น (debug)
export CARD_RETRIEVAL_BROWSER_HEADLESS="false"
```

หรือสร้างไฟล์ `.env`:

```env
CARD_RETRIEVAL_DATABASE_URL=sqlite:///data/promotions.db
CARD_RETRIEVAL_LOG_LEVEL=INFO
CARD_RETRIEVAL_BROWSER_HEADLESS=true
```

---

## อธิบาย Component ทุกตัว

### 1. Core Layer

#### `core/models.py` - Pydantic Schemas

โมเดลข้อมูลหลัก 2 ตัว:

**Promotion** - โปรโมชัน 1 รายการ

```python
class Promotion(BaseModel):
    id: str                          # UUID สร้างอัตโนมัติ
    bank: str                        # "ktc", "cardx", "kasikorn"
    source_id: str                   # ID ต้นทางจากเว็บธนาคาร
    source_url: str                  # URL ตรงไปหน้าโปรโมชัน
    title: str                       # ชื่อโปรโมชัน
    description: str                 # รายละเอียด
    image_url: str | None            # รูปภาพ
    card_types: list[str]            # ประเภทบัตรที่ใช้ได้
    category: str | None             # "dining", "shopping", "travel", ...
    merchant_name: str | None        # ชื่อร้านค้า
    discount_type: str | None        # "percentage", "cashback", "points", "discount"
    discount_value: str | None       # "50%", "500 baht", "5000 points"
    minimum_spend: float | None      # ยอดใช้จ่ายขั้นต่ำ (บาท)
    start_date: date | None          # วันเริ่มต้น
    end_date: date | None            # วันสิ้นสุด
    terms_and_conditions: str | None # เงื่อนไข
    raw_data: dict                   # ข้อมูลดิบจากต้นทาง (debug)
    scraped_at: datetime             # เวลาที่ scrape
    checksum: str                    # SHA-256 (computed) สำหรับตรวจจับการเปลี่ยนแปลง
```

**checksum** คำนวณจาก: `bank + source_id + title + description + discount_type + discount_value + start_date + end_date` แล้ว hash ด้วย SHA-256 เพื่อใช้เปรียบเทียบว่าข้อมูลเปลี่ยนหรือไม่

**ScrapeRun** - บันทึกการรันแต่ละรอบ

```python
class ScrapeRun(BaseModel):
    id: str                          # UUID
    bank: str                        # ธนาคารที่รัน
    started_at: datetime
    finished_at: datetime | None
    status: str                      # "running", "success", "failed"
    promotions_found: int            # จำนวนที่พบ
    promotions_new: int              # จำนวนที่เพิ่มใหม่
    promotions_updated: int          # จำนวนที่อัปเดต
    error_message: str | None        # ข้อความ error (ถ้ามี)
```

#### `core/registry.py` - Adapter Registry

ระบบลงทะเบียน adapter ด้วย decorator:

```python
from card_retrieval.core.registry import register

@register("my_bank")
class MyBankAdapter(BaseAdapter):
    ...
```

ภายในเก็บเป็น dict: `{"ktc": KtcAdapter, "cardx": CardxAdapter, ...}`

Functions:
- `register(name)` - decorator สำหรับลงทะเบียน
- `get_adapter(name)` - ดึง adapter class ตามชื่อ
- `list_adapters()` - ดูทั้งหมดที่ลงทะเบียนแล้ว

#### `core/base_adapter.py` - Abstract Base

Interface ที่ทุก adapter ต้อง implement:

```python
class BaseAdapter(ABC):
    @abstractmethod
    def get_bank_name(self) -> str: ...         # ชื่อธนาคาร

    @abstractmethod
    def get_source_url(self) -> str: ...        # URL หน้าโปรโมชัน

    @abstractmethod
    async def fetch_promotions(self) -> list[Promotion]: ...  # ดึงข้อมูล

    async def close(self) -> None: ...          # cleanup (optional override)
```

#### `core/pipeline.py` - Orchestrator

ควบคุมลำดับการทำงาน:

1. สร้าง `ScrapeRun` record (status=running)
2. เรียก `adapter.fetch_promotions()` ดึงข้อมูล
3. เรียก `repo.upsert_promotions()` บันทึกลง DB
4. อัปเดต `ScrapeRun` (status=success/failed)
5. เรียก `adapter.close()` cleanup resources
6. บันทึก `ScrapeRun` ลง DB

ถ้า error จะ catch exception แล้วบันทึก error_message ลง ScrapeRun ไม่ crash ทั้งระบบ

#### `core/exceptions.py` - Custom Exceptions

```
CardRetrievalError          # base
├── FetchError              # ดึงข้อมูลไม่ได้ (HTTP error, timeout)
├── ParseError              # แปลงข้อมูลไม่ได้ (HTML เปลี่ยนโครงสร้าง)
├── AdapterError            # error ใน adapter
└── StorageError            # เขียน DB ไม่ได้
```

---

### 2. Adapters (ตัวดึงข้อมูลแต่ละธนาคาร)

#### KTC Adapter (`adapters/ktc/`)

**วิธีทำงาน:**

KTC ใช้ Next.js (SSR) ซึ่งจะฝัง JSON ข้อมูลทั้งหมดใน `<script id="__NEXT_DATA__">` tag ใน HTML ทำให้ไม่ต้องเปิด browser เลย แค่ request HTTP แล้ว parse JSON ได้เลย

```
1. HTTP GET ไป https://www.ktc.co.th/promotion
2. หา <script id="__NEXT_DATA__"> ใน HTML
3. JSON.parse() แล้วเข้าไปดูใน props.pageProps.promotions
4. แปลงแต่ละ item เป็น Promotion object
5. วนรัน 10 categories: dining, shopping, travel, ...
6. รวม + dedup ด้วย source_id
```

**Fallback:** ถ้าไม่มี `__NEXT_DATA__` จะ parse จาก HTML ด้วย CSS selectors แทน

**Rate limit:** 2 วินาทีระหว่าง request (รวมประมาณ 22 วินาที/รอบ สำหรับ 11 pages)

**Files:**
- `adapter.py` - KtcAdapter class, วนดึงแต่ละ category
- `parser.py` - `extract_next_data()`, `parse_promotions_from_next_data()`, `parse_promotions_from_html()`
- `constants.py` - URLs, category list, rate limit

#### CardX Adapter (`adapters/cardx/`)

**วิธีทำงาน:**

CardX เป็น Flutter web app (SPA) ที่ render ทุกอย่างฝั่ง client ไม่มี HTML ให้ parse ต้องเปิด browser จริง แล้วดัก API response ที่ Flutter app เรียก

```
1. เปิด Playwright Chromium browser
2. ตั้ง response interceptor (ดักทุก response ที่ URL ตรง pattern)
3. เข้าหน้า https://www.cardx.co.th/credit-card/promotion
4. รอ 8 วินาทีให้ Flutter app โหลดเสร็จแล้วเรียก API
5. เก็บ JSON response ที่ดักได้
6. แปลง JSON -> Promotion objects
```

**API Intercept Patterns:**
- `api.cardx.co.th`
- `/api/`
- `promotion`
- `graphql`

**Rate limit:** 5 วินาทีระหว่าง request

**Files:**
- `adapter.py` - CardxAdapter class, เรียก BrowserFetcher
- `parser.py` - `parse_intercepted_data()`, รองรับหลายรูปแบบ API response (REST, GraphQL)
- `constants.py` - URLs, API patterns

#### Kasikorn Adapter (`adapters/kasikorn/`)

**วิธีทำงาน:**

Kasikorn มีระบบ anti-bot ที่ return 403 สำหรับ bot ทั่วไป ต้องใช้ stealth browser ที่ปลอมตัวเป็นคน

```
1. เปิด Playwright แบบ stealth (ลบ webdriver flag, ปลอม plugins, ตั้ง timezone)
2. เข้า homepage ก่อนเพื่อได้ cookies/session
3. รอ 1-3 วินาที (เหมือนคนกำลังอ่าน)
4. เข้าหน้าโปรโมชัน
5. รอ element ขึ้น (.kb-card-promotion)
6. scroll หน้า 3 รอบ (เหมือนคนเลื่อนอ่าน)
7. ดึง HTML ที่ render แล้ว
8. Parse ด้วย CSS selectors
9. แปลงวันที่ภาษาไทย (เช่น "1 ม.ค. 67" -> 2024-01-01)
```

**Stealth Techniques:**
- ลบ `navigator.webdriver` flag
- ปลอม `navigator.plugins` (5 plugins)
- ตั้ง timezone เป็น `Asia/Bangkok`
- ตั้ง locale เป็น `th-TH`
- ปิด `AutomationControlled` blink feature
- ใส่ `window.chrome = {runtime: {}}`
- หน่วงเวลาแบบ random (ไม่ใช่จังหวะเท่ากัน)
- Scroll แบบ smooth ทีละ 70% ของ viewport

**Rate limit:** 10 วินาทีระหว่าง request

**Thai Date Parser:**
รองรับรูปแบบ:
- `1 ม.ค. 67` -> 2024-01-01 (ปี พ.ศ. ย่อ)
- `1 มกราคม 2567` -> 2024-01-01 (ปี พ.ศ. เต็ม)
- `01/01/2024` -> 2024-01-01 (สากล)

---

### 3. Fetchers (ตัวดึง HTML/API)

#### `HttpFetcher` (`fetchers/http_fetcher.py`)

สำหรับเว็บที่ไม่ต้องใช้ browser (เช่น KTC)

- ใช้ `httpx` async client พร้อม HTTP/2
- Headers ปลอมเป็น Chrome browser (User-Agent, Accept-Language ภาษาไทย)
- Auto-retry 3 ครั้ง ด้วย exponential backoff (2s, 4s, 8s)
- Follow redirects อัตโนมัติ
- Timeout: 30 วินาที

#### `BrowserFetcher` (`fetchers/browser_fetcher.py`)

สำหรับเว็บ SPA ที่ต้อง render JavaScript (เช่น CardX)

- ใช้ Playwright Chromium
- Viewport: 1920x1080
- 2 modes:
  - `fetch_with_intercept()` - เปิดหน้าเว็บแล้วดัก API response
  - `fetch_rendered_html()` - เปิดหน้าเว็บแล้ว return HTML ที่ render แล้ว

#### `StealthFetcher` (`fetchers/stealth_fetcher.py`)

สำหรับเว็บที่บล็อก bot (เช่น Kasikorn)

- ทุกอย่างที่ `BrowserFetcher` มี + เพิ่ม:
  - Inject JavaScript ตอนเปิดทุกหน้าเพื่อลบ fingerprint
  - `pre_visit_url` - เข้าหน้าอื่นก่อนเพื่อได้ cookies
  - `_human_like_delay()` - หน่วงเวลาแบบ random
  - `_scroll_page()` - เลื่อนหน้าเหมือนคน

---

### 4. Storage Layer

#### `storage/database.py` - Database Connection

```python
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
```

เปลี่ยน database ได้ง่ายแค่เปลี่ยน `CARD_RETRIEVAL_DATABASE_URL`:
- SQLite: `sqlite:///data/promotions.db`
- PostgreSQL: `postgresql://user:pass@host:5432/dbname`

#### `storage/orm_models.py` - Table Definitions

**ตาราง `promotions`:**

| Column | Type | หมายเหตุ |
|--------|------|----------|
| id | VARCHAR(36) PK | UUID |
| bank | VARCHAR(50) | indexed |
| source_id | VARCHAR(255) | ID จากต้นทาง |
| source_url | VARCHAR(1024) | |
| title | VARCHAR(500) | |
| description | TEXT | |
| image_url | VARCHAR(1024) | nullable |
| card_types | JSON | list of strings |
| category | VARCHAR(100) | nullable |
| merchant_name | VARCHAR(255) | nullable |
| discount_type | VARCHAR(50) | nullable |
| discount_value | VARCHAR(100) | nullable |
| minimum_spend | FLOAT | nullable |
| start_date | DATE | nullable |
| end_date | DATE | nullable |
| terms_and_conditions | TEXT | nullable |
| raw_data | JSON | ข้อมูลดิบ |
| checksum | VARCHAR(64) | SHA-256 |
| scraped_at | DATETIME | |
| is_active | BOOLEAN | default true, indexed |
| created_at | DATETIME | auto |
| updated_at | DATETIME | auto on update |

**ตาราง `scrape_runs`:**

| Column | Type | หมายเหตุ |
|--------|------|----------|
| id | VARCHAR(36) PK | UUID |
| bank | VARCHAR(50) | indexed |
| started_at | DATETIME | |
| finished_at | DATETIME | nullable |
| status | VARCHAR(20) | running/success/failed |
| promotions_found | INT | |
| promotions_new | INT | |
| promotions_updated | INT | |
| error_message | TEXT | nullable |

#### `storage/repository.py` - Data Access

**`upsert_promotions(promotions)`:**

Logic:
1. ค้นหาด้วย `bank + source_id`
2. ถ้าไม่เจอ -> INSERT (นับเป็น new)
3. ถ้าเจอแต่ checksum ต่างกัน -> UPDATE (นับเป็น updated)
4. ถ้าเจอและ checksum เหมือน -> ข้าม (ข้อมูลไม่เปลี่ยน)
5. Return `(new_count, updated_count)`

ด้วยวิธีนี้รันซ้ำกี่รอบก็ไม่มี duplicate records

---

### 5. Scheduling

#### `scheduling/scheduler.py`

ใช้ APScheduler (AsyncIOScheduler) ตั้งเวลา:

| ธนาคาร | ความถี่ | เหตุผล |
|---------|---------|--------|
| KTC | ทุก 6 ชั่วโมง | HTTP request เบา, เว็บอัปเดตบ่อย |
| CardX | ทุก 12 ชั่วโมง | ต้องเปิด browser, ปานกลาง |
| Kasikorn | ทุก 24 ชั่วโมง | Stealth browser หนัก, เว็บไม่อัปเดตบ่อย |

---

### 6. Utilities

#### `utils/text.py` - Thai Text Processing

**`normalize_thai_text(text)`:**
- ลบ zero-width characters (U+200B, U+200C, U+200D, U+FEFF) ที่มักซ่อนอยู่ในเว็บไทย
- รวม whitespace ซ้ำเป็นช่องเดียว
- strip ซ้าย-ขวา

**`extract_discount(text)`:**
ดึงประเภทส่วนลดจากข้อความภาษาไทย:
- `"ส่วนลด 50%"` -> `("percentage", "50%")`
- `"รับเงินคืน 500 บาท"` -> `("cashback", "500 baht")`
- `"5 เท่า"` -> `("points", "5 points")`
- ลำดับตรวจ: percentage -> points -> cashback/discount

**`extract_minimum_spend(text)`:**
ดึงยอดใช้จ่ายขั้นต่ำ:
- `"ช้อปครบ 3,000 บาท"` -> `3000.0`
- `"ขั้นต่ำ 500 baht"` -> `500.0`
- รองรับ keywords: ครบ, ตั้งแต่, ขั้นต่ำ, minimum

#### `utils/rate_limiter.py` - Per-Domain Rate Limiting

ควบคุมไม่ให้ request ถี่เกินไปต่อแต่ละ domain:

```python
await rate_limiter.wait("ktc.co.th", 2.0)    # รออย่างน้อย 2 วินาทีจาก request ล่าสุด
await rate_limiter.wait("cardx.co.th", 5.0)   # รออย่างน้อย 5 วินาที
```

ใช้ `asyncio.Lock` ป้องกัน race condition ระหว่าง concurrent requests

---

## Data Schema

### Flow ของข้อมูล

```
เว็บธนาคาร (HTML/JSON)
    │
    v
Adapter.fetch_promotions()       <-- ดึง + parse
    │
    v
list[Promotion]                  <-- Pydantic validated
    │
    v
Repository.upsert_promotions()   <-- dedup ด้วย checksum
    │
    v
PromotionRow (SQLAlchemy)        <-- เขียนลง DB
    │
    v
SQLite / PostgreSQL
```

### Discount Types

| Type | ตัวอย่าง | ความหมาย |
|------|----------|----------|
| `percentage` | 50% | ลดเป็นเปอร์เซ็นต์ |
| `cashback` | 500 baht | เงินคืน (ต้องมีคำว่า "คืน" หรือ "cashback") |
| `discount` | 1000 baht | ลดเป็นจำนวนเงิน |
| `points` | 5000 points | คะแนนสะสม/เท่า |

---

## Database

### การ Migrate (Alembic)

```bash
# สร้าง migration ใหม่
.venv/bin/alembic revision --autogenerate -m "add new column"

# รัน migration
.venv/bin/alembic upgrade head

# ดู migration ปัจจุบัน
.venv/bin/alembic current
```

### ดูข้อมูลใน SQLite โดยตรง

```bash
sqlite3 data/promotions.db

# ดูจำนวนโปรโมชันแต่ละธนาคาร
SELECT bank, COUNT(*) FROM promotions GROUP BY bank;

# ดูโปรโมชันล่าสุด
SELECT bank, title, discount_type, discount_value, end_date
FROM promotions
WHERE is_active = 1
ORDER BY scraped_at DESC
LIMIT 10;

# ดูประวัติการรัน
SELECT bank, status, promotions_found, promotions_new, started_at
FROM scrape_runs
ORDER BY started_at DESC
LIMIT 10;
```

---

## วิธีเพิ่มธนาคารใหม่

ตัวอย่าง: เพิ่ม SCB (Siam Commercial Bank)

### ขั้นตอนที่ 1: สร้างโฟลเดอร์

```
src/card_retrieval/adapters/scb/
├── __init__.py
├── constants.py
├── parser.py
└── adapter.py
```

### ขั้นตอนที่ 2: เขียน constants

```python
# adapters/scb/constants.py
BASE_URL = "https://www.scb.co.th"
PROMOTION_URL = f"{BASE_URL}/th/personal-banking/credit-cards/promotions"
BANK_NAME = "scb"
RATE_LIMIT_SECONDS = 3.0
```

### ขั้นตอนที่ 3: เขียน parser

```python
# adapters/scb/parser.py
from card_retrieval.core.models import Promotion

def parse_promotions(data: dict) -> list[Promotion]:
    promotions = []
    for item in data.get("items", []):
        promotions.append(Promotion(
            bank="scb",
            source_id=str(item["id"]),
            source_url=f"https://www.scb.co.th/promotion/{item['slug']}",
            title=item["title"],
            description=item.get("description", ""),
            # ... map fields ...
            raw_data=item,
        ))
    return promotions
```

### ขั้นตอนที่ 4: เขียน adapter

```python
# adapters/scb/adapter.py
from card_retrieval.core.base_adapter import BaseAdapter
from card_retrieval.core.registry import register

@register("scb")                              # <-- แค่นี้ลงทะเบียนเสร็จ
class ScbAdapter(BaseAdapter):
    def get_bank_name(self) -> str:
        return "scb"

    def get_source_url(self) -> str:
        return "https://www.scb.co.th/.../promotions"

    async def fetch_promotions(self) -> list[Promotion]:
        # เลือก fetcher ตามความเหมาะสม
        fetcher = HttpFetcher()               # หรือ BrowserFetcher / StealthFetcher
        html = await fetcher.fetch(self.get_source_url())
        return parse_promotions(html)

    async def close(self):
        await self._fetcher.close()
```

### ขั้นตอนที่ 5: Import ใน `adapters/__init__.py`

```python
from card_retrieval.adapters.scb import adapter as _scb  # noqa: F401
```

### ขั้นตอนที่ 6: ทดสอบ

```bash
card-retrieval list-adapters          # ต้องเห็น scb
card-retrieval run --bank scb         # ทดสอบดึงข้อมูล
```

**ไม่ต้องแก้ไข pipeline, CLI, scheduler, หรือ adapter อื่นเลย**

---

## การทดสอบ

### รัน tests

```bash
# ทุก tests
.venv/bin/python -m pytest tests/ -v

# เฉพาะ test ของ adapter
.venv/bin/python -m pytest tests/adapters/ -v

# พร้อม coverage report
.venv/bin/python -m pytest tests/ --cov=card_retrieval --cov-report=html
```

### Tests ทั้งหมด (28 tests)

| Test File | จำนวน | ทดสอบอะไร |
|-----------|-------|-----------|
| `test_models.py` | 4 | checksum deterministic, change detection, defaults, dates |
| `test_registry.py` | 3 | register, get, list adapters |
| `test_repository.py` | 5 | upsert new, dedup, update on change, query, scrape runs |
| `test_text_utils.py` | 6 | Thai text normalize, discount extraction, minimum spend |
| `test_ktc_parser.py` | 4 | __NEXT_DATA__ extraction, JSON parse, HTML fallback |
| `test_cardx_parser.py` | 3 | API response parse, empty, malformed |
| `test_kasikorn_parser.py` | 2 | HTML parse + Thai date, empty HTML |
| **รวม** | **28** | **ทั้งหมดผ่าน** |

Tests ทั้งหมดใช้ saved fixtures (HTML/JSON) ใน `tests/fixtures/` จึงไม่ต้องเชื่อมต่อเว็บจริง

### Linting

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/ruff format src/ tests/
```

---

## Deployment

### คำแนะนำ: deploy ที่ไหนดีและประหยัด

#### ความต้องการของระบบ

สิ่งสำคัญที่ต้องพิจารณา:
- ระบบใช้ **Playwright (Chromium browser)** สำหรับ CardX + Kasikorn -> ต้องการ RAM อย่างน้อย ~512MB-1GB
- รันไม่ตลอด, รันเป็นรอบๆ (KTC ทุก 6 ชม., CardX ทุก 12 ชม., Kasikorn ทุก 24 ชม.) -> เหมาะกับ **serverless/scheduled jobs** มากกว่า always-on server
- Database เล็ก (ไม่กี่ MB) -> SQLite พอ
- ไม่มี incoming traffic (เป็น batch job, ไม่ใช่ web server)

---

#### ตัวเลือกที่ 1: Railway.app (แนะนำที่สุด)

| | |
|-|-|
| **ราคา** | ~$5/เดือน (Hobby plan) |
| **ข้อดี** | Deploy ง่ายสุด, รองรับ Playwright, persistent volume สำหรับ SQLite |
| **ข้อเสีย** | ไม่มี free tier แล้ว |
| **เหมาะกับ** | ต้องการ deploy เร็ว ไม่ต้องจัดการ server |

```dockerfile
# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY . .
RUN pip install -e .
RUN playwright install chromium

# รัน scheduler ตลอด
CMD ["python", "-m", "card_retrieval.main", "schedule"]
```

Railway ให้ persistent volume mount ที่ `/data` เก็บ SQLite ได้

---

#### ตัวเลือกที่ 2: Hetzner VPS (ถูกที่สุดสำหรับ always-on)

| | |
|-|-|
| **ราคา** | EUR 3.79/เดือน (~150 บาท) สำหรับ CX22 (2 vCPU, 4GB RAM) |
| **ข้อดี** | ถูกมาก, เต็มที่ทุกอย่าง, ตั้ง cron job ได้เอง |
| **ข้อเสีย** | ต้อง setup server เอง (SSH, install dependencies) |
| **เหมาะกับ** | คนที่ถนัด Linux, ต้องการ control เต็มที่ |

```bash
# บน Hetzner VPS (Ubuntu 22.04)
sudo apt update && sudo apt install -y python3.11 python3.11-venv
curl -LsSf https://astral.sh/uv/install.sh | sh

cd /opt/card-retrieval
uv venv --python 3.11
uv pip install -e .
playwright install --with-deps chromium

# ตั้ง systemd service
sudo tee /etc/systemd/system/card-retrieval.service << 'EOF'
[Unit]
Description=Card Data Retrieval Scheduler
After=network.target

[Service]
Type=simple
User=app
WorkingDirectory=/opt/card-retrieval
ExecStart=/opt/card-retrieval/.venv/bin/python -m card_retrieval.main schedule
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now card-retrieval
```

---

#### ตัวเลือกที่ 3: Google Cloud Run Jobs + Cloud Scheduler (ประหยัดสุดถ้ารันไม่บ่อย)

| | |
|-|-|
| **ราคา** | ~$0-2/เดือน (Free tier ครอบคลุมเกือบหมด) |
| **ข้อดี** | จ่ายเฉพาะตอนรัน, free tier เยอะ |
| **ข้อเสีย** | Setup ซับซ้อนกว่า, ต้อง build Docker image ใหญ่ (Playwright ~1.5GB), cold start ช้า |
| **เหมาะกับ** | ต้องการประหยัดสูงสุด, คุ้นเคย GCP |

```yaml
# cloudbuild.yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/card-retrieval', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/card-retrieval']
```

ใช้ Cloud Scheduler ยิง Cloud Run Job ตามรอบ:
- KTC: `0 */6 * * *` (ทุก 6 ชม.)
- CardX: `0 */12 * * *` (ทุก 12 ชม.)
- Kasikorn: `0 3 * * *` (วันละครั้ง ตี 3)

**ข้อควรระวัง:** Cloud Run มี timeout สูงสุด 60 นาที (เพียงพอ) แต่ Playwright image ใหญ่ ทำให้ cold start ช้า ~30-60 วินาที

---

#### ตัวเลือกที่ 4: AWS EC2 t3.micro + EventBridge (ถ้าใช้ AWS อยู่แล้ว)

| | |
|-|-|
| **ราคา** | ฟรี 12 เดือนแรก, หลังจากนั้น ~$8/เดือน |
| **ข้อดี** | Free tier ปีแรก, ecosystem AWS ใหญ่ |
| **ข้อเสีย** | t3.micro มี RAM แค่ 1GB, อาจไม่พอสำหรับ Playwright |
| **เหมาะกับ** | มี AWS account อยู่แล้ว, ใช้ t3.small (2GB) ขึ้นไป |

---

#### ตัวเลือกที่ 5: Fly.io

| | |
|-|-|
| **ราคา** | ~$3-5/เดือน |
| **ข้อดี** | Deploy ง่าย, มี persistent volume, server ใน Singapore |
| **ข้อเสีย** | Free tier จำกัดมาก |
| **เหมาะกับ** | ต้องการ latency ต่ำ (server ใกล้ไทย) |

```bash
fly launch
fly volumes create data --size 1
fly deploy
```

---

### สรุปเปรียบเทียบ

| Platform | ราคา/เดือน | Setup | Playwright | ความเหมาะสม |
|----------|-----------|-------|------------|------------|
| **Hetzner VPS** | ~150 บาท | ปานกลาง | รองรับ | **ถูกที่สุดสำหรับ always-on** |
| **GCP Cloud Run** | ~0-70 บาท | ยาก | รองรับ (image ใหญ่) | **ถูกที่สุดถ้ารันไม่บ่อย** |
| **Railway** | ~175 บาท | ง่ายสุด | รองรับ | **ง่ายที่สุด** |
| **Fly.io** | ~105-175 บาท | ง่าย | รองรับ | ดี, server ใกล้ไทย |
| **AWS EC2** | ฟรี -> ~280 บาท | ปานกลาง | ต้อง t3.small+ | ดีถ้ามี AWS อยู่แล้ว |

### คำแนะนำตามสถานการณ์

- **"ของ่ายที่สุด deploy 5 นาทีเสร็จ"** -> **Railway**
- **"ขอถูกที่สุด"** -> **Hetzner CX22** (~150 บาท/เดือน, ได้ server เต็มตัว)
- **"ขอฟรีไปก่อน"** -> **GCP Cloud Run Jobs** (free tier น่าจะพอ)
- **"ใช้ AWS อยู่แล้ว"** -> **EC2 t3.small** + cron หรือ EventBridge
- **"ต้องการ latency ต่ำ (server ใกล้ไทย)"** -> **Fly.io** (Singapore region) หรือ **Hetzner** (Singapore datacenter)

---

### Production Tips

```bash
# 1. ใช้ PostgreSQL แทน SQLite
export CARD_RETRIEVAL_DATABASE_URL="postgresql://user:pass@localhost:5432/card_promo"

# 2. เปิด JSON logging
export CARD_RETRIEVAL_LOG_JSON="true"

# 3. รัน Alembic migration
alembic upgrade head

# 4. ติดตั้ง Playwright browser dependencies (Linux)
playwright install --with-deps chromium

# 5. เช็ค health
card-retrieval history --limit 3
```

### Docker (Production-ready)

```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
COPY pyproject.toml .
RUN uv venv && uv pip install .

# Copy source
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Install Playwright browsers
RUN .venv/bin/playwright install chromium

# Create data directory
RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "card_retrieval.main", "schedule"]
```

```bash
docker build -t card-retrieval .
docker run -v card-data:/app/data card-retrieval
```
