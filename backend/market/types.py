from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StockPrice:
    ticker: str
    price: float
    prev_price: float
    change_pct: float
    timestamp: datetime
    company_name: str = field(default="")
