# 🎯 Smart Recruit — Internal HR & Recruitment Management System

A full-stack web application for managing the complete internal recruitment lifecycle — from vacancy requests by employees to AI-powered resume screening, intelligent candidate shortlisting, interview scheduling, and onboarding.

The system uses **Retrieval-Augmented Generation (RAG)** with **Sentence Transformers + ChromaDB + Groq LLM** to efficiently screen resumes while reducing LLM cost and preserving candidate privacy.

---

# 🔄 How It Works — Full Recruitment Flow

Employee raises vacancy request
↓
HR / Admin reviews & approves → Job Opening created
↓
Recruitment team uploads resumes (Bulk Upload Supported)
↓
Resume files received (PDF or DOCX)
↓

┌─────────────────────────────────────────┐
│ Resume Parsing Pipeline                 │
│                                         │
│ DOCX → python-docx extracts text        │
│ Text PDF → pdfplumber extracts text     │
│ Scanned PDF → OCR via pytesseract       │
└─────────────────────────────────────────┘

```
    ↓  
```

Extracted text sent for section-based chunking

```
    ↓  
```

┌─────────────────────────────────────────┐
│ Section Based Chunking                  │
│                                         │
│ Personal Information                    │
│ Skills                                  │
│ Experience                              │
│ Education                               │
│ Projects                                │
│ Certifications                          │
└─────────────────────────────────────────┘

```
    ↓  
```

Sentence Transformer generates embeddings

```
    ↓  
```

Embeddings stored in ChromaDB Vector Database

```
    ↓  
```

Job Description received

```
    ↓  
```

Generate Job Description embedding

```
    ↓  
```

Vector similarity search performed

```
    ↓  
```

Retrieve top matching resumes only

```
    ↓  
```

PII extraction removes:

* Name
* Email
* Phone number
* Address
* Sensitive information

  ```
    ↓  
  ```

Threshold check performed

If similarity score > threshold:

→ Candidate directly shortlisted

Else:

→ Retrieved resumes sent to Groq LLM (Llama 3.1)

```
    ↓  
```

LLM generates:

* Match score
* Missing skills
* Candidate strengths
* Detailed reasoning

  ```
    ↓  
  ```

HR views screening results

```
    ↓  
```

JRHR / HR manages candidates using Kanban board

[Shortlisted → Interview Scheduled → Selected / Rejected]

```
    ↓  
```

Interview invitation email sent

```
    ↓  
```

Selected → Candidate onboarding
Rejected → Rejection email sent

---

# 📌 Features

## 👥 Employee & Vacancy Management

* Employees can raise vacancy requests
* HR/Admin approves requests
* Approved requests automatically create job openings

---

## 📄 Bulk Resume Upload

* Upload multiple resumes simultaneously
* Supports PDF and DOCX
* Supports scanned resumes

---

## 🤖 AI-Powered Resume Screening (RAG)

* Uses Retrieval-Augmented Generation architecture
* Resume section-based chunking
* Sentence Transformer embeddings
* ChromaDB vector storage
* Semantic search retrieval
* Groq LLM evaluation

---

## 🔒 Privacy Preserving Screening

PII extraction layer removes:

* Names
* Emails
* Phone numbers
* Addresses
* Sensitive information

Benefits:

* Better privacy
* Reduced bias
* Safer AI processing

---

## ⚡ Intelligent Auto Shortlisting

Candidates with high similarity score:

→ Automatically shortlisted

Lower score candidates:

→ Sent to LLM for evaluation

---

## 📊 Candidate Results

HR can view:

* Match scores
* Candidate strengths
* Missing skills
* Detailed AI reasoning
* Ranking

---

## 🗂️ Kanban Interview Pipeline

Drag-and-drop workflow:

Shortlisted
→ Interview Scheduled
→ Selected
→ Rejected

Actions:

* Send interview email
* Send rejection email
* Trigger onboarding

---

## 🔐 Role-Based Access Control

| Role             | Access                                          |
| ---------------- | ----------------------------------------------- |
| Admin            | Full access                                     |
| HR               | Approve vacancies, shortlist candidates, Kanban |
| JRHR             | Manage interview stages                         |
| Recruitment Team | Upload resumes and run screening                |
| Employee         | Raise vacancy requests                          |

---

# 🛠️ Tech Stack

