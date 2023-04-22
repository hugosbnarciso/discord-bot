import os
import logging #for verbose
import discord #discord
import openai #open ai
from discord.ext import commands #discord
from collections import defaultdict #makes conversation history available
import json #format to save the converstaion history

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s') #VERBOSE
last_message_id = {}

def read_prompt(file_name): #READ PROMPT FROM FILE
    with open(file_name, "r") as f:
        return f.read()

#fetches discord's channel history
async def fetch_and_update_channel_history(channel_id):
    channel = bot.get_channel(channel_id)
    last_id = last_message_id.get(channel_id)
    if last_id:
        after = discord.Object(id=last_id)
    else:
        after = None

    async for message in channel.history(limit=None, after=after):  # change limit to go back x in time - None for no limit
        logging.debug(f"FETCHING HISTORY") ##DEBUG
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        message_entry = f"{timestamp} | {message.author.display_name}: {message.content}"
        if message_entry not in local_history[channel_id]:
            local_history[channel_id].append(message_entry)
            last_message_id[channel_id] = message.id


#loads conversation history
def load_conversation_history(file_name):
    try:
        with open(file_name, 'r') as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}

    # Convert the loaded history into a defaultdict with integer keys
    loaded_history = defaultdict(list, {int(k): v for k, v in history.items()})
    return loaded_history

#saves conversation history
def save_conversation_history(file_path, history):
    with open(file_path, 'w') as f:
        json.dump(history, f)

with open("secrets.json") as secrets_file:
    secrets = json.load(secrets_file)

DISCORD_BOT_TOKEN = secrets["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = secrets["DISCORD_CHANNEL_ID"]
openai.api_key = secrets["OPENAI_API_KEY"]

# Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

# Load conversation history
#conversation_history = load_conversation_history('conversation_history.json')
local_history = load_conversation_history('conversation_history.json')

bot = commands.Bot(command_prefix='!', intents=intents) # COMMAND PREFIX

#ON_READY
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

# on_message event to update the conversation history
@bot.event
async def on_message(message):
    if message.author.bot and message.author != bot.user:   #switch to not ignore other bots
#    if message.author.id == bot.user.id:                   #switch to not ignore other bots
        return

    channel_id = message.channel.id
    if channel_id not in local_history:
        local_history[channel_id] = []


    timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    local_history[channel_id].append(f"{timestamp} | {message.author.display_name}: {message.content}")

    # Save the updated conversation history
    save_conversation_history('conversation_history.json', local_history)

    # Process the bot commands
    await bot.process_commands(message)



# !DOWNLOAD_PHOTOS
@bot.command()
async def download_photos(ctx):
    if ctx.channel.id == TARGET_CHANNEL_ID:
        channel = ctx.channel
        async for message in channel.history(limit=1000): #change limit to go back x in time - None for no limit
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    timestamp = message.created_at.strftime("%Y%m%d_%H%M%S")
                    new_filename = f'{timestamp}_{attachment.filename}'
                    await attachment.save(f'./downloaded_photos/{new_filename}')
                    print(f'Saved {new_filename}')


# !ABED
@bot.command()

async def abed(ctx, *, question: str):
    logging.debug(f"COMMAND RECEIVED: {question}") ##DEBUG
    user_name = ctx.author.display_name
    channel_id = ctx.channel.id

    if channel_id not in local_history:
        local_history[channel_id] = [] 
    await fetch_and_update_channel_history(channel_id)  # Fetch the channel history if it's not in the local history

    # Add the current question to the local history
    timestamp = ctx.message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    local_history[channel_id].append(f"{timestamp} | {user_name}: {question}")

    prompt = read_prompt("prompt.txt")  # Read the prompt from the file
    prompt += "\n\n" + "\n".join(local_history[channel_id]) + "\n"
    logging.debug(f"PROMPT: {prompt}") ##DEBUG

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=250,
        n=1,
        stop=None,
        temperature=0.7,
        #(0.1), the response is more focused and concise. (0.5), the answer is more detailed and covers more destinations. (1.0),more creative and provides richer descriptions
    )

    reply = response.choices[0].text.strip()

    # Remove "Abed:" from the generated response if it's present
    if reply.startswith("Abed:"):
        reply = reply[5:].strip()

    # Remove the timestamp from the reply
    reply = reply.split('Abed:', 1)[-1].strip()
   # Remove the timestamp from the generated response if it's present
#    timestamp_position = reply.find("|")
#    if timestamp_position != -1:
#        reply = reply[timestamp_position + 1:].strip()
        
    await ctx.send(reply)

    save_conversation_history('conversation_history.json', local_history)


bot.run(DISCORD_BOT_TOKEN)