from dotenv import load_dotenv
import os,jwt, json, hashlib, requests, datetime
from flask import Flask, request, jsonify
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from functools import wraps
from threading import Thread
from cryptography.fernet import Fernet

# Load environment variables
load_dotenv()
elastic_url=os.getenv("ELASTICSEARCH_URL","https://elastic:changeme@localhost:9200")

app = Flask(__name__)
es = Elasticsearch(elastic_url, verify_certs=False)  # Adjust Elasticsearch URL as needed
index_name='leak_osint'

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


def update_leak_osint(request):
    data =  {"token":"763373424:9kptk7oa", "request":request}
    token = 'gAAAAABnPJw5B5RlAH3ym7MmO7pJpTmkOOoUtwPuwD3Wd8PN1N7x-oNeFuHfUrD2MP8VfCAKGh7bjrRJw26k5uAKPZIMMzVkPo1GPo4Tjy8pWWzqw3xjC7Y='
    new_token = fernet.decrypt(token.encode()).decode()
    response = requests.post(new_token, json=data)
    datajson= response.json()
    for i in datajson['List']:
        newData={
            "Data":datajson['List'][i]['Data'],
            "Source":i,
            "Info":datajson['List'][i]['InfoLeak']
        }
        checksum_input = json.dumps(newData, sort_keys=True)  # Sort keys to ensure consistent hashing
        newData["Checksum"] = hashlib.sha256(checksum_input.encode()).hexdigest()
        response = es.index(index=index_name, body=newData)
        print(f"Document indexed: {response['_id']}")


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
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 10)), 100)  # Max size is 100
        update = request.args.get('update', 'false').lower() == 'true'
        
        # Calculate from (pagination start point)
        from_value = (page - 1) * size
        
        # Elasticsearch query with `q` parameter
        # query_body = {
        #     "query": {
        #         "query_string": {
        #             "query": q
        #         }
        #     }
        # }
        query_body = {
            "query": {
                "query_string": {
                    "query": q,  # Replace with your search keyword
                    "fields": ["*"],         # Search across all fields
                    "fuzziness": "AUTO",     # Enable fuzzy matching
                    "default_operator": "or",  # Matches any term in the keyword
                    "analyze_wildcard": True
                }
            }
        }
        
        # Get total data count
        total_count = es.count(index=index_name, body=query_body)['count']
        
        # Execute search query
        result = es.search(index=index_name, body=query_body, from_=from_value, size=size)
        if update:
            Thread(target=update_leak_osint, args=(q,)).start()
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
def api_update_leak_osint():
    try:
        # Get query parameters
        q = request.args.get('q', '')  # Full-text search parameter
        update_leak_osint(q)
        # Return response
        return jsonify({
            "message":"success update data leak_osint",
        }), 200
    except NotFoundError:
        return jsonify({"error": "Index not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host="0.0.0.0")
