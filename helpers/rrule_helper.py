from helpers.tools import get_ordinal


class Selectable:
    RAW = []
    EN = []

    @classmethod
    def raw_from_selection(cls, sel: str):
        if sel in cls.EN:
            return cls.RAW[cls.EN.index(sel)]

    @classmethod
    def en_from_raw(cls, raw: str):
        if raw in cls.RAW:
            return cls.EN[cls.RAW.index(raw)]


class WeekOfMonth(Selectable):
    RAW = [*range(1, 6), -1]
    EN = [*[get_ordinal(week) for week in range(1, 6)], 'Last']


class Weekdays(Selectable):
    MO = "MO"
    TU = "TU"
    WE = "WE"
    TH = "TH"
    FR = "FR"
    SA = "SA"
    SU = "SU"
    RAW = [MO, TU, WE, TH, FR, SA, SU]
    EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class Monthday(Selectable):
    RAW = [*range(1, 32), -1]
    EN = [*[get_ordinal(day) for day in range(1, 32)], 'Last Day']


class Frequencies(Selectable):
    YEARLY = "YEARLY"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"
    RAW = [YEARLY, MONTHLY, WEEKLY, DAILY]
    EN = ["Year(s)", "Month(s)", "Week(s)", "Day(s)"]