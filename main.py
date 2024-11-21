from dotenv import load_dotenv
import os,jwt, json, hashlib, requests, datetime, asyncio
from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from functools import wraps
from threading import Thread
from cryptography.fernet import Fernet
from telethon import TelegramClient, events

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv("TELEGRAM_API_ID")  # Replace with your API ID
API_HASH = os.getenv("TELEGRAM_API_HASH")  # Replace with your API Hash
old_token_stealer = "gAAAAABnPajlia63seTkzD8232OsGZ_ebOiI7Uektl7yu42yL5BWSrpTvypo67RO_k0yGKH4r8k7v7bEeWbl2vm69mjzoJVsTg=="  # Target bot username

DOWNLOAD_DIR = "./"  # Directory to save downloaded files

elastic_url=os.getenv("ELASTICSEARCH_URL","https://elastic:changeme@localhost:9200")

app = Flask(__name__)
es = Elasticsearch(elastic_url, verify_certs=False)  # Adjust Elasticsearch URL as needed
index_name='darkspyder'

# JWT secret key
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is not set.")

# Load the APP_SECRET from environment variables
app_secret = os.getenv('APP_SECRET')

# Ensure that APP_SECRET exists
if not app_secret:
    raise ValueError("APP_SECRET environment variable is not set.")

# Create a Fernet object using the key from the environment variable
fernet = Fernet(app_secret)


def update_darkspyder(request):
    data =  {"token":"763373424:9kptk7oa", "request":request}
    print("run breach")
    token = 'gAAAAABnPJw5B5RlAH3ym7MmO7pJpTmkOOoUtwPuwD3Wd8PN1N7x-oNeFuHfUrD2MP8VfCAKGh7bjrRJw26k5uAKPZIMMzVkPo1GPo4Tjy8pWWzqw3xjC7Y='
    new_token = fernet.decrypt(token.encode()).decode()
    print("try to search breach")
    response = requests.post(new_token, json=data)
    datajson= response.json()
    print("data breach got")
    for i in datajson['List']:
        print(f"breach -{datajson['List'][i]}")
        newData={
            "Data":datajson['List'][i]['Data'],
            "Source":i,
            "Info":datajson['List'][i]['InfoLeak'],
            "type": "breach"
        }
        checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
        newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
        # Check if the document with this checksum already exists
        print("save breach to db")
        search_response = es.search(
            index=index_name,
            body={
                "query": {
                    "term": {"Checksum": newData["Checksum"]}
                }
            }
        )
        print("done save breach to db")
        
        # If a document exists with the same checksum, update it
        if search_response['hits']['total']['value'] > 0:
            pass
            # doc_id = search_response['hits']['hits'][0]['_id']
            # update_response = es.update(
            #     index=index_name,
            #     id=doc_id,
            #     body={"doc": newData}
            # )
            # print(f"Document with Checksum {newData['Checksum']} updated: {update_response['_id']}")
            print("data ditemukan sama")
        
        # If no document exists with the same checksum, create a new one
        else:
            response = es.index(index=index_name, body=newData)
            print(f"Document indexed with new Checksum {newData['Checksum']}: {response['_id']}")


# Middleware for JWT validation
def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        try:
            # Validate JWT
            jwt.decode(token.split("Bearer ")[1], JWT_SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username_app=os.getenv('USERNAME_APP')
    password_app=os.getenv('PASSWORD_APP')
    username = data.get('username')
    password = data.get('password')

    # Validate credentials
    if username == username_app and password == password_app:
        token = jwt.encode({
            "user": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }, JWT_SECRET_KEY, algorithm="HS256")
        return jsonify({"token": token})
    else:
        return jsonify({"error": "Invalid credentials"}), 401

@app.route('/search', methods=['GET'])
@jwt_required  # Protect this endpoint with JWT middleware
def search():
    try:
        # Get query parameters
        q = request.args.get('q', '')  # Full-text search parameter
        type_param = request.args.get('type', '')  # Parameter type tambahan
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 10)), 100)  # Max size is 100
        update = request.args.get('update', 'false').lower() == 'true'

        # Hitung from (awal pagination)
        from_value = (page - 1) * size

        # Elasticsearch query dasar
        query_body = {
            "query": {
                "bool": {
                    "must": []
                }
            }
        }

        # Tambahkan query full-text search jika ada
        if q:
            query_body['query']['bool']['must'].append({
                "query_string": {
                    "query": q
                }
            })

        # Tambahkan filter berdasarkan type jika disediakan
        if type_param in ['stealer', 'breach']:
            query_body['query']['bool']['must'].append({
                "term": {
                    "type.keyword": type_param
                }
            })

        # Mendapatkan total jumlah data
        total_count = es.count(index=index_name, body=query_body)['count']

        # Eksekusi query pencarian
        result = es.search(index=index_name, body=query_body, from_=from_value, size=size)
        if update:
            thread=Thread(target=update_darkspyder, args=(q,)).start()
            thread.start()
            update_stealer(q)
        # Return response
        return jsonify({
            "page": page,
            "size": size,
            "total": total_count,  # Total matching documents
            "current_page_data": result['hits']['hits']  # Data for the current page
        })
    except NotFoundError:
        return jsonify({"error": "Index not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/update', methods=['GET'])
@jwt_required  # Protect this endpoint with JWT middleware
def api_update_darkspyder():
    try:
        # Get query parameters
        q = request.args.get('q', '')  # Full-text search parameter
        asyncio.run(update_stealer(q))
        update_darkspyder(q)
    
        # Return response
        return jsonify({
            "message":"success update data darkspyder",
        }), 200
    except NotFoundError:
        return jsonify({"error": "Index not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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


def json_to_el_stealer(filename):
    try:
        # Open the file and process it
        with open(filename, "r") as file1:
            terbaca = file1.readlines()

        for line in terbaca:
            sub_line = line.replace("\n", "").split(":", 1)
            pisah_email = sub_line[1].split("(http", 1)
            url = f"http{pisah_email[1][:-1]}"

            newData = {
                "username": sub_line[0],
                "password": pisah_email[0].replace(' ', ''),
                "domain": url,
                "type": "stealer"
            }

            # Generate checksum for the new data
            checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
            newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()

            # Search for an existing document with the same checksum
            search_response = es.search(
                index=index_name,
                body={
                    "query": {
                        "term": {"Checksum": newData["Checksum"]}
                    }
                }
            )

            # If a document exists with the same checksum, update it
            if search_response['hits']['total']['value'] > 0:
                doc_id = search_response['hits']['hits'][0]['_id']
                update_response = es.update(
                    index=index_name,
                    id=doc_id,
                    body={"doc": newData}
                )
                print(f"Document with Checksum {newData['Checksum']} updated: {update_response['_id']}")
            
            # If no document exists with the same checksum, create a new one
            else:
                response = es.index(index=index_name, body=newData)
                print(f"Document indexed with new Checksum {newData['Checksum']}: {response['_id']}")

        # If no exception was raised, delete the file after processing
        print(f"File {filename} processed and deleted successfully.")

    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        os.remove(filename)


if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")
