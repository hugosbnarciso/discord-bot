import aiohttp
import json
import ssl


# Read secrets.json
with open('config/secrets.json', 'r') as f:
    secrets = json.load(f)

# Set the API key and URL
HOMEASSISTANT_API_KEY = secrets['HOMEASSISTANT_API_KEY']
HOMEASSISTANT_URL = secrets['HOMEASSISTANT_URL']

headers = {
    'Authorization': f"Bearer {HOMEASSISTANT_API_KEY}",
    'content-type': 'application/json'
}

async def fetch_all_entities():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE


    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        async with session.get(HOMEASSISTANT_URL, headers=headers) as resp:
            if resp.status == 200:
                response_text = await resp.text()
                data = await resp.json(content_type="application/json")
                print(f'Home Assistant fetch_all_entities success!') ##DEBUG
                return data
            else:
                print(f'Home Assistant fetch_all_entities failed! {resp.reason}') ##DEBUG
                return None

def find_entity_by_friendly_name(entities, search_name):
    search_name_lower = search_name.lower()
    for entity in entities:
        attributes = entity.get("attributes", {})
        friendly_name = attributes.get("friendly_name", "").lower()

        if search_name_lower in friendly_name:
            return entity

    return None
