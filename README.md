In collaboration with my peer team, Group 31
This chatbot mimics basic AI decision-making by analyzing user inputs, identifying key terms, and matching them to predefined patterns or logic. It then selects appropriate responses based on rules or models, simulating intelligent behavior. While not truly "thinking," it imitates decision-making through structured processing and context-aware output generation.



CryptoRoast Bot

Cryptoroast is a full-stack Django web application designed to serve as a crypto trading assistant bot. It integrates a Python backend engine that processes trading logic and connects seamlessly with a responsive frontend for real-time interaction. The app is fully deployed on [Render](https://render.com) using their free hosting tier.

---

Features

Custom Trading Bot Engine: Core logic built in Python to simulate and process crypto trade decisions.
Django Framework: Robust MVC structure using Django for managing business logic, templates, and static assets.
Responsive Frontend: Clean HTML/CSS/JavaScript UI with custom styles and visuals for engaging user experience.
Backend & Frontend Integration: Connected views, forms, and models to allow end-to-end interaction.
Deployment on Render: Hosted on [Render.com](https://render.com) with production-grade settings.


Project Structure

```bash
CryptoRoast/
├── bot/
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py
│   ├── templates/bot/
│   │   ├── index.html
│   ├── static/bot/
│   │   ├── images/
│   │   ├── script.js
│   │   ├── style.css
│   └── ...
├── cryptoroast/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── db.sqlite3
├── requirements.txt
├── render.yaml
└── README.md
````


Setup Instructions

1. Clone the Repo

```bash
git clone https://github.com/charles-hartley/Cryptobot.git
cd Cryptobot
```

2. Set Up Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

3. Install Dependencies

```bash
pip install -r requirements.txt
```

4. Run Migrations

```bash
python manage.py migrate
```

5. Collect Static Files

```bash
python manage.py collectstatic
```

6. Start Development Server

```bash
python manage.py runserver
```

Deployment (Render.com)

Required Files

* `render.yaml` for automated deployment settings
* `requirements.txt` with all dependencies
* `gunicorn` for WSGI server

