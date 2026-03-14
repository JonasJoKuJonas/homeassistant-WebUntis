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
| `event.<name>_lesson_change`           | `event.<name>_stundenanderung`               |
| `event.<name>_new_homework`            | `event.<name>_neue_hausaufgabe`              |

> ⚠️ **Important:**  
> The **Exam Calendar** and **Homework Calendar** are **not available when using a parent account**.  
> Please use a **student account** to access exams and homework.

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
- `compact_tolerance_minutes` (degault: 0) - maximum break in minutes between lessons for compacting

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
