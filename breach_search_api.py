from flask import Flask, jsonify, request
import requests
import os

app = Flask(__name__)

# Static API key for this service
API_KEY = "breach-search-api-key-2024"

# Backend service URL
BACKEND_URL = "http://localhost:5001"

# Internal credentials for backend authentication
INTERNAL_USERNAME = "admin"  # Change this to your backend username
INTERNAL_PASSWORD = "admin"  # Change this to your backend password

# JWT token storage (will be refreshed automatically)
jwt_token = None

def validate_api_key():
    """Validate the API key from request headers"""
    provided_key = request.headers.get('X-API-Key')
    return provided_key == API_KEY

def get_backend_jwt():
    """Get JWT token for backend authentication"""
    global jwt_token
    
    if jwt_token:
        # TODO: Add token expiry check here
        return jwt_token
    
    try:
        # Login to backend service
        login_data = {
            "username": INTERNAL_USERNAME,
            "password": INTERNAL_PASSWORD
        }
        
        response = requests.post(f"{BACKEND_URL}/login", json=login_data)
        
        if response.status_code == 200:
            jwt_token = response.json().get('access_token')
            return jwt_token
        else:
            print(f"Failed to login to backend: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error getting backend JWT: {str(e)}")
        return None

@app.route('/breach-search', methods=['GET'])
def breach_search():
    """
    Proxy endpoint for breach searches only with API key authentication
    Forwards requests to main backend /search with type=breach limitation
    """
    # Validate API key
    if not validate_api_key():
        return jsonify({"error": "Invalid or missing API key"}), 401
    
    # Get query parameters
    q = request.args.get('q', '').strip()
    page = request.args.get('page', '1')
    size = request.args.get('size', '10')
    username = request.args.get('username', '')
    domain = request.args.get('domain', '')
    password = request.args.get('password', '')
    
    # Validate required parameters
    if not q:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
    
    try:
        # Prepare parameters for backend request - FORCE breach type only
        params = {
            'q': q,
            'type': 'breach',  # HARDCODED: Only allow breach searches
            'page': page,
            'size': size
        }
        
        # Add optional filter parameters if provided
        if username:
            params['username'] = username
        if domain:
            params['domain'] = domain
        if password:
            params['password'] = password
        
        # Proxy request to main backend service
        # TODO: Implement proper JWT authentication for backend
        response = requests.get(f"{BACKEND_URL}/search", params=params)
        
        # Return proxied response from backend
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Backend service unavailable"}), 503
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "breach-search-api"}), 200

@app.route('/api-info', methods=['GET'])
def api_info():
    """API information endpoint"""
    return jsonify({
        "service": "Breach Search API",
        "version": "1.0.0",
        "description": "Proxy API for searching breach data only - limits access to breach searches with API key authentication",
        "backend_service": BACKEND_URL,
        "proxy_target": "/search endpoint with type=breach",
        "endpoints": {
            "/breach-search": {
                "method": "GET",
                "description": "Proxy to backend breach search - automatically sets type=breach",
                "auth": "X-API-Key header required",
                "parameters": {
                    "q": "Search query (required)",
                    "page": "Page number (optional, default: 1)",
                    "size": "Results per page (optional, default: 10)",
                    "username": "Filter by username (optional)",
                    "domain": "Filter by domain (optional)", 
                    "password": "Filter by password (optional)"
                }
            }
        }
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)