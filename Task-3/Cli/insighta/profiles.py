import csv
import json
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from insighta.api import api_request

console = Console()


def _print_table(profiles: list):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", width=36)
    table.add_column("Name", width=20)
    table.add_column("Gender", width=8)
    table.add_column("Age", width=5)
    table.add_column("Group", width=10)
    table.add_column("Country", width=8)
    table.add_column("G.Prob", width=7)

    for p in profiles:
        table.add_row(
            p["id"],
            p["name"],
            p["gender"],
            str(p["age"]),
            p["age_group"],
            p["country_id"],
            f"{p['gender_probability']:.2f}",
        )

    console.print(table)


def list_profiles(
    gender: str = None,
    age_group: str = None,
    country: str = None,
    min_age: int = None,
    max_age: int = None,
    sort_by: str = "created_at",
    order: str = "asc",
    page: int = 1,
    limit: int = 10,
):
    params = {
        "sort_by": sort_by,
        "order": order,
        "page": page,
        "limit": limit,
    }
    if gender:
        params["gender"] = gender
    if age_group:
        params["age_group"] = age_group
    if country:
        params["country_id"] = country
    if min_age is not None:
        params["min_age"] = min_age
    if max_age is not None:
        params["max_age"] = max_age

    res = api_request("GET", "/api/profiles", params=params)
    data = res.json()

    if res.status_code != 200:
        typer.echo(f"Error: {data['message']}")
        raise typer.Exit(1)

    console.print(
        f"\n[green]Page {data['page']} of {data['total_pages']} | "
        f"Total: {data['total']} profiles[/green]\n"
    )
    _print_table(data["data"])

    if data["links"]["next"]:
        console.print(f"\n[grey50]Next page: use --page {data['page'] + 1}[/grey50]")


def search_profiles(query: str, page: int = 1, limit: int = 10):
    res = api_request("GET", "/api/profiles/search", params={"q": query, "page": page, "limit": limit})
    data = res.json()

    if res.status_code != 200:
        typer.echo(f"Error: {data['message']}")
        raise typer.Exit(1)

    console.print(f"\n[green]Found {data['total']} profiles matching '{query}'[/green]\n")
    _print_table(data["data"])


def get_profile(profile_id: str):
    res = api_request("GET", f"/api/profiles/{profile_id}")
    data = res.json()

    if res.status_code != 200:
        typer.echo(f"Error: {data['message']}")
        raise typer.Exit(1)

    p = data["data"]
    console.print("\n[bold]Profile Details[/bold]")
    console.print("[grey50]" + "─" * 40 + "[/grey50]")
    console.print(f"[cyan]ID:[/cyan]          {p['id']}")
    console.print(f"[cyan]Name:[/cyan]        {p['name']}")
    console.print(f"[cyan]Gender:[/cyan]      {p['gender']} ({p['gender_probability']:.2f})")
    console.print(f"[cyan]Age:[/cyan]         {p['age']} ({p['age_group']})")
    console.print(f"[cyan]Country:[/cyan]     {p['country_name']} [{p['country_id']}] ({p['country_probability']:.2f})")
    console.print(f"[cyan]Created:[/cyan]     {p['created_at']}")
    console.print("[grey50]" + "─" * 40 + "[/grey50]\n")


def export_profiles():
    console.print("[yellow]Exporting profiles...[/yellow]")
    res = api_request("GET", "/api/profiles/export", params={"format": "csv"})

    if res.status_code != 200:
        typer.echo(f"Error: {res.json()['message']}")
        raise typer.Exit(1)

    filename = "profiles.csv"
    with open(filename, "w") as f:
        f.write(res.text)

    console.print(f"[green]✓ Exported to {filename}[/green]")


def create_profile():
    console.print("[bold]\nCreate New Profile (Admin only)\n[/bold]")

    name = typer.prompt("Name")
    gender = typer.prompt("Gender (male/female)")
    gender_probability = typer.prompt("Gender probability (0-1)")
    age = typer.prompt("Age")
    age_group = typer.prompt("Age group (child/teenager/adult/senior)")
    country_id = typer.prompt("Country ID (e.g. NG)")
    country_name = typer.prompt("Country name")
    country_probability = typer.prompt("Country probability (0-1)")

    res = api_request("POST", "/api/profiles", json={
        "name": name,
        "gender": gender,
        "gender_probability": float(gender_probability),
        "age": int(age),
        "age_group": age_group,
        "country_id": country_id,
        "country_name": country_name,
        "country_probability": float(country_probability),
    })

    data = res.json()

    if res.status_code != 201:
        typer.echo(f"Error: {data['message']}")
        raise typer.Exit(1)

    console.print("[green]\n✓ Profile created successfully![/green]")
    rprint(data["data"])