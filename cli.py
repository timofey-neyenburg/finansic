import re
import sys

from os import get_terminal_size
from datetime import datetime, date, timedelta

from finansic import Deposit, Finansic, FinanceRecord, FinanceRecordType, AnalyticsBuilder
from utils import calc_input


LOGO = """
  ▄▄                                       
 ██  ▀▀                          ▀▀        
▀██▀ ██  ████▄  ▀▀█▄ ████▄ ▄█▀▀▀ ██  ▄████ 
 ██  ██  ██ ██ ▄█▀██ ██ ██ ▀███▄ ██  ██    
 ██  ██▄ ██ ██ ▀█▄██ ██ ██ ▄▄▄█▀ ██▄ ▀████ 
                                           
"""


_ANSI_RESET = "\033[0m"
_ANSI_FG_BLACK = "\033[30m"
_ANSI_BG_GREEN = "\033[42m"
_ANSI_BG_YELLOW = "\033[43m"
_ANSI_BG_RED = "\033[41m"
_ANSI_BG_BLUE = "\033[44m"
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def delim(symbol: str):
    width = get_terminal_size().columns
    print(symbol * width)


def _last_calendar_month_bounds(today: date | None = None) -> tuple[date, date]:
    t = today or date.today()
    first_this = t.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _format_money(x: float) -> str:
    return f"{x:.2f}"


def _style_income_amount(s: str) -> str:
    return f"{_ANSI_FG_BLACK}{_ANSI_BG_GREEN}{s}{_ANSI_RESET}"


def _style_expense_amount(s: str) -> str:
    return f"{_ANSI_FG_BLACK}{_ANSI_BG_YELLOW}{s}{_ANSI_RESET}"


def _style_balance_amount(balance: float) -> str:
    s = _format_money(balance)
    if balance < 0:
        return f"{_ANSI_FG_BLACK}{_ANSI_BG_RED}{s}{_ANSI_RESET}"
    if balance > 0:
        return f"{_ANSI_FG_BLACK}{_ANSI_BG_BLUE}{s}{_ANSI_RESET}"
    return s


def _parse_optional_float(raw: str) -> float | None:
    if not raw:
        return None
    s = raw.strip().replace(",", ".")
    return float(s)


def _visible_len(s: str) -> int:
    return len(_ANSI_ESCAPE_RE.sub("", s))


def _pad_visible(s: str, width: int, align: str = "left") -> str:
    n = _visible_len(s)
    pad = max(0, width - n)
    if align == "right":
        return " " * pad + s
    return s + " " * pad


def _print_deposits_table(deps: list[Deposit]) -> None:
    """Колонки: №, название, доступно, план, описание — выровнены по ширине столбцов."""
    n = len(deps)
    idx_w = max(len(f"  [{i}]") for i in range(n))
    w_name = max(len("название"), *(len(d.name) for d in deps))
    w_avail = max(
        len("доступно"),
        *(_visible_len(_style_balance_amount(d.available_amount)) for d in deps),
    )
    plan_strs = [
        "—" if d.planning_amount is None else _format_money(d.planning_amount) for d in deps
    ]
    w_plan = max(len("план"), *(len(s) for s in plan_strs))
    w_desc = max(len("описание"), *(len(d.description) for d in deps))

    sep = "  "
    head = (
        f"{_pad_visible('', idx_w)}{sep}"
        f"{_pad_visible('название', w_name)}{sep}"
        f"{_pad_visible('доступно', w_avail, 'right')}{sep}"
        f"{_pad_visible('план', w_plan, 'right')}{sep}"
        f"{_pad_visible('описание', w_desc)}"
    )
    print(head)
    for i, d in enumerate(deps):
        avail_styled = _style_balance_amount(d.available_amount)
        row = (
            f"{_pad_visible(f'  [{i}]', idx_w)}{sep}"
            f"{_pad_visible(d.name, w_name)}{sep}"
            f"{_pad_visible(avail_styled, w_avail, 'right')}{sep}"
            f"{_pad_visible(plan_strs[i], w_plan, 'right')}{sep}"
            f"{_pad_visible(d.description, w_desc)}"
        )
        print(row)


