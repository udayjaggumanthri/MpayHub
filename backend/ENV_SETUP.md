# Environment Setup Guide

## .env File Created

Your `.env` file has been created with the following database configuration:

```
DATABASE_URL=postgresql://postgres:StrongPass%40123@localhost:5432/mpayhub
```

## Database Configuration

The backend is configured to use your PostgreSQL database:
- **Host:** localhost
- **Port:** 5432
- **Database:** mpayhub
- **User:** postgres
- **Password:** StrongPass@123

## Next Steps

1. **Verify Database Connection:**
   ```bash
   python manage.py check --database default
   ```

2. **Create Migrations:**
   ```bash
   python manage.py makemigrations
   ```

3. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Create Superuser:**
   ```bash
   python manage.py createsuperuser
   ```

5. **Seed Initial Data (Optional):**
   ```bash
   python scripts/seed_data.py
   ```

6. **Start Development Server:**
   ```bash
   python manage.py runserver
   ```

## Environment Variables

The `.env` file includes:
- Database connection (using DATABASE_URL)
- Django settings (DEBUG, SECRET_KEY)
- CORS configuration
- Placeholders for external API keys

## Security Note

The `.env` file is automatically ignored by git (via `.gitignore`). Never commit this file to version control as it contains sensitive credentials.

## Updating Database Credentials

If you need to change database credentials, edit the `.env` file:
- Update `DATABASE_URL` with new credentials
- Or update individual `DB_*` variables if not using DATABASE_URL
