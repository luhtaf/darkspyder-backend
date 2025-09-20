# DarkSpyder API - Postman Collection Guide

## 📋 Overview
File Postman collection ini berisi semua endpoint API DarkSpyder yang telah dibuat, termasuk:
- Setup endpoints
- Authentication
- User management (Admin)
- Package management (Admin)
- Payment flow
- MongoDB access (Admin)
- Search & Data
- Domain management

## 🚀 Setup Postman

### 1. Import Collection
1. Buka Postman
2. Klik **Import** di sidebar kiri
3. Pilih file `DarkSpyder_API.postman_collection.json`
4. Collection akan muncul di sidebar

### 2. Import Environment
1. Klik **Import** lagi
2. Pilih file `DarkSpyder_Environment.postman_environment.json`
3. Environment akan muncul di dropdown environment (kanan atas)

### 3. Select Environment
1. Klik dropdown environment di kanan atas
2. Pilih **"DarkSpyder Environment"**

## 🔧 Environment Variables

### Base Variables
- `base_url`: http://localhost:5001
- `jwt_token`: Token JWT untuk authentication (akan diisi otomatis)
- `user_id`: ID user untuk testing
- `access_id`: Access ID user untuk login

### Test Data Variables
- `admin_email`: admin@example.com
- `admin_username`: admin_user
- `test_email`: test@example.com
- `test_username`: testuser
- `pricing_id`: ID pricing untuk testing

## 📝 Cara Penggunaan

### 1. Setup Awal
1. **Create First Admin**
   - Jalankan request "Create First Admin"
   - Copy `access_id` dari response
   - Update variable `access_id` dengan nilai tersebut

2. **Update Existing Users**
   - Jalankan request "Update Existing Users"
   - Ini akan menambahkan field baru ke user yang sudah ada

### 2. Authentication
1. **Login User**
   - Gunakan `access_id` yang sudah diisi
   - Masukkan TOTP code dari authenticator app
   - Copy `token` dari response
   - Update variable `jwt_token` dengan token tersebut

### 3. Testing Admin Functions
Setelah login sebagai admin, Anda bisa test semua endpoint admin:
- User management
- Package assignment
- MongoDB access
- dll.

## 🔄 Workflow Testing

### Complete User Registration & Package Assignment Flow:

1. **Setup Admin**
   ```
   POST /setup/create-first-admin
   → Copy access_id to environment
   ```

2. **Login Admin**
   ```
   POST /new-login
   → Copy token to environment
   ```

3. **Create User**
   ```
   POST /admin/users
   → Copy user_id to environment
   ```

4. **Assign Package**
   ```
   POST /admin/users/{user_id}/assign-package
   ```

5. **Check User Plan**
   ```
   GET /my-plan
   ```

### Payment Flow Testing:

1. **Get Pricing**
   ```
   GET /pricing
   → Copy pricing ID to environment
   ```

2. **Create Invoice**
   ```
   POST /create-invoice
   → Copy invoice ID to environment
   ```

3. **Create Payment**
   ```
   POST /create-payment
   → Copy payment ID to environment
   ```

4. **Process Payment**
   ```
   POST /process-payment
   ```

## 🎯 Tips Penggunaan

### 1. Environment Variables
- Selalu update environment variables setelah mendapat response
- Gunakan `{{variable_name}}` untuk menggunakan variable di request

### 2. JWT Token
- Token akan expire dalam 1 jam
- Login ulang jika mendapat error 401 Unauthorized

### 3. Testing Sequence
- Ikuti urutan workflow yang sudah disediakan
- Setup admin dulu sebelum test endpoint admin
- Login dulu sebelum test endpoint yang memerlukan authentication

### 4. Error Handling
- Check response status code
- Read error message di response body
- Pastikan semua required fields sudah diisi

## 📊 Response Examples

### Successful Login Response:
```json
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "message": "Login successful"
}
```

### User Creation Response:
```json
{
    "data": {
        "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "access_id": "AbC123XyZ789MnP456QrS",
        "email": "user@example.com",
        "username": "user123",
        "provision_url": "otpauth://totp/...",
        "is_admin": false,
        "is_active": true
    },
    "message": "User created successfully"
}
```

### Package Assignment Response:
```json
{
    "data": {
        "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "plan": {
            "plan": "64f1a2b3c4d5e6f7g8h9i0j1",
            "expired": "2024-02-15T10:30:00Z",
            "domain": "5",
            "breach": "unlimited",
            "current_breach": "0",
            "registered_domain": [],
            "registered_breach_domain": [],
            "assigned_at": "2024-01-15T10:30:00Z",
            "assigned_by": "admin_user_id"
        },
        "pricing_info": {
            "id": "64f1a2b3c4d5e6f7g8h9i0j1",
            "domain": "5",
            "description": "For growing businesses",
            "features": ["Unlimited scans", "API access", ...]
        }
    },
    "message": "Package assigned successfully"
}
```

## 🚨 Common Issues

### 1. 401 Unauthorized
- Token expired atau tidak valid
- Login ulang untuk mendapat token baru

### 2. 403 Forbidden
- User bukan admin
- Check `is_admin` di JWT token

### 3. 400 Bad Request
- Required field kosong
- Format data tidak sesuai
- Check request body

### 4. 404 Not Found
- User ID tidak ditemukan
- Endpoint salah
- Check URL dan parameters

## 📞 Support

Jika ada masalah dengan API atau Postman collection:
1. Check server logs
2. Verify environment variables
3. Test dengan curl untuk memastikan API berfungsi
4. Check dokumentasi API lengkap di `API_DOCUMENTATION.md`
