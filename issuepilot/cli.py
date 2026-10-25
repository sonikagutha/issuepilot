import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="issuepilot",
    help="Agentic GitHub issue triage and recommendation.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print the installed IssuePilot version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("issuepilot"))


@app.command()
def analyze(
    repo: str = typer.Argument(..., help="owner/repository"),
    issue: int = typer.Option(..., "--issue", help="Issue number to analyze"),
) -> None:
    """Run the analysis pipeline (investigation + complexity) on one issue."""
    from issuepilot.config import get_settings
    from issuepilot.github.client import GitHubAPIError, GitHubClient
    from issuepilot.graph.pipeline import run_pipeline
    from issuepilot.observability.trace_store import TraceStore

    if "/" not in repo:
        console.print(f"[red]error:[/red] expected owner/repository, got: {repo}")
        raise typer.Exit(1)
    owner, repo_name = repo.split("/", 1)

    settings = get_settings()

    try:
        with GitHubClient(settings) as client:
            gh_issue = client.fetch_issue(owner, repo_name, issue)
    except GitHubAPIError as exc:
        console.print(f"[red]GitHub error:[/red] {exc}")
        raise typer.Exit(1) from exc

    trace_store = TraceStore(settings.trace_db_path)
    try:
        result = run_pipeline(gh_issue, settings=settings, trace_store=trace_store)
    except ValueError as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1) from exc
    finally:
        trace_store.close()

    context, complexity = result.context, result.complexity
    analysis = context.analysis
    console.print(Panel(f"[bold]{gh_issue.title}[/bold]\n#{gh_issue.number} · {repo}", title="Issue"))

    color = {"Easy": "green", "Medium": "yellow", "Difficult": "red"}[complexity.result.difficulty]
    console.print(
        f"[bold {color}]{complexity.result.difficulty}[/bold {color}] "
        f"(score {complexity.result.overall_score}/5) · effort: {complexity.effort_estimate}"
    )
    if complexity.required_skills:
        console.print(f"[bold]Skills:[/bold] {', '.join(complexity.required_skills)}")
    console.print(f"[bold]Summary:[/bold] {analysis.summary}\n")

    if analysis.stated_requirements:
        console.print("[bold]Stated requirements:[/bold]")
        for item in analysis.stated_requirements:
            console.print(f"  • {item}")

    if analysis.likely_relevant_paths:
        console.print("\n[bold]Likely relevant paths:[/bold]")
        for item in analysis.likely_relevant_paths:
            console.print(f"  • {item}")

    if analysis.ambiguities:
        console.print("\n[bold]Ambiguities:[/bold]")
        for item in analysis.ambiguities:
            console.print(f"  • {item}")

    if context.referenced_numbers:
        refs = ", ".join(f"#{n}" for n in context.referenced_numbers)
        console.print(f"\n[bold]Referenced issues/PRs:[/bold] {refs}")

    console.print(f"\n[dim]{analysis.reasoning}[/dim]")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to listen on"),
) -> None:
    """Start the local web UI."""
    import uvicorn

    console.print(f"IssuePilot web UI: [bold]http://{host}:{port}[/bold]")
    uvicorn.run("issuepilot.web:app", host=host, port=port)


if __name__ == "__main__":
    app()
