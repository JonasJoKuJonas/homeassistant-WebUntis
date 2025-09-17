def get_timetable_object(timetable_source_id, timetable_source, session):
    """return the object to request the timetable"""

    source = None

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


def get_lesson_name(server, lesson):

    def get_attr(obj, attr, default=None):
        """Versucht obj.attr oder obj[attr] zu holen"""
        if hasattr(obj, attr):
            return getattr(obj, attr, default)
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return default

    try:
        subjects = get_attr(lesson, "subjects", [])
        first_subject = subjects[0] if subjects else None
        if first_subject:
            if server.lesson_long_name:
                subject = get_attr(first_subject, "long_name", None)
            else:
                subject = get_attr(first_subject, "name", None)
        else:
            subject = None
    except IndexError:
        subject = None

    if not subject:
        subject = get_attr(lesson, "lstext", get_attr(lesson, "substText", "Noneasd"))

    name = server.lesson_replace_name.get(subject, subject)

    if subject in server.lesson_add_teacher:

        teachers = get_attr(lesson, "teachers", [])
        if teachers:
            teacher = get_attr(teachers[0], "name", None)

            name += f" - {teacher}"

    return name


def get_lesson_name_str(server, subject, teacher):

    name = server.lesson_replace_name.get(subject, subject)

    if subject in server.lesson_add_teacher:
        name += f" - {teacher}"

    return name
