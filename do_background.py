from flask import Flask, jsonify, request, send_file
import subprocess, jwt, datetime, json, os
from breach1 import search_breach1
from breach2 import search_lcheck_stealer
from functools import wraps
from cred import username_app, password_app, JWT_SECRET_KEY
from es_config import search_elastic, update_valid, update_valid_bulk, download_elastic
from stealer2 import search_stealer2
from trait import ResponseError
from parsing_db_to_json import parse_html_to_json, save_to_json
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './'


max_query=1000


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

    data = {
        "username": username,
        "domain": domain,
        "password": password
    }
    try:
        file_path = download_elastic(q, type_param, data, valid)

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
        response = search_lcheck_stealer(q, "domain")
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
        subprocess.Popen(["python3", "breach2.py", q, 'auto'])
    elif type_param == 'stealer':
        # subprocess.Popen(["python3", "breach2.py", q, 'domain'])
        subprocess.Popen(["python3", "stealer1_update_only.py", q])
        subprocess.Popen(["python3", "stealer2.py", q])
    elif type_param == 'all':
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

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)


