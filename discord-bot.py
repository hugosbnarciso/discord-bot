import os
import logging
import discord
import openai
import pytz
import datetime
from collections import defaultdict
import json
from discord.ext import commands
from core.download_photos import download_photos
from discord import Intents

# Read the secrets.json file which contains API keys and tokens
with open('config/secrets.json', 'r') as f:
    secrets = json.load(f)

# Set tokens and API keys from the secrets file
DISCORD_BOT_TOKEN = secrets["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = secrets["DISCORD_CHANNEL_ID"]
openai.api_key = secrets["OPENAI_API_KEY"]
MAX_TOKENS = 4096  # Or whatever maximum token limit you want to set - 4096 MAX , 250 ANSWER
TIMEZONE = secrets["TIMEZONE"]

# Set up logging to output information about the bot's actions and events
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s: %(message)s')
# logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

# Define the Discord intents for the bot. Intents define what events the bot will listen for.
intents = Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True 

# Create an instance of the bot with the specified command prefix and intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Event that runs when the bot is ready and connected to Discord
@bot.event
async def on_ready():
    logging.info(f'{bot.user} has connected to Discord!')

# Define a dictionary to store the last message ID for each channel
last_message_id = {}

# Function to read the prompt from a file
def read_prompt(file_name):
    with open(file_name, "r") as f:
        return f.read()

# Function to fetch and update the channel history
async def fetch_and_update_channel_history(channel_id):
    channel = bot.get_channel(channel_id)
#2    # last_id = last_message_id.get(channel_id)
    # if last_id:
    #     after = discord.Object(id=last_id)
    # else:
    #     after = None
   
    # Initialize a temporary list to hold the new history
    new_history = []

    # Use the .history() method without the after parameter, and set the limit to xxx
    async for message in channel.history(limit=100):  # change limit to go back x in time - None for no limit

        # Convert the timestamp to your desired timezone
        desired_tz = pytz.timezone(TIMEZONE)  # replace with your timezone 
        utc_time = message.created_at.replace(tzinfo=pytz.utc)  # Specify that this is a UTC datetime
        local_time = utc_time.astimezone(desired_tz)
        timestamp = local_time.strftime("%Y-%m-%d %H:%M") # to add seconds - ("%Y-%m-%d %H:%M:%S")
        logging.info(f"FETCHING: {timestamp} | {message.author.display_name}: {message.content}") 

 ##1       timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        message_entry = f"{timestamp} | {message.author.display_name}: {message.content}"
        new_history.append(message_entry)

    # Reverse the new_history list to keep messages in chronological order
    new_history.reverse()

   #2     # if message_entry not in local_history[channel_id]:
        #     local_history[channel_id].append(message_entry)
        #     last_message_id[channel_id] = message.id

    # Replace the old history with the new history
    local_history[channel_id] = new_history

# Function to load the conversation history from a file
def load_conversation_history(file_name):
    try:
        with open(file_name, 'r') as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {}
    loaded_history = defaultdict(list, {int(k): v for k, v in history.items()})
    return loaded_history

# Function to save the conversation history to a file
def save_conversation_history(file_path, history):
    with open(file_path, 'w') as f:
        json.dump(history, f)

# Load the conversation history
local_history = load_conversation_history('resources/conversation_history.json')

# Event that runs when a message is received
@bot.event
async def on_message(message):
    # Do not process commands if they are coming from a bot
    if message.author.bot and message.author != bot.user:   
        return
    
    # Check if the message is a command
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # Add the message to the history
    channel_id = message.channel.id

    # Convert the timestamp to your desired timezone
    desired_tz = pytz.timezone(TIMEZONE)  # replace with your timezone 
    utc_time = message.created_at.replace(tzinfo=pytz.utc)  # Specify that this is a UTC datetime
    local_time = utc_time.astimezone(desired_tz)
    timestamp = local_time.strftime("%Y-%m-%d %H:%M") # to add seconds - ("%Y-%m-%d %H:%M:%S")

    message_entry = f"{timestamp} | {message.author.display_name}: {message.content}"
    local_history[channel_id].append(message_entry)
    last_message_id[channel_id] = message.id
    save_conversation_history('resources/conversation_history.json', local_history)

# Command to ask the bot a question
@bot.command(name='abed', help='Ask Abed a question')
async def abed(ctx, *, question):
    # Fetch the channel history
    await fetch_and_update_channel_history(ctx.channel.id)

    # Construct the conversation
    conversation = '\n'.join(local_history[ctx.channel.id])

    # Truncate the conversation to fit within the model's maximum token limit
    conversation = conversation[-MAX_TOKENS:]
    logging.info(f'CONVERSATION:\n{conversation}')
    
    # Read the prompt from the file
    rules = read_prompt('config/rules.txt')

    # Define the prompt
    prompt = f'{rules}\n{conversation}\nAbed:'
    # prompt = f'{rules}\n{conversation}\n{ctx.message.author.display_name}: {question}\nAbed:'
    logging.info(f'PROMPT:\n{prompt}') 


    # Use OpenAI to generate a response to the question
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=350,
        n=1,
        stop=None,
        temperature=0.7, # (0.1), the response is more focused and concise. (0.5), the answer is more detailed and covers more destinations. (1.0),more creative and provides richer descriptions
    )
    reply = response.choices[0].text.strip()

    # Remove the timestamp and Abed: from the reply
    reply = reply.split('Abed:', 1)[-1].strip()

    # Check if the reply is empty
    if not reply:
        reply = "Sorry, I glitched for a moment. Please ask again"

    if "what time is it" in question.lower():
        # Get the current time in the desired timezone
        desired_tz = pytz.timezone(TIMEZONE)
        current_time = datetime.datetime.now(desired_tz)

        # Format the time
        formatted_time = current_time.strftime("%H:%M")

        # Add the time to the reply
        reply = f"The current time is {formatted_time}."

    # Send the response as a message
    logging.info(f'REPLY: {reply}\nEND OF CODE, STANDING BY') 
    await ctx.send(reply)
        
# Run the bot
bot.run(DISCORD_BOT_TOKEN)