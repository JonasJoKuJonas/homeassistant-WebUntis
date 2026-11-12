## Optional Configurations

### Filter Options

Control which lessons or subjects are included or excluded.

| Option             | Description                                              | Example/Default  |
| :----------------- | :------------------------------------------------------- | :--------------- |
| filter_mode        | Filter mode, e.g., `Blacklist` or `Whitelist`.           | `Blacklist`      |
| filter_subjects    | Subjects to exclude from any data.                       | `["Math", "PE"]` |
| filter_description | Exclude lessons containing specific text in description. | `"Online"`       |
| invalid_subjects   | Allow lessons without subjects.                          | `False`          |

### Calendar Options

Customize what is shown in calendar entities.

| Option                          | Description                                  | Default          |
| :------------------------------ | :------------------------------------------- | :--------------- |
| calendar_show_cancelled_lessons | Show cancelled lessons in calendar.          | `False`          |
| calendar_description            | Display format for event description.        | `JSON`           |
| calendar_room                   | Specify location display.                    | `Room long name` |
| calendar_show_room_change       | Show room changes in calendar.               | `False`          |
| calendar_replace_name           | Replace words in event name.                 | `None`           |


### Lesson Options

Control how the lesson name is displayed.

| Option                        | Description                                    | Default |
| :---------------------------- | :--------------------------------------------- | :------ |
| lesson_long_name              | Show the full lesson name.                     | `True`  |
| lesson_replace_name           | Replace lesson names based on mapping.         | `None`  |
| lesson_add_teacher            | Show the teacher's name for selected subjects. | `None`  |
| lesson_compacting_tolerance   | Break (in minutes) between lessons for merge.  |  `0`    |
| lesson_compacting_parallel    | Compact parallel lessons that overlap or share the same time. | `False` |

### Notification Options

Configure how lesson change notifications are sent. Besides lesson changes, the options include new
homework (`homework`) and new WebUntis messages (`message`, requires the messages option below).

| Option           | Description                                                   | Default         |
| :--------------- | :------------------------------------------------------------ | :-------------- |
| name             | Name of the Notify device.                                    | `entity_id`     |
| notify_entity_id | Home Assistant notification service, e.g., `notify.telegram`. | `None`          |
| target           | Additional targets for the notification.                      | `None`          |
| data             | Additional data for the notification service.                 | `None`          |
| template         | Notification template to use.                                 | `message_title` |
| options          | Options that trigger the notification.                        | `None`          |

### Live Timetable Options

Show your current lessons as Live Activities directly on your Lock Screen.

| Option        | Description                                                   | Default.    |
| :------------ | :------------------------------------------------------------ | :---------- |
| name          | Name of the Notify device.                                    | `entity_id` |
| platform      | Device platform for this target.                              | `None`      |
| entity_id     | Mobile App notify service, e.g., `notify.iphone_von_max`.     | `None`      |
| start_offset  | Minutes before the first lesson to start the live activity.   | `10`        |
| end_offset    | Minutes after the last lesson to stop the live activity.      | `10`        |

### Messages Options

WebUntis messages ("Mitteilungen"). All options are off by default (opt-in): open the integration's
options, choose **Messages** and enable **Load messages**.

| Option                     | Description                                                                                                                                               | Default |
| :------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| messages                   | Adds `sensor.<name>_messages` and `event.<name>_new_message` and enables the `message` notification option. Messages are not marked as read.             | `False` |
| message_attachments        | Adds download links for attachments to the messages (`attachments`). Links contain a token valid for 7 days. Only has an effect when `messages` is enabled. | `False` |
| message_attachments_unread | Also opens unread messages to load their attachments. **This may mark them as read in WebUntis.**                                                         | `False` |

### Backend Options

Control backend behavior and data generation.

| Option         | Description                                                 | Default |
| :------------- | :---------------------------------------------------------- | :------ |
| keep_logged_in | Keep the client logged in (Beta).                           | `False` |
| generate_json  | Generate JSON in sensor attributes for templates.           | `False` |
| exclude_data   | Automatically exclude data if the user lacks access rights. | `None`  |
