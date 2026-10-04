# To-do list

The most basic to-do list in Django: add a to-do, mark it done, delete it.

## Run it on your laptop

You need Python 3.10 or newer. Check with `python3 --version` (on Windows, `py --version`).

**1. Get the code.**

```bash
git clone https://github.com/kreativitea/anyone-can-build-todo.git
cd anyone-can-build-todo
```

**2. Make a virtual environment and turn it on.** This keeps the project's packages
separate from everything else on your computer. When it is on, your prompt starts with `(.venv)`.

Mac:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

If Windows says running scripts is disabled, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then try again.

**3. Install the packages.**

```bash
pip install -r requirements.txt
```

**4. Create the database.** This makes a file called `db.sqlite3`.

```bash
python manage.py migrate
```

**5. Start the server.**

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. Press `Ctrl+C` in the terminal to stop the server.

**6. Run the tests.**

```bash
python manage.py test
```

You should see `Ran 5 tests` and `OK`.

Next time, you only need to `cd` into the folder, turn the virtual environment on again
(step 2, second line), and run step 5.

## How it is put together

| File | What it does |
|---|---|
| `config/settings.py` | Settings for the whole project |
| `config/urls.py` | Sends each address to the right app |
| `todos/models.py` | The `Todo` table in the database |
| `todos/urls.py` | The addresses of the to-do pages |
| `todos/views.py` | What happens when each address is visited |
| `todos/templates/todos/todo_list.html` | The page you see |
| `todos/tests.py` | The tests |

## Put it on the internet

A live server needs three environment variables. Never put their real values in the code.

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A long random string. Make one with `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | The site's address without `https://`, for example `my-todo.onrender.com` |

Build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate
```

Start command:

```bash
gunicorn config.wsgi
```
