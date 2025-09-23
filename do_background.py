from flask import Flask, jsonify, request, send_file
from flask.json.provider import DefaultJSONProvider
import subprocess, jwt, datetime, json, os, string, random, threading
from datetime import datetime as dt
from breach1 import search_breach1
from breach2 import search_lcheck_stealer
from functools import wraps
from cred import username_app, password_app, JWT_SECRET_KEY
from es_config import search_elastic, update_valid, update_valid_bulk, download_elastic
from stealer2 import search_stealer2
from trait import ResponseError
from parsing_db_to_json import parse_html_to_json, save_to_json
from werkzeug.utils import secure_filename
from init_mongo import mongo_db, MONGO_DB_NAME
from init_payment import payment
from bson import ObjectId, json_util
from handle_totp import generate_url_otp, verify_totp, generate_secret
from dateutil.relativedelta import relativedelta
from background_function import background_task

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, dt):
            return obj.isoformat()
        return super().default(obj)

app = Flask(__name__)
app.json_provider_class = CustomJSONProvider
app.json = app.json_provider_class(app)
app.config['UPLOAD_FOLDER'] = './'


max_query=1000

def get_jwt_data(token):
    if not token:
        return jsonify({"error": "Missing token"}), 401
    
    return jwt.decode(token.split("Bearer ")[1], JWT_SECRET_KEY, algorithms=["HS256"])

def validate_object_id(id_string):
    """Validate and convert string to ObjectId"""
    try:
        if not id_string:
            return None, "ObjectId cannot be empty"
        
        if len(id_string) != 24:
            return None, f"ObjectId must be exactly 24 characters, got {len(id_string)}"
        
        # Check if it's a valid hex string
        try:
            int(id_string, 16)
        except ValueError:
            return None, f"ObjectId must contain only hexadecimal characters (0-9, a-f), got: {id_string}"
        
        return ObjectId(id_string), None
    except Exception as e:
        return None, f"Invalid ObjectId: {str(e)}"

def extract_domain_from_url(url_or_domain):
    """
    Extract base domain from URL or domain string
    Examples:
    - https://sub.example.com/path -> example.com
    - sub.example.com -> example.com  
    - example.com -> example.com
    - /path -> None (invalid, no domain)
    """
    from urllib.parse import urlparse
    
    # Handle edge cases
    if not url_or_domain or url_or_domain.strip() == "":
        return None
        
    # If it starts with just a path (like /path), it's not a valid domain
    if url_or_domain.startswith('/'):
        return None
    
    try:
        # Remove protocol if present
        if url_or_domain.startswith(('http://', 'https://')):
            parsed = urlparse(url_or_domain)
            domain = parsed.netloc
        else:
            # Remove path if present (e.g., example.com/path -> example.com)
            domain = url_or_domain.split('/')[0]
        
        # Remove port if present
        domain = domain.split(':')[0].strip()
        
        # Check if domain is empty after processing
        if not domain:
            return None
            
        # Split domain parts
        parts = domain.split('.')
        
        # Domain must have at least one dot to be valid (e.g., example.com)
        # Single words without dots are not considered valid domains for this validation
        if len(parts) < 2:
            return domain  # Return as-is, let the validation handle it
        
        # If domain has more than 2 parts, try to get the main domain
        # This handles cases like sub.example.com -> example.com
        if len(parts) >= 2:
            # Return last two parts as main domain (handles most cases)
            return '.'.join(parts[-2:])
        
        return domain
        
    except Exception:
        return None

def is_domain_or_subdomain_allowed(input_domain, registered_domains):
    """
    Check if input_domain matches any registered domain or is a subdomain of registered domains
    """
    # Extract base domain from input
    base_domain = extract_domain_from_url(input_domain)
    
    # If extraction failed, try direct comparison
    if base_domain is None:
        base_domain = input_domain
    
    for registered_domain in registered_domains:
        # Direct match
        if input_domain == registered_domain or base_domain == registered_domain:
            return True
            
        # Check if input is subdomain of registered domain
        if input_domain.endswith('.' + registered_domain):
            return True
            
        # Check if base domain is subdomain of registered domain  
        if base_domain != input_domain and base_domain.endswith('.' + registered_domain):
            return True
            
        # Check if registered domain is subdomain of input (reverse check)
        if registered_domain.endswith('.' + base_domain):
            return True
    
    return False

