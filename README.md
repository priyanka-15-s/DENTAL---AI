# Dental AI Diagnosis System

## Overview
The Dental AI Diagnosis System is a web application that analyzes dental X-ray images using a simulated AI model. It detects common dental conditions, displays confidence scores, and stores analysis history in a SQLite database.

## Features
- Upload dental X-ray images
- AI-based detection of:
  - Dental Caries (Cavities)
  - Dental Fillings
  - Dental Implants
  - Impacted Teeth
- Confidence score for each detected condition
- Dashboard with scan statistics
- Analysis history stored in SQLite

## Technologies Used
- Python
- Flask
- SQLite
- HTML5
- CSS3
- JavaScript

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run the Project

```bash
cd backend
python app.py
```

Open your browser and visit:

```
http://localhost:5000
```

## Project Structure

```
Dental-AI/
├── backend/
├── frontend/
├── README.md
```

## Future Improvements
- Integrate a real AI/Deep Learning model
- User authentication
- PDF report generation
- Cloud database integration
- Multi-user support

## Author
Priyanka
