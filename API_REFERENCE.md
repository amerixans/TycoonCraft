# TycoonCraft API Reference

Complete API documentation with examples.

## Base URL

- Development: `http://localhost:8000/api`
- Production: `https://tycooncraft.com/api`

## Authentication

All endpoints except `/register/` and `/login/` require authentication via session cookies.

## Endpoints

### 1. Register User

Create a new user account.

**Endpoint**: `POST /api/register/`

**Request**:
```json
{
  "username": "player1",
  "password": "securepassword123",
  "email": "player1@example.com"
}
```

**Response** (201 Created):
```json
{
  "user": {
    "id": 1,
    "username": "player1",
    "email": "player1@example.com"
  },
  "profile": {
    "id": 1,
    "user": {...},
    "coins": "100.00",
    "time_crystals": "0.00",
    "current_era": "Hunter-Gatherer",
    "last_coin_update": "2024-10-10T12:00:00Z",
    "created_at": "2024-10-10T12:00:00Z",
    "updated_at": "2024-10-10T12:00:00Z"
  }
}
```

**Errors**:
- 400: Username already exists
- 400: Username and password required

---

### 2. Login

Authenticate an existing user.

**Endpoint**: `POST /api/login/`

**Request**:
```json
{
  "username": "player1",
  "password": "securepassword123"
}
```

**Response** (200 OK):
```json
{
  "user": {
    "id": 1,
    "username": "player1",
    "email": "player1@example.com"
  },
  "profile": {
    "id": 1,
    "coins": "150.50",
    "time_crystals": "0.00",
    "current_era": "Hunter-Gatherer"
  }
}
```

**Errors**:
- 401: Invalid credentials

---

### 3. Logout

End the current session.

**Endpoint**: `POST /api/logout/`

**Request**: No body required

**Response** (200 OK):
```json
{
  "success": true
}
```

---

### 4. Get Game State

Retrieve complete game state for the current user.

**Endpoint**: `GET /api/game-state/`

**Response** (200 OK):
```json
{
  "profile": {
    "id": 1,
    "coins": "250.75",
    "time_crystals": "5.00",
    "current_era": "Agriculture"
  },
  "discoveries": [
    {
      "id": 1,
      "game_object": {
        "id": 1,
        "object_name": "Rock",
        "era_name": "Hunter-Gatherer",
        "cost": "10.00",
        "income_per_second": "0.1000",
        "footprint_w": 1,
        "footprint_h": 1,
        "image_path": "/media/objects/rock.png"
      },
      "discovered_at": "2024-10-10T12:00:00Z"
    }
  ],
  "placed_objects": [
    {
      "id": 1,
      "game_object": {...},
      "x": 10,
      "y": 20,
      "is_operational": true,
      "is_building": false,
      "placed_at": "2024-10-10T12:05:00Z",
      "build_complete_at": "2024-10-10T12:05:00Z",
      "retire_at": "2024-10-10T12:10:00Z"
    }
  ],
  "era_unlocks": [
    {
      "id": 1,
      "era_name": "Hunter-Gatherer",
      "unlocked_at": "2024-10-10T12:00:00Z"
    }
  ],
  "all_objects": [...]
}
```

---

### 5. Craft Objects

Combine two objects to create a new one.

**Endpoint**: `POST /api/craft/`

**Request**:
```json
{
  "object_a_id": 1,
  "object_b_id": 2
}
```

**Response** (200 OK or 201 Created):
```json
{
  "object": {
    "id": 5,
    "object_name": "Stone Tool",
    "era_name": "Hunter-Gatherer",
    "is_keystone": false,
    "category": "structure",
    "cost": "25.00",
    "income_per_second": "0.5000",
    "footprint_w": 1,
    "footprint_h": 1,
    "size": "1.00",
    "flavor_text": "A primitive tool made from stone.",
    "image_path": "/media/objects/abc123.png"
  },
  "newly_discovered": true,
  "newly_created": true
}
```

**Response Fields**:
- `newly_created`: true if this is the first time anyone created this combination
- `newly_discovered`: true if this is the first time YOU discovered it

**Errors**:
- 400: Both objects required
- 403: Object not discovered
- 404: Object not found
- 429: Rate limit exceeded
- 500: AI generation failed

---

### 6. Place Object

Place a discovered object on the canvas.

**Endpoint**: `POST /api/place/`

**Request**:
```json
{
  "object_id": 5,
  "x": 50,
  "y": 75
}
```