def domain_validation(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get domain parameter
        domain = request.args.get('domain')
        type_param = request.args.get('type', '').strip().lower()
        if type_param == 'stealer':
            try:
                # Get user information from JWT token
                token = request.headers.get("Authorization")
                decoded = get_jwt_data(token)
                user_id = decoded['user_id']
                
                # Get user's registered domains from MongoDB
                accounts_collection = mongo_db.get_accounts_collection()
                account = accounts_collection.find_one(
                    {"_id": ObjectId(user_id)}, 
                    {"_id": 1, "myPlan": 1}
                )
                
                if not account:
                    return jsonify({"error": "User account not found"}), 404
                    
                # Check if user has registered domains
                plan_info = account.get('myPlan', {})
                if plan_info ['expired']<datetime.datetime.now() and plan_info['expired'] != 'unlimited':
                    return jsonify({"error": "Your plan has expired"}), 403
                registered_domains = plan_info.get('registered_domain', [])
                request.registered_domain = registered_domains
                request.plan_info = plan_info
                if plan_info['domain'] != 'unlimited':
                    q = request.args.get('q', "")
                    if q!="":
                        return jsonify({"error": "You can only search for domains registered in your plan"}), 403
                    if not registered_domains:
                        return jsonify({"error": "No domains registered. Please register domains first using /register-domain"}), 403
                        
                    # Validate if the provided domain matches any registered domain or subdomain
                    if not is_domain_or_subdomain_allowed(domain, registered_domains):
                        return jsonify({"error": f"Domain '{domain}' is not registered or not a subdomain of registered domains. Registered domains: {registered_domains}"}), 403
                else:
                    if len(registered_domains) == 0:
                        request.registered_domain.append('unlimited')
            except Exception as e:
                return jsonify({"error": f"Domain validation failed: {str(e)}"}), 500
        elif type_param == 'breach':
            try:
                token = request.headers.get("Authorization")
                decoded = get_jwt_data(token)
                user_id = decoded['user_id']
                accounts_collection = mongo_db.get_accounts_collection()
                account = accounts_collection.find_one(
                    {"_id": ObjectId(user_id)}, 
                    {"_id": 1, "myPlan": 1}
                )
                plan_info = account.get('myPlan', {})
                if plan_info ['expired']<datetime.datetime.now() and plan_info['expired'] != 'unlimited':
                    return jsonify({"error": "Your plan has expired"}), 403
                breach = plan_info.get('breach', 0)
                if breach != 'unlimited':
                    breach = int(breach)
                current_breach = int(plan_info.get('current_breach', 0))
                if breach != 'unlimited' and (current_breach >= breach):
                    return jsonify({"error": "You have exceeded the number of breach allowed in your plan"}), 403
                else:
                    set_data = {
                        "$set": {
                            "myPlan.current_breach": str(current_breach + 1)
                            }
                    }
                    filter = {"_id": ObjectId(user_id)}
                    accounts_collection.update_one(
                        filter,
                        set_data
                    )
            except Exception as e:
                return jsonify({"error": f"Breach validation failed: {str(e)}"}), 500
        return f(*args, **kwargs)
    return decorated_function


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        try:
            # Validate JWT
            decoded = get_jwt_data(token)
            
            # Check if it's the new user_id based login or old username based
            if 'user_id' in decoded:
                # Verify user_id still exists in database
                accounts_collection = mongo_db.get_accounts_collection()
                if not accounts_collection.find_one({"_id": ObjectId(decoded['user_id'])}):
                    return jsonify({"error": "Invalid user"}), 401
                request.user_id = decoded['user_id']
                    
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception as e:
            print(e)
            return jsonify({"error": "Invalid user ID format"}), 401
        return f(*args, **kwargs)
    return decorated_function



@app.route("/search", methods=["GET"])
@jwt_required
def start_search():
    q = request.args.get("q", "")
    type_param = request.args.get('type', '').strip().lower() 
    page = int(request.args.get('page', 1))
    size = request.args.get('size', 10)
    if (size != "all"):
        try:
            size = int(size)
        except ValueError:
            return jsonify({"error": "Invalid size parameter"}), 400
            
    username = request.args.get('username')  
    domain = request.args.get('domain')
    password = request.args.get('password')
    
    valid = request.args.get('valid', '').strip().lower()
    data = {
        "username": username,
        "domain": domain,
        "password": password
    }

    response = search_elastic(q, type_param, page, size, data, valid)
    
    # Handle the size limit response
    if response.get("status") == 400:
        return jsonify(response), 400
        
    return jsonify(response), response.get("status", 200)

@app.route("/search/download", methods=["GET"])
@jwt_required
def download_search():
    q = request.args.get("q", "")
    type_param = request.args.get('type', '').strip().lower()
    username = request.args.get('username')
    domain = request.args.get('domain')
    password = request.args.get('password')
    valid = request.args.get('valid', '').strip().lower()
    logo_url = request.args.get('logo_url', '').strip().lower()

    data = {
        "username": username,
        "domain": domain,
        "password": password
    }
    try:
        file_path = download_elastic(q, type_param, data, valid, logo_url)

        return send_file(file_path, as_attachment=True)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    

@app.route("/search/update/all", methods=["GET"])
@jwt_required
def start_task_update_with_search_all():
    # Extract arguments from the query parameters
    q = request.args.get("q", "")
    type_param = request.args.get('type', '').strip().lower() 
    if type_param == 'breach':
        response = search_breach1(q)
        subprocess.Popen(["python3", "breach1.py", q])
        subprocess.Popen(["python3", "breach2.py", q, 'username'])
        subprocess.Popen(["python3", "breach2.py", q, 'auto'])
    elif type_param == 'stealer':
        response = search_lcheck_stealer(q, "origin")
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "stealer1_update_only.py", q])
        subprocess.Popen(["python3", "stealer2.py", q])
    else:
        response = ResponseError("Please Specify Type",400)
    return jsonify(response), response['status']

@app.route("/search/update", methods=["GET"])
@jwt_required
def start_task_update_with_search():
    # Extract arguments from the query parameters
    q = request.args.get("q", "")
    size = min(int(request.args.get('size', 10)), max_query) 
    page = int(request.args.get('page', 1))
    type_param = request.args.get('type', '').strip().lower() 
    if type_param == 'breach':
        subprocess.Popen(["python3", "breach1.py", q])
        response = search_breach1(q)
    elif type_param == 'stealer':
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "stealer2.py", q])
        response = search_stealer2(q, page)
    else:
        response = ResponseError("Please Specify Type",400)
    return jsonify(response), response['status']

@app.route("/update", methods=["GET"])
@jwt_required
def start_task_update():
    # Extract arguments from the query parameters
    q = request.args.get("q", "")
    type_param = request.args.get('type', '').strip().lower() 
    if type_param == 'breach':
        subprocess.Popen(["python3", "breach1.py",q])
        subprocess.Popen(["python3", "breach2.py", q, 'username'])
        subprocess.Popen(["python3", "breach2.py", q, 'domain'])
        subprocess.Popen(["python3", "breach2.py", q, 'auto'])
    elif type_param == 'stealer':
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "stealer1_update_only.py", q])
        subprocess.Popen(["python3", "stealer2.py", q])
    elif type_param == 'all':
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "breach2.py", q, 'domain'])
        subprocess.Popen(["python3", "breach2.py", q, 'username'])
        subprocess.Popen(["python3", "breach2.py", q, 'auto'])
        subprocess.Popen(["python3", "breach1.py", q])
        subprocess.Popen(["python3", "stealer1_update_only.py", q])
        subprocess.Popen(["python3", "stealer2.py", q])
    else:
        return jsonify({"msg":"Please Specify Response"})
    response={"msg":"Updating DB Complete, please wait a few moment to get your full data"}
    return jsonify(response), 200

@app.route('/login', methods=['POST'])
def login_route():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if username == username_app and password == password_app:
        token = jwt.encode({
            "user": username,
            "exp": datetime.datetime.now() + datetime.timedelta(hours=7*24)
        }, JWT_SECRET_KEY, algorithm="HS256")
        return {"token": token}, 200
    else:
        return {"error": "Invalid credentials"}, 401
    
@app.route('/mark-as-valid/<id>', methods=['PUT'])
@jwt_required
def mark_as_valid(id):
    data = request.json
    valid = data.get('valid')    
    if valid is not None and not isinstance(valid, bool):          
        return jsonify({"msg": "Valid must be boolean or null"}), 400
    response = update_valid(id, valid)
    return jsonify(response), response['status']

@app.route('/mark-as-valid', methods=['POST'])
@jwt_required
def mark_as_valid_bulk():
    data = request.json
    if not isinstance(data, dict):
        return jsonify({"msg": "Request body must be a dictionary of id:valid pairs"}), 400
        
    response = update_valid_bulk(data)
    return jsonify(response), response['status']


@app.route('/db-info', methods=['GET'])
@jwt_required
def database():
    with open("info.json", 'r') as file:
        data = json.load(file)
        return jsonify(data)

@app.route('/db-info-all', methods=['GET'])
@jwt_required
def database_all():
    with open("databases.json", 'r', encoding='utf-8') as file:
        data = json.load(file)
        return jsonify(data)

@app.route('/db-info-stealer', methods=['GET'])
@jwt_required
def database_stealer():
    with open("databases-list.json", 'r', encoding='utf-8') as file:
        data = json.load(file)
        return jsonify(data)

