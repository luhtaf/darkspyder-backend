# DarkSpyder Backend API Documentation

## Overview
API untuk pengelolaan data breach, stealer, dan user management dengan sistem paket berlangganan.

## Base URL
```
http://localhost:5001
```

## Authentication
Semua endpoint admin memerlukan JWT token dengan format:
```
Authorization: Bearer <your_jwt_token>
```

### JWT Token Structure
JWT token berisi informasi berikut:
```json
{
    "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
    "username": "user123",  // Opsional, hanya ada jika user memiliki username
    "is_admin": true,       // Opsional, hanya ada jika user adalah admin
    "exp": 1640995200
}
```

**Note:** 
- `username` hanya ada di JWT jika user memiliki username
- `is_admin` hanya ada di JWT jika user adalah admin (true)

---

## 🔧 Setup Endpoints

### 1. Create First Admin User
**POST** `/setup/create-first-admin`

Membuat admin pertama (tidak memerlukan authentication).

**Request Body:**
```json
{
    "email": "admin@example.com",
    "username": "admin_user"
}
```

**Note:** Email wajib diisi, username opsional.

**Response:**
```json
{
    "data": {
        "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "access_id": "AbC123XyZ789MnP456QrS",
        "email": "admin@example.com",
        "username": "admin_user",
        "provision_url": "otpauth://totp/...",
        "is_admin": true,
        "is_active": true
    },
    "message": "First admin user created successfully"
}
```

### 2. Update Existing Users
**POST** `/setup/update-existing-users`

Menambahkan field baru (is_admin, is_active, email, username) ke user yang sudah ada.

**Response:**
```json
{
    "message": "Updated 5 users with new fields",
    "updated_count": 5
}
```

---

## 👥 User Management Endpoints (Admin Only)

### 1. Get All Users
**GET** `/admin/users`

Mendapatkan daftar semua user dengan pagination.

**Query Parameters:**
- `page` (optional): Halaman (default: 1)
- `size` (optional): Jumlah data per halaman (default: 10, max: 100)
- `search` (optional): Pencarian berdasarkan access_id, email, atau username

**Response:**
```json
{
    "data": [
        {
            "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
            "access_id": "AbC123XyZ789MnP456QrS",
            "email": "user@example.com",
            "username": "user123",
            "created_at": "2024-01-15T10:30:00Z",
            "last_login": "2024-01-20T14:25:00Z",
            "myPlan": {...},
            "is_admin": false,
            "is_active": true
        }
    ],
    "pagination": {
        "page": 1,
        "size": 10,
        "total": 25,
        "pages": 3
    },
    "message": "Success get all users"
}
```

### 2. Get User by ID
**GET** `/admin/users/{user_id}`

Mendapatkan detail user berdasarkan ID.

**Response:**
```json
{
    "data": {
        "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "access_id": "AbC123XyZ789MnP456QrS",
        "email": "user@example.com",
        "created_at": "2024-01-15T10:30:00Z",
        "last_login": "2024-01-20T14:25:00Z",
        "login_history": [...],
        "myPlan": {...},
        "is_admin": false,
        "is_active": true
    },
    "message": "Success get user"
}
```

### 3. Create New User
**POST** `/admin/users`

Membuat user baru (admin only).

**Request Body:**
```json
{
    "email": "newuser@example.com",
    "username": "newuser123",
    "is_admin": false,
    "is_active": true
}
```

**Note:** Email wajib diisi, username opsional.

**Response:**
```json
{
    "data": {
        "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "access_id": "AbC123XyZ789MnP456QrS",
        "email": "newuser@example.com",
        "username": "newuser123",
        "provision_url": "otpauth://totp/...",
        "is_admin": false,
        "is_active": true
    },
    "message": "User created successfully"
}
```

### 4. Update User
**PUT** `/admin/users/{user_id}`

Mengupdate informasi user.

**Request Body:**
```json
{
    "email": "updated@example.com",
    "username": "updateduser",
    "is_admin": false,
    "is_active": true
}
```

**Response:**
```json
{
    "message": "User updated successfully"
}
```

### 5. Delete User (Soft Delete)
**DELETE** `/admin/users/{user_id}`

Menghapus user (soft delete dengan mengset is_active = false).

**Response:**
```json
{
    "message": "User deleted successfully"
}
```

