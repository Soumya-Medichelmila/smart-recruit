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
  Resume file received (PDF or DOCX)
        ↓
  ┌─────────────────────────────────┐
  │  Is PDF text-based?             │
  │  YES → pdfplumber extracts text │
  │  NO (scanned/image PDF)         │
  │      → pytesseract OCR extracts │
  └─────────────────────────────────┘
        ↓
  Extracted text sent to Groq LLM (Llama 3.1)
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
- Supports both **text-based PDFs** (via pdfplumber) and **scanned/image PDFs** (via pytesseract OCR)

### 📄 Smart Resume Parsing Pipeline
| File Type | Parsing Method |
|-----------|---------------|
| DOCX | python-docx |
| Text-based PDF | pdfplumber |
| Scanned / Image PDF | pdf2image + pytesseract OCR |

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
| PDF Extraction | pdfplumber (text-based PDFs) |
| OCR (Scanned PDFs) | pytesseract + pdf2image + Poppler |
| DOCX Parsing | python-docx |
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
    │   ├── urls.py
    │   └── utils/
    │       └── resume_parser.py     # pdfplumber + pytesseract logic
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

### 4. Install Tesseract OCR Engine (for scanned PDFs)

Tesseract is an external binary required by pytesseract.

**Windows:**
1. Download the installer from [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run the installer (default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
3. Add Tesseract to your system PATH, **or** set it in your code:
```python
# In resume_parser.py or settings.py
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr
```

**Mac:**
```bash
brew install tesseract
```

### 5. Install Poppler (required by pdf2image)

pdf2image converts scanned PDF pages into images for OCR.

**Windows:**
1. Download Poppler for Windows from [https://github.com/oschwartz10612/poppler-windows/releases](https://github.com/oschwartz10612/poppler-windows/releases)
2. Extract and add the `bin/` folder to your system PATH

**Ubuntu/Debian:**
```bash
sudo apt install poppler-utils
```

**Mac:**
```bash
brew install poppler
```

### 6. Create `.env` file inside `backend/`
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

### 7. Run migrations
```bash
cd backend
python manage.py migrate
```

### 8. Create superuser
```bash
python manage.py createsuperuser
```

### 9. Start the server
```bash
python manage.py runserver
```

### 10. Open the frontend
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

### Resume Parsing Pipeline

Before sending to the LLM, each uploaded resume goes through a smart parsing pipeline:

```
Resume Uploaded (PDF or DOCX)
        ↓
   Is it a DOCX?
   YES → python-docx extracts text directly
        ↓
   Is it a PDF?
        ↓
   ┌─── Try pdfplumber ───────────────────────────────┐
   │    Extracts text from text-based/digital PDFs    │
   │    Fast, accurate, preserves formatting          │
   └──────────────────────────────────────────────────┘
        ↓
   Was text found? (len > threshold)
   YES → Use pdfplumber text ✅
   NO  → PDF is scanned/image-based
        ↓
   ┌─── Fallback: pytesseract OCR ────────────────────┐
   │    pdf2image converts each page → image          │
   │    pytesseract reads text from image via OCR     │
   │    Handles scanned resumes, photo PDFs           │
   └──────────────────────────────────────────────────┘
        ↓
   Extracted text → sent to Groq LLM for scoring
```

### Scoring
| Score | Match Level |
|-------|-------------|
| 80–100 | Excellent match |
| 60–79 | Good match |
| 40–59 | Partial match |
| 0–39 | Poor match |

---

## 📦 Key Dependencies

```
django
djangorestframework
djangorestframework-simplejwt
groq
pdfplumber
pytesseract
pdf2image
python-docx
python-dotenv
Pillow
```

> Full list in `backend/requirements.txt`

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
Built with Django REST Framework + Groq AI + pdfplumber + pytesseract OCR + Mailtrap

---

## 📄 License

MIT License — free to use and modify.
