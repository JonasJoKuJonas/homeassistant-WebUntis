# WebUntis
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
![Version](https://img.shields.io/github/v/release/JonasJoKuJonas/homeassistant-WebUntis)
![Downloads](https://img.shields.io/github/downloads/JonasJoKuJonas/homeassistant-WebUntis/total)

Custom component to access data from Web Untis in Home Assistant

## Installation

### HACS

This component is easiest installed using [HACS](https://github.com/custom-components/hacs).

### Manual installation

Copy all files from custom_components/webuntis/ to custom_components/webuntis/ inside your config Home Assistant directory.


## Configuration via UI

### Server & School
Visit https://webuntis.com and click on your school.

In the URL you should find the information you need:
```
https://demo.webuntis.com/WebUntis/?school=Demo-School#/basic/login
        ^^^^^^^^^^^^^^^^^                  ^^^^^^^^^^^
              Server                          School
```

### Username and Password
Unfortunately, it is not possible to use the Untis API with an anonymous user.

You can ask the school administration to give you an access, otherwise it won't work.

### Timetable Timetable source & Full name/ Class/ Subject/ Room
With the timetable source, you can select where the data for the sensor should come from.
The final configuration field allows you to specify a name or class from which the data is pulled.

### Docker
If your home assistant is running on a docker, you may need to set your local timezone in the docker configuration!

## Entities

The integration creates multiple entities in the format `sensor.NAME_entity`.

|Sensor  |Type|Description
|:-----------|:---|:------------
|`binary_sensor.NAME_class`| bool | indicates if a lesson is currently taking place.
|`sensor.NAME_next_class`| datetime | the start time of the next lesson.
|`sensor.NAME_next_lesson_to_wake_up`| datetime | the start of the next first lesson of the day.
|`calendar.NAME_webuntis_calender`| calendar | Calendar entry

## Template

### List lessons from next day
```
{% set json = state_attr("sensor.NAME_next_lesson_to_wake_up", "day") | from_json %}

{% for lesson in json -%}
  {{ lesson.subjects.0.long_name + "\n" }}
{%- endfor %}
```

```
{% set lessonList = namespace(lesson=[]) %}
{% set lessons = state_attr("sensor.NAME_next_lesson_to_wake_up", "day") | from_json %}

{% for lesson in lessons -%}
  {% set lessonList.lesson = lessonList.lesson + [lesson.subjects.0.long_name] %}
{%- endfor %}
{{ lessonList.lesson | unique | join(', ') }}
```
