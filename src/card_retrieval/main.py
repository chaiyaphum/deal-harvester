from __future__ import annotations

import asyncio
from typing import Optional

import structlog
import typer
from rich.console import Console
from rich.table import Table

# Configure structlog before anything else
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

app = typer.Typer(name="card-retrieval", help="Credit card promotion data retrieval system")
console = Console()


def _ensure_db():
    from card_retrieval.storage.repository import PromotionRepository

    repo = PromotionRepository()
    repo.ensure_tables()
    repo.close()


@app.command()
def run(
    bank: Optional[str] = typer.Option(None, "--bank", "-b", help="Run specific bank adapter"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch and parse but skip DB writes"),
):
    """Run promotion scraping pipeline."""
    _ensure_db()

    # Import adapters to trigger registration
    import card_retrieval.adapters  # noqa: F401
    from card_retrieval.core.pipeline import run_pipeline

    banks = [bank] if bank else None

    label = "DRY RUN " if dry_run else ""
    scope = f"  for {bank}" if bank else " for all banks"
    console.print(f"[bold]{label}Starting scrape{scope}...[/bold]")
    results = asyncio.run(run_pipeline(banks=banks, dry_run=dry_run))

    for r in results:
        status_color = "green" if r.status == "success" else "red"
        console.print(
            f"  [{status_color}]{r.bank}[/{status_color}]: "
            f"{r.status} | found={r.promotions_found} new={r.promotions_new} "
            f"updated={r.promotions_updated}"
        )
        if r.error_message:
            console.print(f"    [red]Error: {r.error_message}[/red]")


@app.command()
def list_adapters():
    """List all registered bank adapters."""
    import card_retrieval.adapters  # noqa: F401
    from card_retrieval.core.registry import list_adapters as _list

    adapters = _list()
    table = Table(title="Registered Adapters")
    table.add_column("Bank", style="cyan")
    table.add_column("Class", style="green")
    table.add_column("Source URL")

    for name, cls in adapters.items():
        instance = cls()
        table.add_row(name, cls.__name__, instance.get_source_url())

    console.print(table)


@app.command()
def show(
    bank: Optional[str] = typer.Option(None, "--bank", "-b", help="Filter by bank"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
):
    """Show stored promotions."""
    _ensure_db()
    from card_retrieval.storage.repository import PromotionRepository

    repo = PromotionRepository()
    promos = repo.get_promotions(bank=bank)[:limit]

    table = Table(title=f"Promotions ({len(promos)} shown)")
    table.add_column("Bank", style="cyan", width=10)
    table.add_column("Title", width=40)
    table.add_column("Category", width=12)
    table.add_column("Discount", width=15)
    table.add_column("End Date", width=12)

    for p in promos:
        table.add_row(
            p.bank,
            p.title[:40],
            p.category or "-",
            f"{p.discount_type}: {p.discount_value}" if p.discount_type else "-",
            str(p.end_date) if p.end_date else "-",
        )

    console.print(table)
    repo.close()


@app.command()
def history(
    bank: Optional[str] = typer.Option(None, "--bank", "-b", help="Filter by bank"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
):
    """Show scrape run history."""
    _ensure_db()
    from card_retrieval.storage.repository import PromotionRepository

    repo = PromotionRepository()
    runs = repo.get_scrape_runs(bank=bank, limit=limit)

    table = Table(title="Scrape Runs")
    table.add_column("Bank", style="cyan")
    table.add_column("Status")
    table.add_column("Found", justify="right")
    table.add_column("New", justify="right")
    table.add_column("Updated", justify="right")
    table.add_column("Started At")
    table.add_column("Error")

    for r in runs:
        status_style = "green" if r.status == "success" else "red"
        table.add_row(
            r.bank,
            f"[{status_style}]{r.status}[/{status_style}]",
            str(r.promotions_found),
            str(r.promotions_new),
            str(r.promotions_updated),
            str(r.started_at)[:19],
            (r.error_message or "-")[:40],
        )

    console.print(table)
    repo.close()


@app.command()
def schedule():
    """Start the scheduler for periodic scraping."""
    _ensure_db()

    import card_retrieval.adapters  # noqa: F401
    from card_retrieval.config import settings
    from card_retrieval.scheduling.scheduler import create_scheduler

    console.print("[bold]Starting scheduler...[/bold]")
    console.print(f"  KTC: every {typer.style(str(settings.schedule_ktc), fg='cyan')}h")
    console.print(f"  CardX: every {typer.style(str(settings.schedule_cardx), fg='cyan')}h")
    console.print(f"  Kasikorn: every {typer.style(str(settings.schedule_kasikorn), fg='cyan')}h")

    sched = create_scheduler()
    sched.start()

    async def _run_forever():
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            pass

    try:
        asyncio.run(_run_forever())
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[bold]Scheduler stopped.[/bold]")
        sched.shutdown()


@app.command()
def init_db():
    """Initialize the database tables."""
    _ensure_db()
    console.print("[green]Database initialized successfully.[/green]")


if __name__ == "__main__":
    app()
