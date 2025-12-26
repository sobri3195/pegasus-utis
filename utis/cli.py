"""CLI for UTIS modules."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from utis.core import SQLiteStorageEngine, EventProcessor
from utis.modules.email.analyzer import EmailAnalyzer
from utis.modules.whatsapp.analyzer import WhatsAppAnalyzer
from utis.modules.osint.engine import OSINTEngine, LocalJSONLProvider, GithubProvider


@click.group()
def cli():
    """UTIS - Unified Tracking & Intelligence System CLI."""
    pass


@cli.group()
def email():
    """Email security & deliverability analyzer."""
    pass


@email.command("analyze")
@click.argument("path", type=click.Path(exists=True))
@click.option("--out", default=None, help="Output JSON report path")
@click.option("--db", default="utis.db", help="UTIS database path")
@click.option("--entity", default=None, help="Entity ID to attach event (optional)")
def email_analyze(path: str, out: Optional[str], db: str, entity: Optional[str]):
    """Analyze email from .eml file or raw headers."""
    analyzer = EmailAnalyzer()
    result = analyzer.analyze(path)

    if out:
        Path(out).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        click.echo(f"Report saved to {out}")

    click.echo(json.dumps(result.to_dict(), indent=2))

    # Always persist analysis as an event.
    storage = SQLiteStorageEngine(db)
    proc = EventProcessor(storage, actor="cli_user")

    if not entity:
        from_addr = result.headers.get("From") or "unknown"
        derived = "email:" + from_addr
        # stable-ish id to group analyses for the same From header
        import hashlib

        entity = "email-" + hashlib.sha256(derived.encode("utf-8")).hexdigest()[:16]

    proc.create_event(
        entity_id=entity,
        event_type="email_analysis",
        payload=result.to_dict(),
        source="email_cli",
    )
    click.echo(f"Event logged to entity {entity}")


@cli.group()
def wa():
    """WhatsApp chat export analyzer."""
    pass


@wa.command("analyze")
@click.argument("path", type=click.Path(exists=True))
@click.option("--entity", required=True, help="Entity ID")
@click.option("--export", default=None, help="Export analysis to directory")
@click.option("--db", default="utis.db", help="UTIS database path")
def wa_analyze(path: str, entity: str, export: Optional[str], db: str):
    """Analyze WhatsApp chat export .txt file."""
    analyzer = WhatsAppAnalyzer()
    result = analyzer.analyze(path)

    click.echo(json.dumps(result.to_dict(), indent=2))

    if export:
        analyzer.export(result, export)
        click.echo(f"Exported analysis to {export}/")

    storage = SQLiteStorageEngine(db)
    proc = EventProcessor(storage, actor="cli_user")
    proc.create_event(
        entity_id=entity,
        event_type="whatsapp_export_analysis",
        payload=result.to_dict(),
        source="whatsapp_cli",
    )
    click.echo(f"Event logged to entity {entity}")


@cli.group()
def osint():
    """OSINT public footprint checker."""
    pass


@osint.command("search")
@click.argument("query")
@click.option("--providers", default="local", help="Comma-separated: local, github")
@click.option("--local-dataset", default="osint_data.jsonl", help="Path to local JSONL dataset")
@click.option("--entity", default=None, help="Entity ID to attach event (optional)")
@click.option("--db", default="utis.db", help="UTIS database path")
def osint_search(query: str, providers: str, local_dataset: str, entity: Optional[str], db: str):
    """Search query using OSINT providers."""
    storage = SQLiteStorageEngine(db)
    engine = OSINTEngine(storage)

    prov_list = []
    for pname in [p.strip() for p in providers.split(",")]:
        if pname == "local":
            prov_list.append(LocalJSONLProvider(local_dataset))
        elif pname == "github":
            prov_list.append(GithubProvider())

    if not prov_list:
        click.echo("Error: No valid providers specified", err=True)
        return

    results = engine.search(query, prov_list)

    out = [r.to_dict() for r in results]
    click.echo(json.dumps(out, indent=2))

    # Always persist as osint_footprint event
    proc = EventProcessor(storage, actor="cli_user")

    if not entity:
        import hashlib

        entity = "osint-" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]

    proc.create_event(
        entity_id=entity,
        event_type="osint_footprint",
        payload={"query": query, "results": out},
        source="osint_cli",
    )
    click.echo(f"Event logged to entity {entity}")


@cli.command("run-location-api")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8000, type=int, help="Port to bind")
@click.option("--db", default="utis.db", help="UTIS database path")
def run_location_api(host: str, port: int, db: str):
    """Run the location check-in FastAPI server."""
    os.environ["UTIS_DB_PATH"] = db
    import uvicorn
    from utis.modules.location.api import app

    click.echo(f"Starting location API on {host}:{port} with DB={db}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
