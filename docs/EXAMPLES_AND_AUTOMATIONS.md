# WebUntis Examples & Automations

This page contains **ready-to-use automation examples** and template snippets for the WebUntis Home Assistant integration.
Replace `<name>` with your actual WebUntis integration device name.

---

## Table of Contents

1. [Wake-Up Alarm (Dynamic Time)](#wake-up-alarm-dynamic-time)
2. [Wake-Up Alarm (Fixed Time)](#wake-up-alarm-fixed-time)
3. [List Lessons from Next Day](#list-lessons-from-next-day)
4. [Lesson Change Event Trigger](#lesson-change-event-trigger)
5. [New Homework Event Trigger](#new-homework-event-trigger)
6. [Add Homework to ToDo](#add-homework-to-todo)

---

## Wake-Up Alarm (Dynamic Time)

```yaml
sensor:
  - platform: template
    sensors:
      webuntis_wake_time:
        friendly_name: "WebUntis Wake-Up Time"
        value_template: >
          {% set datetime = states('sensor.<name>_next_lesson_to_wake_up') %}
          {% if datetime not in ["unknown", "unavailable", None] %}
            {{ as_datetime(datetime) - timedelta(hours=1, minutes=10) }}
          {% else %}
            {{ None }}
          {% endif %}
```

Trigger automation at wake-up time:

```yaml
trigger:
  platform: time
  entity_id: sensor.webuntis_wake_time
action:
  # Add your wake-up actions here, e.g., switch on lights, play alarm
```

---

## Wake-Up Alarm (Fixed Time)

```yaml
{% set datetime = states('sensor.<name>_next_lesson_to_wake_up') %}
{% if datetime not in ["unknown", "unavailable", None] %}
  {% set datetime = datetime | as_datetime | as_local %}
  {% set time = datetime.hour|string + ":" + datetime.minute|string %}
  {% if time == "8:0" %}
    {% set wake_up_time = "6:25" %}
  {% elif time == "9:14" %}
    {% set wake_up_time = "7:30" %}
  {% elif time == "10:45" %}
    {% set wake_up_time = "8:45" %}
  {% endif %}
  {{ datetime.replace(hour=wake_up_time.split(":")[0]|int, minute=wake_up_time.split(":")[1]|int) }}
{% else %}
  {{ None }}
{% endif %}
```

---

## List Lessons from Next Day

**Simple list:**

```yaml
{% set json = state_attr("sensor.<name>_next_lesson_to_wake_up", "day") | from_json %}
{% for lesson in json -%}
  {{ lesson.subjects.0.long_name + "\n" }}
{%- endfor %}
```

**Unique subjects list:**

```yaml
{% set lessonList = namespace(lesson=[]) %}
{% set lessons = state_attr("sensor.<name>_next_lesson_to_wake_up", "day") | from_json %}
{% for lesson in lessons -%}
  {% set lessonList.lesson = lessonList.lesson + [lesson.subjects.0.long_name] %}
{%- endfor %}
{{ lessonList.lesson | unique | join(', ') }}
```

---

## Lesson Change Event Trigger

```yaml
trigger:
  platform: state
  entity_id: event.<name>_lesson_change
```

Access event type:

```yaml
to_state:
  entity_id: event.<name>_lesson_change
  attributes:
    event_type: code
```

There can be different event_type's

- code
- rooms
- teachers
- cancelled
- subject
- info
- lstext

Available lesson chage Attributes

```yaml
to_state:
    entity_id: event.NAME_webuntis_lesson_change
    attributes:
      event_type: code
      old_lesson:
        start: '2025-02-12T07:45:00+01:00'
        end: '2025-02-12T09:15:00+01:00'
        subject_id: xxx
        id: xxx
        lsnumber: xxx
        code: irregular
        type: ls
        subjects:
          - name: M
             long_name: Mathe
        rooms:
          - name: R1
            long_name: Raum 1
        original_rooms: []
        teachers:
          - name: x
            long_name: xxx
      new_lesson:
        start: '2025-02-12T07:45:00+01:00'
        end: '2025-02-12T09:15:00+01:00'
        subject_id: None
        id: xxx
        lsnumber: xxx
        code: cancelled
        type: ls
        subjects: []
        rooms:
          - name: R1
            long_name: Room 1
        original_rooms: []
        teachers:
          - name: x
            long_name: xxx
```

---

## New Homework Event Trigger

```yaml
trigger:
  platform: state
  entity_id: event.<name>_new_homework
```

Available homework attributes:

```yaml
to_state:
  entity_id: event.<name>_new_homework
  attributes:
    event_type: homework
    homework_data:
      homework_id: ??? # Replace with homework ID
      subject: IT
      teacher: Jonas
      student_id: 42
      completed: false
      date_assigned: "2025-02-18"
      due_date: "2025-02-25"
      text: Fix all bugs in the WebUntis integration!
```

---

## Add Homework to ToDo

Automatically add new homework to a **ToDo integration**:

```yaml
alias: Add Homework to ToDo
description: ""
trigger:
  - platform: state
    entity_id:
      - event.<name>_webuntis_homework
condition: []
action:
  - service: todo.add_item
    target:
      entity_id: todo.hausaufgaben
    data:
      item: "{{ trigger.to_state.attributes.homework_data.subject }}"
      due_date: "{{ trigger.to_state.attributes.homework_data.due_date }}"
      description: "{{ trigger.to_state.attributes.homework_data.text }}"
mode: single
```

---

### Notes

- Replace all `<name>` placeholders with your actual WebUntis integration device name.
- Enable **Backend → generate JSON** in options to access attributes in templates.
- Combine these triggers with notifications, smart home actions, or scripts as needed.
