# BloodCare – Blood Management System

BloodCare is a web-based Blood Management System developed using Flask and MySQL.

## Features
- Dashboard and blood inventory statistics
- Donor management
- Blood donation management
- Hospital blood requests
- Emergency blood matching
- Blood reservations
- Blood distribution
- Reports with charts and CSV export
- Dark, Light and System themes

## Technology Stack
- Python
- Flask
- MySQL
- HTML
- CSS
- JavaScript

## Project Structure
- app.py – Flask application
- config.py – Database configuration
- database/schema.sql – Database schema
- templates/ – HTML pages
- static/ – CSS and JavaScript assets
- requirements.txt – Python dependencies

## Local Setup

1. Clone this repository.
2. Install dependencies:

   pip install -r requirements.txt

3. Configure database environment variables:
   DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

4. Create the MySQL database and import database/schema.sql.

5. Configure the demo database and synthetic demo data.

6. Start the application:

   python run_demo.py

7. Open http://127.0.0.1:5001

## Security
Database credentials must be configured using environment variables. Never publish passwords or private database dumps.

Demo data is synthetic and intended for demonstration purposes.

## GitHub Repository
https://github.com/harsita22/BloodCare-Blood-Management-System

## Developer
Harsita .K.A

