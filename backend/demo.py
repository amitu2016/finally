"""
Terminal demo for the market data provider.

Provider is selected from .env in the project root:
  USE_YAHOO=true              → YahooFinanceProvider (free, ~15 min delay, no key needed)
  INDIAN_STOCK_API_KEY=<key>  → FallbackProvider (IndianAPI + simulator standby)
  Neither                     → SimulatorProvider (GBM only)

Run with:  uv run python demo.py
Press 'q' to quit.
"""

import asyncio
import curses
import time
from pathlib import Path

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

from market.factory import create_market_provider
from market.fallback import FallbackProvider
from market.indian_api import IndianAPIProvider
from market.simulator import SEED_PRICES, SimulatorProvider
from market.yahoo import YahooFinanceProvider

TICKERS = list(SEED_PRICES.keys())
SPARKLINE_WIDTH = 20
REFRESH_HZ = 0.25


SPARK_CHARS = " ▁▂▃▄▅▆▇█"


def spark_char(val: float, lo: float, hi: float) -> str:
    if hi == lo:
        return SPARK_CHARS[0]
    idx = int((val - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))
    return SPARK_CHARS[max(0, min(idx, len(SPARK_CHARS) - 1))]


def sparkline(prices: list[float], width: int) -> str:
    if not prices:
        return " " * width
    window = prices[-width:]
    lo, hi = min(window), max(window)
    return "".join(spark_char(p, lo, hi) for p in window).ljust(width)


def color_for_change(change_pct: float) -> int:
    if change_pct > 0:
        return curses.color_pair(1)
    if change_pct < 0:
        return curses.color_pair(2)
    return curses.color_pair(3)


def flash_color(price: float, prev: float) -> int:
    if price > prev:
        return curses.color_pair(1)
    if price < prev:
        return curses.color_pair(2)
    return curses.color_pair(3)


def provider_label(provider) -> str:
    if isinstance(provider, YahooFinanceProvider):
        return "YahooFinanceProvider (NSE .NS, ~15 min delay, polls every 60s)"
    if isinstance(provider, FallbackProvider):
        mode = "FALLBACK→SIMULATOR" if provider.is_using_fallback else "IndianAPI+Simulator"
        return f"FallbackProvider [{mode}]"
    if isinstance(provider, IndianAPIProvider):
        return "IndianAPIProvider"
    return "SimulatorProvider (GBM)"


def quota_line(provider) -> str | None:
    api = None
    if isinstance(provider, FallbackProvider):
        api = provider._primary
    elif isinstance(provider, IndianAPIProvider):
        api = provider
    if api is None:
        return None
    q = api.get_quota_status()
    return (
        f"API quota {q['quota_month']}: "
        f"{q['calls_this_month']}/{q['monthly_quota']} used  "
        f"({q['calls_remaining']} remaining)"
    )


def draw_header(win, width: int, elapsed: float, tick_count: int, provider) -> int:
    """Draw header block; returns next available row."""
    title = "FinAlly Market Data Demo"
    win.addstr(0, 0, title.center(width), curses.color_pair(4) | curses.A_BOLD)

    mode = f"Provider: {provider_label(provider)}"
    win.addstr(1, 0, mode.center(width), curses.color_pair(4))

    stats = f"ticks: {tick_count:4d}  elapsed: {elapsed:5.1f}s  press 'q' to quit"
    win.addstr(2, 0, stats.center(width), curses.color_pair(3))

    row = 3
    q = quota_line(provider)
    if q:
        win.addstr(row, 0, q.center(width), curses.color_pair(5))
        row += 1

    win.addstr(row, 0, "-" * width, curses.color_pair(3))
    return row + 1


def draw_column_headers(win, row: int) -> None:
    header = (
        f"{'TICKER':<12} {'PRICE':>10} {'CHG%':>8}  "
        f"{'SPARKLINE (last 20 ticks)':<24}  {'PREV':>10}  {'SOURCE':<8}"
    )
    win.addstr(row, 0, header, curses.color_pair(4) | curses.A_UNDERLINE)


def draw_ticker_row(win, row: int, ticker: str, sp, history: list[float], source: str) -> None:
    col = flash_color(sp.price, sp.prev_price)
    change_col = color_for_change(sp.change_pct)
    spark = sparkline(history, SPARKLINE_WIDTH)

    line = f"{ticker:<12} {sp.price:>10.2f} "
    win.addstr(row, 0, line, col | curses.A_BOLD)
    win.addstr(row, len(line), f"{sp.change_pct:>+7.2f}%", change_col | curses.A_BOLD)
    win.addstr(row, len(line) + 9, f"  {spark}  ", curses.color_pair(4))
    x = len(line) + 9 + 2 + SPARKLINE_WIDTH + 2
    win.addstr(row, x, f"{sp.prev_price:>10.2f}  {source:<8}", curses.color_pair(3))


