import discord as dpy
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import aiohttp
import random
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- File Paths ---
BLACKLIST_FILE = 'blacklist.json'
PREFIXES_FILE = 'prefixes.json'
FLAGGED_WORDS_FILE = 'flagged_words.json'
AUTO_MODERATION_FILE = 'auto_moderation.json'

# --- Configuration Loading ---
def load_json_file(filename, default_value):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_value

# --- Bot Class ---
class PlasticBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blacklist = set(load_json_file(BLACKLIST_FILE, []))
        self.prefixes = load_json_file(PREFIXES_FILE, {})
        self.flagged_words = load_json_file(FLAGGED_WORDS_FILE, {})

    def save_prefixes(self):
        with open(PREFIXES_FILE, 'w') as f:
            json.dump(self.prefixes, f, indent=4)

    def save_flagged_words(self):
        with open(FLAGGED_WORDS_FILE, 'w') as f:
            json.dump(self.flagged_words, f, indent=4)

# --- Dynamic Prefix ---
def get_prefix(bot, message):
    if not message.guild:
        return "?"
    return bot.prefixes.get(str(message.guild.id), "?")

# --- Bot Intents ---
intents = dpy.Intents.default()
intents.presences = True
intents.members = True
intents.message_content = True

bot = PlasticBot(command_prefix=get_prefix, intents=intents)

# --- Gemini Configuration ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# --- Auto Moderation Config ---
auto_moderation_config = load_json_file(AUTO_MODERATION_FILE, {})

def save_auto_moderation_config():
    with open(AUTO_MODERATION_FILE, 'w') as f:
        json.dump(auto_moderation_config, f, indent=4)

# --- Helper Function: Looser Moderation ---
async def is_offensive_content(message_content):
    """
    Looser check: Only flag clear hate or harassment.
    """
    prompt = (
        "Determine if the following text contains clearly hateful, harassing, or violent content directed at a person or group. "
        "Ignore mild profanity or non-serious insults. "
        "Respond with ONLY 'yes' or 'no'. "
        f"Text: ```{message_content}```"
    )
    try:
        response = model.generate_content(prompt)
        result = response.text.strip().lower()
        return result.startswith("yes")
    except Exception as e:
        print(f"Error checking content with Gemini: {e}")
        return False

# --- Global Check ---
@bot.check
async def is_not_blacklisted(ctx):
    user = getattr(ctx, 'author', getattr(ctx, 'user', None))
    return user.id not in bot.blacklist if user else True

# --- Event Listeners ---
@bot.event
async def on_ready():
    activity = dpy.Activity(type=dpy.ActivityType.watching, name="plasticbot.org")
    await bot.change_presence(status=dpy.Status.online, activity=activity)
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')
    print('Bot is ready.')

@bot.event
async def on_message(message):
    if not message.guild or message.author.bot or message.author.id in bot.blacklist:
        return

    guild_id = str(message.guild.id)
    is_moderation_enabled = auto_moderation_config.get(guild_id, False)

    # Auto moderation
    if is_moderation_enabled:
        if await is_offensive_content(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention} Your message was removed because it contained offensive content.",
                    delete_after=10
                )
            except dpy.errors.Forbidden:
                print(f"Missing permissions to delete message in {message.guild.name}.")
                await message.channel.send(
                    f"{message.author.mention} Offensive content detected but could not delete."
                )
            except dpy.errors.NotFound:
                pass
            return

    # Flagged words (your existing logic)
    if guild_id in bot.flagged_words:
        config = bot.flagged_words[guild_id]
        is_global = config.get("sync_global", False)
        is_correct_channel = not is_global and config.get("channel") == message.channel.id
        if is_global or is_correct_channel:
            flagged_words_in_message = [word for word in config.get("words", []) if word in message.content.lower().split()]
            if flagged_words_in_message:
                custom_message = config.get("message", "A flagged word was detected.")
                response_message = f"{message.author.mention} {custom_message}"
                try:
                    await message.delete()
                    await message.channel.send(response_message, delete_after=10)
                except dpy.errors.Forbidden:
                    await message.channel.send(response_message)
                except dpy.errors.NotFound:
                    pass
                return

    await bot.process_commands(message)

# --- Moderation Slash Command ---
@bot.tree.command(name="moderation", description="Manage auto-moderation of offensive content.")
@app_commands.describe(action="Choose enable, disable, or status.")
async def moderation(interaction: dpy.Interaction, action: str):
    guild_id = str(interaction.guild.id)
    action = action.lower()
    if action == "enable":
        auto_moderation_config[guild_id] = True
        save_auto_moderation_config()
        await interaction.response.send_message("✅ Auto-moderation ENABLED. Offensive messages will be deleted.", ephemeral=True)
    elif action == "disable":
        auto_moderation_config[guild_id] = False
        save_auto_moderation_config()
        await interaction.response.send_message("🛑 Auto-moderation DISABLED.", ephemeral=True)
    elif action == "status":
        enabled = auto_moderation_config.get(guild_id, False)
        status_text = "✅ ENABLED" if enabled else "🛑 DISABLED"
        await interaction.response.send_message(f"Auto-moderation is currently: {status_text}", ephemeral=True)
    else:
        await interaction.response.send_message("Please specify a valid action: `enable`, `disable`, or `status`.", ephemeral=True)

# --- Ping Command Example ---
@bot.command(name='ping', help="Check the bot's latency.")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(embed=dpy.Embed(
        title="Pong!",
        description=f"My latency is **{latency}ms**.",
        color=dpy.Color.green()
    ))

# --- Error Handling ---
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to run this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"You are missing an argument. Use `{get_prefix(bot, ctx.message)}help {ctx.command}` for info.")
    else:
        print(f"Unexpected error: {error}")

# --- Run Bot ---
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("ERROR: DISCORD_TOKEN not found in .env file.")
else:
    try:
        bot.run(TOKEN)
    except dpy.errors.LoginFailure:
        print("Login failed: invalid token.")
    except Exception as e:
        print(f"Unexpected error during bot execution: {e}")
