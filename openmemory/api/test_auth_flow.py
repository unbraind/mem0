import sys
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid

# Ensure the current directory is in sys.path for imports like `from main import app`
# and `from app.database import ...`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from main import app # Assuming app instance is in openmemory/api/main.py
from app.database import Base, get_db # Assuming get_db is in openmemory/api/app/database.py
from app.models import User # Assuming User model is in openmemory/api/app/models.py

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_temp.db" # Will be created in the api/ directory
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Store original get_db
original_get_db = app.dependency_overrides.get(get_db)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)

def run_tests():
    print("Starting auth flow tests...")

    # Clean up any existing test database file before starting
    db_path = "./test_temp.db" # Relative to where the script is run (openmemory/api/)
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing {db_path}")

    # Apply override
    app.dependency_overrides[get_db] = override_get_db

    # Create tables for the test DB
    Base.metadata.create_all(bind=engine) # Ensure tables are created before tests
    print(f"Recreated database tables for {db_path}")

    test_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "strongpassword123"

    # Test Registration
    print(f"Attempting to register user: {test_email}")
    response_register = client.post(
        "/auth/register",
        json={"email": test_email, "password": test_password},
    )
    print(f"Registration response status: {response_register.status_code}")
    print(f"Registration response body: {response_register.text[:300]}...")
    assert response_register.status_code == 201, f"Registration failed: {response_register.text}"
    print("User registration successful.")
    registered_user_id = response_register.json().get("id")
    assert registered_user_id, "Registration response did not include a user ID."

    # Verify user in DB
    db = TestingSessionLocal()
    user_in_db = db.query(User).filter(User.email == test_email).first()
    assert user_in_db is not None, "User not found in database after registration."
    assert user_in_db.id == uuid.UUID(registered_user_id), "Registered user ID mismatch with DB."
    assert not hasattr(user_in_db, 'salt'), "User model in DB still has a salt attribute."
    assert user_in_db.hashed_password is not None, "Hashed password not set in DB."
    print(f"Verified user {test_email} in database with ID {user_in_db.id} and hashed password.")
    db.close()

    # Test Login with correct credentials
    print(f"Attempting to login user: {test_email}")
    response_login_correct = client.post(
        "/auth/login",
        json={"email": test_email, "password": test_password},
    )
    print(f"Login (correct) response status: {response_login_correct.status_code}")
    print(f"Login (correct) response body: {response_login_correct.text[:300]}...")
    assert response_login_correct.status_code == 200, f"Login failed: {response_login_correct.text}"
    assert "openmemory_access_token" in response_login_correct.cookies, "Access token cookie not found."
    print("User login with correct credentials successful.")

    # Test Login with incorrect password
    print(f"Attempting to login user with incorrect password: {test_email}")
    response_login_incorrect = client.post(
        "/auth/login",
        json={"email": test_email, "password": "wrongpassword"},
    )
    print(f"Login (incorrect) response status: {response_login_incorrect.status_code}")
    print(f"Login (incorrect) response body: {response_login_incorrect.text[:300]}...")
    assert response_login_incorrect.status_code == 401, "Login with incorrect password did not fail as expected."
    print("User login with incorrect credentials correctly failed.")

    print("All auth flow tests passed!")

    # Clean up the test database file after tests
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Cleaned up {db_path}")

    # Restore original get_db if it was overridden
    if original_get_db:
        app.dependency_overrides[get_db] = original_get_db
    elif get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]


if __name__ == "__main__":
    run_tests()