### 6. Make User Admin
**POST** `/admin/users/{user_id}/make-admin`

Memberikan hak admin kepada user.

**Response:**
```json
{
    "message": "User is now admin"
}
```

### 7. Remove Admin Privileges
**POST** `/admin/users/{user_id}/remove-admin`

Menghapus hak admin dari user.

**Response:**
```json
{
    "message": "Admin privileges removed"
}
```

---

## 🔍 Breach Management Endpoints

### 1. Use Breach Quota
**POST** `/use-breach`

Menggunakan kuota breach tanpa parameter apapun. Endpoint ini akan otomatis mengurangi kuota breach user dengan menambah `current_breach` +1.

**Authentication:** Required (JWT token)

**Request Body:** Tidak ada parameter yang diperlukan

**Response Success (200):**

Untuk kuota terbatas:
```json
{
    "message": "Breach quota used successfully",
    "status": "success",
    "current_breach": 2,
    "breach_limit": 10
}
```

Untuk kuota unlimited:
```json
{
    "message": "You have unlimited breach quota",
    "status": "success",
    "current_breach": 5,
    "breach_limit": "unlimited"
}
```

**Error Responses:**
- `404` - User account not found
- `403` - User does not have an active plan / Plan expired / Quota exceeded
- `500` - Internal server error

**Contoh Penggunaan:**
```bash
POST /use-breach
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

**Fitur:**
- Validasi apakah user memiliki plan aktif
- Cek apakah plan belum expired
- Validasi kuota breach yang tersisa
- Otomatis increment `current_breach` counter
- Support untuk plan unlimited breach

---

## 📦 Package Management Endpoints (Admin Only)

### 1. Assign Package to User
**POST** `/admin/users/{user_id}/assign-package`

Menugaskan paket tertentu kepada user.

**Request Body:**
```json
{
    "idPricing": "64f1a2b3c4d5e6f7g8h9i0j1",
    "plan": "monthly"
}
```

**Response:**
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

### 2. Extend User Package
**POST** `/admin/users/{user_id}/extend-package`

Memperpanjang paket user.

**Request Body:**
```json
{
    "extend_months": 3
}
```

**Response:**
```json
{
    "data": {
        "user_id": "64f1a2b3c4d5e6f7g8h9i0j1",
        "old_expired": "2024-02-15T10:30:00Z",
        "new_expired": "2024-05-15T10:30:00Z",
        "extension_months": 3
    },
    "message": "Package extended successfully"
}
```

### 3. Remove User Package
**POST** `/admin/users/{user_id}/remove-package`

Menghapus paket dari user.

**Response:**
```json
{
    "message": "Package removed successfully"
}
```

---

## 🗄️ MongoDB Connection Endpoints (Admin Only)

### 1. MongoDB Connection Status
**GET** `/admin/mongodb/status`

Mengecek status koneksi MongoDB dan informasi database.

**Response:**
```json
{
    "status": "connected",
    "database": "darkspyder",
    "database_stats": {
        "collections": 2,
        "data_size": 1024000,
        "storage_size": 2048000,
        "indexes": 4
    },
    "collections": [
        {
            "name": "account",
            "count": 25
        },
        {
            "name": "pricing",
            "count": 8
        }
    ],
    "message": "MongoDB connection successful"
}
```

### 2. Get Collection Data
**GET** `/admin/mongodb/collections/{collection_name}`

Mendapatkan data dari collection tertentu.

**Query Parameters:**
- `page` (optional): Halaman (default: 1)
- `size` (optional): Jumlah data per halaman (default: 10, max: 100)
- `search` (optional): Pencarian

**Response:**
```json
{
    "collection": "account",
    "data": [
        {
            "_id": "64f1a2b3c4d5e6f7g8h9i0j1",
            "access_id": "AbC123XyZ789MnP456QrS",
            "email": "user@example.com",
            ...
        }
    ],
    "pagination": {
        "page": 1,
        "size": 10,
        "total": 25,
        "pages": 3
    },
    "message": "Success get data from account"
}
```

### 3. Get Collection Statistics
**GET** `/admin/mongodb/collections/{collection_name}/stats`

Mendapatkan statistik collection.

**Response:**
```json
{
    "collection": "account",
    "stats": {
        "count": 25,
        "size": 512000,
        "avgObjSize": 20480,
        "storageSize": 1024000,
        "totalIndexSize": 102400,
        "indexes": 2
    },
    "sample_documents": [...],
    "field_analysis": [
        {"_id": "access_id", "count": 25},
        {"_id": "email", "count": 25},
        {"_id": "created_at", "count": 25}
    ],
    "message": "Success get stats for account"
}
```

---

## 🔄 Alur Assign User ke Paket

### Langkah-langkah:

1. **Cek Pricing** - Gunakan endpoint `/pricing` untuk melihat daftar paket
2. **Create Invoice** - Gunakan endpoint `/create-invoice` untuk membuat invoice
3. **Create Payment** - Gunakan endpoint `/create-payment` untuk membuat payment
4. **Process Payment** - Gunakan endpoint `/process-payment` untuk memproses payment

### Atau untuk Admin:

1. **Assign Package** - Langsung assign paket ke user menggunakan `/admin/users/{user_id}/assign-package`

---

## 📋 Struktur User

```json
{
    "_id": "ObjectId",
    "access_id": "String (18-22 chars)",
    "email": "String (required)",
    "username": "String (optional)",
    "created_at": "DateTime",
    "last_login": "DateTime",
    "login_history": [
        {
            "timestamp": "DateTime",
            "ip_address": "String"
        }
    ],
    "secret": "String (TOTP secret)",
    "using_totp": "Boolean",
    "is_admin": "Boolean",
    "is_active": "Boolean",
    "myPlan": {
        "plan": "ObjectId (pricing ID)",
        "expired": "DateTime",
        "domain": "String",
        "breach": "String",
        "current_breach": "String",
        "registered_domain": ["String"],
        "registered_breach_domain": ["String"],
        "assigned_at": "DateTime",
        "assigned_by": "ObjectId"
    },
    "transaction": [
        {
            "id": "ObjectId",
            "plan": "String",
            "domain": "String",
            "invoice": {...},
            "payment": {...}
        }
    ]
}
```

---

## 🚨 Error Responses

Semua endpoint mengembalikan error dengan format:

```json
{
    "error": "Error message description"
}
```

**HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

---

## 🔐 Security Notes

1. Semua endpoint admin memerlukan JWT token yang valid
2. User harus memiliki `is_admin: true` untuk mengakses endpoint admin
3. Soft delete digunakan untuk user deletion
4. TOTP authentication diperlukan untuk login user
5. Admin tidak bisa menghapus privilege admin dari dirinya sendiri

---

## 🚀 Contoh Penggunaan

### 1. **Setup Awal:**
```bash
# 1. Buat admin pertama (email wajib, username opsional)
POST /setup/create-first-admin
{
    "email": "admin@example.com",
    "username": "admin_user"
}

