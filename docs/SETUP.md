# WebUntis Setup & Installation

This page provides instructions to install and configure the WebUntis integration for Home Assistant.

---

## Installation

### HACS Installation

1. Install [HACS](https://github.com/custom-components/hacs) if you haven't already.
2. Open HACS and install the **WebUntis Integration**.
3. Restart Home Assistant.
4. Add the integration via the [Home Assistant UI](https://my.home-assistant.io/redirect/integrations/) or click [here](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis).

### Manual Installation

1. Copy all files from `custom_components/webuntis/` to your Home Assistant config directory at `custom_components/webuntis/`.
2. Restart Home Assistant.
3. Add the integration via the [Home Assistant UI](https://my.home-assistant.io/redirect/integrations/) or click [here](https://my.home-assistant.io/redirect/config_flow_start/?domain=webuntis).

### Docker Users

If Home Assistant is running in Docker, make sure to set your local timezone.

**Option 1: Mount `/etc/localtime`**

```yaml
volumes:
  - /etc/localtime:/etc/localtime:ro
```

**Option 2: Environment variable**
TZ=Europe/Berlin

## Configuration via UI
Just follow the config flow. The integration uses the untis school search to search your school details based on a search term. You only need your username and your password.

---

### Username and Password

Unfortunately, it is not possible to use the Untis API with an anonymous user.

You can ask the school administration to give you access, otherwise it won't work.


---

### iServ or Office365 Login

Since v3.1.0 it is possible to login with iServ or Office365. You can select the QRCode login option in the config flow. You can find the QRCode/ credentials in the WebUntis webapp under **Your Name > Data access**.

---


### Timetable Source

Select from witch source the intigration should pull the data.

If the student or teacher is not found try

first name: `first name` `middle name` <br>
last name: `last name`

(This could vary from school to school)
