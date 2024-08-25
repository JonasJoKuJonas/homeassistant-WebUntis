def get_timetable_object(timetable_source_id, timetable_source, session):
    """return the object to request the timetable"""

    if timetable_source == "student":
        source = session.get_student(timetable_source_id[1], timetable_source_id[0])
    elif timetable_source == "klasse":
        klassen = session.klassen()

        source = klassen.filter(name=timetable_source_id)[0]
    elif timetable_source == "teacher":
        source = session.get_teacher(timetable_source_id[1], timetable_source_id[0])
    elif timetable_source == "subject":
        pass
    elif timetable_source == "room":
        pass

    return {timetable_source: source}


from datetime import datetime


def get_schoolyear(school_year, date=datetime.now().date()):
    if not school_year:
        return None
    for time_range in school_year:
        if time_range.start.date() <= date <= time_range.end.date():
            return time_range

    return None
