# ftask - FastAPI Task Manager

![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-asyncio-brightgreen)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-relational-blue)
[![Docker](https://img.shields.io/badge/Docker-available-%230db7ed)](https://www.docker.com/)
![License](https://img.shields.io/badge/license-MIT-green)


A high-performance, asynchronous task management API built with FastAPI.
This project features a robust, layered architecture, secure JWT token-based authentication,
and flexible role-based authorization using scopes. It is fully containerized with Docker for easy,
reproducible deployments.

---

## Overview

---

## Features

### 🚀 Modern Architecture
- **Asynchronous & High-Performance**: Built with **FastAPI** and **SQLAlchemy 2.0**.
- **Clean Layered Design**: Organized into router, service, and repository layers.
- **Dependency Injection**: Uses FastAPI’s DI for maintainable and testable code.
- **Production-Ready Logging**: Structured and configurable logging with **Loguru**.

### 🔒 Security & Authentication
- **Secure Authentication**: Robust **JWT** token-based flow.
- **Role-Based Authorization**: Flexible scopes (e.g., `user` vs. `admin`).
- **Password Hashing**: Safe password storage using **bcrypt**.

### 👤 User & Admin Management
- **User Registration**: Unique username and email validation.
- **User Authentication**: Login with username and password.
- **User Profile**: Retrieve and update personal data.
- **Admin Tools**: Admin-only endpoints for managing users.

### 🗄️ Database & Migrations
- **Async Database Access**: Fully asynchronous **SQLAlchemy ORM** with PostgreSQL.
- **Database Migrations**: Version-controlled schema with **Alembic**.
- **Database Metrics**: **Prometheus** metrics for connection pool & transactions.

### 🐳 Containerization & Deployment
- **Fully Containerized**: Production-ready **Docker Compose** setup (app + DB).
- **Robust Startup**: Entrypoint waits for DB and applies migrations automatically.

### 📖 Developer Experience
- **Interactive API Docs**: Auto-generated **Swagger UI** & **ReDoc**.

---

## Tech Stack

### 🐍 Core
- **Python 3.12**
- **FastAPI** — modern async web framework
- **Uvicorn** — lightning-fast ASGI server

### 🗄️ Database Layer
- **PostgreSQL** — robust relational database
- **SQLAlchemy (async)** — ORM with async support via `asyncpg`
- **Alembic** — database migrations
- **Prometheus Client** — DB connection pool & transaction metrics

### 🔒 Security & Auth
- **bcrypt** — password hashing
- **PyJWT / python-jose** — JWT authentication & authorization

### 📦 Tooling & Dev Experience
- **Pydantic** — data validation & parsing
- **Poetry** — dependency management
- **Ruff** — linter & formatter
- **Mypy** — static type checking
- **Pytest** — testing framework
- **Pre-commit** — Git hooks for code quality

### 🐳 Containerization
- **Docker & Docker Compose** — containerized, production-ready setup

---

## Installation & Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/valed-dm/ftask.git
   cd ftask
   ```

2. **Create the Environment File:**

 ```bash
   cp .env.example .env
```
   - DATABASE_URL (PostgreSQL connection string)
   - SECRET_KEY (JWT signing secret)
   - ALGORITHM (e.g., HS256)
   - ACCESS_TOKEN_EXPIRE_MINUTES (token expiry duration)
   - Other app-specific settings as needed


3. **Build and Run the Application:**


```bash
  docker-compose up --build -d
```

This command will:

- Build the ftask-app Docker image based on the Dockerfile.
- Pull the official postgres image.
- Start both containers.
- The application container will wait for the database to be ready, run any pending migrations, and then start the Uvicorn server.

---

### API Endpoints Overview

- API Root (redirects to docs): http://localhost:8000
- Interactive Docs (Swagger UI): http://localhost:8000/docs
- Prometheus Metrics: http://localhost:8000/metrics


| Endpoint | Method | Description | Authorization |
|---|---|---|---|
| **Authentication** | | | |
| `/users/register` | POST | Register a new user account. | Public |
| `/users/token` | POST | Obtain a JWT access token (login). | Public |
| **User Profile (Self)** | | | |
| `/users/me` | GET | Get the current authenticated user's profile. | Authenticated (`user`) |
| `/users/me` | PUT | Update the current authenticated user's profile. | Authenticated (`user`) |
| **Task Management** | | | |
| `/tasks/` | POST | Create a new task for the current user. | Authenticated (`user`) |
| `/tasks/` | GET | Retrieve all tasks owned by the current user. | Authenticated (`user`) |
| `/tasks/{task_id}` | GET | Retrieve a specific task by its ID. | Authenticated (`user`, owner) |
| `/tasks/{task_id}` | PUT | Update a specific task by its ID. | Authenticated (`user`, owner) |
| `/tasks/{task_id}` | DELETE | Delete a specific task by its ID. | Authenticated (`user`, owner) or Admin |
| **Admin** | | | |
| `/admin/users/` | GET | List all users in the system (paginated). | Admin only (`admin`) |
| `/admin/users/{user_id}`| PATCH | Fully update any user's profile by their ID. | Admin only (`admin`) |
| `/admin/status/` | GET | Get a system health or status report. | Admin only (`admin`) |

---

## Security & Authentication

| Security Feature              | Implementation Details                          |
|-------------------------------|-----------------------------------------------|
| **Password Hashing**          | bcrypt algorithm for secure storage           |
| **Authentication Flow**       | OAuth2 password flow with JWT tokens          |
| **Token Features**            | Includes scopes for fine-grained permissions  |
| **Endpoint Protection**       | FastAPI Dependency Injection + SecurityScopes |
| **Admin Route Enforcement**   | Additional scope requirements for admin-only endpoints |

### Key Characteristics:
- 🔒 All passwords are irreversibly hashed before storage
- 🔑 JWT tokens contain user identity and permission scopes
- 🛡️ Automatic token validation on protected routes
- 👮 Admin routes require both valid token and admin privileges
- ⏱️ Tokens have configurable expiration for enhanced security

---

## Monitoring & Metrics

| Component               | Monitoring Solution      | Benefits                          |
|-------------------------|--------------------------|-----------------------------------|
| Database connections    | Prometheus metrics       | Tracks pool usage and efficiency  |
| Transaction durations   | Prometheus metrics       | Enables performance optimization  |


## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for full details.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)


### SCREENSHOTS:

[<img src="docs/images/img_17.png" width="600"/>]()

[<img src="docs/images/img_18.png" width="600"/>]()

[<img src="docs/images/img_01.png" width="1000"/>]()

[<img src="docs/images/img_02.png" width="1000"/>]()

[<img src="docs/images/img_03.png" width="1000"/>]()

[<img src="docs/images/img_04.png" width="1000"/>]()

[<img src="docs/images/img_05.png" width="1000"/>]()

[<img src="docs/images/img_06.png" width="1000"/>]()

[<img src="docs/images/img_07.png" width="1000"/>]()

[<img src="docs/images/img_08.png" width="1000"/>]()

[<img src="docs/images/img_09.png" width="1000"/>]()

[<img src="docs/images/img_10.png" width="1000"/>]()

[<img src="docs/images/img_11.png" width="1000"/>]()

[<img src="docs/images/img_12.png" width="1000"/>]()

[<img src="docs/images/img_13.png" width="1000"/>]()

[<img src="docs/images/img_14.png" width="1000"/>]()

[<img src="docs/images/img_15.png" width="1000"/>]()

[<img src="docs/images/img_16.png" width="1000"/>]()

[<img src="docs/images/img_19.png" width="1000"/>]()

[<img src="docs/images/img_20.png" width="1000"/>]()

[<img src="docs/images/img_21.png" width="1000"/>]()

[<img src="docs/images/img_22.png" width="1000"/>]()
