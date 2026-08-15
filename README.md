# AI Student Performance Prediction System

1. Install MySQL and create the database by running `database/database.sql`.
2. Copy the trained model file `student_performance_model.joblib` from the ML phase into `model/`.
3. Install dependencies: `pip install -r requirements.txt`
4. Set MySQL environment variables if needed.
5. Run: `python app.py`
6. For first local setup only, visit `/setup-admin?username=admin&password=changeMe`.
7. Remove or disable the setup-admin route before production use.

The application uses the actual model selected during the ML phase and stores prediction history in MySQL.
