# 📋 CRUD Endpoint Test Commands

This markdown file documents how to test your FastAPI CRUD endpoints using both `Invoke-RestMethod` in PowerShell and `curl` in Bash.  
Make sure your FastAPI server is running at [http://localhost:8000](http://localhost:8000).

---

## 🔐 Authentication Header

> All authenticated endpoints require this header:

```powershell
"token" = "fake-super-secret-token"
```

---

## 📦 Items Endpoints

### 📃 Create Item (POST `/api/v1/items`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/items" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "token" = "fake-super-secret-token"
  } `
  -Body '{"name": "Notebook", "description": "A lined paper notebook"}'
```

#### Bash:

```bash
curl -L -X POST "http://localhost:8000/api/v1/items"   -H "token: fake-super-secret-token"   -H "Content-Type: application/json"   -d '{"name": "Notebook", "description": "A lined paper notebook"}'
```

### 🔍 Get All Items (GET `/api/v1/items`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/items" `
  -Headers @{
    "token" = "fake-super-secret-token"
  }
```

#### Bash:

```bash
curl -L -X GET "http://localhost:8000/api/v1/items"   -H "token: fake-super-secret-token"
```

### 🔍 Get Item by ID (GET `/api/v1/items/{item_id}`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/items/1" `
  -Headers @{
    "token" = "fake-super-secret-token"
  }
```

#### Bash:

```bash
curl -L -X GET "http://localhost:8000/api/v1/items/1"   -H "token: fake-super-secret-token"
```

### 🔍 Filter Items by Query (GET `/api/v1/items?name=book`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/items?name=book" `
  -Headers @{
    "token" = "fake-super-secret-token"
  }
```

#### Bash:

```bash
curl -L -X GET "http://localhost:8000/api/v1/items?name=book"   -H "token: fake-super-secret-token"
```

---

## 👤 Users Endpoints

### 📃 Create User (POST `/api/v1/users`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/users" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
  } `
  -Body '{"username": "john", "email": "john@example.com"}'
```

#### Bash:

```bash
curl -L -X POST "http://localhost:8000/api/v1/users"   -H "Content-Type: application/json"   -d '{"username": "john", "email": "john@example.com"}'
```

### 🔍 Get All Users (GET `/api/v1/users`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/users" `
  -Headers @{
    "token" = "fake-super-secret-token"
  }
```

#### Bash:

```bash
curl -L -X GET "http://localhost:8000/api/v1/users"   -H "token: fake-super-secret-token"
```

### 🔍 Get User by ID (GET `/api/v1/users/1`)

#### PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/users/1" `
  -Headers @{
    "token" = "fake-super-secret-token"
  }
```

#### Bash:

```bash
curl -L -X GET "http://localhost:8000/api/v1/users/1"   -H "token: fake-super-secret-token"
```
