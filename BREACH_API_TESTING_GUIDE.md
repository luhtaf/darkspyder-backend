# Breach Search API - Postman Testing Guide

## 📋 Overview
Dokumentasi lengkap untuk testing Breach Search API menggunakan Postman Collection yang telah disediakan.

## 🚀 Quick Start

### 1. Setup Postman
1. **Import Collection:**
   - Buka Postman
   - Click **Import** → **Files**
   - Select `Breach_Search_API.postman_collection.json`

2. **Import Environment:**
   - Click **Import** → **Files** 
   - Select `Breach_Search_API.postman_environment.json`
   - Set sebagai active environment

3. **Verify Variables:**
   - Base URL: `http://localhost:5002`
   - API Key: `breach-search-api-key-2024`

### 2. Start Services
```bash
# Terminal 1: Start main backend service
cd darkspyder-backend
python main.py

# Terminal 2: Start breach search API
python breach_search_api.py
```

### 3. Run Tests
Gunakan **Collection Runner** atau test manual per endpoint.

---

## 📁 Collection Structure

### **System Endpoints**
- ✅ **Health Check** - Status API
- ✅ **API Info** - Dokumentasi endpoint

### **Search Endpoints**
- 🔍 **Basic Query** - Pencarian sederhana
- 📄 **With Pagination** - Dengan pagination
- 🔎 **With All Filters** - Semua filter aktif
- 📊 **Large Dataset** - Test performa

### **Error Testing**
- ❌ **Missing API Key** - Test autentikasi
- ❌ **Invalid API Key** - Test key salah
- ❌ **Missing Query** - Test validasi parameter
- ❌ **Empty Query** - Test parameter kosong

---

## 🧪 Testing Scenarios

### **Scenario 1: Basic Functionality**
```
1. Health Check → Should return 200
2. API Info → Should return service details
3. Basic Query → Should return breach data
```

### **Scenario 2: Authentication Testing**
```
1. Missing API Key → Should return 401
2. Invalid API Key → Should return 401
3. Valid API Key → Should return 200
```

### **Scenario 3: Parameter Validation**
```
1. Missing Query → Should return 400
2. Empty Query → Should return 400
3. Valid Query → Should return 200
```

### **Scenario 4: Advanced Filtering**
```
1. Domain Filter → Filter by gmail.com
2. Username Filter → Filter by john
3. Validity Filter → Filter valid=true
4. Combined Filters → All filters together
```

### **Scenario 5: Performance Testing**
```
1. Small Dataset (size=10)
2. Medium Dataset (size=50)
3. Large Dataset (size=100)
4. Check response times < 5000ms
```

---

## 🔧 Environment Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `base_url` | `http://localhost:5002` | API base URL |
| `api_key` | `breach-search-api-key-2024` | Static API key |
| `backend_url` | `http://localhost:5001` | Main backend URL |
| `test_email` | `example@gmail.com` | Test email |
| `test_domain` | `gmail.com` | Test domain |
| `test_username` | `john` | Test username |

---

## 📊 Expected Responses

### ✅ Success Responses

**Health Check:**
```json
{
    "status": "healthy",
    "service": "breach-search-api"
}
```

**Breach Search Success:**
```json
{
    "data": [
        {
            "email": "user@example.com",
            "username": "user",
            "domain": "example.com",
            "password": "********",
            "source": "breach_name",
            "date": "2024-01-01"
        }
    ],
    "total": 150,
    "page": 1,
    "size": 10
}
```

### ❌ Error Responses

**Missing API Key (401):**
```json
{
    "error": "Invalid or missing API key"
}
```

**Missing Query (400):**
```json
{
    "error": "Query parameter 'q' is required"
}
```

**Backend Unavailable (503):**
```json
{
    "error": "Backend service unavailable"
}
```

---

## 🔍 Manual Testing Examples

### **cURL Commands:**

