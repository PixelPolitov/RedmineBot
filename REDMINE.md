# redmine-bot

Interact with your task tracker via Telegram.

## Introduction

### Features

- Get in Telegram messages when issue is created or updated in Redmine
- Answer to Redmine issues by the replying to message in Telegram chat
- Create new issues in your Redmine using Telegram. Select a project and priority you need for a new issue
- Operate with files and media
- Compatible with Redmine 4.2 and 5.0
- The authorization process operates through a custom field in Redmine, where the user's Telegram login is specified. Upon initial login acquisition, a request is initiated to retrieve the user's API key from the Redmine database, thereby restricting access only to the necessary projects and tasks for the user. The storage and retrieval of information concerning the login and API key are implemented in Redis.


## Quickstart

### Install

#### Docker-compose

Do the following steps:
- Clone this git-repo
- Configure redmine-bot (see [Configure](#configure) section for details)
- Launch the Bot with command:
  ```
  docker-compose up -d
  ``` 

### Settings

Default configuration file path: `/config.ini`.

#### General settings

- Redis settings
- MySQL settings
- Redmine settings

##### Redis settings

| Option     | Type   | Required | Default value | Description         |
|---         | :---:  | :---:    | :---:         |---                  |
| `expire_time_seconds` | Int | Yes      | 86400             |  Time to store user data    |


##### MySQL settings

| Option     | Type   | Required | Default value | Description         |
|---         | :---:  | :---:    | :---:         |---                  |
| `host`     | String | Yes      | -             | Host to connect     |
| `user`     | String | Yes      | -             | User to connect     |
| `password` | String | Yes      | -             | Password to connect |
| `database` | String | Yes      | -             | DB name to connect  |

##### Redmine settings

| Option     | Type   | Required | Default value | Description         |
|---         | :---:  | :---:    | :---:         |---                  |
| `url`      | String | Yes      | -             | Url to your Redmine     |
| `custom_id`     | Int | Yes      | -             | Id from your custom field created in Redmine    |

### Configure

To complete the Bot installation you need to do some actions described in this section. 

#### Redmine

After you've installed and configured the Redmine, do the following to take the redmine-bot collaboration.

##### General

Check the option `Enable REST web service` on `/settings?tab=api` page in your Redmine is enabled.

Then create a new one (or take an existing) account with administrator permissions. In the account settings page look for an `API access key` and use this value as a `REDMINE_ADMIN_API_KEY` option in **start.sh(bat)**.

Then create a new custom filed for telegram username `/redmine/custom_fields?tab=UserCustomField`

#### nxs-chat-redmine plugin

I modified the nxs-chat-redmine plugin a little and you should install my modified plugin, but read how to configure [nxs-chat-redmine](https://github.com/nixys/nxs-chat-redmine) plugin in your Redmine.

#### redmine-bot

Now you need to set up redmine-bot config file (see options description in [settings section](#settings)). To configure the Bot you need to change the file start.sh(bat) on yours env vars:
- `BOT_TOKEN` - token from your telegram bot
- `REDMINE_ADMIN_API_KEY` - admin api key from redmine
- `SECRET_TOKEN` - secret token for webhook server
- `REDIS_PASS` - redis password

## Inspired by this article
https://habr.com/ru/companies/nixys/articles/347526/

p.s. please don't be too harsh in your judgment, this is just my pet project and I'm not a developer.