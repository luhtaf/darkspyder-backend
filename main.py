from dotenv import load_dotenv
import os,jwt, json, hashlib, requests, datetime, asyncio
from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from functools import wraps
from threading import Thread
from cryptography.fernet import Fernet
from telethon import TelegramClient, events
from flask_restx import Api, Resource, fields

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = os.getenv("TELEGRAM_API_ID")  # Replace with your API ID
API_HASH = os.getenv("TELEGRAM_API_HASH")  # Replace with your API Hash
old_token_stealer = "gAAAAABnPajlia63seTkzD8232OsGZ_ebOiI7Uektl7yu42yL5BWSrpTvypo67RO_k0yGKH4r8k7v7bEeWbl2vm69mjzoJVsTg=="  # Target bot username

DOWNLOAD_DIR = "./"  # Directory to save downloaded files

elastic_url=os.getenv("ELASTICSEARCH_URL","https://elastic:changeme@localhost:9200")
authorizations = {
    'Bearer': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'Masukkan token JWT dengan format: Bearer <token>'
    }
}
app = Flask(__name__)
app.config['SWAGGER_UI_DOC_EXPANSION'] = 'list'
app.config['RESTX_MASK_SWAGGER'] = False
app.config['ERROR_404_HELP'] = False
api = Api(
    app, 
    authorizations=authorizations,
    title="DarkSpyder API", 
    description="API untuk pengelolaan data breach dan stealer", 
    doc="/swagger-ui",
    version="1.0"
)

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

login_model = api.model('Login', {
    'username': fields.String(required=True, description='Username untuk autentikasi'),
    'password': fields.String(required=True, description='Password untuk autentikasi')
})

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

@api.route('/login')
class Login(Resource):
    @api.expect(login_model)
    @api.response(200, 'Success', fields.Raw)
    @api.response(401, 'Invalid credentials')
    def post(self):
        """Autentikasi pengguna dan menghasilkan token JWT"""
        data = request.json
        username_app = os.getenv('USERNAME_APP')
        password_app = os.getenv('PASSWORD_APP')
        username = data.get('username')
        password = data.get('password')

        if username == username_app and password == password_app:
            token = jwt.encode({
                "user": username,
                "exp": datetime.datetime.now() + datetime.timedelta(hours=1)
            }, JWT_SECRET_KEY, algorithm="HS256")
            return {"token": token}, 200
        else:
            return {"error": "Invalid credentials"}, 401

@api.route('/search')
class Search(Resource):
    @api.doc(
        params={
            'q': 'Query pencarian',
            'type': 'Tipe pencarian (password, email, username, breach, stealer)',
            'page': 'Halaman pagination (default: 1)',
            'size': 'Jumlah data per halaman (default: 10, max: 100)',
            'update': 'Perbarui data jika ditemukan (true/false)'
        },
    )
    @api.response(200, 'Success', fields.Raw)
    @api.response(400, 'Invalid parameters')
    @api.response(401, 'Unauthorized')
    @jwt_required
    def get(self):
        """Pencarian data berdasarkan query dan tipe"""
        try:
            # Get query parameters
            q = request.args.get('q', '').strip()  # Query parameter pencarian
            type_param = request.args.get('type', '').strip().lower()  # Type pencarian (password, email, dll.)
            page = int(request.args.get('page', 1))
            size = min(int(request.args.get('size', 10)), 100)  # Max size adalah 100
            update = request.args.get('update', 'false').lower() == 'true'

            # Hitung from (awal pagination)
            from_value = (page - 1) * size

            # Validasi type yang diperbolehkan
            valid_types = ['stealer', 'breach', 'password', 'email', 'username']
            if type_param not in valid_types:
                return jsonify({"error": f"Invalid type. Allowed types: {', '.join(valid_types)}"}), 400

            # Elasticsearch query dasar
            query_body = {
                "query": {
                    "bool": {
                        "must": []
                    }
                }
            }

            # Tambahkan logika spesifik berdasarkan `type`
            if type_param in ['password', 'email', 'username']:
                if not q:
                    return jsonify({"error": "Parameter 'q' is required for this type"}), 400

                # Field pencarian sesuai type
                field_queries = [
                    {"term": {f"{type_param}.keyword": q}},  # Field utama
                    {"term": {f"Data.{type_param.capitalize()}.keyword": q}}  # Field dalam objek Data dengan kapitalisasi
                ]
                query_body['query']['bool']['must'].append({
                    "bool": {
                        "should": field_queries,
                        "minimum_should_match": 1
                    }
                })

            elif type_param in ['stealer', 'breach']:
                # Filter berdasarkan type keyword
                query_body['query']['bool']['must'].append({
                    "term": {
                        "type.keyword": type_param
                    }
                })

                # Pencarian di semua field dengan q
                if q:
                    query_body['query']['bool']['must'].append({
                        "query_string": {
                            "query": q,
                            "default_operator": "AND"
                        }
                    })

            # Mendapatkan total jumlah data
            total_count = es.count(index=index_name, body=query_body)['count']

            # Eksekusi query pencarian
            result = es.search(index=index_name, body=query_body, from_=from_value, size=size)
            print(result)
            # Jika parameter update = true, jalankan update dalam thread
            # if update:
            #     thread = Thread(target=update_darkspyder, args=(q,))
            #     thread.start()
            #     update_stealer(q)

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

@api.route('/update')
class Update(Resource):
    @api.doc(
        params={
            'q': 'Query parameter untuk pembaruan data'
        },
        security='Bearer'
    )
    @api.response(200, 'Success', fields.Raw)
    @api.response(401, 'Unauthorized')
    @api.response(404, 'Index not found')
    @api.response(500, 'Internal Server Error')
    @jwt_required  # Protect this endpoint with JWT middleware
    def get(self):
        """Perbarui data berdasarkan query"""
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
            try:
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
            except Exception as inner_e:
                # Handle errors for the current line and continue
                print(f"Error processing line: {line}. Error: {inner_e}")

        # If no exception was raised, delete the file after processing
        print(f"File {filename} processed and deleted successfully.")

    except Exception as e:
        print(f"Error processing file: {e}")
    finally:
        os.remove(filename)


if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")
