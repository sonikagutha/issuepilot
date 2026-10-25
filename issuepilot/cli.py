import typer

app = typer.Typer(
    name="issuepilot",
    help="Agentic GitHub issue triage and recommendation.",
    no_args_is_help=True,
)


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
    """Analyze a single GitHub issue (M1 vertical slice)."""
    typer.echo(f"analyze {repo}#{issue} — not implemented yet")


if __name__ == "__main__":
    app()
