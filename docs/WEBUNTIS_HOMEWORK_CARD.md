# WebUntis Homework Card

A custom Lovelace card that renders the `homeworks` attribute of the
[`sensor.<name>_homework_list`](ENTITIES_AND_SERVICES.md#sensorname_homework_list) entity as a grouped
list, just like the "Hausaufgaben" page on webuntis.com — split into **Bald fällig** (due soon),
**Noch nicht abgeschlossen** (open) and **Verpasst** (overdue), each with its own color, plus a print
button.

> Requires a **student account**. Homework data is not available for parent or teacher accounts
> (see [ENTITIES_AND_SERVICES.md](ENTITIES_AND_SERVICES.md)).

## Installation

1. Copy [`www/webuntis-homework-card.js`](../www/webuntis-homework-card.js) from this repository into
   your Home Assistant `<config>/www/` folder (create the folder if it doesn't exist yet).
2. In Home Assistant, go to **Settings → Dashboards → ⋮ (top right) → Resources → Add Resource**.
   - URL: `/local/webuntis-homework-card.js`
   - Resource type: `JavaScript Module`
3. Add the card to a dashboard (via the card picker "WebUntis Homework Card", or as YAML):

```yaml
type: custom:webuntis-homework-card
entity: sensor.<name>_homework_list
title: Hausaufgaben # optional, defaults to "Hausaufgaben" / "Homework"
show_completed: false # optional, shows a 4th "Erledigt" group when true
due_soon_days: 3 # optional, how many days ahead counts as "due soon"
```

## Features

- Groups homework the same way as WebUntis, color-coded (orange = due soon, red = overdue, green =
  completed when `show_completed: true`).
- Columns: subject, teacher, assigned date, due date, homework text — dates are shown with weekday
  names (e.g. "Donnerstag, 17.09.2026").
- **Print button** (top right of the card) opens the browser's print dialog with a clean, printer-friendly
  version of the list (no dashboard chrome, no dark background).
- Automatically follows your Home Assistant language for date formatting and default labels
  (German/English built in; override any label via the optional `labels:` config key).

## Screenshot reference

The card intentionally mirrors the layout of the WebUntis web UI's homework list
(`Fächer | Lehrkräfte | Aufgabedatum | Fälligkeitsdatum`, grouped into "Bald fällig" /
"Noch nicht abgeschlossen" / "Verpasst") so it feels familiar if you already use webuntis.com.
