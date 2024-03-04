# WebUntis

### Custom component to access data from Web Untis in Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
![Version](https://img.shields.io/github/v/release/JonasJoKuJonas/homeassistant-WebUntis)
[![Downloads](https://img.shields.io/github/downloads/JonasJoKuJonas/homeassistant-WebUntis/total)](https://tooomm.github.io/github-release-stats/?username=JonasJoKuJonas&repository=HomeAssistant-WebUntis)



[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JonasJoKuJonas&repository=Homeassistant-WebUntis)



[![Discord Banner 4](https://discordapp.com/api/guilds/1090218586565509170/widget.png?style=banner4)](https://discord.gg/34EHnHQaPm)




## Installation

### HACS

1. Install [HACS](https://github.com/custom-components/hacs).
2. Install Integration.
3. Restart Home Assistant
4. Add Integration via [UI](https://my.home-assistant.io/redirect/integrations/) or click [HERE](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis)

### Manual installation 

1. Copy all files from custom_components/webuntis/ to custom_components/webuntis/ inside your config Home Assistant directory.
2. Restart Home Assistant
4. Add Integration via [UI](https://my.home-assistant.io/redirect/integrations/) or click [HERE](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis)

### Docker
If your home assistant is running on a docker, you may need to set your local timezone in the docker configuration!

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

You can ask the school administration to give you access, otherwise it won't work.

### Timetable Timetable source & Full name/ Class/ Subject/ Room
With the timetable source, you can select where the data for the sensor should come from.
The final configuration field allows you to specify a name or class from which the data is pulled.
The Format for the student's full name must be in the form <"first name"> <"middle name">, <"last name">. (This could variate from school to school)

## Optional Configurations

### Filter
|Option|Description
|:-----|:----------
|filter_mode|The mode of the filter. e.g. `Blacklist`
|filter_subjects|Subjects that will be excludet from any data.
|filter_description|Exclude all lessons with specific text in the lesson info

### Calendar
|Option|Description|Default
|:-----|:----------|-------
|calendar_long_name|Use the long subject name.|`True`
|calendar_show_cancelled_lessons|Show cancelled lessons.|`False`
|calendar_description|Pick what will be shown in events description.|`JSON`

### Notify
|Option|Description|Default
|:-----|:----------|-------
|notify_entity_id|Home assistant notification service to send lesson changes via, e.g. notify.telegram.|`None`
|notify_target|An object with additional notification service targets|`None`
|notify_data|An object with additional notification service data|`None`
|notify_options|Option that will trigger a notification|`None`

### Backend
|Option|Description|Default
|:-----|:----------|-------
|keep_loged_in|Keep the client logged in. (Beta)|`False`
|generate_json|Generate JSON in sensor attributes.|`False`
|exclude_data|Will be set automatic if user doesn't have rights to prevent logger from spamming errors.|`None`
|extended_timetable|Request extended timetable. Is needed for `filter_description` and `calendar_description(Lesson Info)`|`False`

### Test
Test the notification Configuration


## Entities

The integration creates multiple entities in the format `sensor.NAME_entity`.

|Sensor  |Type|Description
|:-----------|:---|:------------
|`binary_sensor.NAME_class`| bool | indicates if a lesson is currently taking place.
|`sensor.NAME_next_class`| datetime | the start time of the next lesson.
|`sensor.NAME_next_lesson_to_wake_up`| datetime | the start of the next first lesson of the day.
|`calendar.NAME_webuntis_calender`| calendar | Calendar entry

## Template
Before you can use templates you need to enable the option generate JSON in the options flow. (Backend - generate JSON)

Now you can copy this examples and don't forget to change the sensor names and start times. (Replace NAME with your name, and time without leading zero)
### WebUntis Alarm Clock Automation
Create a template -> sensor configuration in your configuration.yaml:
```
- template:
  - sensor:
    - name: Webunits Weck Zeit
        unique_id: "webuntis_wake_up_time"
        icon: mdi:alarm
        device_class: timestamp
        state: >
          {% set datetime = states('sensor.NAME_next_lesson_to_wake_up') %}
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
This will creat a Sensor that represents the wake up time 

Now you can use following trigger in you automation:
```
platform: template
value_template: >-
  {{ 0 < as_timestamp(now()) -
     as_timestamp(states("sensor.webuntis_wake_up_time")|
     as_datetime | as_local) < 60 }}
```
The automation will be triggered according to the time you defined in the sensor template
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
for more examples feel free to check in #code-sharing on [Discord](https://discord.com/channels/1090218586565509170/1208159703520120902)


[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/Jonas_JoKu)
