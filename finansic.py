import json
import sys

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional


class FinanceRecordType(Enum):
    INCOME = "income"
    EXPENSE = "expense"

    def from_cli_option(option: str) -> "FinanceRecordType":
        if option in ["i", "income"]:
            return FinanceRecordType.INCOME
        elif option in ["e", "expense"]:
            return FinanceRecordType.EXPENSE
        else:
            raise ValueError(f"Invalid option: {option}")


@dataclass
class Deposit:
    name: str
    description: str
    available_amount: float = 0
    planning_amount: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "available_amount": self.available_amount,
            "planning_amount": self.planning_amount,
        }
    
    @staticmethod
    def from_dict(data: dict) -> "Deposit":
        return Deposit(
            name=data["name"],
            description=data["description"],
            available_amount=data["available_amount"],
            planning_amount=data.get("planning_amount")
        )


# TODO: implement
@dataclass
class Obligation:
    name: str
    description: str
    amount: float
    payout_date: date
    percent: Optional[float] = None # 0-100%
    percent_period: Optional[str] = None # day, week, month, year
    is_paid: bool = False


@dataclass
class FinanceRecord:
    date: str
    category: str
    amount: float
    type: FinanceRecordType

    @staticmethod
    def from_dict(data: dict) -> "FinanceRecord":
        return FinanceRecord(
            date=data["date"],
            category=data["category"],
            amount=data["amount"],
            type=FinanceRecordType(data["type"])
        )
    
    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "category": self.category,
            "amount": self.amount,
            "type": self.type.value
        }


def _balance_from_records(records: list[FinanceRecord]) -> float:
    inc = sum(r.amount for r in records if r.type == FinanceRecordType.INCOME)
    exp = sum(r.amount for r in records if r.type == FinanceRecordType.EXPENSE)
    return inc - exp


def _parse_record_date(r: FinanceRecord) -> date:
    return datetime.strptime(r.date.strip(), "%d.%m.%Y").date()


def _last_calendar_month_bounds(today: date | None = None) -> tuple[date, date]:
    t = today or date.today()
    first_this = t.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


@dataclass
class AccountTable:
    balance: float
    records: list[FinanceRecord]
    deposits: list[Deposit]

    def to_dict(self) -> dict:
        return {
            "balance": self.balance,
            "deposits": [d.to_dict() for d in self.deposits],
            "records": [r.to_dict() for r in self.records],
        }
    
    @staticmethod
    def from_dict(data: dict) -> "AccountTable":
        records = [FinanceRecord.from_dict(r) for r in data.get("records", [])]
        deposits = [Deposit.from_dict(d) for d in data.get("deposits", [])]
        rec_net = _balance_from_records(records)
        balance = float(data["balance"]) if "balance" in data else rec_net
        return AccountTable(balance=balance, records=records, deposits=deposits)


