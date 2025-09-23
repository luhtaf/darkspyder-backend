from flask import Flask, jsonify, request
import requests
import jwt
import datetime
from cred import JWT_SECRET_KEY

app = Flask(__name__)

# Static API key for this service
API_KEY = "breach-search-api-key-2024"

# Backend service URL
BACKEND_URL = "http://localhost:5001"

# JWT token storage - generate once at startup
jwt_token = None

def generate_jwt_token():
    """Generate JWT token directly without login call - more efficient"""
    global jwt_token
    
    try:
        # Generate JWT with same payload as backend login
        payload = {
            "user": "proxy_service",  # Internal service identifier
            "exp": datetime.datetime.now() + datetime.timedelta(days=7)  # 1 week expiry for service
        }
        
        jwt_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")
        print(f"✅ Generated JWT token for proxy service (expires in 7 days)")
        return jwt_token
        
    except Exception as e:
        print(f"❌ Error generating JWT: {str(e)}")
        return None

def validate_api_key():
    """Validate the API key from request headers"""
    provided_key = request.headers.get('X-API-Key')
    return provided_key == API_KEY

@app.route('/search', methods=['GET'])
def search():
    """
    Proxy search endpoint with API key authentication
    Forwards to backend /search with JWT authentication
    """
    # Validate API key
    if not validate_api_key():
        return jsonify({"error": "Invalid or missing API key"}), 401
    
    # Check if we have JWT token
    if not jwt_token:
        return jsonify({"error": "Backend authentication not available"}), 503
    
    # Get all query parameters
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    # Prepare all parameters - pass everything through
    params = dict(request.args)
    
    # Force type to breach only
    params['type'] = 'breach'
    
    try:
        # Make authenticated request to backend
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(f"{BACKEND_URL}/search", params=params, headers=headers)
        
        # Return proxied response
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Backend service unavailable"}), 503
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    backend_status = "connected" if jwt_token else "disconnected"
    return jsonify({
        "status": "healthy", 
        "service": "breach-proxy-api",
        "backend_auth": backend_status
    }), 200

# Initialize JWT token at startup
print("🚀 Starting Breach Proxy API...")
if generate_jwt_token():
    print("✅ Ready to serve requests!")
else:
    print("⚠️  JWT generation failed - service may not work properly")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)