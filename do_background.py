from flask import Flask, jsonify, request, send_file
from flask.json.provider import DefaultJSONProvider
import subprocess, jwt, datetime, json, os, string, random, threading
from breach1 import search_breach1
from breach2 import search_lcheck_stealer
from functools import wraps
from cred import username_app, password_app, JWT_SECRET_KEY
from es_config import search_elastic, update_valid, update_valid_bulk, download_elastic
from stealer2 import search_stealer2
from trait import ResponseError
from parsing_db_to_json import parse_html_to_json, save_to_json
from werkzeug.utils import secure_filename
from init_mongo import mongo_db
from init_payment import payment
from bson import ObjectId, json_util
from handle_totp import generate_url_otp, verify_totp, generate_secret
from dateutil.relativedelta import relativedelta
from background_function import background_task

class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
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
            "exp": datetime.datetime.now() + datetime.timedelta(hours=1)
        }, JWT_SECRET_KEY, algorithm="HS256")
        return {"token": token}, 200
    else:
        return {"error": "Invalid credentials"}, 401
    
@app.route('/mark-as-valid/<id>', methods=['PUT'])
@jwt_required
def mark_as_valid(id):
    data = request.json
    valid = data.get('valid')    
    if not isinstance(valid, bool) and valid is not None:          
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
        # Generate access ID (18-22 characters, alphanumeric)
        length = random.randint(18, 22)
        characters = string.ascii_letters + string.digits
        access_id = ''.join(random.choice(characters) for _ in range(length))
        
        # Check if access_id already exists (very unlikely but good practice)
        accounts_collection = mongo_db.get_accounts_collection()
        while accounts_collection.find_one({"access_id": access_id}):
            access_id = ''.join(random.choice(characters) for _ in range(length))
        
        secret = generate_secret()
        # Save to MongoDB
        account_data = {
            "access_id": access_id,
            "created_at": datetime.datetime.now(),
            "last_login": None,
            "login_history": [],  # Initialize empty login history array,
            "secret":secret,
            "using_totp": True
        }
        
        result = accounts_collection.insert_one(account_data)
        user_id = str(result.inserted_id)
        provision_url, secret = generate_url_otp(secret=secret,username=user_id)
        
        if result.inserted_id:
            return jsonify({
                "access_id": access_id,
                "provision_url": provision_url,
                "message": "Account registered successfully"
            }), 200
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
        
        totp_valid = verify_totp(account['secret'],token)
        if not totp_valid:
            return jsonify({"error": "Invalid TOTP token"}), 401

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
        
        # Generate JWT token with user_id (MongoDB _id)
        token = jwt.encode({
            "user_id": str(account["_id"]),  # Convert ObjectId to string
            "exp": datetime.datetime.now() + datetime.timedelta(hours=1)
        }, JWT_SECRET_KEY, algorithm="HS256")
        
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
@domain_validation
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
@domain_validation
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

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
