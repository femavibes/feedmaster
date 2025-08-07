# Project Guidelines for Gemini Agent

This file provides specific instructions for the Gemini Code Assist agent to ensure consistent and effective assistance.

## General Rules:
- Prefer **FastAPI** for new API endpoints.
- For database interactions, use **SQLAlchemy**. 
- All new functions should include **docstrings** explaining their purpose, arguments, and return values.
- **Prioritize security:** Always consider potential vulnerabilities (e.g., SQL injection, XSS) and suggest secure coding practices.
- Uses docker compose v2

## Specific Component Notes:
- **Frontend (`frontend/` directory):** This uses Vue.js 3. Ensure all changes are compatible with Vue's reactivity system.
- **API (`api/` directory):** This is a FastAPI application. New endpoints should follow `/api/v1/{resource}` structure.
- **Database (`db/` service):** PostgreSQL. Do not modify the database schema directly without explicit confirmation. Docker container. 

## Common Pitfalls to Avoid:
- Do not hardcode sensitive information (API keys, passwords). Use environment variables.
- Avoid creating temporary files in the root directory. Use `/tmp` or specific project temp directories.

## When in doubt:
- Ask clarifying questions.
- Propose a plan before making significant changes.

### Frontend Project Notes

The project has two distinct frontend directories:

* **`frontend/`**: This is the **primary Vue.js project** we are actively working on. All new features, components, and changes should be implemented here.
* **`frontendtest/`**: This directory contains older but **still functional test pages** like `testpage.html` and `admin.html` plus other html files. These pages are to be used as a **reference** for implementing features in the main Vue.js project.

## Protected Files

# Files/directories that require explicit confirmation before modification.
# Use glob patterns relative to the project root.
# Add patterns here for files or directories you consider critical or stable.
# Examples:
# - backend/aggregations/**/*.py  # Confirm before changing any aggregation logic
# - frontend/src/components/**/*.vue # Confirm before changing core UI components
# - Dockerfile