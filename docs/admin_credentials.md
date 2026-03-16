# Admin Credentials Setup

This project supports first-start admin bootstrap through environment variables.

## Environment Variables

Set these before running `init_admin` or starting the server:

- `DJANGO_INITIAL_ADMIN_USERNAME` (required)
- `DJANGO_INITIAL_ADMIN_PASSWORD` (required)
- `DJANGO_INITIAL_ADMIN_EMAIL` (optional, defaults to `admin@example.com`)

Example:

```bash
export DJANGO_INITIAL_ADMIN_USERNAME=admin
export DJANGO_INITIAL_ADMIN_PASSWORD='ReplaceWithStrongPassword'
export DJANGO_INITIAL_ADMIN_EMAIL=admin@example.com
```

## Local Development

```bash
python3 manage.py migrate
python3 manage.py init_admin
python3 manage.py runserver
```

Then sign in at:

- Django admin: `http://localhost:8000/admin/`
- Web UI: `http://localhost:8000/login/`

## Docker Compose

The included `docker-compose.yml` already sets bootstrap variables and runs:

```bash
python manage.py migrate && python manage.py init_admin && python manage.py runserver 0.0.0.0:8000
```

Default demo credentials in compose:

- username: `admin`
- password: `admin123`

Change these values before non-local use.

## Credential Rotation

Update the environment variables and run:

```bash
python3 manage.py init_admin
```

If the configured user already exists, the command updates:

- password
- staff/superuser flags
- email

## Security Notes

- Do not commit real admin passwords.
- Use a long random password in production.
- Prefer secrets injection via your deployment platform rather than plain `.env` files.
