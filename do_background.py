from flask import Flask, jsonify, request
import subprocess, jwt, datetime
from breach1 import search_breach1
from breach2 import search_lcheck_stealer
from functools import wraps
from cred import username_app, password_app, JWT_SECRET_KEY
from es_config import search_elastic
from stealer2 import search_stealer2
from trait import ResponseError

app = Flask(__name__)

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
    size = min(int(request.args.get('size', 10)), max_query) 
    username = request.args.get('username')  
    domain = request.args.get('domain')
    data={
        "username":username,
        "domain":domain
        }

    response = search_elastic(q, type_param, page, size, data)
    return jsonify(response), 200


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
        subprocess.Popen(["python3", "breach2.py", q, 'domain'])
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
        try:
            response = search_stealer2(q, page)
        except:
            response = search_lcheck_stealer(q, "domain", size)
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
        subprocess.Popen(["python3", "breach2.py", q, 'domain'])
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


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)