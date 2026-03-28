import json
import sys

from enum import Enum
from pathlib import Path
from datetime import datetime, date, timedelta
from os import get_terminal_size
from dataclasses import dataclass


LOGO = """
  ▄▄                                       
 ██  ▀▀                          ▀▀        
▀██▀ ██  ████▄  ▀▀█▄ ████▄ ▄█▀▀▀ ██  ▄████ 
 ██  ██  ██ ██ ▄█▀██ ██ ██ ▀███▄ ██  ██    
 ██  ██▄ ██ ██ ▀█▄██ ██ ██ ▄▄▄█▀ ██▄ ▀████ 
                                           
"""


def delim(symbol: str):
    width = get_terminal_size().columns
    print(symbol * width)


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


class FinanceStore:
    def __init__(self):
        self._datapath = Path("finance.json")
        self._ctx_records = self.load_records()

    def load_records(self) -> list[FinanceRecord]:
        if not self._datapath.exists():
            with open(self._datapath, "w", encoding="utf-8") as f:
                json.dump({"records": []}, f)
            return []
        with open(self._datapath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [FinanceRecord.from_dict(r) for r in raw["records"]]
    
    def save_records(self):
        with open(self._datapath, "w", encoding="utf-8") as f:
            json.dump({"records": [r.to_dict() for r in self._ctx_records]}, f)

    def add_record(self, record: FinanceRecord):
        self._ctx_records.append(record)
        self.save_records()

    @property
    def records(self) -> list[FinanceRecord]:
        return self._ctx_records

    def delete_record(self, index: int) -> None:
        del self._ctx_records[index]
        self.save_records()

    def update_record(self, index: int, record: FinanceRecord) -> None:
        self._ctx_records[index] = record
        self.save_records()


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


def _format_money(x: float) -> str:
    return f"{x:.2f}"


# ANSI: фон для сумм — зелёный (доходы), жёлтый (расходы); чёрный текст для читаемости
_ANSI_RESET = "\033[0m"
_ANSI_FG_BLACK = "\033[30m"
_ANSI_BG_GREEN = "\033[42m"
_ANSI_BG_YELLOW = "\033[43m"


def _style_income_amount(s: str) -> str:
    return f"{_ANSI_FG_BLACK}{_ANSI_BG_GREEN}{s}{_ANSI_RESET}"


def _style_expense_amount(s: str) -> str:
    return f"{_ANSI_FG_BLACK}{_ANSI_BG_YELLOW}{s}{_ANSI_RESET}"


class AnalyticsBuilder:
    def __init__(self, records: list[FinanceRecord]):
        self._records = records

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
        return self.total_income(records) - self.total_expense(records)

    def all_categories(self, records: list[FinanceRecord] | None = None) -> list[str]:
        rs = records if records is not None else self._records
        return sorted({r.category for r in rs})

    def expenses_by_category_sorted(
        self, records: list[FinanceRecord] | None = None
    ) -> list[tuple[str, float]]:
        rs = records if records is not None else self._records
        by_cat: dict[str, float] = {}
        for r in rs:
            if r.type != FinanceRecordType.EXPENSE:
                continue
            by_cat[r.category] = by_cat.get(r.category, 0.0) + r.amount
        return sorted(by_cat.items(), key=lambda x: (-x[1], x[0]))

    def all_expenses_by_categories_sorted(self) -> dict[str, float]:
        return dict(self.expenses_by_category_sorted())

    def records_by_month(self) -> dict[tuple[int, int], list[FinanceRecord]]:
        buckets: dict[tuple[int, int], list[FinanceRecord]] = {}
        for r in self._records:
            k = _month_key(_parse_record_date(r))
            buckets.setdefault(k, []).append(r)
        return buckets

    def month_keys_sorted(self) -> list[tuple[int, int]]:
        return sorted(self.records_by_month().keys())


class BaseCommand:
    def __init__(
        self,
        slug: str,
        description: str,
    ):
        self.slug = slug
        self.description = description
        self.store = FinanceStore()
    
    def execute(self):
        raise NotImplementedError


class ExitCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="exit", description="Выйти из программы")
    
    def execute(self):
        print("Выход из программы.")
        sys.exit(0)


class AddRecordCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="add", description="Добавить запись")
    
    def execute(self):
        date = input("Введите дату (dd.mm.yyyy) [сегодняшняя]: ")
        if not date:
            date = datetime.now().strftime("%d.%m.%Y")

        category = input("Введите категорию: ")
        amount = float(input("Введите сумму: "))
        type = input("Введите тип (income(i)/expense(e)): ")
        
        record = FinanceRecord(
            date=date,
            category=category,
            amount=amount,
            type=FinanceRecordType.from_cli_option(type)
        )
        self.store.add_record(record)

        print("Запись добавлена")
        delim("-")


def _format_record_line(i: int, r: FinanceRecord) -> str:
    t = "доход" if r.type == FinanceRecordType.INCOME else "расход"
    amt = _format_money(r.amount)
    if r.type == FinanceRecordType.INCOME:
        amt = _style_income_amount(amt)
    else:
        amt = _style_expense_amount(amt)
    return f"  [{i}] {r.date} | {r.category} | {amt} | {t}"


class ViewRecordsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="view", description="Посмотреть записи")

    def execute(self):
        recs = self.store.records
        if not recs:
            print("Записей пока нет.")
        else:
            print('Какие записи просмотреть? [все(a)/income(i)/expense(e)]')
            choice = input("Выберите вариант: ")
            if choice == "a":
                recs = recs
            else:
                recs = [r for r in recs if r.type == FinanceRecordType.from_cli_option(choice)]

            print("Записи:")
            for i, r in enumerate(recs):
                print(_format_record_line(i, r))
        delim("-")


class EditRecordCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="edit", description="Редактировать запись")

    def execute(self):
        recs = self.store.records
        if not recs:
            print("Нет записей для редактирования.")
            delim("-")
            return

        print("Записи:")
        for i, r in enumerate(recs):
            print(_format_record_line(i, r))

        idx = int(input("Номер записи для редактирования: "))
        date = input("Дата (dd.mm.yyyy) [Enter — без изменений]: ")
        category = input("Категория [Enter — без изменений]: ")
        amount_raw = input("Сумма [Enter — без изменений]: ")
        rtype_raw = input("Тип income(i)/expense(e) [Enter — без изменений]: ")

        old = recs[idx]
        date_value = date.strip() or old.date
        category_value = category.strip() or old.category
        amount_value = float(amount_raw) if amount_raw.strip() else old.amount
        type_value = FinanceRecordType.from_cli_option(rtype_raw.strip()) if rtype_raw.strip() else old.type

        new = FinanceRecord(
            date=date_value,
            category=category_value,
            amount=amount_value,
            type=type_value,
        )

        self.store.update_record(idx, new)

        print("Запись обновлена.")
        delim("-")


class DeleteRecordCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="delete", description="Удалить запись")

    def execute(self):
        recs = self.store.records
        if not recs:
            print("Нет записей для удаления.")
            delim("-")
            return

        print("Записи:")
        for i, r in enumerate(recs):
            print(_format_record_line(i, r))

        idx = int(input("Номер записи для удаления: "))
        confirm = input('Введите "да" для подтверждения: ').strip().lower()
        if confirm != "да":
            print("Удаление отменено.")
            delim("-")
            return

        self.store.delete_record(idx)

        print("Запись удалена.")
        delim("-")


def _ask_date_period() -> tuple[date, date] | None:
    start_raw = input("Дата начала периода (dd.mm.yyyy): ").strip()
    end_raw = input("Дата конца периода (dd.mm.yyyy): ").strip()
    try:
        start_d = datetime.strptime(start_raw, "%d.%m.%Y").date()
        end_d = datetime.strptime(end_raw, "%d.%m.%Y").date()
    except ValueError:
        print("Неверный формат даты. Ожидается dd.mm.yyyy.")
        return None
    if start_d > end_d:
        print("Дата начала не может быть позже даты конца.")
        return None
    return start_d, end_d


def _print_income_expense(title: str, income: float, expense: float) -> None:
    print(title)
    print(f"  Доходы: {_style_income_amount(_format_money(income))}")
    print(f"  Расходы: {_style_expense_amount(_format_money(expense))}")
    print(f"  Баланс: {_format_money(income - expense)}")


def _print_expenses_by_category(pairs: list[tuple[str, float]], title: str) -> None:
    print(title)
    if not pairs:
        print("  (нет расходов за период)")
        return
    for cat, amt in pairs:
        print(f"  {cat}: {_style_expense_amount(_format_money(amt))}")


class AnalyticsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="analytics", description="Посмотреть аналитику")

    def execute(self):
        records = self.store.records
        b = AnalyticsBuilder(records)

        if not records:
            print("Записей нет — аналитика пуста.")
            delim("-")
            return

        print("Аналитика. Выберите раздел:")
        print("[0] Доходы и расходы за всё время")
        print("[1] Доходы и расходы за прошлый месяц")
        print("[2] Доходы и расходы за выбранный период")
        print("[3] Список категорий")
        print("[4] Траты по категориям — за всё время")
        print("[5] Траты по категориям — за прошлый месяц")
        print("[6] Траты по категориям — за выбранный период")
        print("[7] Полный отчёт по месяцам")
        choice = input("Номер раздела: ").strip()

        if choice == "0":
            _print_income_expense(
                "За всё время:",
                b.total_income(),
                b.total_expense(),
            )
        elif choice == "1":
            lo, hi = _last_calendar_month_bounds()
            rs = b.filtered(lo, hi)
            _print_income_expense(
                f"За прошлый календарный месяц ({lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}):",
                b.total_income(rs),
                b.total_expense(rs),
            )
        elif choice == "2":
            period = _ask_date_period()
            if period is None:
                delim("-")
                return
            lo, hi = period
            rs = b.filtered(lo, hi)
            _print_income_expense(
                f"За период {lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}:",
                b.total_income(rs),
                b.total_expense(rs),
            )
        elif choice == "3":
            cats = b.all_categories()
            print("Категории (все записи):")
            if not cats:
                print("  (нет)")
            else:
                for c in cats:
                    print(f"  — {c}")
        elif choice == "4":
            _print_expenses_by_category(
                b.expenses_by_category_sorted(),
                "Траты по категориям (за всё время), по убыванию суммы:",
            )
        elif choice == "5":
            lo, hi = _last_calendar_month_bounds()
            rs = b.filtered(lo, hi)
            _print_expenses_by_category(
                b.expenses_by_category_sorted(rs),
                f"Траты по категориям за прошлый месяц ({lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}), по убыванию суммы:",
            )
        elif choice == "6":
            period = _ask_date_period()
            if period is None:
                delim("-")
                return
            lo, hi = period
            rs = b.filtered(lo, hi)
            _print_expenses_by_category(
                b.expenses_by_category_sorted(rs),
                f"Траты по категориям за период {lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}, по убыванию суммы:",
            )
        elif choice == "7":
            by_m = b.records_by_month()
            print("Полный отчёт по месяцам (без произвольного периода):")
            for ym in sorted(by_m.keys()):
                y, month = ym
                rs = by_m[ym]
                label = f"{y:04d}-{month:02d}"
                delim(".")
                print(f"Месяц {label}")
                _print_income_expense(
                    "  Сводка:",
                    b.total_income(rs),
                    b.total_expense(rs),
                )
                cats = b.all_categories(rs)
                print("  Категории за месяц:")
                if not cats:
                    print("    (нет)")
                else:
                    for c in cats:
                        print(f"    — {c}")
                _print_expenses_by_category(
                    b.expenses_by_category_sorted(rs),
                    "  Траты по категориям (по убыванию суммы):",
                )
            delim(".")
        else:
            print("Неизвестный пункт меню.")

        delim("-")


COMMANDS = [
    AddRecordCommand(),
    ViewRecordsCommand(),
    EditRecordCommand(),
    DeleteRecordCommand(),
    AnalyticsCommand(),
    ExitCommand(),
]

COMMAND_MAP = {c.slug: c for c in COMMANDS}


def print_commands():
    delim(".")
    for ind, command in enumerate(COMMANDS):
        print(f"[{ind}] {command.slug}: {command.description}")
    print(f"[{len(COMMANDS)}] help: Показать список команд")
    delim(".")


def main():
    print(LOGO)
    print_commands()

    while True:
        choice = input("Выберите команду: ")

        if choice.isdigit():
            choice = int(choice)
            if choice == len(COMMANDS):
                print_commands()
                continue
            command = COMMANDS[choice]
        else:
            choice = choice.strip().lower()
            if choice == "help":
                print_commands()
                continue
            if choice not in COMMAND_MAP:
                print(f"Команда {choice} не найдена.")
                delim("-")
                continue
            command = COMMAND_MAP[choice]

        command.execute()


if __name__ == "__main__":
    main()