@app.route('/update-db-stealer', methods=['POST'])
@jwt_required
def update_database_stealer():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files are allowed"}), 400

    # Save uploaded file temporarily
    uploaded_file = 'databases-list.json'
    filename = secure_filename(uploaded_file)
    file.save(filename)

    try:
        # Reopen the file to ensure it's read from the beginning
        with open(filename, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)

        with open('databases-list.json', 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, indent=4)

        return jsonify({"message": "Database updated successfully"}), 200
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Error parsing JSON {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/db-summary', methods=['GET'])
@jwt_required
def db_summary():
    with open("summary_db.json", 'r', encoding='utf-8') as file:
        data = json.load(file)
        return jsonify(data)

@app.route('/update-db-summary', methods=['POST'])
@jwt_required
def update_database_summary():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files are allowed"}), 400

    # Save uploaded file temporarily
    uploaded_file = 'summary_db.json'
    filename = secure_filename(uploaded_file)
    file.save(filename)

    try:
        # Reopen the file to ensure it's read from the beginning
        with open(filename, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)

        with open('databases-list.json', 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, indent=4)

        return jsonify({"message": "Database updated successfully"}), 200
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Error parsing JSON {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500    

@app.route('/top-10', methods=['GET'])
@jwt_required
def top_10_pass():
    with open("toppass.json", 'r', encoding='utf-8') as file:
        data = json.load(file)
        return jsonify(data)

@app.route('/update-top-10', methods=['POST'])
@jwt_required
def update_database_top10_pass():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files are allowed"}), 400

    # Save uploaded file temporarily
    uploaded_file = 'toppass.json'
    filename = secure_filename(uploaded_file)
    file.save(filename)

    try:
        # Reopen the file to ensure it's read from the beginning
        with open(filename, 'r', encoding='utf-8') as f:
            parsed_data = json.load(f)

        with open('databases-list.json', 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, indent=4)

        return jsonify({"message": "Database updated successfully"}), 200
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Error parsing JSON {e}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/update-db', methods=['POST'])
@jwt_required
def update_database():
    if 'file' not in request.files:
        print(request.files)
        return jsonify({"error": "No file provided"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
        
    if not file.filename.endswith('.html'):
        return jsonify({"error": "Only HTML files are allowed"}), 400

    # Save uploaded file temporarily
    uploaded_file='database_list.html'
    filename = secure_filename(uploaded_file)
    file.save(filename)
    
    try:
        # Parse HTML and save to JSON
        parsed_data = parse_html_to_json(uploaded_file)
        save_to_json(parsed_data)
        
        # Clean up temporary file
        os.remove(filename)
        
        return jsonify({
            "message": "Database updated successfully",
            "entries_processed": len(parsed_data)
        }), 200
        
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({"error": str(e)}), 500

@app.route('/logo', methods=['GET'])
def serve_logo():
    try:
        return send_file('darkspyder-dashboard-1.png', mimetype='image/png')
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/register', methods=['POST'])
def register():
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.json or {}
        else:
            data = request.form.to_dict()
        
        email = data.get('email', '').strip()
        username = data.get('username', '').strip()
        
        # Generate access ID (18-22 characters, alphanumeric)
        length = random.randint(18, 22)
        characters = string.ascii_letters + string.digits
        access_id = ''.join(random.choice(characters) for _ in range(length))
        
        # Check if access_id already exists (very unlikely but good practice)
        accounts_collection = mongo_db.get_accounts_collection()
        while accounts_collection.find_one({"access_id": access_id}):
            access_id = ''.join(random.choice(characters) for _ in range(length))
        
        # Check if email already exists
        if email:
            if accounts_collection.find_one({"email": email}):
                return jsonify({"error": "Email already exists"}), 400
        
        # Check if username already exists (if provided)
        if username:
            if accounts_collection.find_one({"username": username}):
                return jsonify({"error": "Username already exists"}), 400
        
        secret = generate_secret()
        
        # Save to MongoDB
        account_data = {
            "access_id": access_id,
            "email": email,
            "created_at": datetime.datetime.now(),
            "last_login": None,
            "login_history": [],  # Initialize empty login history array
            "secret": secret,
            "using_totp": True,
            "is_admin": False,
            "is_active": True
        }
        
        # Add optional username if provided
        if username:
            account_data["username"] = username
        
        result = accounts_collection.insert_one(account_data)
        user_id = str(result.inserted_id)
        provision_url, secret = generate_url_otp(secret=secret, username=user_id)
        
        if result.inserted_id:
            response_data = {
                "access_id": access_id,
                "email": email,
                "provision_url": provision_url,
                "message": "Account registered successfully"
            }
            
            # Include username in response if provided
            if username:
                response_data["username"] = username
                
            return jsonify(response_data), 200
        else:
            return jsonify({"error": "Failed to register account"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/new-login', methods=['POST'])
def new_login():
    try:
        data = request.json
        access_id = data.get('access_id')
        token = data.get('totp')
        
        if not access_id:
            return jsonify({"error": "Access ID is required"}), 400
    
        if not token:
            return jsonify({"error": "TOTP token is required"}), 400
        
        # Check if access_id exists in MongoDB
        accounts_collection = mongo_db.get_accounts_collection()
        account = accounts_collection.find_one({"access_id": access_id})
        
        if not account:
            return jsonify({"error": "Invalid access ID"}), 401
        
        # totp_valid = verify_totp(account['secret'],token)
        # if not totp_valid:
        #     return jsonify({"error": "Invalid TOTP token"}), 401

        # Get current timestamp
        current_time = datetime.datetime.now()
        
        # Update last login and append to login history
        accounts_collection.update_one(
            {"access_id": access_id},
            {
                "$set": {"last_login": current_time},
                "$push": {
                    "login_history": {
                        "timestamp": current_time,
                        "ip_address": request.remote_addr
                    }
                }
            }
        )
        
        # Prepare JWT payload
        jwt_payload = {
            "user_id": str(account["_id"]),  # Convert ObjectId to string
            "exp": datetime.datetime.now() + datetime.timedelta(hours=1)
        }
        
        # Add username to JWT if exists
        if account.get("username"):
            jwt_payload["username"] = account["username"]
        
        # Add is_admin to JWT if user is admin
        if account.get("is_admin"):
            jwt_payload["is_admin"] = True
        
        # Generate JWT token
        token = jwt.encode(jwt_payload, JWT_SECRET_KEY, algorithm="HS256")
        
        return jsonify({
            "token": token,
            "message": "Login successful"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/pricing',methods=['GET'])
def get_pricing():
    try:
        pricing_collection = mongo_db.get_pricings_collection()
        pricings = pricing_collection.find({})
        new_pricings = list(pricings.limit(0))
        return jsonify({
            "data":new_pricings,
            "message": "Success Get Pricing"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}, 500)


@app.route('/asset-list',methods=['POST'])
@jwt_required
def get_asset_list():
    try:
        data = request.json
        idPricing = data.get('idPricing')
        plan = data.get('plan')
        if not idPricing or not plan:
            return jsonify({"error": "idPricing and plan are required"}), 400
            
        allowed_plans = ['monthly', 'quarterly', 'yearly']
        if plan not in allowed_plans:
            return jsonify({"error": f"Invalid plan. Allowed values: {allowed_plans}"}), 400

        pricing_collection = mongo_db.get_pricings_collection()
        pricing = pricing_collection.find_one({"_id": ObjectId(idPricing)})

        if not pricing:
            return jsonify({"error": "Pricing not found"}), 404

        # Pastikan plan tersedia di pricing
        if plan not in pricing:
            return jsonify({"error": f"Plan '{plan}' not found in pricing data"}), 400
        
        price_value =  pricing[plan]
        try:
            price_value = float(price_value)
        except (ValueError, TypeError):
            return jsonify({"error": "Contact Sales"}), 400
        
        # tax = 1.2%
        tax=101.2
        price = price_value * tax / 100
        list = payment.get_list(price)
        return jsonify({
            "data":list,
            "message": "Success Get Asset List"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/create-invoice',methods=['POST'])
@jwt_required
def create_invoice():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}
    
        data = request.json
        idPricing = data.get('idPricing')
        plan = data.get('plan')
        if not idPricing or not plan:
            return jsonify({"error": "idPricing and plan are required"}), 400
            
        allowed_plans = ['monthly', 'quarterly', 'yearly']
        if plan not in allowed_plans:
            return jsonify({"error": f"Invalid plan. Allowed values: {allowed_plans}"}), 400

        pricing_collection = mongo_db.get_pricings_collection()
        filter_pricing = {"_id": ObjectId(idPricing)}
        pricing = pricing_collection.find_one(filter_pricing)
        
        if not pricing:
            return jsonify({"error": "Pricing not found"}), 404

        # Pastikan plan tersedia di pricing
        if plan not in pricing:
            return jsonify({"error": f"Plan '{plan}' not found in pricing data"}), 400
        

        
        price_value =  pricing[plan]
        try:
            price_value = float(price_value)
        except (ValueError, TypeError):
            return jsonify({"error": "Contact Sales"}), 400
        
        # tax = 1.2%
        tax=101.2
        price = price_value * tax / 100
        list = payment.create_invoice(price)

        new_data = {
            "id":idPricing, 
            "plan":plan,
            "domain":pricing['domain'],
            "invoice":list
            }
        updated_account = accounts_collection.update_one(filter, {"$push": {"transaction":new_data}})

        if updated_account.matched_count == 0:
            return jsonify({"error": "Error update plan in your account"}), 404
        
        return jsonify({
            "data":list,
            "message": "Success Create Payment"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/create-payment',methods=['POST'])
@jwt_required
def create_payment():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}


        data = request.json
        InvoiceId = data.get("invoiceId")
        AssetCode = data.get("assetCode")
        BlockchainCode = data.get("blockchainCode")
        IsEvm = data.get("isEvm")

        required_fields = ["invoiceId", "assetCode", "blockchainCode", "isEvm"]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        
        array_filters=[{"elem.invoice.Id": InvoiceId}]

        list = payment.create_payment(InvoiceId, AssetCode, BlockchainCode, IsEvm)
        set_data = {"$set": {"transaction.$[elem].payment": list}}
        
        result = accounts_collection.update_one(
            filter,
            set_data,
            array_filters=array_filters
        )

        if result.modified_count == 0:
            return jsonify({"error": "Error update plan in your account"}), 404

        return jsonify({
            "data":list,
            "message": "Success Create Payment"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/my-payment',methods=['GET'])
@jwt_required
def my_payment():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        account = accounts_collection.find_one({"_id": ObjectId(user_id)})
        list = account.get('transaction',[])
        
        return jsonify({
            "data":list,
            "message": "Success Get My Payment"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/my-plan',methods=['GET'])
@jwt_required
def my_plan():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        account = accounts_collection.find_one(
            {"_id": ObjectId(user_id)}, 
            {"_id": 0, "myPlan":1}
            )
        list = account.get('myPlan',{})
        list['expired']=str(list['expired'])
        return jsonify({
            "data":list,
            "message": "Success Get My Plan"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/register-domain',methods=['POST'])
@jwt_required
def register_domain():
    try:
        data = request.json
        selected_domains = data.get('selected_domains')
        if not isinstance(selected_domains, list) or not all(isinstance(item, str) for item in selected_domains):
            raise Exception("selected_domain must be array of string")
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}
        account = accounts_collection.find_one(
            filter, 
            {"_id": 0, "myPlan":1}
        )
        plan_info  = account.get('myPlan', None)
        if plan_info is None:
            raise Exception("User does not have an active plan")
        if plan_info ['expired']<datetime.datetime.now():
            return jsonify({"error": "Your plan has expired"}), 403
        if plan_info['domain'] != 'unlimited':
            domain_count = int(plan_info['domain'])
            if len(selected_domains)>domain_count:
                return jsonify({"error": "You have exceeded the number of domains allowed in your plan"}), 403
        set_data = {
            "$set": {
                "myPlan.registered_domain": selected_domains
                }
        }
        accounts_collection.update_one(
            filter,
            set_data
        )

        return jsonify({
            "data": None,
            "message": "Success Register Domain"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/register-breach-domain',methods=['POST'])
@jwt_required
def register_breach_domain():
    try:
        data = request.json
        selected_domains = data.get('selected_domains')
        if not isinstance(selected_domains, list) or not all(isinstance(item, str) for item in selected_domains):
            raise Exception("selected_domains must be an array of strings")
        
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        
        accounts_collection = mongo_db.get_accounts_collection()
        filter_user = {"_id": ObjectId(user_id)}
        
        account = accounts_collection.find_one(
            filter_user, 
            {"_id": 0, "myPlan": 1}
        )
        
        plan_info = account.get('myPlan', None)
        if plan_info is None:
            raise Exception("User does not have an active plan")
        
        if plan_info.get('expired') < datetime.datetime.now() and plan_info.get('expired') != 'unlimited':
            return jsonify({"error": "Your plan has expired"}), 403
        
        if plan_info.get('domain') != 'unlimited':
            return jsonify({"error": "This feature is only available for unlimited plan users"}), 403

        set_data = {
            "$set": {
                "myPlan.registered_breach_domain": selected_domains
            }
        }
        accounts_collection.update_one(filter_user, set_data)

        return jsonify({"message": "Breach domains registered successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/my-domain',methods=['GET'])
@jwt_required
def get_my_domain():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}
        account = accounts_collection.find_one(
            filter, 
            {"_id": 0, "myPlan":1}
        )
        plan_info  = account.get('myPlan', None)
        if plan_info is None:
            raise Exception("User does not have an active plan")
        if plan_info ['expired']<datetime.datetime.now():
            return jsonify({"error": "Your plan has expired"}), 403
        
        my_domain = plan_info['registered_domain']

        return jsonify({
            "data": my_domain,
            "message": "Success Get Domain"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/my-breach',methods=['GET'])
@jwt_required
def get_my_breach():
    try:
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}
        account = accounts_collection.find_one(
            filter, 
            {"_id": 0, "myPlan":1}
        )
        plan_info  = account.get('myPlan', None)
        if plan_info is None:
            raise Exception("User does not have an active plan")
        if plan_info ['expired']<datetime.datetime.now():
            return jsonify({"error": "Your plan has expired"}), 403
        
        my_breach = plan_info['breach']
        my_current_breach = plan_info['current_breach']
        list = {
            "breach": my_breach,
            "current_breach": my_current_breach
        }
        return jsonify({
            "data": list,
            "message": "Success Get Breach"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get-payment/<id>',methods=['GET'])
@jwt_required
def my_payment_detail(id):
    try:
        type = request.args.get('type','payment')
        if not type:
            return jsonify({"error": "Type is required"}), 400

        allowed_types = ['payment', 'invoice']
        if type not in allowed_types:
            return jsonify({"error": f"Invalid type. Allowed values: {allowed_types}"}), 400

        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        accounts_collection = mongo_db.get_accounts_collection()
        filter = {"_id": ObjectId(user_id)}
        if type == "payment":
            filter['transaction.payment.Id']=id
        elif type == "invoice":
            filter['transaction.invoice.Id']=id
        selected_filter = {"_id": 0, "transaction.$": 1}  
        account = accounts_collection.find_one(filter, selected_filter)
        if account == None:
            return jsonify({"error": "Transaction Not Found"}), 404
        list = account.get('transaction',[])

        return jsonify({
            "data":list,
            "message": "Success Get My Payment"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/process-payment',methods=['POST'])
@jwt_required
def process_payment():
    try:
        accounts_collection = mongo_db.get_accounts_collection()

        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']

        data = request.json
        PaymentId = data["paymentId"]
        
        required_fields = ["paymentId"]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        
        filter = {"_id": ObjectId(user_id), "transaction.payment.Id": PaymentId}
        user = accounts_collection.find_one(
            filter,
            {"_id": 0, "transaction.$": 1}
        )
        current_payment = user.get("transaction", None)
        if current_payment is None:
            return jsonify({"error": "Transaction Not Found"}), 404
        current_payment=current_payment[0]

        payment_data = payment.get_payment(PaymentId)
        if payment_data['Status']==0:
            return jsonify({"error": "Plan is not Paid yet"}), 400
        
        set_data = {
            "$set": {
                "transaction.$[elem].payment": payment_data
            }
        }

        if payment_data["Status"]==100 and current_payment["payment"]["Status"]==0:
            now = datetime.datetime.now()
            if current_payment['plan']=='monthly':
                expired = now + relativedelta(months=1)
            elif current_payment['plan']=='quarterly':
                expired = now + relativedelta(months=3)
            elif current_payment['plan']=='yearly':
                expired = now + relativedelta(years=1)

            
            set_data['$set']['myPlan']={
                "plan":current_payment['id'],
                "expired": expired,
                "domain":current_payment['domain'],
                "breach":current_payment['breach'],
                "current_breach": "0"
            }
        else:
            return jsonify({"error" : "Please Finish Your Payment"}, 403)
        
        array_filters=[{"elem.payment.Id": payment_data['Id']}]
        result = accounts_collection.update_one(
            filter,
            set_data,
            array_filters = array_filters
            )

        if result.matched_count == 0:
            return jsonify({"error": "Payment ID not found for current user"}), 404

        return jsonify({
            "data":payment_data,
            "message": "Success Get Payment Data"
            }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/background-check", methods=["POST"])
@jwt_required
def cek_jadwal():
    token = request.headers.get("Authorization", None)
    if not token:
        return jsonify({"error": "Authorization token missing"}), 400
    data = request.json
    paymentId = data.paymentId
    thread = threading.Thread(target=background_task, args=(token,paymentId,))
    thread.daemon = True
    thread.start()
    return jsonify({"message": "Scheduled background job started with token"}), 200


@app.route("/do-search", methods=["GET"])
@jwt_required
@domain_validation
def start_do_search():
    q = request.args.get('q', "")
    type_param = request.args.get('type', '').strip().lower() 
    page = int(request.args.get('page', 1))
    size = request.args.get('size', 10)
    if (size != "all"):
        try:
            size = int(size)
        except ValueError:
            return jsonify({"error": "Invalid size parameter"}), 400
            
    username = request.args.get('username')  
    # Handle both unlimited and limited domain plans
    if hasattr(request, 'plan_info') and request.plan_info:
        plan_info = request.plan_info
        if plan_info['domain'] != 'unlimited':
            registered_domains = plan_info.get('registered_domain', [])
            if len(registered_domains) == 0:
                return jsonify({"error": "No domains registered. Please register domains first using /register-domain"}), 403
            first_domain = registered_domains[0]
            domain = request.args.get('domain', first_domain)
        else:
            domain = request.args.get('domain', None)
    else:
        domain = request.args.get('domain', None)

    password = request.args.get('password')
    
    valid = request.args.get('valid', '').strip().lower()
    data = {
        "username": username,
        "domain": domain,
        "password": password
    }

    response = search_elastic(q, type_param, page, size, data, valid)
    
    # Handle the size limit response
    if response.get("status") == 400:
        return jsonify(response), 400
        
    return jsonify(response), response.get("status", 200)
@app.route("/do-search/download", methods=["GET"])
@jwt_required
@domain_validation
def download_do_search():
    q = request.args.get('q', "")
    type_param = request.args.get('type', '').strip().lower()
    username = request.args.get('username')
    # Handle both unlimited and limited domain plans
    if hasattr(request, 'registered_domain') and request.registered_domain:
        first_domain = request.registered_domain[0]
        domain = request.args.get('domain', first_domain)    
    password = request.args.get('password')
    valid = request.args.get('valid', '').strip().lower()
    logo_url = request.args.get('logo_url', '').strip().lower()

    data = {
        "username": username,
        "domain": domain,
        "password": password
    }
    try:
        file_path = download_elastic(q, type_param, data, valid, logo_url)

        return send_file(file_path, as_attachment=True)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    

@app.route("/do-search/update/all", methods=["GET"])
@jwt_required
# @domain_validation
def start_task_update_with_do_search_all():
    # Extract arguments from the query parameters
    # Handle both unlimited and limited domain plans
    if hasattr(request, 'registered_domain') and request.registered_domain:
        first_domain = request.registered_domain[0]
        # q = request.args.get('domain', first_domain)
        q = request.args.get('q', "")
    type_param = request.args.get('type', '').strip().lower() 
    if type_param == 'breach':
        response = search_breach1(q)
        subprocess.Popen(["python3", "breach1.py", q])
        subprocess.Popen(["python3", "breach2.py", q, 'username'])
        subprocess.Popen(["python3", "breach2.py", q, 'auto'])
    elif type_param == 'stealer':
        response = search_lcheck_stealer(q, "origin")
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "stealer1_update_only.py", q])
        subprocess.Popen(["python3", "stealer2.py", q])
    else:
        response = ResponseError("Please Specify Type",400)
    return jsonify(response), response['status']

@app.route("/do-search/update", methods=["GET"])
@jwt_required
# @domain_validation
def start_task_update_with_do_search():
    # Extract arguments from the query parameters
    # Handle both unlimited and limited domain plans
    if hasattr(request, 'registered_domain') and request.registered_domain:
        first_domain = request.registered_domain[0]
        # q = request.args.get('domain', first_domain)
        q = request.args.get('q', "")
    size = min(int(request.args.get('size', 10)), max_query) 
    page = int(request.args.get('page', 1))
    type_param = request.args.get('type', '').strip().lower() 
    if type_param == 'breach':
        subprocess.Popen(["python3", "breach1.py", q])
        response = search_breach1(q)
    elif type_param == 'stealer':
        subprocess.Popen(["python3", "breach2.py", q, 'origin'])
        subprocess.Popen(["python3", "stealer2.py", q])
        response = search_stealer2(q, page)
    else:
        response = ResponseError("Please Specify Type",400)
    return jsonify(response), response['status']

@app.route("/use-breach", methods=["POST"])
@jwt_required
def use_breach():
    """
    Endpoint to use breach quota without any parameters.
    Handles:
    - Checking if user has active plan
    - Validating breach quota limits
    - Incrementing current_breach counter
    """
    try:
        # Get user information from JWT token
        token = request.headers.get("Authorization")
        decoded = get_jwt_data(token)
        user_id = decoded['user_id']
        
        # Get user's plan information from MongoDB
        accounts_collection = mongo_db.get_accounts_collection()
        account = accounts_collection.find_one(
            {"_id": ObjectId(user_id)}, 
            {"_id": 1, "myPlan": 1}
        )
        
        if not account:
            return jsonify({"error": "User account not found"}), 404
            
        plan_info = account.get('myPlan', {})
        if not plan_info:
            return jsonify({"error": "User does not have an active plan"}), 403
            
        # Check if plan has expired
        if plan_info.get('expired') < datetime.datetime.now() and plan_info.get('expired') != 'unlimited':
            return jsonify({"error": "Your plan has expired"}), 403
            
        # Check breach quota
        breach = plan_info.get('breach', 0)
        
        
        # Handle unlimited breach quota
        if breach == 'unlimited':
            return jsonify({
                "message": "You have unlimited breach quota",
                "status": "success",
                "current_breach": current_breach,
                "breach_limit": "unlimited"
            }), 200
        
        # Handle limited breach quota
        breach = int(breach)
        current_breach = int(plan_info.get('current_breach', 0))
        
        # Check if user has exceeded breach quota
        if current_breach >= breach:
            return jsonify({"error": "You have exceeded the number of breach allowed in your plan"}), 403
            
        # Increment current_breach counter
        set_data = {
            "$set": {
                "myPlan.current_breach": str(current_breach + 1)
            }
        }
        filter = {"_id": ObjectId(user_id)}
        accounts_collection.update_one(filter, set_data)
        
        return jsonify({
            "message": "Breach quota used successfully",
            "status": "success",
            "current_breach": current_breach + 1,
            "breach_limit": breach
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== ADMIN USER MANAGEMENT ENDPOINTS ====================

def admin_required(f):
    """Middleware untuk memastikan hanya admin yang bisa akses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Missing token"}), 401
        try:
            decoded = get_jwt_data(token)
            user_id = decoded['user_id']
            
            # Check if user is admin (bisa disesuaikan dengan logic admin Anda)
            accounts_collection = mongo_db.get_accounts_collection()
            account = accounts_collection.find_one({"_id": ObjectId(user_id)})
            
            if not account or not account.get('is_admin', False):
                return jsonify({"error": "Admin access required"}), 403
                
            request.admin_user_id = user_id
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 401
    return decorated_function

# ==================== CRUD USER ENDPOINTS ====================

@app.route('/admin/users', methods=['GET'])
@admin_required
def get_all_users():
    """Get all users with pagination"""
    try:
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 10)), 100)
        search = request.args.get('search', '').strip()
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Build query
        query = {}
        if search:
            search_conditions = [
                {"access_id": {"$regex": search, "$options": "i"}}
            ]
            
            # Add email and username search conditions
            search_conditions.extend([
                {"email": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}}
            ])
            
            query = {"$or": search_conditions}
        
        # Get total count
        total = accounts_collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * size
        users = list(accounts_collection.find(
            query,
            {
                "_id": 1,
                "access_id": 1,
                "email": 1,
                "username": 1,
                "created_at": 1,
                "last_login": 1,
                "myPlan": 1,
                "is_admin": 1,
                "is_active": 1
            }
        ).skip(skip).limit(size))
        
        # Convert ObjectId to string for JSON serialization
        for user in users:
            if '_id' in user:
                user['_id'] = str(user['_id'])
        
        return jsonify({
            "data": users,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            },
            "message": "Success get all users"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>', methods=['GET'])
@admin_required
def get_user_by_id(user_id):
    """Get specific user by ID"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        user = accounts_collection.find_one({"_id": obj_id})
        
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        return jsonify({
            "data": user,
            "message": "Success get user"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user (admin only)"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        username = data.get('username', '').strip()
        is_admin = data.get('is_admin', False)
        is_active = data.get('is_active', True)
        
        if not email:
            return jsonify({"error": "Email is required"}), 400
            
        # Generate access ID
        length = random.randint(18, 22)
        characters = string.ascii_letters + string.digits
        access_id = ''.join(random.choice(characters) for _ in range(length))
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if email already exists
        if accounts_collection.find_one({"email": email}):
            return jsonify({"error": "Email already exists"}), 400
        
        # Check if username already exists (if provided)
        if username:
            if accounts_collection.find_one({"username": username}):
                return jsonify({"error": "Username already exists"}), 400
            
        # Check if access_id already exists
        while accounts_collection.find_one({"access_id": access_id}):
            access_id = ''.join(random.choice(characters) for _ in range(length))
        
        secret = generate_secret()
        
        # Create user data
        user_data = {
            "access_id": access_id,
            "email": email,
            "created_at": datetime.datetime.now(),
            "last_login": None,
            "login_history": [],
            "secret": secret,
            "using_totp": True,
            "is_admin": is_admin,
            "is_active": is_active,
            "created_by": request.admin_user_id
        }
        
        # Add optional username if provided
        if username:
            user_data["username"] = username
        
        result = accounts_collection.insert_one(user_data)
        user_id = str(result.inserted_id)
        provision_url, secret = generate_url_otp(secret=secret, username=user_id)
        
        response_data = {
            "user_id": user_id,
            "access_id": access_id,
            "email": email,
            "provision_url": provision_url,
            "is_admin": is_admin,
            "is_active": is_active
        }
        
        # Include username in response if provided
        if username:
            response_data["username"] = username
        
        return jsonify({
            "data": response_data,
            "message": "User created successfully"
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """Update user information"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        data = request.json
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prepare update data
        update_data = {}
        allowed_fields = ['email', 'username', 'is_admin', 'is_active']
        
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        if not update_data:
            return jsonify({"error": "No valid fields to update"}), 400
        
        # Check email uniqueness if email is being updated
        if 'email' in update_data and update_data['email']:
            existing_user = accounts_collection.find_one({
                "email": update_data['email'],
                "_id": {"$ne": obj_id}
            })
            if existing_user:
                return jsonify({"error": "Email already exists"}), 400
        
        # Check username uniqueness if username is being updated
        if 'username' in update_data and update_data['username']:
            existing_user = accounts_collection.find_one({
                "username": update_data['username'],
                "_id": {"$ne": obj_id}
            })
            if existing_user:
                return jsonify({"error": "Username already exists"}), 400
        
        update_data['updated_at'] = datetime.datetime.now()
        update_data['updated_by'] = request.admin_user_id
        
        # Update user
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "No changes made"}), 400
            
        return jsonify({
            "message": "User updated successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """Delete user (soft delete by setting is_active to False)"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Soft delete - set is_active to False
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": datetime.datetime.now(),
                    "deleted_by": request.admin_user_id
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to delete user"}), 400
            
        return jsonify({
            "message": "User deleted successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== ASSIGN USER TO PACKAGE ENDPOINTS ====================

@app.route('/admin/users/<user_id>/assign-package', methods=['POST'])
@admin_required
def assign_user_to_package(user_id):
    """Assign existing user to specific package"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        data = request.json
        idPricing = data.get('idPricing')
        plan = data.get('plan')
        
        if not idPricing or not plan:
            return jsonify({"error": "idPricing and plan are required"}), 400
            
        allowed_plans = ['monthly', 'quarterly', 'yearly']
        if plan not in allowed_plans:
            return jsonify({"error": f"Invalid plan. Allowed values: {allowed_plans}"}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        pricing_collection = mongo_db.get_pricings_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Validate pricing ObjectId
        pricing_obj_id, error = validate_object_id(idPricing)
        if error:
            return jsonify({"error": f"Invalid pricing ID: {error}"}), 400
        
        # Check if pricing exists
        pricing = pricing_collection.find_one({"_id": pricing_obj_id})
        if not pricing:
            return jsonify({"error": "Pricing not found"}), 404
        
        # Check if plan exists in pricing
        if plan not in pricing:
            return jsonify({"error": f"Plan '{plan}' not found in pricing data"}), 400
        
        # Calculate expiration date
        now = datetime.datetime.now()
        if plan == 'monthly':
            expired = now + relativedelta(months=1)
        elif plan == 'quarterly':
            expired = now + relativedelta(months=3)
        elif plan == 'yearly':
            expired = now + relativedelta(years=1)
        
        # Create plan data
        plan_data = {
            "plan": idPricing,
            "expired": expired,
            "domain": pricing['domain'],
            "breach": pricing.get('breach', 'unlimited'),
            "current_breach": "0",
            "registered_domain": [],
            "registered_breach_domain": [],
            "assigned_at": now,
            "assigned_by": request.admin_user_id
        }
        
        # Update user with new plan
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {"$set": {"myPlan": plan_data}}
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to assign package"}), 400
        
        return jsonify({
            "data": {
                "user_id": user_id,
                "plan": plan_data,
                "pricing_info": {
                    "id": idPricing,
                    "domain": pricing['domain'],
                    "description": pricing.get('description', ''),
                    "features": pricing.get('features', [])
                }
            },
            "message": "Package assigned successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>/extend-package', methods=['POST'])
@admin_required
def extend_user_package(user_id):
    """Extend user's current package"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        data = request.json
        extend_months = data.get('extend_months', 1)
        
        # Convert to int if it's a string number
        try:
            extend_months = int(extend_months)
        except (ValueError, TypeError):
            return jsonify({"error": "extend_months must be a valid integer"}), 400
        
        if extend_months <= 0:
            return jsonify({"error": "extend_months must be a positive integer"}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists and has a plan
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        current_plan = user.get('myPlan')
        if not current_plan:
            return jsonify({"error": "User has no active plan"}), 400
        
        # Extend the expiration date
        current_expired = current_plan.get('expired')
        if isinstance(current_expired, str):
            current_expired = datetime.datetime.fromisoformat(current_expired.replace('Z', '+00:00'))
        
        new_expired = current_expired + relativedelta(months=extend_months)
        
        # Update the plan
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "myPlan.expired": new_expired,
                    "myPlan.extended_at": datetime.datetime.now(),
                    "myPlan.extended_by": request.admin_user_id,
                    "myPlan.extension_months": extend_months
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to extend package"}), 400
        
        return jsonify({
            "data": {
                "user_id": user_id,
                "old_expired": str(current_expired),
                "new_expired": str(new_expired),
                "extension_months": extend_months
            },
            "message": "Package extended successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>/remove-package', methods=['POST'])
@admin_required
def remove_user_package(user_id):
    """Remove user's current package"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Remove the plan
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {
                "$unset": {"myPlan": ""},
                "$set": {
                    "package_removed_at": datetime.datetime.now(),
                    "package_removed_by": request.admin_user_id
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to remove package"}), 400
        
        return jsonify({
            "message": "Package removed successfully"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== SETUP ENDPOINTS ====================

@app.route('/setup/create-first-admin', methods=['POST'])
def create_first_admin():
    """Create first admin user (no authentication required)"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        username = data.get('username', '').strip()
        
        if not email:
            return jsonify({"error": "Email is required"}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if any admin already exists
        existing_admin = accounts_collection.find_one({"is_admin": True})
        if existing_admin:
            return jsonify({"error": "Admin user already exists"}), 400
        
        # Check if email already exists
        if accounts_collection.find_one({"email": email}):
            return jsonify({"error": "Email already exists"}), 400
        
        # Check if username already exists (if provided)
        if username:
            if accounts_collection.find_one({"username": username}):
                return jsonify({"error": "Username already exists"}), 400
        
        # Generate access ID
        length = random.randint(18, 22)
        characters = string.ascii_letters + string.digits
        access_id = ''.join(random.choice(characters) for _ in range(length))
        
        # Check if access_id already exists
        while accounts_collection.find_one({"access_id": access_id}):
            access_id = ''.join(random.choice(characters) for _ in range(length))
        
        secret = generate_secret()
        
        # Create admin user data
        admin_data = {
            "access_id": access_id,
            "email": email,
            "created_at": datetime.datetime.now(),
            "last_login": None,
            "login_history": [],
            "secret": secret,
            "using_totp": True,
            "is_admin": True,
            "is_active": True,
            "created_by": "system"
        }
        
        # Add optional username if provided
        if username:
            admin_data["username"] = username
        
        result = accounts_collection.insert_one(admin_data)
        user_id = str(result.inserted_id)
        provision_url, secret = generate_url_otp(secret=secret, username=user_id)
        
        response_data = {
            "user_id": user_id,
            "access_id": access_id,
            "email": email,
            "provision_url": provision_url,
            "is_admin": True,
            "is_active": True
        }
        
        # Include username in response if provided
        if username:
            response_data["username"] = username
        
        return jsonify({
            "data": response_data,
            "message": "First admin user created successfully"
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/setup/update-existing-users', methods=['POST'])
def update_existing_users():
    """Update existing users to add new fields (is_admin, is_active, email, username)"""
    try:
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Get all users that don't have the new fields
        users_to_update = accounts_collection.find({
            "$or": [
                {"is_admin": {"$exists": False}},
                {"is_active": {"$exists": False}},
                {"email": {"$exists": False}},
                {"username": {"$exists": False}}
            ]
        })
        
        updated_count = 0
        for user in users_to_update:
            update_data = {}
            
            # Add missing fields with default values
            if "is_admin" not in user:
                update_data["is_admin"] = False
            if "is_active" not in user:
                update_data["is_active"] = True
            if "email" not in user:
                # Generate a placeholder email if none exists
                update_data["email"] = f"user_{user['access_id']}@placeholder.com"
            if "username" not in user:
                # Username is optional, don't add placeholder
                pass
            
            if update_data:
                accounts_collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": update_data}
                )
                updated_count += 1
        
        return jsonify({
            "message": f"Updated {updated_count} users with new fields",
            "updated_count": updated_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>/make-admin', methods=['POST'])
@admin_required
def make_user_admin(user_id):
    """Make a user admin"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Update user to admin
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "is_admin": True,
                    "admin_granted_at": datetime.datetime.now(),
                    "admin_granted_by": request.admin_user_id
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to make user admin"}), 400
        
        return jsonify({
            "message": "User is now admin"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<user_id>/remove-admin', methods=['POST'])
@admin_required
def remove_user_admin(user_id):
    """Remove admin privileges from user"""
    try:
        # Validate ObjectId
        obj_id, error = validate_object_id(user_id)
        if error:
            return jsonify({"error": error}), 400
        
        accounts_collection = mongo_db.get_accounts_collection()
        
        # Check if user exists
        user = accounts_collection.find_one({"_id": obj_id})
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Prevent removing admin from self
        if user_id == request.admin_user_id:
            return jsonify({"error": "Cannot remove admin privileges from yourself"}), 400
        
        # Update user to remove admin
        result = accounts_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "is_admin": False,
                    "admin_removed_at": datetime.datetime.now(),
                    "admin_removed_by": request.admin_user_id
                }
            }
        )
        
        if result.modified_count == 0:
            return jsonify({"error": "Failed to remove admin privileges"}), 400
        
        return jsonify({
            "message": "Admin privileges removed"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== MONGODB CONNECTION ENDPOINTS ====================

@app.route('/admin/mongodb/status', methods=['GET'])
@admin_required
def mongodb_connection_status():
    """Check MongoDB connection status"""
    try:
        # Test connection
        mongo_db.client.admin.command('ping')
        
        # Get database info
        db_stats = mongo_db.db.command("dbStats")
        
        # Get collections info
        collections = mongo_db.db.list_collection_names()
        collections_info = []
        
        for collection_name in collections:
            collection = mongo_db.db[collection_name]
            count = collection.count_documents({})
            collections_info.append({
                "name": collection_name,
                "count": count
            })
        
        return jsonify({
            "status": "connected",
            "database": MONGO_DB_NAME,
            "database_stats": {
                "collections": db_stats.get("collections", 0),
                "data_size": db_stats.get("dataSize", 0),
                "storage_size": db_stats.get("storageSize", 0),
                "indexes": db_stats.get("indexes", 0)
            },
            "collections": collections_info,
            "message": "MongoDB connection successful"
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "disconnected",
            "error": str(e),
            "message": "MongoDB connection failed"
        }), 500

@app.route('/admin/mongodb/collections/<collection_name>', methods=['GET'])
@admin_required
def get_collection_data(collection_name):
    """Get data from specific MongoDB collection"""
    try:
        page = int(request.args.get('page', 1))
        size = min(int(request.args.get('size', 10)), 100)
        search = request.args.get('search', '').strip()
        
        collection = mongo_db.db[collection_name]
        
        # Build query
        query = {}
        if search:
            # Try to search in common fields
            query = {
                "$or": [
                    {"access_id": {"$regex": search, "$options": "i"}},
                    {"email": {"$regex": search, "$options": "i"}},
                    {"username": {"$regex": search, "$options": "i"}},
                    {"_id": {"$regex": search, "$options": "i"}}
                ]
            }
        
        # Get total count
        total = collection.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * size
        documents = list(collection.find(query).skip(skip).limit(size))
        
        return jsonify({
            "collection": collection_name,
            "data": documents,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            },
            "message": f"Success get data from {collection_name}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/mongodb/collections/<collection_name>/stats', methods=['GET'])
@admin_required
def get_collection_stats(collection_name):
    """Get statistics for specific MongoDB collection"""
    try:
        collection = mongo_db.db[collection_name]
        
        # Get collection stats
        stats = mongo_db.db.command("collStats", collection_name)
        
        # Get sample documents
        sample_docs = list(collection.find().limit(3))
        
        # Get field analysis
        pipeline = [
            {"$project": {"arrayofkeyvalue": {"$objectToArray": "$$ROOT"}}},
            {"$unwind": "$arrayofkeyvalue"},
            {"$group": {"_id": "$arrayofkeyvalue.k", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        field_analysis = list(collection.aggregate(pipeline))
        
        return jsonify({
            "collection": collection_name,
            "stats": {
                "count": stats.get("count", 0),
                "size": stats.get("size", 0),
                "avgObjSize": stats.get("avgObjSize", 0),
                "storageSize": stats.get("storageSize", 0),
                "totalIndexSize": stats.get("totalIndexSize", 0),
                "indexes": stats.get("nindexes", 0)
            },
            "sample_documents": sample_docs,
            "field_analysis": field_analysis,
            "message": f"Success get stats for {collection_name}"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/demo", methods=["GET"])
@jwt_required
def start_search_demo():
    q = request.args.get("q", "")
    # type_param = request.args.get('type', '').strip().lower() 
    type_param = "breach"  # Force type to breach only
    page = int(request.args.get('page', 1))
    size = request.args.get('size', 10)
    if (size != "all"):
        try:
            size = int(size)
        except ValueError:
            return jsonify({"error": "Invalid size parameter"}), 400
            
    username = request.args.get('username')  
    domain = request.args.get('domain')
    password = request.args.get('password')
    
    valid = request.args.get('valid', '').strip().lower()
    data = {
        "username": username,
        "domain": domain,
        "password": password
    }

    response = search_elastic(q, type_param, page, size, data, valid)
    
    # Handle the size limit response
    if response.get("status") == 400:
        return jsonify(response), 400
        
    return jsonify(response), response.get("status", 200)


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