| Layer           | Technology                       |
| --------------- | -------------------------------- |
| Backend         | Django, Django REST Framework    |
| Frontend        | HTML, CSS, JavaScript            |
| AI / LLM        | Groq API (Llama 3.1)             |
| Embedding Model | Sentence Transformers            |
| Vector Database | ChromaDB                         |
| Database        | SQLite (dev) / PostgreSQL (prod) |
| Authentication  | JWT (SimpleJWT)                  |
| OCR             | pytesseract + pdf2image          |
| PDF Parsing     | pdfplumber                       |
| DOCX Parsing    | python-docx                      |
| Email           | Mailtrap                         |
| Environment     | python-dotenv                    |

---

# 📁 Project Structure

```text
smart-recruit/

├── frontend/
│   ├── css/
│   │   └── style.css
│   ├── index.html
│   ├── admin-dashboard.html
│   ├── employee-dashboard.html
│   ├── hr-screening-results.html
│   ├── jrhr-dashboard.html
│   ├── jrhr-kanban.html
│   ├── recruitment-screen.html
│   └── recruitment-resumes.html

└── backend/
    ├── accounts/
    ├── employee_management/
    │   ├── settings.py
    │   ├── urls.py
    │   ├── asgi.py
    │   └── wsgi.py

    ├── jobs/
    ├── masters/

    ├── recruitment/
    │   ├── migrations/
    │   ├── models.py
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │
    │   └── utils/
    │       ├── resume_parser.py
    │       ├── section_chunker.py
    │       ├── embedding_service.py
    │       ├── vector_store.py
    │       ├── pii_extractor.py
    │       └── rag_pipeline.py

    ├── media/
    ├── chromadb/
    ├── manage.py
    └── requirements.txt
```

---

# ⚙️ Setup & Installation

### Clone repository

```bash
git clone https://github.com/Soumya-Medichelmila/smart-recruit.git

cd smart-recruit
```

### Create virtual environment

Windows:

```bash
python -m venv venv

venv\Scripts\activate
```

Linux/Mac:

```bash
python -m venv venv

source venv/bin/activate
```

### Install dependencies

```bash
pip install -r backend/requirements.txt
```

### Configure .env

```env
GROQ_API_KEY=your_api_key

SECRET_KEY=your_secret_key

DEBUG=True

DATABASE_URL=your_database_url

EMAIL_HOST=sandbox.smtp.mailtrap.io

EMAIL_PORT=2525

EMAIL_HOST_USER=your_user

EMAIL_HOST_PASSWORD=your_password

EMAIL_USE_TLS=True
```

### Run migrations

```bash
cd backend

python manage.py migrate
```

### Create admin

```bash
python manage.py createsuperuser
```

### Start server

```bash
python manage.py runserver
```

---

# 📡 API Endpoints

### Authentication

| Method | Endpoint           |
| ------ | ------------------ |
| POST   | /api/auth/login/   |
| POST   | /api/auth/refresh/ |

### Recruitment

| Method | Endpoint                                   |
| ------ | ------------------------------------------ |
| POST   | /api/recruitment/bulk-upload/              |
| POST   | /api/recruitment/screen/<job_id>/          |
| GET    | /api/recruitment/results/<job_id>/         |
| POST   | /api/recruitment/shortlist/<candidate_id>/ |

---

# 🤖 AI Screening Details

Resume Upload
↓

Resume Parsing
↓

Section Based Chunking
↓

Sentence Transformer Embeddings
↓

Store in ChromaDB
↓

Generate JD Embedding
↓

Semantic Search
↓

Retrieve Top Matches
↓

Remove PII
↓

Threshold Check

High score?

YES → Auto Shortlist

NO → Send to Groq LLM

↓

Generate Final Result

---

# 📦 Key Dependencies

* django
* djangorestframework
* djangorestframework-simplejwt
* groq
* sentence-transformers
* chromadb
* pdfplumber
* pytesseract
* pdf2image
* python-docx
* python-dotenv
* Pillow

---

# 📧 Email Notifications

| Trigger             | Action                    |
| ------------------- | ------------------------- |
| Interview Scheduled | Send interview invitation |
| Rejected            | Send rejection email      |
| Selected            | Trigger onboarding        |

---

# 🚫 .gitignore

```gitignore
venv/
__pycache__/
*.pyc
.env
db.sqlite3
media/
chromadb/
staticfiles/
.vscode/
```

---

# 👨‍💻 Author

Soumya Medichelmila

Built with Django REST Framework + RAG + ChromaDB + Sentence Transformers + Groq AI + OCR + Mailtrap
