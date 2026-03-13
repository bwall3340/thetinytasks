"""CLI entry point for the DataFinder scraper agent."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from agent.orchestrator import ScraperAgent
from agent.output import OutputFormatter

app = typer.Typer(
    name="datafinder",
    help="Intelligent web scraping agent powered by Claude.",
    add_completion=False,
)
console = Console()
fmt = OutputFormatter()


@app.command()
def scrape(
    goal: str = typer.Argument(..., help="Natural language description of the data to extract."),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json | csv | table"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="File path to write output."),
    max_loops: Optional[int] = typer.Option(None, "--max-loops", "-m", help="Override max agent loops."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full tool call logs."),
) -> None:
    """Run the scraper agent to extract data matching GOAL."""
    console.print(Panel(f"[bold cyan]DataFinder Agent[/bold cyan]\n[dim]{goal}[/dim]", expand=False))

    if max_loops is not None:
        from agent import config
        config.settings.max_loops = max_loops

    agent = ScraperAgent()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Running agent...", total=None)

        def _run() -> dict:
            return asyncio.run(_run_agent(agent, goal, progress, task, verbose))

        result = _run()

    _display_result(result, format, output)


async def _run_agent(
    agent: ScraperAgent,
    goal: str,
    progress: Progress,
    task_id: int,
    verbose: bool,
) -> dict:
    """Run the agent with live progress updates."""
    original_execute = agent._execute_tool

    async def _instrumented(name: str, args: dict):
        url = args.get("url", args.get("query", ""))
        progress.update(task_id, description=f"[cyan]{name}[/cyan] → [dim]{url[:60]}[/dim]")
        result = await original_execute(name, args)
        if verbose:
            console.log(f"[dim]Loop {agent.state.current_loop} | {name} → success={result.success}[/dim]")
        return result

    agent._execute_tool = _instrumented  # type: ignore[method-assign]
    return await agent.run(goal)


def _display_result(result: dict, format: str, output: Optional[Path]) -> None:
    """Print or save the final result."""
    data = result.get("data")
    summary = result.get("summary", "")
    loops = result.get("loops", 0)

    console.print(f"\n[green]Done[/green] in {loops} loop(s). {summary}\n")

    if not data:
        console.print("[yellow]No data extracted.[/yellow]")
        return

    # Normalise data to list[dict] when possible
    rows: list[dict] = []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        rows = data
    elif isinstance(data, dict):
        # Prefer tables, then json_data
        tables = data.get("tables", [])
        if tables and isinstance(tables[0], list):
            rows = tables[0]
        elif isinstance(data.get("json_data"), list):
            rows = data["json_data"]

    if format == "csv":
        content = fmt.to_csv(rows) if rows else fmt.to_json(data)
    elif format == "table" and rows:
        _print_table(rows[:20])
        if len(rows) > 20:
            console.print(f"[dim]... and {len(rows) - 20} more rows.[/dim]")
        content = None
    else:
        content = fmt.to_json(data, pretty=True)

    if content and output:
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]Saved to {output}[/green]")
    elif content:
        console.print(content[:2000] + ("\n[dim]... (truncated)[/dim]" if len(content) > 2000 else ""))


def _print_table(rows: list[dict]) -> None:
    if not rows:
        return
    table = Table(show_header=True, header_style="bold magenta")
    for col in rows[0].keys():
        table.add_column(str(col))
    for row in rows:
        table.add_row(*[str(v) for v in row.values()])
    console.print(table)


if __name__ == "__main__":
    app()
