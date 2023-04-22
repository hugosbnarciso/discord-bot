import os
import logging
import discord
from discord.ext import commands
import openai
from collections import defaultdict
import json
from core.home_assistant import fetch_all_entities, find_entity_by_friendly_name

# Read the secrets.json file
with open('config/secrets.json', 'r') as f:
    secrets = json.load(f)

# Set Tokens and API Keys
DISCORD_BOT_TOKEN = secrets["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = secrets["DISCORD_CHANNEL_ID"]
openai.api_key = secrets["OPENAI_API_KEY"]
HOMEASSISTANT_API_KEY = secrets['HOMEASSISTANT_API_KEY']
HOMEASSISTANT_URL = secrets['HOMEASSISTANT_URL']

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s') #VERBOSE

# Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

# Create a bot instance and set the command predix
bot = commands.Bot(command_prefix='!', intents=intents)

# Bot event: on_ready
# Triggered when the bot is connected and ready to receive messages@bot.event
async def on_ready():
    logging.debug(f'{bot.user} has connected to Discord!') ##DEBUG

# Define the last_message_id dictionary to store the last message ID for each channel
last_message_id = {}

# Read the prompt from a file
def read_prompt(file_name):
    with open(file_name, "r") as f:
        return f.read()

# Fetch and update channel history
async def fetch_and_update_channel_history(channel_id):
    channel = bot.get_channel(channel_id)
    last_id = last_message_id.get(channel_id)
    if last_id:
        after = discord.Object(id=last_id)
    else:
        after = None

    async for message in channel.history(limit=100, after=after):  # change limit to go back x in time - None for no limit
        logging.debug(f"FETCHING HISTORY") ##DEBUG
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        message_entry = f"{timestamp} | {message.author.display_name}: {message.content}"
        if message_entry not in local_history[channel_id]:
            local_history[channel_id].append(message_entry)
            last_message_id[channel_id] = message.id

# Load conversation history from a file
def load_conversation_history(file_name):
    try:
        with open(file_name, 'r') as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}


    loaded_history = defaultdict(list, {int(k): v for k, v in history.items()})
    return loaded_history

# Save conversation history to a file
def save_conversation_history(file_path, history):
    with open(file_path, 'w') as f:
        json.dump(history, f)

# Load conversation history
#conversation_history = load_conversation_history('conversation_history.json')
local_history = load_conversation_history('resources/conversation_history.json')        

# Load conversation history
#conversation_history = load_conversation_history('conversation_history.json')
local_history = load_conversation_history('resources/conversation_history.json')

# Update conversation history on receiving a message
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
    save_conversation_history('resources/conversation_history.json', local_history)

    # Process the bot commands
    await bot.process_commands(message)

# Command: !download_photos
@bot.command()
async def download_photos(ctx):
    if ctx.channel.id == DISCORD_CHANNEL_ID:
        channel = ctx.channel
        async for message in channel.history(limit=500): #change limit to go back x in time - None for no limit
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    timestamp = message.created_at.strftime("%Y%m%d_%H%M%S")
                    new_filename = f'{timestamp}_{attachment.filename}'
                    await attachment.save(f'./downloaded_photos/{new_filename}')
                    logging.info(f'Saved {new_filename}') ##DEBUG

# !ABED
@bot.command()
async def abed(ctx, *, question: str):
    logging.debug(f'QUESTION: {question}') ##DEBUG
    user_name = ctx.author.display_name
    channel_id = ctx.channel.id

    if channel_id not in local_history:
        local_history[channel_id] = [] 
    await fetch_and_update_channel_history(channel_id)  # Fetch the channel history if it's not in the local history

    # Add the current question to the local history
    timestamp = ctx.message.created_at.strftime("%Y-%m-%d %H:%M:%S")
    local_history[channel_id].append(f"{timestamp} | {user_name}: {question}")

    prompt = read_prompt("config/prompt.txt")  # Read the prompt from the file
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

### HOME ASSISTANT ###
    try:
        # Fetch all entities from the Home Assistant API
        entities = await fetch_all_entities()  # Use the API key from the secrets file
        logging.debug(f'{entities}') ##DEBUG

        # Iterate through the entities and check if the reply matches fully or partially to any of the entities
        matched_entity = None
        allowed_entity_types = ("light", "fan", "binary_sensor", "lock")

        for entity in entities:
            entity_id = entity.get("entity_id", "")
            entity_type = entity_id.split(".")[0]

            if entity_type not in allowed_entity_types:
                continue

            attributes = entity.get("attributes", {})
            friendly_name = attributes.get("friendly_name", "").lower()
            logging.debug(f'FOUND FRIENDLY NAME: {friendly_name}') ##DEBUG

            if friendly_name in reply.lower():
                matched_entity = entity
                logging.debug(f'MATCHED ENTITY: {matched_entity}') ##DEBUG
                break

        # If a matching entity is found, add its state to the reply
        if matched_entity:
            search_name = matched_entity["attributes"]["friendly_name"]
            entity_id = matched_entity["entity_id"]
            entity_state = matched_entity["state"]

            reply += f" The current state of the {search_name} is '{entity_state}'."
#        else:
#            reply += f" I couldn't find an entity with a name matching the reply."
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        reply = "I'm sorry, but I couldn't process your request. I'm taking a nap"

    # Remove the timestamp from the reply
    reply = reply.split('Abed:', 1)[-1].strip()
        
    await ctx.send(reply)
    save_conversation_history('resources/conversation_history.json', local_history)

bot.run(DISCORD_BOT_TOKEN)