class FinanceStore:
    def __init__(self):
        self._datapath = Path("finance.json")
        self._account = self._load_account()

    def _load_account(self) -> AccountTable:
        if not self._datapath.exists():
            self._baseline = 0.0
            empty = AccountTable(balance=0.0, records=[], deposits=[])
            self._json_dump(empty.to_dict())
            return empty

        with open(self._datapath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        acc = AccountTable.from_dict(raw)
        self._baseline = acc.balance - _balance_from_records(acc.records)
        return acc

    def save_account(self):
        rec_net = _balance_from_records(self._account.records)
        self._account.balance = self._baseline + rec_net
        self._json_dump(self._account.to_dict())
        self._account = self._load_account()

    def set_balance(self, new_total: float) -> None:
        """Задать итоговый баланс; записи не трогаем, подстраивается начальный остаток."""
        rec_net = _balance_from_records(self._account.records)
        self._baseline = new_total - rec_net
        self.save_account()

    def add_record(self, record: FinanceRecord):
        self._account.records.append(record)
        self.save_account()
    
    def _json_dump(self, data: dict):
        with open(self._datapath, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

    def delete_record(self, index: int) -> None:
        del self._account.records[index]
        self.save_account()

    def update_record(self, index: int, record: FinanceRecord) -> None:
        self._account.records[index] = record
        self.save_account()

    @property
    def account(self) -> AccountTable:
        account = self._load_account()
        return account

    @property
    def records(self) -> list[FinanceRecord]:
        account = self._load_account()
        return account.records

    @property
    def deposits(self) -> list[Deposit]:
        account = self._load_account()
        return account.deposits

    def add_deposit(self, deposit: Deposit) -> None:
        self._account.deposits.append(deposit)
        self.save_account()

    def update_deposit(self, index: int, deposit: Deposit) -> None:
        self._account.deposits[index] = deposit
        self.save_account()

    def delete_deposit(self, index: int) -> None:
        del self._account.deposits[index]
        self.save_account()


class AnalyticsBuilder:
    def __init__(self, account: AccountTable):
        self._account = account

    @property
    def _records(self) -> list[FinanceRecord]:
        return self._account.records

    def filtered(self, start: date | None, end: date | None) -> list[FinanceRecord]:
        if start is None and end is None:
            return list(self._records)
        out: list[FinanceRecord] = []
        for r in self._records:
            d = _parse_record_date(r)
            if start is not None and d < start:
                continue
            if end is not None and d > end:
                continue
            out.append(r)
        return out

    def total_income(self, records: list[FinanceRecord] | None = None) -> float:
        rs = records if records is not None else self._records
        return sum(r.amount for r in rs if r.type == FinanceRecordType.INCOME)

    def total_expense(self, records: list[FinanceRecord] | None = None) -> float:
        rs = records if records is not None else self._records
        return sum(r.amount for r in rs if r.type == FinanceRecordType.EXPENSE)

    def total_balance(self, records: list[FinanceRecord] | None = None) -> float:
        rs = records if records is not None else self._records
        net = self.total_income(rs) - self.total_expense(rs)
        if records is None:
            return self._account.balance
        return net

    def all_categories(self, records: list[FinanceRecord] | None = None) -> list[str]:
        rs = records if records is not None else self._records
        return sorted({r.category for r in rs})

    def expenses_by_category_sorted(self, records: list[FinanceRecord] | None = None) -> list[tuple[str, float]]:
        rs = records if records is not None else self._records
        by_cat: dict[str, float] = {}
        for r in rs:
            if r.type != FinanceRecordType.EXPENSE:
                continue
            by_cat[r.category] = by_cat.get(r.category, 0.0) + r.amount
        return sorted(by_cat.items(), key=lambda x: (-x[1], x[0]))

    def all_expenses_by_categories_sorted(self, records: list[FinanceRecord] | None = None) -> dict[str, float]:
        return dict(self.expenses_by_category_sorted(records))

    def records_by_month(self) -> dict[tuple[int, int], list[FinanceRecord]]:
        buckets: dict[tuple[int, int], list[FinanceRecord]] = {}
        for r in self._records:
            k = _month_key(_parse_record_date(r))
            buckets.setdefault(k, []).append(r)
        return buckets

    def month_keys_sorted(self) -> list[tuple[int, int]]:
        return sorted(self.records_by_month().keys())


class Finansic:
    def __init__(self) -> None:
        self._store = FinanceStore()
    
    @property
    def account(self) -> AccountTable:
        return self._store.account

    def add_record(self, record: FinanceRecord) -> None:
        self._store.add_record(record)
    
    def update_record(self, index: int, record: FinanceRecord) -> None:
        self._store.update_record(index, record)
    
    def view_all_records(self) -> list[FinanceRecord]:
        return self._store.records
    
    def view_income_records(self) -> list[FinanceRecord]:
        return [r for r in self._store.records if r.type == FinanceRecordType.INCOME]
    
    def view_expense_records(self) -> list[FinanceRecord]:
        return [r for r in self._store.records if r.type == FinanceRecordType.EXPENSE]
    
    def delete_record(self, index: int) -> None:
        self._store.delete_record(index)
    
    def set_balance(self, new_total: float) -> None:
        self._store.set_balance(new_total)

    def view_all_deposits(self) -> list[Deposit]:
        return self._store.deposits

    def add_deposit(self, deposit: Deposit) -> None:
        self._store.add_deposit(deposit)

    def update_deposit(self, index: int, deposit: Deposit) -> None:
        self._store.update_deposit(index, deposit)

    def delete_deposit(self, index: int) -> None:
        self._store.delete_deposit(index)
    
    def get_total_income_and_expense(self) -> tuple[float, float]:
        builder = AnalyticsBuilder(self._store.account)
        return builder.total_income(), builder.total_expense()
    
    def get_previous_month_income_and_expense(self) -> tuple[float, float]:
        builder = AnalyticsBuilder(self._store.account)
        lo, hi = _last_calendar_month_bounds()
        rs = builder.filtered(lo, hi)
        return builder.total_income(rs), builder.total_expense(rs)
    
    def get_period_income_and_expense(self, period: tuple[date, date]) -> tuple[float, float]:
        builder = AnalyticsBuilder(self._store.account)
        rs = builder.filtered(period[0], period[1])
        return builder.total_income(rs), builder.total_expense(rs)
    
    def get_all_categories(self) -> list[str]:
        builder = AnalyticsBuilder(self._store.account)
        return builder.all_categories()
    
    def get_total_expenses_by_categories(self) -> dict[str, float]:
        builder = AnalyticsBuilder(self._store.account)
        return builder.all_expenses_by_categories_sorted()
    
    def get_total_expenses_by_categories_previous_month(self) -> dict[str, float]:
        builder = AnalyticsBuilder(self._store.account)
        lo, hi = _last_calendar_month_bounds()
        rs = builder.filtered(lo, hi)
        return builder.all_expenses_by_categories_sorted(rs)
    
    def get_total_expenses_by_categories_period(self, period: tuple[date, date]) -> dict[str, float]:
        builder = AnalyticsBuilder(self._store.account)
        lo, hi = period
        rs = builder.filtered(lo, hi)
        return builder.all_expenses_by_categories_sorted(rs)
    