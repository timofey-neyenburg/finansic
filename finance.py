import json

from enum import Enum
from pathlib import Path
from datetime import datetime
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


class AnalyticsBuilder:
    def __init__(self, records: list[FinanceRecord]):
        self._records = records


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


class AddRecordCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="add", description="Добавить запись")
    
    def execute(self):
        date = input("Введите дату (dd.mm.yyyy) [сегодняшняя]: ")
        if not date:
            date = datetime.now().strftime("%d.%m.%Y")

        category = input("Введите категорию: ")
        amount = float(input("Введите сумму: "))
        type = input("Введите тип (income/expense): ")

        record = FinanceRecord(
            date=date,
            category=category,
            amount=amount,
            type=FinanceRecordType(type)
        )
        self.store.add_record(record)

        print("Запись добавлена")
        delim("-")


def _format_record_line(i: int, r: FinanceRecord) -> str:
    t = "доход" if r.type == FinanceRecordType.INCOME else "расход"
    return f"  [{i}] {r.date} | {r.category} | {r.amount} | {t}"


class ViewRecordsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="view", description="Посмотреть записи")

    def execute(self):
        recs = self.store.records
        if not recs:
            print("Записей пока нет.")
        else:
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
        rtype_raw = input("Тип income/expense [Enter — без изменений]: ")

        old = recs[idx]
        new = FinanceRecord(
            date=date.strip() or old.date,
            category=category.strip() or old.category,
            amount=float(amount_raw) if amount_raw.strip() else old.amount,
            type=FinanceRecordType(rtype_raw.strip()) if rtype_raw.strip() else old.type,
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


class AnalyticsCommand(BaseCommand):
    def __init__(self):
        super().__init__(slug="analytics", description="Посмотреть аналитику")

    def execute(self):
        AnalyticsBuilder(self.store.records)
        print("Аналитика: заглушка (AnalyticsBuilder пока пустой).")
        delim("-")


COMMANDS = [
    AddRecordCommand(),
    ViewRecordsCommand(),
    EditRecordCommand(),
    DeleteRecordCommand(),
    AnalyticsCommand(),
]


def main():
    print(LOGO)
    delim(".")
    for ind, command in enumerate(COMMANDS):
        print(f"[{ind}] {command.slug}: {command.description}")
    delim(".")

    choice = int(input("Выберите команду: "))

    command = COMMANDS[choice]
    command.execute()


if __name__ == "__main__":
    main()