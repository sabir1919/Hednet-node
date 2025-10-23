# hednet_nodes_live_termux.py
# Headless Hednet Multi-node Bot for Termux / Ubuntu ARM
# Supports proxies and real-time points display
# Install: pip install pyppeteer rich asyncio

import asyncio
import csv
from pathlib import Path
from pyppeteer import launch
from rich.console import Console
from rich.table import Table
from datetime import datetime

console = Console()

# Load accounts
def load_accounts(file_path="accounts.csv"):
    accounts = []
    if not Path(file_path).exists():
        console.print(f"[red]Accounts file not found:[/red] {file_path}")
        return accounts
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].strip().lower() == "email":
                continue
            email = row[0].strip()
            pwd = row[1].strip() if len(row) > 1 else ""
            accounts.append({"email": email, "password": pwd})
    return accounts

# Load proxies
def load_proxies(file_path="proxies.txt"):
    proxies = []
    if not Path(file_path).exists():
        return proxies
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                proxies.append(line)
    return proxies

# Node task
async def run_node(account, proxy=None):
    try:
        launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        if proxy:
            launch_args["args"].append(f"--proxy-server={proxy}")
        
        browser = await launch(**launch_args)
        page = await browser.newPage()
        await page.goto("https://app.hednet.io/dashboard", timeout=60000)
        await asyncio.sleep(2)

        # Check if already logged in
        if "login" in page.url.lower():
            console.print(f"[yellow]{account['email']}[/yellow] needs manual login or saved state.")
            await browser.close()
            return {"email": account['email'], "points": 0, "status": "Login required"}

        # Extract points
        try:
            # Update selector according to your Hednet dashboard
            points_element = await page.querySelector("div:has-text('Points')")
            points = await page.evaluate("(el) => el.innerText", points_element) if points_element else "0"
            status = "Active"
        except Exception:
            points = "0"
            status = "Error fetching points"

        await browser.close()
        return {"email": account['email'], "points": points, "status": status, "proxy": proxy, "last": datetime.now().strftime("%H:%M:%S")}
    except Exception as e:
        return {"email": account['email'], "points": "0", "status": f"Error: {e}", "proxy": proxy, "last": datetime.now().strftime("%H:%M:%S")}

# Display table
def display_table(nodes_data):
    table = Table(title="Hednet Multi-node Dashboard", show_lines=True)
    table.add_column("Email", style="cyan", no_wrap=True)
    table.add_column("Proxy", style="magenta")
    table.add_column("Points", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Last", style="white")
    for node in nodes_data:
        table.add_row(node.get("email", ""), node.get("proxy", ""), str(node.get("points", "")),
                      node.get("status", ""), node.get("last", ""))
    console.clear()
    console.print(table)

# Main loop
async def main(accounts_file="accounts.csv", proxies_file="proxies.txt"):
    accounts = load_accounts(accounts_file)
    proxies = load_proxies(proxies_file)
    nodes_data = []

    while True:
        tasks = []
        for idx, acc in enumerate(accounts):
            proxy = proxies[idx % len(proxies)] if proxies else None
            tasks.append(run_node(acc, proxy))
        nodes_data = await asyncio.gather(*tasks)
        display_table(nodes_data)
        await asyncio.sleep(60)  # Refresh every 60s

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", default="accounts.csv", help="CSV file of email,password")
    parser.add_argument("--proxies", default="proxies.txt", help="Proxies file (one per line)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.accounts, args.proxies))
    except KeyboardInterrupt:
        console.print("[red]Exiting...[/red]")
