## About

#### Bot for parsing news, translating into Portuguese and publishing in a Telegram channel and on Facebook page
- [t.me/sportportugal](https://t.me/sportportugal)
- [facebook.com/desportportugal](https://www.facebook.com/desportportugal)

## Troubleshooting

### One session files are accessed by two different IP addresses
```commandline
telethon.errors.rpcerrorlist.AuthKeyDuplicatedError: The authorization key (session file) was used under two different IP addresses 
simultaneously, and can no longer be used. Use the same session exclusively, or use different sessions 
(caused by InvokeWithLayerRequest(InitConnectionRequest(GetConfigRequest)))
```
1. Remove session files `*.session`
2. Launch the bot 
3. Enter phone, code from telegram and password

### Facebook token is outdated or damaged
```commandline
Graph returned an error: (#200) This endpoint is deprecated since the required permission publish_actions is deprecated
```

1. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select App from the top right dropdown menu
3. Select item in "Page Access Token" section from dropdown, not User Token (pages_read_engagement,	pages_manage_posts) 
4. Select needed permissions (38 items)
5. Tap on "Generate Access Token" and generated new token
6. Copy access token
7. Open [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
8. Paste copied token and press "Debug"
9. Press "Extend Access Token" and copy the generated long-lived user access token
Use copied token

## Redis Configuration

### Local Development
1. Install Redis:
```bash
sudo apt-get install redis-server  # For Ubuntu
brew install redis                 # For MacOS
```

2. Start Redis server:
```bash
redis-server
```

3. Set environment variables:
```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
```

### CI/CD Environment
Redis persistence is automatically configured in GitHub Actions using service containers and caching.
