# WebUntis

### Custom component to access data from Web Untis in Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
![Version](https://img.shields.io/github/v/release/JonasJoKuJonas/homeassistant-WebUntis)
[![Downloads](https://img.shields.io/github/downloads/JonasJoKuJonas/homeassistant-WebUntis/total)](https://tooomm.github.io/github-release-stats/?username=JonasJoKuJonas&repository=HomeAssistant-WebUntis)



[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JonasJoKuJonas&repository=Homeassistant-WebUntis)



[![Discord Banner 4](https://discordapp.com/api/guilds/1090218586565509170/widget.png?style=banner4)](https://discord.gg/34EHnHQaPm)


### Help Translate with Crowdin

We're using Crowdin to make translating our project easier for everyone. If you're fluent in another language and want to help, you can get started on Crowdin right away. Your contributions are welcome in any language! If you need help or want to add a new language, please let us know through a pull request or on Discord. 

Help us:

<a href="https://crowdin.com/project/homeassistant-webuntis" rel="nofollow"><img style="width:140;height:40px" src="https://badges.crowdin.net/badge/light/crowdin-on-dark.png" srcset="https://badges.crowdin.net/badge/light/crowdin-on-dark.png 1x,https://badges.crowdin.net/badge/light/crowdin-on-dark@2x.png 2x" alt="Crowdin | Agile localization for tech companies" /></a>

## Installation

### HACS

1. Install [HACS](https://github.com/custom-components/hacs).
2. Go to HACS and install the WebUntis Integration.
3. Restart Home Assistant.
4. Add the Integration via [UI](https://my.home-assistant.io/redirect/integrations/) or click [HERE](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis).

### Manual Installation 

1. Copy all files from `custom_components/webuntis/` to `custom_components/webuntis/` inside your Home Assistant config directory.
2. Restart Home Assistant.
3. Add the Integration via [UI](https://my.home-assistant.io/redirect/integrations/) or click [HERE](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis).

   
### Docker
If your Home Assistant is running in Docker, you may need to set your local timezone in the Docker configuration!

Example:

Add to compose
```
volumes:
 - /etc/localtime:/etc/localtime:ro
```
Or add environment variable

```TZ=Europe/Berlin```

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

### Timetable Source
Select from witch source the intigration should pull the data.

If the student or Teacher is not found try

first name: `first name` `middle name` <br>
last name: `last name`

(This could vary from school to school)

## Optional Configurations

### Filter
| Option | Description |
|:------|:------------|
| filter_mode | The mode of the filter, e.g., `Blacklist`. |
| filter_subjects | Subjects excluded from any data. |
| filter_description | Exclude all lessons with specific text in the lesson info. |
| invalid_subjects | Allow lessons with no subjects |

### Calendar
| Option | Description | Default |
|:------|:------------|-------|
| calendar_show_cancelled_lessons | Show cancelled lessons. | `False` |
| calendar_description | Pick what to show in event descriptions. | `JSON` |
| calendar_room | Specify what to display for location. | `Room long name` |
| calendar_show_room_change | Show room changes in the calendar. | `False` |
| calendar_replace_name | Replace words in event Name | `None` |


### Lesson
| Option | Description | Default |
|:------|:------------|-------|
| lesson_long_name | Show long lesson name | `True` |
| lesson_replace_name | Replace Lesson name | `None` |
| lesson_add_teacher | Select which subjects should be displayed with the teacher's name. | `None` |


### Notification Configuration
| Option | Description | Default |
|:------|:------------|-------|
| name | The Notify Name | entity_id |
| notify_entity_id | Home Assistant notification service to send lesson changes via, e.g., notify.telegram. | `None` |
| target | Object with additional notification service targets. | `None` |
| data | Object with additional notification service data. | `None` |
| template | Notify Template that is used for notification | `message_title` |
| options | Options that will trigger a notification. | `None` |

### Backend
|Option|Description|Default
|:-----|:----------|-------|
| keep_logged_in | Keep the client logged in. (Beta) | `False` |
| generate_json | Generate JSON in sensor attributes. | `False` |
| exclude_data | Set automatically if the user doesn't have rights, to prevent error spamming. | `None` |
| extended_timetable | Request extended timetable, needed for `filter_description` and `calendar_description (Lesson Info)`. | `False` |

## Entities

The integration creates several entities in the format `sensor.NAME_entity`.

| Sensor | Type | Description |
|:-------|:-----|:------------|
| `binary_sensor.NAME_class` | bool | Indicates if a lesson is currently taking place. |
| `sensor.NAME_next_class` | datetime | The start time of the next lesson. |
| `sensor.NAME_next_lesson_to_wake_up` | datetime | The start of the next first lesson of the day. |
| `sensor.NAME_today_school_start` | datetime | The start time of todays fist lesson. Can also have todays lessons as JSON. |
| `sensor.NAME_today_school_end` | datetime | The end time of todays last lesson. |
| `calendar.NAME_webuntis_calendar` | calendar | Calendar entry. |
| `calendar.NAME_webuntis_exam_calendar` | calendar | Calendar with current exams. |
| `calendar.NAME_webuntis_homework_calendar` | calendar | Calendar with current homework. |
| `event.NAME_webuntis_lesson_change` | event | Lesson change events. |
| `event.NAME_webuntis_homework` | event | Homework events. |


### Event Entity

The event entity allows you to trigger an automation on a timetable change.
The automation can then send your own type of notification, make a announcement on a smart speaker, add homework to a todo list or other cool stuff.

Trigger automation:
```
trigger: state
entity_id: event.NAME_webuntis_lesson_change
```

There can be different event_type's
- code
- rooms
- teachers
- cancelled
- lesson_change

Example automation variables
```
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

Trigger automation:
```
trigger: state
entity_id: event.NAME_webuntis_homework
```


Example automation variables
```
to_state:
    entity_id: event.NAME_webuntis_homework
    attributes:
      event_type: homework
      homework_data:
        homework_id: ???
        subject: IT
        teacher: Jonas
        student_id: 42
        completed: false
        date_assigned: '2025-02-18'
        due_date: '2025-02-25'
        text: Fix all bugs in the WebUntis integration!
      
```

## Templates
Before you can use templates, you need to enable the option to generate JSON in the options flow (Backend - generate JSON).


Now you can copy this examples and don't forget to change the sensor names and start times. (Replace NAME with your name, and time without leading zero)
### WebUntis Alarm Clock Automation
Create a [template helper](https://my.home-assistant.io/redirect/config_flow_start?domain=template) -> sensor <br>
Edit the template to your needs:

Dynamic Time:
```
{% set datetime = states('sensor.NAME_next_lesson_to_wake_up') %}
{% if datetime not in ["unknown", "unavailable", None] %}
  {{ as_datetime(datetime) - timedelta(hours=1, minutes=10) }}
{% else %}
  {{ None }}
{% endif %} 
```

Fixed Time:
```
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
This creates a sensor that represents the wake-up time.

Now, you can use the following trigger in your automation:
```
platform: time
at: sensor.webuntis_weck_zeit
```
The automation will be triggered according to the time you defined in the sensor template
### List Lessons from the Next Day
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


## Support me ♥️
I'm a 18-year-old software developer from Germany. I love to develop software in my free time. If you like my projects consider donating a small amount to support my work. 

<a href="https://www.buymeacoffee.com/Jonas_JoKu" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174" ></a>

<a href="https://www.paypal.com/donate/?hosted_button_id=29CAZV3ZHWDMW">
  <img src="https://raw.githubusercontent.com/andreostrovsky/donate-with-paypal/925c5a9e397363c6f7a477973fdeed485df5fdd9/blue.svg" alt="Donate with PayPal" height="40"/>
</a>


<p align="right"><a href="#top"><img src="https://cdn-icons-png.flaticon.com/512/892/892692.png" height="50px"></a></p>
