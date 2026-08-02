# server-guardian

Server monitoring service with automatic Wake-on-LAN recovery.

## Installation

```sh
git clone https://github.com/MrBest2525/server-guardian && cd server-guardian && chmod +x install.sh && sudo ./install.sh
```

## Configuration

After installation, edit:

```text
/etc/server-guardian/config.yml
```

Then start the service:

```sh
sudo systemctl start server-guardian
```