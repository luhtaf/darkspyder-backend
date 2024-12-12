from init_crypt import fernet
from dotenv import load_dotenv
from telethon import TelegramClient, events
from es_config import json_to_el_stealer
import os, sys, asyncio

load_dotenv()

# Telegram API credentials
API_ID = os.getenv("TELEGRAM_API_ID")  # Replace with your API ID
API_HASH = os.getenv("TELEGRAM_API_HASH")  # Replace with your API Hash
old_token_stealer = "gAAAAABnPajlia63seTkzD8232OsGZ_ebOiI7Uektl7yu42yL5BWSrpTvypo67RO_k0yGKH4r8k7v7bEeWbl2vm69mjzoJVsTg=="  # Target bot username
DOWNLOAD_DIR = "./" 

async def update_stealer(q):
    print("pre run stealer")
    async with TelegramClient('name', API_ID, API_HASH) as client:
        print("running stealer")
        token_stealer = fernet.decrypt(old_token_stealer.encode()).decode()
        # Step 1: Send the search query
        await client.send_message(token_stealer, f"/search {q}")
        print(f"Query sent: /search {q}")

        # Step 2: Wait for the response (handle it only once)
        @client.on(events.NewMessage(from_users=token_stealer))
        async def handle_search_response(event):
            response = event.message.message
            print(f"Received response: {response}")

            # Remove the event handler after it's triggered once
            client.remove_event_handler(handle_search_response)

            # Step 3: If results are found, send the /download command
            if "No results found for your search." not in response:
                await client.send_message(token_stealer, "/download")
                print("Sent /download command.")
            else:
                print("No results found, exiting.")
                client.disconnect()

        # Step 4: Wait for the file download (handle it only once)
        @client.on(events.NewMessage(from_users=token_stealer))
        async def handle_file_download(event):
            if event.message.file:
                file_path = await event.message.download_media(file=DOWNLOAD_DIR)
                print(f"File downloaded to: {file_path}")
                
                # Process the downloaded file
                json_to_el_stealer(file_path)

                # Remove the event handler after it's triggered once
                client.remove_event_handler(handle_file_download)
                client.disconnect()
            else:
                print("No file attached in the response.")
                client.remove_event_handler(handle_file_download)
                client.disconnect()

        # Keep the client running to handle events
        await client.run_until_disconnected()


def main():
    argumen=sys.argv
    if len(argumen)!=1:
        q=argumen[1]
        asyncio.run(update_stealer(q))
    else:
        print("Please Input Argumen")
    pass

if __name__ == "__main__":
    main()