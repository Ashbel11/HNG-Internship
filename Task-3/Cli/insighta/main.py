import typer
from typing import Optional
from insighta.store import is_logged_in
from insighta import auth, profiles

app = typer.Typer(help="Insighta Labs CLI — Query demographic profiles")
profiles_app = typer.Typer(help="Manage profiles")
app.add_typer(profiles_app, name="profiles")


@app.command()
def login():
    """Authenticate via GitHub OAuth."""
    try:
        user = auth.login()
        typer.echo(f"\n✓ Logged in as {user['username']} ({user['role']})\n")
    except Exception as e:
        typer.echo(f"\nLogin failed: {e}\n")
        raise typer.Exit(1)


@app.command()
def logout():
    """Clear stored tokens."""
    auth.logout()
    typer.echo("✓ Logged out successfully")


@app.command()
def whoami():
    """Show current login status."""
    if not is_logged_in():
        typer.echo("Not logged in. Run: insighta login")
    else:
        typer.echo("✓ You are logged in")


@profiles_app.command("list")
def profiles_list(
    gender: Optional[str] = typer.Option(None, help="male or female"),
    age_group: Optional[str] = typer.Option(None, "--age-group", help="child/teenager/adult/senior"),
    country: Optional[str] = typer.Option(None, help="Country ID e.g. NG"),
    min_age: Optional[int] = typer.Option(None, "--min-age"),
    max_age: Optional[int] = typer.Option(None, "--max-age"),
    sort_by: str = typer.Option("created_at", "--sort-by"),
    order: str = typer.Option("asc"),
    page: int = typer.Option(1),
    limit: int = typer.Option(10),
):
    """List profiles with optional filters."""
    profiles.list_profiles(gender, age_group, country, min_age, max_age, sort_by, order, page, limit)


@profiles_app.command("search")
def profiles_search(
    query: str = typer.Argument(..., help="Natural language query"),
    page: int = typer.Option(1),
    limit: int = typer.Option(10),
):
    """Natural language search."""
    profiles.search_profiles(query, page, limit)


@profiles_app.command("get")
def profiles_get(profile_id: str = typer.Argument(..., help="Profile UUID")):
    """Get a profile by ID."""
    profiles.get_profile(profile_id)


@profiles_app.command("export")
def profiles_export():
    """Export all profiles as CSV."""
    profiles.export_profiles()


@profiles_app.command("create")
def profiles_create():
    """Create a new profile (admin only)."""
    profiles.create_profile()


if __name__ == "__main__":
    app()