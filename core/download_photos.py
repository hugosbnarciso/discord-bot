from discord.ext import commands
import openai
import json

# Read the secrets.json file which contains API keys and tokens
with open('config/secrets.json', 'r') as f:
    secrets = json.load(f)

# Set tokens and API keys from the secrets file
DISCORD_BOT_TOKEN = secrets["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = secrets["DISCORD_CHANNEL_ID"]

class download_photos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

@commands.command(name='download_photos')
async def download_photos(self, ctx, *, message):
    if ctx.channel.id == DISCORD_CHANNEL_ID:
        channel = ctx.channel
        async for message in channel.history(limit=500): #change limit to go back x in time - None for no limit
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    timestamp = message.created_at.strftime("%Y%m%d_%H%M%S")
                    new_filename = f'{timestamp}_{attachment.filename}'
                    await attachment.save(f'./downloaded_photos/{new_filename}')
                    logging.info(f'Saved {new_filename}') 
