# EX-DIGITAL — Enterprise Attendance Management System

> An enterprise-grade, microservice-based attendance management system built with **PostgreSQL**, **FastAPI**, and **Flask**.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Network                              │
│                                                                 │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  PostgreSQL   │◄──│  FastAPI Core     │   │  Flask Gateway  │ │
│  │  :5432        │◄──│  :8000            │   │  :5001          │ │
│  │              │   │                  │   │                │  │
│  │  • Users      │   │  • JWT Auth       │   │  • Data Export  │ │
│  │  • Courses    │   │  • Sessions       │   │  • Sync Engine  │ │
│  │  • Sessions   │   │  • Rapid-Scan     │   │  • Portal Push  │ │
│  │  • Attendance │   │  • RBAC           │   │  • API-Key Auth │ │
│  │  • Sync Logs  │   │                  │   │                │  │
│  └──────────────┘   └──────────────────┘   └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/Olajerry11/EX-CODERS-Solution.git
cd EX-CODERS-Solution
cp .env.example .env
# Edit .env with your secrets
```

### 2. Launch with Docker

```bash
docker compose up --build -d
```

### 3. Initialize Database

```bash
# Run migrations
docker exec exdigital-fastapi python -m database.migrations

# Seed with sample data
docker exec exdigital-fastapi python -m database.seed
```

### 4. Access Services

| Service | URL |
|---------|-----|
| FastAPI Docs | http://localhost:8000/docs |
| FastAPI ReDoc | http://localhost:8000/redoc |
| Flask Gateway | http://localhost:5001/ |

## 📡 API Reference

### FastAPI Core (Port 8000)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/login` | — | Get JWT token |
| `POST` | `/api/v1/auth/register` | — | Create user |
| `GET` | `/api/v1/auth/me` | 🔒 JWT | Current user profile |
| `POST` | `/api/v1/sessions/` | 🔒 Lecturer/Admin | Create session |
| `GET` | `/api/v1/sessions/` | 🔒 Any | List sessions |
| `PATCH` | `/api/v1/sessions/{id}/lock` | 🔒 Lecturer/Admin | Lock session |
| `POST` | `/api/v1/attendance/rapid-scan` | 🔒 Lecturer/Admin | Batch scan |
| `GET` | `/api/v1/attendance/session/{id}` | 🔒 Any | View attendance |

### Flask Gateway (Port 5001)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/gateway/v1/export/student/{ext_id}/attendance` | 🔑 API Key | Student attendance |
| `GET` | `/gateway/v1/export/course/{code}/attendance` | 🔑 API Key | Course roster |
| `GET` | `/gateway/v1/export/course/{code}/summary` | 🔑 API Key | Course summary |
| `POST` | `/gateway/v1/sync/trigger` | 🔑 API Key | Trigger sync |
| `GET` | `/gateway/v1/sync/status` | 🔑 API Key | Queue stats |
| `GET` | `/gateway/v1/sync/history` | 🔑 API Key | Sync history |

## 🔐 Test Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@exdigital.edu | Admin@1234 |
| Lecturer | dr.okonkwo@exdigital.edu | Lecturer@1234 |
| Student | student01@exdigital.edu | Student@1234 |

## 📂 Project Structure

```
EX-CODERS-Solution/
├── database/                    # Phase 1: Database Layer
│   ├── config.py                #   SQLAlchemy engine & session
│   ├── models.py                #   ORM models (6 tables)
│   ├── migrations.py            #   Table creation
│   └── seed.py                  #   Test data seeder
├── core_api/                    # Phase 2: FastAPI Core
│   ├── main.py                  #   App factory
│   ├── settings.py              #   Pydantic settings
│   ├── auth.py                  #   JWT & RBAC
│   ├── schemas.py               #   Request/response models
│   └── routes/                  #   API routers
│       ├── auth.py
│       ├── sessions.py
│       └── attendance.py
├── integration_gateway/         # Phase 3: Flask Gateway
│   ├── app.py                   #   Flask app factory
│   ├── config.py                #   Gateway config
│   ├── auth.py                  #   API-key auth
│   ├── export.py                #   Data export endpoints
│   └── sync.py                  #   External sync service
├── scripts/
│   └── init_db.py               #   DB initialization script
├── Dockerfile.fastapi           # Phase 4: Docker
├── Dockerfile.flask
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── requirements.txt
└── README.md
```

## 📄 License

Built for the EX-CODERS hackathon challenge.
