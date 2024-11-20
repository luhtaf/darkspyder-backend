from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

# Telegram API credentials
API_ID = os.getenv("TELEGRAM_API_ID")  # Replace with your API ID
API_HASH = os.getenv("TELEGRAM_API_HASH")  # Replace with your API Hash
BOT_USERNAME = "@stealerlogbot"  # Target bot username
DOWNLOAD_DIR = "./"  # Directory to save downloaded files

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def update_stealer(q):
    async with TelegramClient('name', API_ID, API_HASH) as client:

        # Step 1: Send the search query
        await client.send_message(BOT_USERNAME, f"/search {q}")
        print(f"Query sent: /search {q}")

        # Step 2: Wait for the response (handle it only once)
        @client.on(events.NewMessage(from_users=BOT_USERNAME))
        async def handle_search_response(event):
            response = event.message.message
            print(f"Received response: {response}")

            # Remove the event handler after it's triggered once
            client.remove_event_handler(handle_search_response)

            # Step 3: If results are found, send the /download command
            if "No results found for your search." not in response:
                await client.send_message(BOT_USERNAME, "/download")
                print("Sent /download command.")
            else:
                print("No results found, exiting.")
                client.disconnect()

        # Step 4: Wait for the file download (handle it only once)
        @client.on(events.NewMessage(from_users=BOT_USERNAME))
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


def json_to_el_stealer(filename):
    try:
        with open(filename, "r") as file1:
            terbaca = file1.readlines()

        for line in terbaca:
            sub_line = line.replace("\n", "").split(":", 1)
            pisah_email = sub_line[1].split("(http", 1)
            url = f"http{pisah_email[1][:-1]}"

            new = {
                "username": sub_line[0],
                "password": pisah_email[0].replace(' ', ''),
                "domain": url,
                "type": "breach"
            }
            # Placeholder for the actual logic to process 'new' dictionary
            print(new)  # Just printing for now, replace with your logic
    except Exception as e:
        print(f"Error processing file: {e}")


if __name__ == "__main__":
    q = 'astra'  # Example query, replace with the actual query
    asyncio.run(update_stealer(q))
