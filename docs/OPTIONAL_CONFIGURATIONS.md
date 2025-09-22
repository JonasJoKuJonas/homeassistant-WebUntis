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

| Option                          | Description                           | Default          |
| :------------------------------ | :------------------------------------ | :--------------- |
| calendar_show_cancelled_lessons | Show cancelled lessons in calendar.   | `False`          |
| calendar_description            | Display format for event description. | `JSON`           |
| calendar_room                   | Specify location display.             | `Room long name` |
| calendar_show_room_change       | Show room changes in calendar.        | `False`          |
| calendar_replace_name           | Replace words in event name.          | `None`           |

### Lesson Options

Control how the lesson name is displayed.

| Option              | Description                                    | Default |
| :------------------ | :--------------------------------------------- | :------ |
| lesson_long_name    | Show the full lesson name.                     | `True`  |
| lesson_replace_name | Replace lesson names based on mapping.         | `None`  |
| lesson_add_teacher  | Show the teacher's name for selected subjects. | `None`  |

### Notification Options

Configure how lesson change notifications are sent.

| Option           | Description                                                   | Default         |
| :--------------- | :------------------------------------------------------------ | :-------------- |
| name             | Name of the Notify device.                                    | `entity_id`     |
| notify_entity_id | Home Assistant notification service, e.g., `notify.telegram`. | `None`          |
| target           | Additional targets for the notification.                      | `None`          |
| data             | Additional data for the notification service.                 | `None`          |
| template         | Notification template to use.                                 | `message_title` |
| options          | Options that trigger the notification.                        | `None`          |

### Backend Options

Control backend behavior and data generation.

| Option         | Description                                                 | Default |
| :------------- | :---------------------------------------------------------- | :------ |
| keep_logged_in | Keep the client logged in (Beta).                           | `False` |
| generate_json  | Generate JSON in sensor attributes for templates.           | `False` |
| exclude_data   | Automatically exclude data if the user lacks access rights. | `None`  |
