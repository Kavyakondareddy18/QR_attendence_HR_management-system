# QR Attendance HR Management

A smart web application that uses QR codes to automate employee attendance tracking and salary calculation. Employees scan their unique QR codes to mark attendance, while admins securely manage staff, salaries, and reports through an intuitive dashboard—all designed to save time and reduce errors.

## Features

- **Employee Registration**: Register employees with unique QR codes generated automatically.
- **QR Code Scanning**: Employees scan their QR codes to mark check-in and check-out times.
- **Admin Dashboard**: Manage employees, view attendance reports, and calculate salaries.
- **Salary Calculation**: Automatic calculation based on daily salary and worked days.
- **Secure Authentication**: Admin login with password hashing.
- **CSV Export**: Export attendance and salary reports.

## Technologies Used

- **Backend**: Flask (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS (Jinja2 templates)
- **QR Code Generation**: qrcode library
- **ORM**: SQLAlchemy

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/akshata1807/QR_Attendance-HR_Management.git
   cd QR_Attendance-HR_Management
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python app.py
   ```

4. **Access the app**:
   Open your browser and go to `http://127.0.0.1:5000/`

## Usage

1. **Admin Registration**: First, register an admin at `/admin_register`.
2. **Login**: Admins log in at `/login`.
3. **Register Employees**: Add employees and generate QR codes.
4. **Scan Attendance**: Employees scan QR codes at `/scan`.
5. **Manage**: Use the admin dashboard to view reports and calculate salaries.

## Project Structure

- `app.py`: Main Flask application
- `models.py`: Database models
- `templates/`: HTML templates
- `static/`: CSS and QR code images
- `instance/`: SQLite database file
- `requirements.txt`: Python dependencies

## Contributing

Feel free to fork and contribute to this project.

## License

This project is open-source.
