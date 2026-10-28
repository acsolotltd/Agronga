from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    name: str
    decimals: int

    def format(self, amount: Decimal) -> str:
        return f"{self.symbol}{amount:,.{self.decimals}f}"


NGN = Currency("NGN", "₦", "Nigerian naira", 0)
USD = Currency("USD", "$", "US dollars", 2)

CURRENCIES = {c.code: c for c in (NGN, USD)}
COOKIE = "agronga_currency"
