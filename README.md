If you want to host your own instance, you must create a file called **.env**. It should look like this:
DISCORD_TOKEN=tokenhere
GOOGLE_API_KEY=googleapileyhere
To get a Gemini API key, go to https://aistudio.google.com/apikey and follow the instructions. Then put the API key in the .env file. 
To get a Discord bot token, go to https://discord.com/developers/applications and create a new application. Then go to Bot and turn on all the Intents then click Save Changes. Then go to Token and click Reset Token and copy the token and put it in the .env file.

Requrired packages and stuff 

If you haven't already, go to https://www.python.org/ and get the Python download. Then install it to PATH. This is important. Once python is installed, open a new CMD window and copy this: pip install discord.py python-dotenv google-generativeai aiohttp
Once completed, if you run the bot by clicking on the file twice, it will run. 


\\ Notes //
You HAVE to go Installation and click Adminstrator. 
The bot will NOT run without the token and API key in the .env file. If you can't do this, the bot WILL fail to start.