**Response** (201 Created):
```json
{
  "id": 10,
  "game_object": {
    "id": 5,
    "object_name": "Stone Tool",
    ...
  },
  "x": 50,
  "y": 75,
  "placed_at": "2024-10-10T12:30:00Z",
  "build_complete_at": "2024-10-10T12:30:00Z",
  "retire_at": "2024-10-10T12:35:00Z",
  "is_building": false,
  "is_operational": true
}
```

**Errors**:
- 400: object_id, x, and y required
- 400: Insufficient coins
- 400: Insufficient time crystals
- 400: Placement cap reached
- 400: Space occupied
- 400: Out of bounds
- 403: Object not discovered
- 404: Object not found

---

### 7. Remove Object

Remove a placed object and get partial refund.

**Endpoint**: `POST /api/remove/`

**Request**:
```json
{
  "placed_id": 10
}
```

**Response** (200 OK):
```json
{
  "refund": 5.0,
  "coins": 255.75
}
```

**Errors**:
- 400: placed_id required
- 404: Placed object not found

---

### 8. Unlock Era

Unlock the next era using time crystals.

**Endpoint**: `POST /api/unlock-era/`

**Request**:
```json
{
  "era_name": "Agriculture"
}
```

**Response** (200 OK):
```json
{
  "era_unlock": {
    "id": 2,
    "era_name": "Agriculture",
    "unlocked_at": "2024-10-10T12:45:00Z"
  },
  "profile": {
    "coins": "250.75",
    "time_crystals": "0.00",
    "current_era": "Agriculture"
  }
}
```

**Errors**:
- 400: Invalid era
- 400: Era already unlocked
- 400: Insufficient time crystals

---

### 9. Export Game

Export complete game state as JSON.

**Endpoint**: `GET /api/export/`

**Response** (200 OK):
```json
{
  "profile": {...},
  "discoveries": [...],
  "placed_objects": [...],
  "era_unlocks": [...]
}
```

---

### 10. Import Game

Import previously exported game state.

**Endpoint**: `POST /api/import/`

**Request**: Full game state JSON (from export)

**Response** (200 OK):
```json
{
  "success": true
}
```

---

## Error Response Format

All errors follow this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

## Rate Limiting

- **User Discoveries**: 4 per minute per user
- **Global API Calls**: 50 per minute across all users

When rate limited, you'll receive a 429 status code:

```json
{
  "error": "Rate limit exceeded. Please wait."
}
```

## Testing with cURL

### Register
```bash
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'
```

### Login
```bash
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}' \
  -c cookies.txt
```

### Get Game State
```bash
curl -X GET http://localhost:8000/api/game-state/ \
  -b cookies.txt
```

### Craft Objects
```bash
curl -X POST http://localhost:8000/api/craft/ \
  -H "Content-Type: application/json" \
  -d '{"object_a_id":1,"object_b_id":2}' \
  -b cookies.txt
```

### Place Object
```bash
curl -X POST http://localhost:8000/api/place/ \
  -H "Content-Type: application/json" \
  -d '{"object_id":5,"x":10,"y":20}' \
  -b cookies.txt
```

## Testing with Python

```python
import requests

# Create session
session = requests.Session()
base_url = "http://localhost:8000/api"

# Register
response = session.post(f"{base_url}/register/", json={
    "username": "test",
    "password": "test123"
})
print(response.json())

# Get game state
response = session.get(f"{base_url}/game-state/")
state = response.json()
print(f"Coins: {state['profile']['coins']}")

# Craft objects
response = session.post(f"{base_url}/craft/", json={
    "object_a_id": 1,
    "object_b_id": 2
})
new_object = response.json()
print(f"Created: {new_object['object']['object_name']}")

# Place object
response = session.post(f"{base_url}/place/", json={
    "object_id": new_object['object']['id'],
    "x": 10,
    "y": 20
})
print(response.json())
```

## Testing with JavaScript

```javascript
// Register
const response = await fetch('http://localhost:8000/api/register/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    username: 'test',
    password: 'test123'
  })
});
const data = await response.json();

// Get game state
const state = await fetch('http://localhost:8000/api/game-state/', {
  credentials: 'include'
}).then(r => r.json());

// Craft objects
const craft = await fetch('http://localhost:8000/api/craft/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    object_a_id: 1,
    object_b_id: 2
  })
}).then(r => r.json());
```

## Notes

- All timestamps are in ISO 8601 format (UTC)
- All decimal values are returned as strings for precision
- Session cookies are required for authenticated endpoints
- CSRF token is automatically handled by the frontend
