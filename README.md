#  CallHub Phone Directory Management System  
**CS-432 Assignment 2**

---

##  Overview

This project implements the **CallHub Phone Directory Management System** as part of CS-432 Assignment 2.  
The system provides a complete solution for managing member information with secure access control, efficient data retrieval, and auditing mechanisms.

* **Module A: Lightweight DBMS with B+ Tree Index:** A custom, in-memory database management system built from scratch. It uses a custom B+ Tree data structure to solve the inefficiencies of linear search (O(n)), enabling ultra-low latency contact lookups (O(log n)) and efficient range queries for scaling applications.
* **Module B: Backend Application & UI:** A complete Flask-based backend providing a RESTful API, web interface, Role-Based Access Control (RBAC), and database auditing mechanisms.
  
### Key Highlights
- Custom B+ Tree indexing vs. Brute-force linear search benchmarking
- Graphviz-based visualization of tree structure
- Role-Based Access Control (RBAC)  
- RESTful API development using Flask  
- Web-based user interface  
- Audit logging and monitoring  
- Performance optimization using indexing and benchmarking  

---

## Project Structure  

```
Assignment2/
├─ Module A/
│  ├─ database/
│  │  ├─ bplustree.py              
│  │  ├─ bruteforce.py             
│  │  ├─ db_manager.py  
│  │  ├─ performance_analyzer.py             
│  │  ├─ table.py                  
│  ├─ requirements.txt
│  ├─ report.ipynb
├─ Module B/
│  ├─ Module_B_Report.md
│  ├─ benchmarks/ (# here json files will be saved)
│  ├─ callhub_backend/ (This includes the complete app)
│  │  ├─ benchmark_and_index.py
│  │  ├─ config.py
│  │  ├─ db.py
│  │  ├─ main.py
│  │  ├─ report.ipynb
│  │  ├─ requirements.txt
│  │  ├─ setup_audit_triggers.py
│  │  ├─ routes/
│  │  │  ├─ auth_routes.py
│  │  │  ├─ member_routes.py
│  │  │  ├─ portfolio_routes.py
│  │  ├─ static/
│  │  │  ├─ css/style.css
│  │  │  ├─ js/login.js
│  │  │  ├─ js/protfolio.js
│  │  ├─ templates/
│  │  │  ├─ create.html
│  │  │  ├─ delete.html
│  │  │  ├─ error.html
│  │  │  ├─ Homepage.html
│  │  │  ├─ Login.html
│  │  │  ├─ portfolio.html
│  │  │  ├─ read.html
│  │  │  ├─ success.html
│  │  │  ├─ update.html
│  │  ├─ utils/
│  │  │  ├─ auth.py
│  │  │  ├─ logger.py
│  │  │  ├─ rbac.py
```

---

##  Prerequisites  

- Python 3.10 or higher  
- pip  
- Virtual environment 
- MySQL (or database configured in `config.py`)  

---

##  Setup Instructions  

### 1. Navigate to Backend Directory  
```bash
cd Assignment2/Module B/callhub_backend
```

### 2. Create Virtual Environment  
```bash
python -m venv .venv
```

### 3. Activate Virtual Environment  

**Windows:**
```bash
.venv\Scripts\activate
```


### 4. Install Dependencies  
```bash
pip install -r requirements.txt
```

### 5. Database Configuration  
- Update database credentials in `config.py` using .env 
- Create the required database in MySQL  

### 6. Setup Audit Triggers  
```bash
python setup_audit_triggers.py
```

---

##  Running the Application  

```bash
python main.py
```

Open your browser and go to the link showed after running this file.

---

##  Core Features  

- Authentication using sessions  
- Member CRUD operations  
- Search and filtering  
- Role-Based Access Control (RBAC)  
- Portfolio view with structured data  
- Audit logging (database + file)  
- Performance benchmarking and indexing  

---

##  Benchmarking  

```bash
python benchmark_and_index.py
```

---

After this the API response time and query execution time before and after indexing will be saved benchmarks/ directory in JSON files, and then can run report.ipynb to see the plots.
