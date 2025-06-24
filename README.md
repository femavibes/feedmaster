# feedmaster
# Feedmaster Application Deployment Guide

This section outlines the necessary steps to deploy and run the Feedmaster application, including setting up the environment, managing the database, and launching the services using Docker Compose.

---

## 1. Project Setup and Configuration

Ensure your project structure and configuration files are correctly set up.

### Directory Structure:

Your project root should look similar to this:

```
your_project_root/
├── .env                  <-- Environment variables (sensitive info)
├── backend/              <-- FastAPI application code
│   ├── alembic/
│   ├── ... (other Python files: main.py, models.py, schemas.py, crud.py, etc.)
│   └── __init__.py
├── config/               <-- Application configuration files
│   └── feeds.json        <-- Defines Contrails feeds to listen to
├── FeedMaster0.12.html   <-- Frontend HTML file
├── Dockerfile            <-- Docker image build instructions
├── docker-compose.yml    <-- Orchestrates Docker services
├── alembic.ini           <-- Alembic database migration configuration
└── README.md             <-- This file
```

### Configuration Files:

* **`.env` file (at project root):**
    Create or update this file with your environment variables. **Do not commit this file to public repositories.**

    ```env
    # Database Connection
    SQLALCHEMY_DATABASE_URL="postgresql://user:password@db:5432/feedmaster_db"

    # Bluesky API for DID resolution
    BLUESKY_API_BASE_URL="[https://api.bsky.app/xrpc](https://api.bsky.app/xrpc)"

    # JWT Authentication
    SECRET_KEY="your_super_strong_and_random_secret_key_here" # !!! IMPORTANT: Replace with a secure, random string !!!
    ALGORITHM="HS256" # Or another algorithm you prefer, e.g., "HS512"
    ACCESS_TOKEN_EXPIRE_MINUTES=30 # How long access tokens are valid in minutes

    # Worker Configuration
    WORKER_POLLING_INTERVAL_SECONDS=5
    AGGREGATION_INTERVAL_MINUTES=5
    PROMINENT_DID_REFRESH_INTERVAL_MINUTES=30

    # Configuration directory (should typically be 'config')
    CONFIG_DIR="config"
    ```
    *Make sure to replace the placeholder `SECRET_KEY` with a unique, strong random string.*

* **`config/feeds.json`:**
    This file defines the Contrails feeds your `aggregator_worker` will subscribe to.
    Example `config/feeds.json`:
    ```json
    [
      {
        "id": "home-feed-graze",
        "name": "Graze Home Feed",
        "description": "The default home feed from Graze Contrails.",
        "contrails_websocket_url": "wss://contrails.graze.social/feeds/home-feed-graze",
        "tier": "silver"
      },
      {
        "id": "tech-news-graze",
        "name": "Graze Tech News",
        "description": "Tech news feed curated by Contrails.",
        "contrails_websocket_url": "wss://contrails.graze.social/feeds/tech-news-graze",
        "tier": "gold"
      }
      // Add more existing Contrails feed IDs as needed, with their specific URLs and tiers
    ]
    ```
    *Ensure this file exists and is correctly formatted. If `config/tiers.json` exists from previous iterations, delete it as it's no longer used.*

