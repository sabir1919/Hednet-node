# hednet_nodes_live_dynamic.py
# Hednet Multi-node Dashboard for Termux/Android
# Features:
# - Dynamic points detection (even for React/Next.js)
# - Proxy support
# - Live updating colored table
# - Optional JS script execution
# Usage:
# python hednet_nodes_live_dynamic.py --accounts accounts.csv --proxies proxies.txt --script run_script.js

import asyncio
import csv
import argparse
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from rich.table import Table
from rich.console import Console
from rich.live import Live
from rich.text import Text

console = Console()

# Default check interval in seconds
CHECK_INTERVAL = 15

async def extract_points(page):
    """Dynamically extract points from dashboard"""
    try:
        points = await page.evaluate("""
        () => {
            const els = Array.from(document.querySelectorAll('*'));
            for (const el of els) {
                if (/\\d+\\s*points?/i.test(el.innerText)) {
                    return el.innerText.match(/\\d+/)[0];
                }
            }
            return null;
        }
        """)
        return int(points) if points else 0
    except Exception:
        return 0

async def run_node(account, proxy_server=None, js_file=None):
    """Run a single Hednet node"""
    tag = f"[{account['email']}]"
    try:
        async with async_playwright() as p:
            chromium = p.chromium
            launch_args = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            }

            # Setup proxy
            if proxy_server:
                from urllib.parse import urlparse
                parsed = urlparse(proxy_server)
                proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
                if parsed.username:
                    proxy["username"] = parsed.username
                if parsed.password:
                    proxy["password"] = parsed.password
                launch_args["proxy"] = proxy

            browser = await chromium.launch(**launch_args)
            context = await browser.new_context()
            # Use stored session if exists
            state_file = f"storage_state_{account['email'].replace('@','_')}.json"
            if Path(state_file).exists():
                context = await browser.new_context(storage_state=state_file)

            page = await context.new_page()

            # Go to dashboard
            await page.goto("https://app.hednet.io/dashboard", timeout=60000)
            await page.wait_for_timeout(5000)

            # Run optional JS on dashboard
            if js_file and Path(js_file).exists():
                try:
                    js_code = Path(js_file).read_text(encoding="utf-8")
                    await page.evaluate(js_code)
                except Exception as e:
                    console.log(f"{tag} [red]Error executing JS: {e}[/red]")

            # Save session state
            await context.storage_state(path=state_file)

            # Node loop
            while True:
                points = await extract_points(page)
                status = "Active"
                yield {
                    "email": account['email'],
                    "proxy": proxy_server or "N/A",
                    "points": points,
                    "status": status,
                    "last": datetime.now().strftime("%H:%M:%S")
                }
                await asyncio.sleep(CHECK_INTERVAL)
    except PlaywrightTimeoutError:
        yield {
            "email": account['email'],
            "proxy": proxy_server or "N/A",
            "points": 0,
            "status": "Timeout/Error",
            "last": datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        yield {
            "email": account['email'],
            "proxy": proxy_server or "N/A",
            "points": 0,
            "status": f"Error: {str(e)}",
            "last": datetime.now().strftime("%H:%M:%S")
        }

async def main(args):
    # Load accounts
    accounts = []
    if not Path(args.accounts).exists():
        console.print(f"[red]Accounts file not found: {args.accounts}[/red]")
        return
    with open(args.accounts, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row or row[0].strip().lower() == "email":
                continue
            email = row[0].strip()
            pwd = row[1].strip() if len(row) > 1 else ""
            accounts.append({"email": email, "password": pwd})

    if not accounts:
        console.print("[red]No accounts found[/red]")
        return

    # Load proxies
    proxies = []
    if args.proxies and Path(args.proxies).exists():
        for ln in open(args.proxies, "r", encoding="utf-8"):
            ln = ln.strip()
            if ln:
                proxies.append(ln)

    # Start nodes
    tasks = []
    async def node_worker(account, proxy):
        async for node_info in run_node(account, proxy_server=proxy, js_file=args.script):
            # Update live table
            table_rows[account['email']] = node_info

    table_rows = {}
    for idx, acc in enumerate(accounts):
        proxy = proxies[idx % len(proxies)] if proxies else None
        tasks.append(node_worker(acc, proxy))

    # Display live table
    def make_table():
        table = Table(title="Hednet Multi-node Dashboard", expand=True)
        table.add_column("Email", justify="left")
        table.add_column("Proxy", justify="left")
        table.add_column("Points", justify="right")
        table.add_column("Status", justify="left")
        table.add_column("Last", justify="center")

        for info in table_rows.values():
            points_text = Text(str(info['points']))
            if info['points'] > 0:
                points_text.stylize("green")
            table.add_row(
                info['email'],
                info['proxy'],
                points_text,
                info['status'],
                info['last']
            )
        return table

    with Live(make_table(), refresh_per_second=1) as live:
        await asyncio.gather(*[asyncio.create_task(t) for t in tasks], return_exceptions=True)
        while True:
            live.update(make_table())
            await asyncio.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", default="accounts.csv", help="CSV file of email,password")
    parser.add_argument("--proxies", default=None, help="Proxies file (one per line)")
    parser.add_argument("--script", default=None, help="Optional JS file to run on dashboard")
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        console.print("[red]Interrupted by user. Exiting...[/red]")
