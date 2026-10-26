# EduTrack — Student Performance Analysis System

EduTrack is a full-stack academic performance management and analytics system built with **Python**, **Flask**, and **MySQL**. It features student profile tracking, multi-assessment marks entry, real-time grading, performance analytics, and automated Matplotlib data visualization.

---

## 🌟 Features

- **Dashboard**: High-level overview with total students, pass percentage, class average, and top performer.
- **Student Management**: Add, view, edit, search, and delete students with duplicate roll-number protection.
- **Marks Management**: Record and update marks across assessments (*Internal 1*, *Internal 2*, *Semester Exam*) with automatic mark validation and duplicate submission prevention.
- **Results Viewer**: Student-by-student transcript view with percentage, letter grades (A+ to F), and pass/fail status.
- **Performance Analytics**:
  - Class subject-wise averages.
  - Dynamically generated Matplotlib bar chart (encoded in base64).
  - Topper ranking (students completing all 4 core subjects).
  - Students requiring teacher assistance (any failed subject).
  - Incomplete records alert.
- **Cloud-Ready Backend**:
  - Dual driver support (`pymysql` and `mysql-connector-python`).
  - Automatic `DATABASE_URL` parsing and individual `DB_*` support.
  - Idempotent auto-migration (`init_db`) on startup — no manual SQL shell execution required on Render!
  - 1-click sample data seeding (`/seed-demo-data`).

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.x, Gunicorn
- **Database**: MySQL 8.x / TiDB Cloud / Aiven MySQL
- **Drivers**: PyMySQL / MySQL Connector Python
- **Visualization**: Matplotlib (headless `Agg` backend)
- **Frontend**: HTML5, CSS3, JavaScript (Jinja2 templates)

---

## 📁 Project Structure

```text
├── app.py              # Main Flask application & routes
├── db.py               # Robust database connection engine & auto-migration
├── database.sql        # MySQL table schema and seed definitions
├── db_test.py          # Database connection diagnostic script
├── Procfile            # Gunicorn entrypoint for Render
├── render.yaml         # Render Infrastructure-as-Code Blueprint
├── requirements.txt    # Python production dependencies
├── .env.example        # Environment variables template
├── static/
│   ├── style.css       # Clean, modern responsive stylesheet
│   └── script.js       # Search filters & UI interactions
└── templates/
    ├── base.html       # Sidebar layout and header
    ├── dashboard.html  # Statistics & quick navigation
    ├── students.html   # Student records & form
    ├── edit_student.html
    ├── marks.html      # Assessment marks records & form
    ├── edit_mark.html
    ├── results.html    # Academic transcript view
    └── analytics.html  # Visual analytics & ranking
```

---

## 🚀 Running Locally

### 1. Prerequisites
- Python 3.10+
- MySQL Server (Local MySQL, XAMPP, or Docker)

### 2. Configure Local Database
In your local MySQL client (e.g. MySQL Command Line, Workbench, or phpMyAdmin), run:
```sql
CREATE DATABASE IF NOT EXISTS student_performance_db;
```

### 3. Setup Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment
Copy `.env.example` to `.env` and fill in your MySQL credentials:
```ini
FLASK_SECRET_KEY=your-secret-key-here
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=student_performance_db
DB_SSL=false
```

### 5. Verify Database & Start App
```bash
# Test database connectivity
python db_test.py

# Start the development server
python app.py
```
Open **`http://localhost:5000`** in your browser.

> **Tip:** On first launch, if your database has no records, click the **"+ Load Demo Data"** button on the dashboard to immediately test all features!

---

## ☁️ Deploying to Render (Step-by-Step)

Because Render does not provide a free MySQL database natively, pair your Render Web Service with a **free cloud MySQL database** (such as **TiDB Cloud Serverless** or **Aiven for MySQL**).

### Step 1: Create a Free Cloud MySQL Database
1. Go to [TiDB Cloud](https://tidbcloud.com/) or [Aiven](https://aiven.io/).
2. Create a free Serverless MySQL cluster (takes ~30 seconds, no credit card required).
3. Copy your database connection string or connection parameters (`Host`, `Port`, `User`, `Password`, `Database`).

### Step 2: Push Your Code to GitHub
```bash
git add .
git commit -m "Configure production-ready backend and MySQL for Render"
git push origin main
```

### Step 3: Create a Web Service on Render
1. Log in to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Select your GitHub repository: `edutrack-student-performance`.
4. Configure the service:
   - **Name**: `edutrack-performance-system`
   - **Region**: Choose the closest region (e.g., Singapore, Frankfurt, Oregon)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --workers 1 --threads 2 --timeout 120`
   - **Instance Type**: `Free`

### Step 4: Configure Environment Variables on Render
Under the **Environment Variables** tab on Render, add:

| Key | Value / Example |
| :--- | :--- |
| `FLASK_SECRET_KEY` | *(Click "Generate" or enter a random 32-character string)* |
| `DATABASE_URL` | `mysql://user:pass@gateway.tidbcloud.com:4000/edutrack?ssl-mode=REQUIRED` |
| `PYTHON_VERSION` | `3.11.9` |

*(Alternatively, instead of `DATABASE_URL`, you can add `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, and `DB_SSL=true` individually).*

### Step 5: Deploy!
- Click **Create Web Service**.
- Render will automatically build the container and launch Gunicorn.
- The app automatically initializes the schema and default subjects on startup!
- Check your live deployment at `https://<your-service-name>.onrender.com/health` to confirm database connectivity.

---

## 🩺 Health & Diagnostic Endpoints

- `GET /health` or `GET /db-test`: JSON diagnostic reporting MySQL connectivity, active driver, and table row counts.
- `GET /init-db`: Triggers automatic table creation and subject seeding.
- `GET /seed-demo-data`: Seeds 5 sample students and assessment marks for instant demonstration.

---

## 📄 License
MIT License. Built for DBMS academic demonstration and evaluation.
