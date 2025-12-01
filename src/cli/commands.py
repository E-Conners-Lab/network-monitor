"""CLI commands for network monitor."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Network Monitor CLI")
console = Console()


@app.command()
def status():
    """Show monitoring status."""
    console.print("[green]Network Monitor Status[/green]")
    console.print("Service: [bold green]Running[/bold green]")


@app.command()
def devices():
    """List all monitored devices."""
    table = Table(title="Monitored Devices")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("IP Address")
    table.add_column("Type")
    table.add_column("Status")

    # TODO: Fetch from API
    console.print(table)
    console.print("[yellow]Connect to API to fetch devices[/yellow]")


@app.command()
def alerts(active_only: bool = typer.Option(True, "--active/--all", help="Show only active alerts")):
    """List alerts."""
    table = Table(title="Alerts" + (" (Active)" if active_only else " (All)"))
    table.add_column("ID", style="cyan")
    table.add_column("Device")
    table.add_column("Severity", style="red")
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Created")

    # TODO: Fetch from API
    console.print(table)
    console.print("[yellow]Connect to API to fetch alerts[/yellow]")


@app.command()
def check(device_name: str = typer.Argument(..., help="Device name to check")):
    """Run connectivity check on a device."""
    console.print(f"Running connectivity check on [cyan]{device_name}[/cyan]...")
    # TODO: Implement actual check via API
    console.print("[yellow]Not implemented yet[/yellow]")


@app.command()
def sync_netbox():
    """Sync devices from NetBox."""
    console.print("[cyan]Syncing devices from NetBox...[/cyan]")
    # TODO: Implement NetBox sync
    console.print("[yellow]Not implemented yet[/yellow]")


@app.command()
def remediate(
    device_name: str = typer.Argument(..., help="Device name"),
    playbook: str = typer.Argument(..., help="Playbook to run"),
):
    """Manually trigger a remediation playbook."""
    console.print(f"Running playbook [cyan]{playbook}[/cyan] on [magenta]{device_name}[/magenta]...")
    # TODO: Implement remediation trigger
    console.print("[yellow]Not implemented yet[/yellow]")


if __name__ == "__main__":
    app()
