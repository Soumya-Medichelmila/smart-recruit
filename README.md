# smart-recruit


# 🚀 Smart Recruit — AI-Powered HR & Recruitment Management System

A full-stack Django REST API for managing employees, job openings, and AI-powered resume screening using Groq LLM.

---

## 📌 Features

- 🔐 JWT Authentication & Role-Based Access Control
- 👥 Employee & Department Management
- 📋 Job Opening Management
- 📄 Resume Upload & Management
- 🤖 AI-Powered Resume Screening (Groq LLM)
- 📊 Screening Results & Candidate Scoring
- 🏢 HR / Admin / Recruitment Department Permissions

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, Django REST Framework |
| AI/LLM | Groq API (Llama 3.1) |
| Database | PostgreSQL / SQLite |
| Auth | JWT (SimpleJWT) |
| File Parsing | pdfplumber, python-docx |
| Environment | python-dotenv |

---

## 📁 Project Structure

```
smart-recruit/
├── manage.py
├── .env                        # API keys (never commit)
├── .gitignore
├── requirements.txt
├── employee_management/        # Core Django settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                   # Auth & permissions
├── employees/                  # Employee management
├── jobs/                       # Job openings
└── recruitment/                # Resumes & AI screening
    ├── models.py
    ├── views.py
    ├── serializers.py
    └── urls.py
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/smart-recruit.git
cd smart-recruit
```

### 2. Create and activate virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create `.env` file in project root
```env
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=your_django_secret_key_here
DEBUG=True
DATABASE_URL=your_database_url_here
```

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Create superuser
```bash
python manage.py createsuperuser
```

### 7. Start development server
```bash
python manage.py runserver
```

---

## 🔑 Get Free Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Generate an API key
4. Paste it in your `.env` file

---

## 📡 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Login & get JWT token |
| POST | `/api/auth/refresh/` | Refresh JWT token |

### Recruitment
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/recruitment/resumes/` | Recruitment Dept | List all resumes |
| POST | `/api/recruitment/resumes/` | Recruitment Dept | Upload resume |
| DELETE | `/api/recruitment/resumes/<id>/` | Recruitment Dept | Delete resume |
| POST | `/api/recruitment/screen/<job_id>/` | Recruitment Dept | Run AI screening |
| GET | `/api/recruitment/results/<job_id>/` | HR / Admin | View screening results |
| GET | `/api/recruitment/results/` | HR / Admin | List all screened jobs |

---

## 🤖 AI Screening

The system uses **Groq LLM (Llama 3.1)** to automatically screen resumes against job descriptions.

### How it works:
1. Upload resumes (PDF or DOCX)
2. Trigger screening for a specific job opening
3. LLM evaluates each resume against the job description
4. Returns match scores (0-100) with reasons

### Scoring:
| Score | Match Level |
|-------|-------------|
| 80-100 | Excellent match |
| 60-79 | Good match |
| 40-59 | Partial match |
| 0-39 | Poor match |

---

## 🔒 Permissions

| Role | Access |
|------|--------|
| Admin | Full access |
| HR | View screening results, manage employees |
| Recruitment Dept | Upload/manage resumes, run AI screening |
| Others | Limited access |

---

## 📦 Requirements

```
django
djangorestframework
djangorestframework-simplejwt
python-dotenv
requests
pdfplumber
python-docx
psycopg2-binary
```

Generate full requirements:
```bash
pip freeze > requirements.txt
```

---

## 🚫 .gitignore

Make sure these are never committed:
```
.env
__pycache__/
*.pyc
venv/
db.sqlite3
media/
staticfiles/
.vscode/
```

---

## 👨‍💻 Author

**Soumya Medichelmila**  
Built with Django REST Framework + Groq AI

---

## 📄 License

MIT License — free to use and modify.
