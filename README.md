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
3. Select "Get User Access Token" from dropdown (right of access token field) 
4. Select needed permissions (38 items)
5. Copy user access token
6. Open [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)
7. Paste copied token and press "Debug"
8. Press "Extend Access Token" and copy the generated long-lived user access token
9. Open [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
10. Paste copied token into the "Access Token" field
11. Make a GET request with "PAGE_ID?fields=access_token"
12. Find the permanent page access token in the response (node "access_token")