class BaseCommand:
    def __init__(
        self,
        slug: str,
        description: str,
    ):
        self.slug = slug
        self.description = description
        self.finansic = Finansic()
    
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
        amount = calc_input("Введите сумму: ")
        type = input("Введите тип (income(i)/expense(e)): ")
        
        record = FinanceRecord(
            date=date,
            category=category,
            amount=amount,
            type=FinanceRecordType.from_cli_option(type)
        )
        self.finansic.add_record(record)

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
        recs = self.finansic.view_all_records()
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
        recs = self.finansic.view_all_records()
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
        amount_raw = calc_input("Сумма [Enter — без изменений]: ", allow_none=True)
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

        self.finansic.update_record(idx, new)

        print("Запись обновлена.")
        delim("-")


class DeleteRecordCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="delete", description="Удалить запись")

    def execute(self):
        recs = self.finansic.view_all_records()
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

        self.finansic.delete_record(idx)

        print("Запись удалена.")
        delim("-")


class AddDepositCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="dep-add", description="Добавить депозит")

    def execute(self):
        name = input("Название депозита: ").strip()
        description = input("Описание: ").strip()
        try:
            avail_raw = calc_input("Доступная сумма [0]: ")
            available = float(avail_raw) if avail_raw else 0.0
        except ValueError:
            print("Нужно ввести число для доступной суммы.")
            delim("-")
            return
        plan_raw = calc_input("Планируемая сумма [Enter — нет]: ", allow_none=True)
        try:
            planning = _parse_optional_float(plan_raw)
        except ValueError:
            print("Нужно ввести число или оставить пустым.")
            delim("-")
            return

        self.finansic.add_deposit(
            Deposit(
                name=name,
                description=description,
                available_amount=available,
                planning_amount=planning,
            )
        )
        print("Депозит добавлен.")
        delim("-")


class ViewDepositsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="dep-view", description="Посмотреть депозиты")

    def execute(self):
        deps = self.finansic.view_all_deposits()
        if not deps:
            print("Депозитов пока нет.")
        else:
            print("Депозиты:")
            _print_deposits_table(deps)
        delim("-")


class EditDepositCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="dep-edit", description="Редактировать депозит")

    def execute(self):
        deps = self.finansic.view_all_deposits()
        if not deps:
            print("Нет депозитов для редактирования.")
            delim("-")
            return

        print("Депозиты:")
        _print_deposits_table(deps)

        try:
            idx = int(input("Номер депозита для редактирования: "))
        except ValueError:
            print("Нужен целый номер.")
            delim("-")
            return

        if idx < 0 or idx >= len(deps):
            print("Нет депозита с таким номером.")
            delim("-")
            return

        old = deps[idx]
        name = input("Название [Enter — без изменений]: ").strip() or old.name
        description = input("Описание [Enter — без изменений]: ").strip() or old.description
        avail_raw = calc_input("Доступная сумма [Enter — без изменений]: ", allow_none=True)
        plan_raw = calc_input("Планируемая сумма [Enter — без изменений, «-» — сбросить]: ", allow_none=True)

        try:
            available = float(avail_raw) if avail_raw else old.available_amount
        except ValueError:
            print("Нужно ввести число для доступной суммы.")
            delim("-")
            return

        if plan_raw.strip() == "-":
            planning: float | None = None
        elif plan_raw.strip():
            try:
                planning = _parse_optional_float(plan_raw)
            except ValueError:
                print("Нужно ввести число для планируемой суммы.")
                delim("-")
                return
        else:
            planning = old.planning_amount

        self.finansic.update_deposit(
            idx,
            Deposit(
                name=name,
                description=description,
                available_amount=available,
                planning_amount=planning,
            ),
        )
        print("Депозит обновлён.")
        delim("-")


class DeleteDepositCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="dep-delete", description="Удалить депозит")

    def execute(self):
        deps = self.finansic.view_all_deposits()
        if not deps:
            print("Нет депозитов для удаления.")
            delim("-")
            return

        print("Депозиты:")
        _print_deposits_table(deps)

        try:
            idx = int(input("Номер депозита для удаления: "))
        except ValueError:
            print("Нужен целый номер.")
            delim("-")
            return

        if idx < 0 or idx >= len(deps):
            print("Нет депозита с таким номером.")
            delim("-")
            return

        confirm = input('Введите "да" для подтверждения: ').strip().lower()
        if confirm != "да":
            print("Удаление отменено.")
            delim("-")
            return

        self.finansic.delete_deposit(idx)
        print("Депозит удалён.")
        delim("-")


class SetBalanceCommand(BaseCommand):
    def __init__(self):
        super().__init__(
            slug="balance",
            description="Установить баланс (новое значение полностью заменяет предыдущий итог)",
        )

    def execute(self):
        raw = calc_input("Новый баланс (число): ")
        try:
            value = float(raw)
        except ValueError:
            print("Нужно ввести число.")
            delim("-")
            return
        self.finansic.set_balance(value)
        print(f"Баланс установлен: {_style_balance_amount(value)}")
        delim("-")


class AnalyticsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="analytics", description="Посмотреть аналитику")

    def execute(self):
        account = self.finansic.account
        records = account.records
        b = AnalyticsBuilder(account)

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
            self._print_income_expense(
                "За всё время:",
                b.total_income(),
                b.total_expense(),
                balance=b.total_balance(),
            )
        elif choice == "1":
            lo, hi = _last_calendar_month_bounds()
            rs = b.filtered(lo, hi)
            self._print_income_expense(
                f"За прошлый календарный месяц ({lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}):",
                b.total_income(rs),
                b.total_expense(rs),
            )
        elif choice == "2":
            period = self._ask_date_period()
            if period is None:
                delim("-")
                return
            lo, hi = period
            rs = b.filtered(lo, hi)
            self._print_income_expense(
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
            self._print_expenses_by_category(
                b.expenses_by_category_sorted(),
                "Траты по категориям (за всё время), по убыванию суммы:",
            )
        elif choice == "5":
            lo, hi = _last_calendar_month_bounds()
            rs = b.filtered(lo, hi)
            self._print_expenses_by_category(
                b.expenses_by_category_sorted(rs),
                f"Траты по категориям за прошлый месяц ({lo.strftime('%d.%m.%Y')} — {hi.strftime('%d.%m.%Y')}), по убыванию суммы:",
            )
        elif choice == "6":
            period = self._ask_date_period()
            if period is None:
                delim("-")
                return
            lo, hi = period
            rs = b.filtered(lo, hi)
            self._print_expenses_by_category(
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
                self._print_income_expense(
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
                self._print_expenses_by_category(
                    b.expenses_by_category_sorted(rs),
                    "  Траты по категориям (по убыванию суммы):",
                )
            delim(".")
        else:
            print("Неизвестный пункт меню.")

        delim("-")

    def _ask_date_period(self) -> tuple[date, date] | None:
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


    def _print_income_expense(
        self,
        title: str,
        income: float,
        expense: float,
        balance: float | None = None,
    ) -> None:
        print(title)
        print(f"  Доходы: {_style_income_amount(_format_money(income))}")
        print(f"  Расходы: {_style_expense_amount(_format_money(expense))}")
        net = income - expense if balance is None else balance
        print(f"  Баланс: {_style_balance_amount(net)}")


    def _print_expenses_by_category(self, pairs: list[tuple[str, float]], title: str) -> None:
        print(title)
        if not pairs:
            print("  (нет расходов за период)")
            return
        for cat, amt in pairs:
            print(f"  {cat}: {_style_expense_amount(_format_money(amt))}")

COMMANDS = [
    AddRecordCommand(),
    ViewRecordsCommand(),
    EditRecordCommand(),
    DeleteRecordCommand(),
    AddDepositCommand(),
    ViewDepositsCommand(),
    EditDepositCommand(),
    DeleteDepositCommand(),
    SetBalanceCommand(),
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