# 2. Update user yang sudah ada
POST /setup/update-existing-users
```

### 2. **Pendaftaran User Baru:**
```bash
# Pendaftaran dengan email saja (username opsional)
POST /register
{
    "email": "user@example.com"
}

# Pendaftaran dengan email dan username
POST /register
{
    "email": "user@example.com",
    "username": "user123"
}
```

### 3. **Login sebagai Admin:**
```bash
POST /new-login
{
    "access_id": "AbC123XyZ789MnP456QrS",
    "totp": "123456"
}
```

### 4. **Manage Users:**
```bash
# Get all users
GET /admin/users?page=1&size=10&search=user@example.com

# Create new user
POST /admin/users
{
    "email": "newuser@example.com",
    "username": "newuser123",
    "is_admin": false,
    "is_active": true
}

# Assign package
POST /admin/users/{user_id}/assign-package
{
    "idPricing": "64f1a2b3c4d5e6f7g8h9i0j1",
    "plan": "monthly"
}
```

### 5. **Akses MongoDB:**
```bash
# Check connection
GET /admin/mongodb/status

# Get collection data
GET /admin/mongodb/collections/account?page=1&size=10

# Get collection stats
GET /admin/mongodb/collections/account/stats
```

### 6. **Breach Management:**
```bash
# Use breach quota (tidak perlu parameter)
POST /use-breach
Authorization: Bearer <jwt_token>
Content-Type: application/json

# Response:
{
    "message": "Breach quota used successfully",
    "status": "success",
    "current_breach": 2,
    "breach_limit": 10
}
```
