import dateutil
from dateutil.rrule import weekday
from recurrent import format as rrule_format

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


# noinspection PyProtectedMember,SpellCheckingInspection
def get_recurrence_text(recurrence: dateutil.rrule.rrule):

    # workarounds for some limitations of the rrule-to-english package.
    # e.g., some invalid assumptions lead to unconverted rrules
    rec = dateutil.rrule.rrulestr(str(recurrence))
    if rec._freq == 2 and rec._original_rule['byweekday'] is None:
        # add byweekday to original rule in weekly
        rec._original_rule['byweekday'] = tuple(weekday(wd) for wd in rec._byweekday)
    rec_str = str(rec).replace('\n', ';')
    rec_format = str(rrule_format(rec)).replace('\n', ';')
    print(f'{rec_str} [freq:{rec._freq}, byday:{rec._byweekday}] -> {rec_format}  ........  {rec.__dict__}')
    return rec_format
