<p align="center">
<img width="150" height="150" src="https://i.imgur.com/Lkqobis.png">
</p>

<p align="center">
<b>A moderation-heavy general purpose Discord bot.</b>
</p>

<p align="center">
<a href="https://discord.gg/snackbox"><img src="https://img.shields.io/discord/974468300304171038?label=Discord&logo=discord"></a> <a href="https://github.com/snaacky/chiya/actions"><img src="https://github.com/snaacky/chiya/workflows/Docker/badge.svg?branch=master"></a>
</p>

## Getting started

Chiya is deployed into a production environment using [Docker](https://docs.docker.com/engine/reference/run/) images. As such, the install guide will focus on deployment via Docker. Chiya has been tested on both Windows and Linux bare metal environments and attempts to retain compatibility across both operating systems but this may not always be the case. The install guide assumes that you already have Docker and [docker-compose](https://docs.docker.com/compose/) installed.

You will also need a Discord bot with [privileged intents](https://discordpy.readthedocs.io/en/stable/intents.html) enabled and the token for that bot before installation. You can create a new Discord bot [here](https://discord.com/developers/). Keep in mind Chiya will need the `bot` and `applications.commands` scopes selected when you generate your OAuth2 URL to function properly. If you intend on using the Reddit functionality, you will also need to create a Reddit application [here](https://www.reddit.com/prefs/apps/).

## Install

**Step 1:** Clone the repository.

**Step 2:** Copy `config.default.yml` to `config.yml`, fill up the uncommented lines.

**Step 3:** Create a folder called `config` inside the repository, drop `config.yml` there.

**Step 4:** Run `docker compose up --build -d` on the root directory of the repository, and your bot should be up and running now.

## Contributing

Contributors are more than welcome to help make Chiya a better bot. Please follow these steps to get your work merged in:

1. Reach out on Discord and propose your idea beforehand.
2. Clone the repository `git clone` and create a new branch `git checkout -b branch_name` for your work.
3. Add a feature, fix a bug, or refactor some code.
4. Open a Pull Request with a comprehensive list of changes.

## Built on

Chiya relies predominantly on the following projects:

- [Python](https://www.python.org/)
- [MariaDB](https://mariadb.org/)
- [Docker](https://www.docker.com/)
- [pycord](https://github.com/Pycord-Development/pycord)
- [dataset](https://github.com/pudo/dataset)
- [asyncpraw](https://github.com/praw-dev/asyncpraw)
