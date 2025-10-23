import asyncio
import csv
from pyppeteer import launch
from datetime import datetime
from rich.table import Table
from rich.console import Console
from rich import box

console = Console()

# Load accounts from CSV
def load_accounts(filename="accounts.csv"):
    accounts = []
    with open(filename, newline="") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) >= 2:
                email, password = row[0].strip(), row[1].strip()
                accounts.append({"email": email, "password": password})
    return accounts

# Load proxies from TXT
def load_proxies(filename="proxies.txt"):
    proxies = []
    try:
        with open(filename) as f:
            proxies = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        pass
    return proxies

# Fetch points for a single account
async def fetch_points(account, proxy=None):
    try:
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox"]
        }
        if proxy:
            launch_args["args"].append(f"--proxy-server={proxy}")
        
        browser = await launch(**launch_args)
        page = await browser.newPage()
        await page.goto("https://app.hednet.io/dashboard", {"timeout": 30000})
        
        # Example: Extract points from element (update selector as needed)
        points = 0
        try:
            elem = await page.querySelector("selector-for-points")  # TODO: update selector
            points = int(await page.evaluate('(element) => element.innerText', elem))
        except Exception:
            points = 0
        
        await browser.close()
        return points, "Active"
    except Exception as e:
        return 0, f"Error: {e}"

# Display dashboard
async def display_dashboard(accounts, proxies=None):
    table = Table(title="Hednet Multi-node Dashboard", box=box.DOUBLE_EDGE)
    table.add_column("Email", style="cyan")
    table.add_column("Proxy", style="magenta")
    table.add_column("Points", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Last Updated", style="blue")
    
    tasks = []
    for i, account in enumerate(accounts):
        proxy = proxies[i] if proxies and i < len(proxies) else None
        tasks.append(fetch_points(account, proxy))
    
    results = await asyncio.gather(*tasks)
    
    for account, (points, status) in zip(accounts, results):
        proxy = proxies[accounts.index(account)] if proxies and accounts.index(account) < len(proxies) else "-"
        table.add_row(account["email"], proxy or "-", str(points), status, datetime.now().strftime("%H:%M:%S"))
    
    console.clear()
    console.print(table)

# Main loop
async def main():
    accounts = load_accounts()
    proxies = load_proxies()
    
    while True:
        await display_dashboard(accounts, proxies)
        await asyncio.sleep(10)  # refresh every 10 seconds

if __name__ == "__main__":
    asyncio.run(main())
