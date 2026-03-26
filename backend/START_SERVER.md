# Starting the Backend Server

## Quick Start

1. **Activate Virtual Environment:**
   ```powershell
   cd backend
   .\venv\Scripts\Activate.ps1
   ```

2. **Run Migrations (if needed):**
   ```powershell
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Start the Server:**
   ```powershell
   python manage.py runserver --skip-checks
   ```
   
   **Note:** The `--skip-checks` flag bypasses cache backend validation warnings. These warnings are expected in development and don't affect functionality since rate limiting is disabled.
   
   **Alternative:** Use the provided scripts:
   - Windows: Double-click `run_server.bat`
   - PowerShell: `.\run_server.ps1`

## Server URLs

- **API Base URL:** http://localhost:8000/api/
- **API Documentation (Swagger):** http://localhost:8000/api/docs/
- **Admin Panel:** http://localhost:8000/admin/

## Environment Setup

The `.env` file is already configured with your database credentials:
- Database: `mpayhub`
- Host: `localhost:5432`
- User: `postgres`

## First Time Setup

If this is your first time running the server:

1. **Create a superuser:**
   ```powershell
   python manage.py createsuperuser
   ```

2. **Seed initial data (optional):**
   ```powershell
   python scripts/seed_data.py
   ```

## Troubleshooting

### Cache Backend Warning
The cache backend warning is expected in development and won't affect functionality. Rate limiting is disabled in development mode.

### Database Connection Issues
- Ensure PostgreSQL is running
- Verify database credentials in `.env` file
- Check if database `mpayhub` exists

### Port Already in Use
If port 8000 is already in use, specify a different port:
```powershell
python manage.py runserver 8001
```