**1. Health Check:**
```bash
curl -X GET "http://localhost:5002/health"
```

**2. Basic Search:**
```bash
curl -X GET "http://localhost:5002/breach-search?q=example@gmail.com" \
  -H "X-API-Key: breach-search-api-key-2024"
```

**3. Advanced Search:**
```bash
curl -X GET "http://localhost:5002/breach-search?q=gmail&domain=gmail.com&valid=true&page=1&size=20" \
  -H "X-API-Key: breach-search-api-key-2024"
```

**4. Error Test:**
```bash
curl -X GET "http://localhost:5002/breach-search?q=test" \
  -H "X-API-Key: wrong-key"
```

### **JavaScript/Axios Examples:**

```javascript
// Basic search
const response = await axios.get('http://localhost:5002/breach-search', {
  params: {
    q: 'example@gmail.com',
    page: 1,
    size: 10
  },
  headers: {
    'X-API-Key': 'breach-search-api-key-2024'
  }
});

// Advanced search with filters
const advancedResponse = await axios.get('http://localhost:5002/breach-search', {
  params: {
    q: 'gmail',
    domain: 'gmail.com',
    username: 'john',
    valid: 'true',
    page: 2,
    size: 25
  },
  headers: {
    'X-API-Key': 'breach-search-api-key-2024'
  }
});
```

---

## 🐛 Troubleshooting

### **Common Issues:**

1. **Connection Refused:**
   - ✅ Check if services running on correct ports
   - ✅ Verify `python breach_search_api.py` is running

2. **401 Unauthorized:**
   - ✅ Check API key in headers
   - ✅ Verify key matches: `breach-search-api-key-2024`

3. **503 Service Unavailable:**
   - ✅ Ensure main backend service running on port 5001
   - ✅ Check `python main.py` is running

4. **400 Bad Request:**
   - ✅ Ensure 'q' parameter is provided and not empty
   - ✅ Check parameter syntax

### **Debug Tips:**

1. **Check Service Status:**
   ```bash
   # Test breach API
   curl http://localhost:5002/health
   
   # Test main backend  
   curl http://localhost:5001/health
   ```

2. **Monitor Logs:**
   - Check terminal output for error messages
   - Look for connection errors or authentication failures

3. **Validate Environment:**
   - Verify Postman environment variables
   - Check base_url and api_key values

---

## 📈 Performance Benchmarks

### **Expected Response Times:**
- Health Check: < 100ms
- Basic Search: < 2000ms
- Advanced Search: < 3000ms
- Large Dataset: < 5000ms

### **Load Testing:**
```bash
# Using Apache Bench
ab -n 100 -c 10 -H "X-API-Key: breach-search-api-key-2024" \
  "http://localhost:5002/breach-search?q=test"
```

---

## 🔐 Security Notes

1. **API Key Management:**
   - Current key adalah static untuk development
   - Production: implement dynamic key management
   - Rotate keys secara berkala

2. **Rate Limiting:**
   - Belum diimplementasi di versi current
   - Recommended: add rate limiting middleware

3. **Input Validation:**
   - API melakukan basic validation
   - Additional validation di backend service

---

## 📝 Test Reports

Gunakan Postman's built-in reporting atau export results:

1. **Collection Runner:**
   - Run entire collection
   - Generate HTML/JSON reports
   - Track success/failure rates

2. **Newman CLI:**
   ```bash
   npm install -g newman
   newman run Breach_Search_API.postman_collection.json \
     -e Breach_Search_API.postman_environment.json \
     --reporters html,json
   ```

---

## 🚀 Next Steps

1. **Production Setup:**
   - Environment-specific API keys
   - Rate limiting implementation
   - Logging and monitoring

2. **Additional Features:**
   - Bulk search endpoints
   - Export functionality
   - Advanced filtering options

3. **Security Enhancements:**
   - JWT token authentication
   - IP whitelisting
   - Request encryption