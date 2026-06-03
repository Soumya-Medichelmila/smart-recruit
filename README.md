# 🎯 Smart Recruit — Internal HR & Recruitment Management System

A full-stack web application for managing the **end-to-end internal recruitment lifecycle** — from vacancy requests by employees to AI-powered resume screening, candidate shortlisting, interview scheduling, and onboarding.

---

## 🔄 How It Works — Full Recruitment Flow

```
Employee raises vacancy request
        ↓
HR / Admin reviews & approves → Job Opening created
        ↓
Recruitment team uploads resumes & runs AI screening
        ↓
HR views screening results → Shortlists candidates
        ↓
JRHR / HR uses Kanban board → Drags candidates through pipeline
  [Shortlisted → Interview Scheduled → Selected / Rejected]
        ↓
Interview Scheduled → Candidate receives email (via Mailtrap)
        ↓
Selected → Employee is added to the system
Rejected → Candidate receives rejection email
```

---

## 📌 Features

### 👥 Employee & Vacancy Management
- Internal employees can raise vacancy requests
- HR / Admin reviews and approves requests
- Approved requests automatically create job openings

### 🤖 AI-Powered Resume Screening
- Recruitment team uploads resumes (PDF / DOCX) for a job opening
- AI (Groq LLM — Llama 3.1) screens each resume against the job description
- Generates match scores (0–100) with detailed reasons

### 📊 Shortlisting & Results
- HR views AI screening results per job opening
- Shortlists candidates based on scores and review

### 🗂️ Kanban Interview Pipeline (JRHR / HR)
- Drag-and-drop Kanban board to manage candidate stages:
  - **Shortlisted → Interview Scheduled → Selected / Rejected**
- Moving to **Interview Scheduled** → sends interview invitation email (via Mailtrap)
- Moving to **Rejected** → sends rejection email (via Mailtrap)
- Moving to **Selected** → triggers employee onboarding (add to system)

### 🔐 Role-Based Access Control
| Role | Access |
|------|--------|
| Admin | Full access to everything |
| HR | Approve vacancies, view results, shortlist, use Kanban |
| JRHR | Use Kanban pipeline, manage interview stages |
| Recruitment Dept | Upload resumes, run AI screening |
| Employee | Raise vacancy requests only |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 6.0, Django REST Framework |
| Frontend | HTML, CSS, JavaScript |
| AI / LLM | Groq API (Llama 3.1) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT (SimpleJWT) |
| Email | Mailtrap (dummy SMTP for testing) |
| File Parsing | pdfplumber, python-docx |
| Environment | python-dotenv |

---

## 📁 Project Structure

```
smart-recruit/
├── frontend/                        # HTML/CSS/JS frontend
│   ├── css/
│   │   └── style.css
│   ├── index.html                   # Login page
│   ├── admin-dashboard.html
│   ├── employee-dashboard.html
│   ├── hr-screening-results.html
│   ├── jrhr-dashboard.html
│   ├── jrhr-kanban.html             # Kanban drag-and-drop board
│   ├── jrhr-interview-schedule.html
│   ├── recruitment-screen.html
│   ├── recruitment-resumes.html
│   └── ...
│
└── backend/                         # Django REST API
    ├── accounts/                    # Auth, users, roles
    ├── employee_management/         # Django project settings
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py
    ├── jobs/                        # Job openings
    ├── masters/                     # Departments & master data
    ├── recruitment/                 # Resumes, screening, shortlisting
    │   ├── migrations/
    │   ├── models.py
    │   ├── views.py
    │   ├── serializers.py
    │   └── urls.py
    ├── media/                       # Uploaded resumes
    ├── .gitignore
    ├── manage.py
    └── requirements.txt
```

---

## ⚙️ Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/Soumya-Medichelmila/smart-recruit.git
cd smart-recruit
```

### 2. Set up virtual environment
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
pip install -r backend/requirements.txt
```

### 4. Create `.env` file inside `backend/`
```env
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=your_django_secret_key_here
DEBUG=True
DATABASE_URL=your_database_url_here

# Mailtrap email config
EMAIL_HOST=sandbox.smtp.mailtrap.io
EMAIL_PORT=2525
EMAIL_HOST_USER=your_mailtrap_user
EMAIL_HOST_PASSWORD=your_mailtrap_password
EMAIL_USE_TLS=True
```

### 5. Run migrations
```bash
cd backend
python manage.py migrate
```

### 6. Create superuser
```bash
python manage.py createsuperuser
```

### 7. Start the server
```bash
python manage.py runserver
```

### 8. Open the frontend
Open `frontend/index.html` in your browser or serve it via Live Server.

---

## 🔑 Get Free API Keys

### Groq API (AI Screening)
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Generate an API key and paste it in `.env`

### Mailtrap (Email Testing)
1. Go to [mailtrap.io](https://mailtrap.io)
2. Sign up for a free account
3. Go to **Email Testing → Inboxes → SMTP Settings**
4. Copy your credentials into `.env`

---

## 📡 API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login/` | Login & get JWT token |
| POST | `/api/auth/refresh/` | Refresh JWT token |

### Vacancy & Jobs
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/jobs/vacancy-request/` | Employee | Raise vacancy request |
| GET | `/api/jobs/vacancy-requests/` | HR / Admin | View all requests |
| PATCH | `/api/jobs/vacancy-request/<id>/approve/` | HR / Admin | Approve → creates job opening |
| GET | `/api/jobs/openings/` | All | List job openings |

### Recruitment & Screening
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| GET | `/api/recruitment/resumes/` | Recruitment | List all resumes |
| POST | `/api/recruitment/resumes/` | Recruitment | Upload resume |
| DELETE | `/api/recruitment/resumes/<id>/` | Recruitment | Delete resume |
| POST | `/api/recruitment/screen/<job_id>/` | Recruitment | Run AI screening |
| GET | `/api/recruitment/results/<job_id>/` | HR / Admin | View screening results |
| GET | `/api/recruitment/results/` | HR / Admin | All screened jobs |

### Shortlisting & Kanban
| Method | Endpoint | Access | Description |
|--------|----------|--------|-------------|
| POST | `/api/recruitment/shortlist/<candidate_id>/` | HR | Shortlist candidate |
| PATCH | `/api/recruitment/shortlist/<id>/stage/` | HR / JRHR | Update Kanban stage |

---

## 🤖 AI Screening Details

The system uses **Groq LLM (Llama 3.1)** to automatically evaluate resumes against job descriptions.

**Process:**
1. Upload resumes (PDF or DOCX) for a specific job opening
2. Trigger screening — LLM reads each resume and the job description
3. Returns a score (0–100) with a detailed reason for each candidate

**Scoring:**
| Score | Match Level |
|-------|-------------|
| 80–100 | Excellent match |
| 60–79 | Good match |
| 40–59 | Partial match |
| 0–39 | Poor match |

---

## 📧 Email Notifications (via Mailtrap)

All emails are sent to **Mailtrap's sandbox inbox** for testing — no real emails are sent.

| Trigger | Email Sent To |
|---------|--------------|
| Candidate moved to **Interview Scheduled** | Candidate — interview invitation |
| Candidate moved to **Rejected** | Candidate — rejection email |
| Candidate moved to **Selected** | Internal team — onboarding trigger |

---

## 🚫 .gitignore

The following are never committed:
```
venv/
__pycache__/
*.pyc
.env
db.sqlite3
media/
staticfiles/
.vscode/
```

---

## 👨‍💻 Author

**Soumya Medichelmila**  
Built with Django REST Framework + Groq AI + Mailtrap

---

## 📄 License

MIT License — free to use and modify.