* **`docker-compose.yml` (at project root):**
    This file orchestrates your `db`, `api`, and `aggregator_worker` services. Ensure it matches the refined version provided recently:

    ```yaml
    version: '3.8'

    services:
      db:
        image: postgres:15-alpine
        restart: always
        environment:
          POSTGRES_DB: feedmaster_db
          POSTGRES_USER: user
          POSTGRES_PASSWORD: password
        volumes:
          - pgdata:/var/lib/postgresql/data
        ports:
          - "5432:5432"

      api:
        build:
          context: .
          dockerfile: Dockerfile
        command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
        volumes:
          - ./backend:/app/backend
          - ./config:/app/config
        ports:
          - "8000:8000"
        environment:
          SECRET_KEY: ${SECRET_KEY}
          ALGORITHM: ${ALGORITHM}
          ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES}
          SQLALCHEMY_DATABASE_URL: ${SQLALCHEMY_DATABASE_URL}
          BLUESKY_API_BASE_URL: ${BLUESKY_API_BASE_URL}
          CONFIG_DIR: /app/config
        depends_on:
          - db

      aggregator_worker:
        build:
          context: .
          dockerfile: Dockerfile
        command: python backend/aggregator_worker.py
        volumes:
          - ./backend:/app/backend
          - ./config:/app/config
        environment:
          SECRET_KEY: ${SECRET_KEY}
          ALGORITHM: ${ALGORITHM}
          ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES}
          SQLALCHEMY_DATABASE_URL: ${SQLALCHEMY_DATABASE_URL}
          BLUESKY_API_BASE_URL: ${BLUESKY_API_BASE_URL}
          CONFIG_DIR: /app/config
          WORKER_POLLING_INTERVAL_SECONDS: ${WORKER_POLLING_INTERVAL_SECONDS}
          AGGREGATION_INTERVAL_MINUTES: ${AGGREGATION_INTERVAL_MINUTES}
          PROMINENT_DID_REFRESH_INTERVAL_MINUTES: ${PROMINENT_DID_REFRESH_INTERVAL_MINUTES}
        depends_on:
          - db

    volumes:
      pgdata:
    ```

---

## 2. Database Migrations (Alembic)

Alembic is used to manage your database schema changes. These commands must be run from within a Docker container that has access to your application code and the database.

1.  **Start your Docker Compose services (in detached mode):**
    Navigate to your project's root directory in your terminal and run:
    ```bash
    docker compose up -d
    ```
    This will bring up your `db`, `api`, and `aggregator_worker` services.

2.  **Generate a new migration script (if schema changes were made):**
    This command tells Alembic to compare your `models.py` to your current database schema and generate a script to reconcile any differences. If this is your first time setting up the database, this will generate the script to create all your tables.
    ```bash
    docker compose exec api alembic revision --autogenerate -m "Create initial database tables"
    ```
    Review the generated script in `backend/alembic/versions/` to ensure it reflects the expected schema changes.

3.  **Apply all pending migrations to your database:**
    This command executes the SQL commands from your migration scripts, updating your database schema.
    ```bash
    docker compose exec api alembic upgrade head
    ```

    *Repeat steps 2 and 3 whenever you make changes to your `backend/models.py` file.*

---

## 3. Build and Run the Application

After configuring your `.env` and `feeds.json`, and running migrations, you can build and run your entire application stack.

* From your project's root directory, execute:
    ```bash
    docker compose up --build
    ```
    The `--build` flag ensures that your Docker images are rebuilt, incorporating any code changes you've made. This is important for initial setup and after code updates.

    You should see logs indicating that:
    * The PostgreSQL database (`db`) is running.
    * The FastAPI API (`api`) is starting up on port `8000`.
    * The aggregator worker (`aggregator_worker`) is connecting to Contrails WebSockets and beginning to process data.

---

## 4. Verify Backend API

Once your Docker services are running, you can test the backend API:

* Open your web browser and navigate to:
    * **API Documentation:** `http://localhost:8000/docs`
    * **Feeds List:** `http://localhost:8000/feeds`
    * **Posts for a Feed (e.g., home-feed-graze):** `http://localhost:8000/feeds/home-feed-graze/posts`
    * **Aggregates for a Feed (e.g., topHashtags for home-feed-graze):** `http://localhost:8000/feeds/home-feed-graze/aggregates?agg_name=topHashtags&timeframe=24h`

    You should start seeing data being returned as the `aggregator_worker` ingests posts and performs aggregations.

---

## 5. Connect Frontend (`FeedMaster0.12.html`)

Finally, ensure your `FeedMaster0.12.html` file correctly points to your backend API:

* Open `FeedMaster0.12.html` in your web browser.
* Verify that the `BASE_URL` constant within the JavaScript of the HTML file is set to your backend's address (typically `http://localhost:8000` for local development):
    ```javascript
    const BASE_URL = 'http://localhost:8000';
    ```
    Your frontend should now be able to fetch and display data from your running backend.

---

This guide should provide you with all the necessary steps for deploying your Feedmaster application.
