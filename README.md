## About

#### Bot for parsing news, translating into Portuguese and publishing in a Telegram channel and on Facebook page
- [t.me/sportportugal](https://t.me/sportportugal)
- [facebook.com/desportportugal](https://www.facebook.com/desportportugal)


## Steps to Run the Project

1. Create a virtual environment:

   `python -m venv venv`

2.	Activate the virtual environment:

    On macOS/Linux: `source venv/bin/activate`

    On Windows: `venv\Scripts\activate`

3.	Install dependencies:

    `pip install -r requirements.txt`

4.	Create a file named secret and add your credentials to it.
5.	Run the application:

    `python main.py`

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


### Recreate Facebook app
```commandline
error: (#200) this endpoint is deprecated since the required permission publish_actions is deprecated
```
1. Open Graph API Explorer https://developers.facebook.com/tools/explorer/ 
2. Select your MetaApp 
3. Select "User Token" 
4. Set below permissions and Create Access Token 
5. Pass FB Authentication 
6. Select "Page Token" 
7. Pass FB Authentication (select your page during Authentication) 
8. Now you will find your page name inside the token combo at the bottom! Just select it and the page token will appear above. (Do NOT click Create Access Token)

Permissions: pages_manage_cta pages_manage_instant_articles pages_show_list business_management pages_messaging pages_messaging_subscriptions page_events pages_read_engagement pages_manage_metadata pages_read_user_content pages_manage_ads pages_manage_posts pages_manage_engagement

