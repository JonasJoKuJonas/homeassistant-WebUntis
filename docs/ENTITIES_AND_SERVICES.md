# WebUntis Entities & Services

This page lists all available entities and services for the WebUntis Home Assistant integration.  
Replace `<name>` with your actual WebUntis integration device name.

---

## Entities

| Entity ID (English)                    | Entity ID (German)                           |
| -------------------------------------- | -------------------------------------------- |
| `sensor.<name>_next_lesson`            | `sensor.<name>_nachste_stunde`               |
| `sensor.<name>_next_lesson_to_wake_up` | `sensor.<name>_nachste_stunde_zum_aufstehen` |
| `sensor.<name>_today_school_start`     | `sensor.<name>_heutiger_schulbeginn`         |
| `sensor.<name>_today_school_end`       | `sensor.<name>_heutiges_schulende`           |
| `calendar.<name>`                      | `calendar.<name>`                            |
| `calendar.<name>_exams`                | `calendar.<name>_prufungen`                  |
| `calendar.<name>_homework`             | `calendar.<name>_hausaufgaben`               |
| `sensor.<name>_homework_list`          | `sensor.<name>_hausaufgabenliste`            |
| `event.<name>_lesson_change`           | `event.<name>_stundenanderung`               |
| `event.<name>_new_homework`            | `event.<name>_neue_hausaufgabe`              |
| `sensor.<name>_messages`               | `sensor.<name>_mitteilungen`                 |
| `event.<name>_new_message`             | `event.<name>_neue_mitteilung`               |

> ⚠️ **Important:**  
> The **Exam Calendar**, **Homework Calendar** and **Homework List sensor** are **not available when using a parent account**.  
> Please use a **student account** to access exams and homework.

### `sensor.<name>_homework_list`

State: number of open (not completed) homework entries.

Attribute `homeworks` contains the full homework list as a list of objects, grouped the same way as the
"Hausaufgaben" page on webuntis.com:

```yaml
homeworks:
  - homework_id: 12345
    subject: IT
    teacher: Jonas
    student_id: 42
    completed: false
    date_assigned: "2025-02-18"
    due_date: "2025-02-25"
    text: Fix all bugs in the WebUntis integration!
    group: due_soon # one of: due_soon, open, overdue, completed
```

`group` is due within 3 days ("due_soon"), further in the future ("open"), in the past and not completed
("overdue"), or already marked complete ("completed").

See [WebUntis Homework Card](WEBUNTIS_HOMEWORK_CARD.md) for a ready-made dashboard card that renders this
list exactly like the WebUntis "Hausaufgaben" page, including a print button.

### `sensor.<name>_messages`

State: number of unread WebUntis messages ("Mitteilungen").

Messages are opt-in: enable them in the integration options under **Messages** (see
[Optional Configurations](OPTIONAL_CONFIGURATIONS.md#messages-options)).

Attribute `messages` contains the 10 most recent messages, newest first. The text is the preview WebUntis
shows in the message list (shortened to 1000 characters). The integration never opens a message, so
reading messages in Home Assistant does not mark them as read in WebUntis.

```yaml
messages:
  - id: 12345
    subject: Elternabend
    sender: Jonas
    sent: "2025-02-18T13:57:00+01:00"
    read: false
    has_attachments: true
    requires_confirmation: false # true if WebUntis asks for a read confirmation
    text: Liebe Eltern, ...
```

The sensor is unavailable for accounts that cannot access messages. New messages also trigger
`event.<name>_new_message` and the `message` notification option.

---

## Services

The integration provides several services to directly fetch data from WebUntis.

---

### 🔹 `webuntis.get_timetable`

Fetches the timetable for a given date range.  
The result includes all lessons within the range, depending on your filter settings.

**Fields:**

- `device_id` (**required**) – The device/instance of the WebUntis integration.
- `start` (**required**) – Start date (`YYYY-MM-DD`).
- `end` (**required**) – End date (`YYYY-MM-DD`).
- `apply_filter` (default: `true`) – Apply filters defined in the integration (e.g., subject or teacher filters).
- `show_cancelled` (default: `true`) – Include cancelled lessons.
- `compact_result` (default: `true`) – Return a compact result format.
- `compact_tolerance_minutes` (default: `0`) - Maximum break in minutes between lessons when compacting. Only applied when `compact_result` is `true`.

---

### 🔹 `webuntis.count_lessons`

Counts the number of lessons in a given date range.

**Fields:**

- `device_id` (**required**) – The device/instance of the WebUntis integration.
- `start` (**required**) – Start date (`YYYY-MM-DD`).
- `end` (**required**) – End date (`YYYY-MM-DD`).
- `apply_filter` (default: `true`) – Apply filters defined in the integration.
- `count_cancelled` (default: `false`) – Count cancelled lessons as well.

---

### 🔹 `webuntis.get_schoolyears`

Fetches all available school years from WebUntis.

**Fields:**

- `device_id` (**required**) – The device/instance of the WebUntis integration.