def draw_event_log(win, start_row: int, events: list[str], max_rows: int, width: int) -> None:
    win.addstr(start_row, 0, "-" * width, curses.color_pair(3))
    win.addstr(start_row + 1, 0, "Recent Events:", curses.color_pair(4) | curses.A_BOLD)
    for i, msg in enumerate(events[-max_rows:]):
        win.addstr(start_row + 2 + i, 0, msg[:width - 1], curses.color_pair(3))


def get_display_prices(provider, sim_fill: SimulatorProvider | None = None) -> dict[str, tuple]:
    """Return {ticker: (StockPrice, source_label)} for all tracked tickers.

    sim_fill: optional warm SimulatorProvider used as placeholder for Yahoo
    tickers not yet fetched. Those rows show source='sim' until Yahoo delivers.
    """
    if isinstance(provider, YahooFinanceProvider):
        yahoo = provider.get_all_prices()
        base = sim_fill.get_all_prices() if sim_fill else {}
        merged = {}
        for ticker in set(yahoo) | set(base):
            if ticker in yahoo:
                merged[ticker] = (yahoo[ticker], "yahoo")
            elif ticker in base:
                merged[ticker] = (base[ticker], "sim")
        return merged
    if isinstance(provider, FallbackProvider):
        if provider.is_using_fallback:
            return {t: (sp, "sim") for t, sp in provider._fallback.get_all_prices().items()}
        sim = provider._fallback.get_all_prices()
        live = provider._primary.get_all_prices()
        merged = {}
        for ticker in set(sim) | set(live):
            if ticker in live:
                merged[ticker] = (live[ticker], "live")
            elif ticker in sim:
                merged[ticker] = (sim[ticker], "sim")
        return merged
    if isinstance(provider, IndianAPIProvider):
        return {t: (sp, "live") for t, sp in provider.get_all_prices().items()}
    return {t: (sp, "sim") for t, sp in provider.get_all_prices().items()}


async def run_demo(stdscr) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_WHITE, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    curses.init_pair(5, curses.COLOR_YELLOW, -1)

    provider = create_market_provider()
    provider.set_tickers(TICKERS)
    await provider.start()

    # Warm simulator fills in tickers Yahoo hasn't fetched yet
    sim_fill: SimulatorProvider | None = None
    if isinstance(provider, YahooFinanceProvider):
        sim_fill = SimulatorProvider()
        sim_fill.set_tickers(TICKERS)
        await sim_fill.start()

    start_time = time.monotonic()
    tick_count = 0
    price_history: dict[str, list[float]] = {t: [] for t in TICKERS}
    events: list[str] = []

    try:
        while True:
            ch = stdscr.getch()
            if ch in (ord("q"), ord("Q")):
                break

            height, width = stdscr.getmaxyx()
            display = get_display_prices(provider, sim_fill)

            for ticker, (sp, _) in display.items():
                hist = price_history.setdefault(ticker, [])
                if hist and abs(sp.price - sp.prev_price) / sp.prev_price > 0.015:
                    direction = "UP" if sp.price > sp.prev_price else "DOWN"
                    events.append(
                        f"[{time.strftime('%H:%M:%S')}] EVENT {ticker} {direction}  "
                        f"{sp.prev_price:.2f} -> {sp.price:.2f}  "
                        f"({(sp.price - sp.prev_price) / sp.prev_price * 100:+.2f}%)"
                    )
                hist.append(sp.price)

            tick_count += 1
            elapsed = time.monotonic() - start_time

            stdscr.erase()
            next_row = draw_header(stdscr, width, elapsed, tick_count, provider)
            draw_column_headers(stdscr, next_row)

            for i, ticker in enumerate(TICKERS):
                row = next_row + 1 + i
                if row >= height - 8:
                    break
                entry = display.get(ticker)
                if entry:
                    sp, source = entry
                    draw_ticker_row(stdscr, row, ticker, sp, price_history.get(ticker, []), source)

            event_start = next_row + 1 + len(TICKERS) + 1
            max_event_rows = height - event_start - 3
            if max_event_rows > 0:
                draw_event_log(stdscr, event_start, events, max_event_rows, width)

            stdscr.refresh()
            await asyncio.sleep(REFRESH_HZ)
    finally:
        await provider.stop()
        if sim_fill:
            await sim_fill.stop()


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _curses_main(stdscr):
        loop.run_until_complete(run_demo(stdscr))

    try:
        curses.wrapper(_curses_main)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
