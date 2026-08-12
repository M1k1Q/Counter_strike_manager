import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import models
from app.main import app
from app.database import Base, get_db

from sqlalchemy.pool import StaticPool

# Create an in-memory SQLite database for testing auth
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)




def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestAuthEndpoints(unittest.TestCase):

    def setUp(self):
        # Reset database tables before each test
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

    def test_register_and_login_flow(self):
        # 1. Register new user
        reg_payload = {
            "username": "navi_manager",
            "email": "navi@esports.gg",
            "password": "SecurePassword123!"
        }
        res = client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 201, res.text)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["username"], "navi_manager")
        self.assertEqual(data["user"]["email"], "navi@esports.gg")

        token = data["access_token"]

        # 2. Access /api/auth/me with valid token
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["username"], "navi_manager")

        # 3. Login with registered username
        login_payload = {
            "username_or_email": "navi_manager",
            "password": "SecurePassword123!"
        }
        login_res = client.post("/api/auth/login", json=login_payload)
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json())

        # 4. Login with registered email
        email_login_payload = {
            "username_or_email": "navi@esports.gg",
            "password": "SecurePassword123!"
        }
        email_login_res = client.post("/api/auth/login", json=email_login_payload)
        self.assertEqual(email_login_res.status_code, 200)

    def test_invalid_login_credentials(self):
        # Attempt login with non-existent user
        login_payload = {
            "username_or_email": "fake_user",
            "password": "WrongPassword123!"
        }
        res = client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()["detail"], "Invalid username/email or password")

    def test_weak_password_rejection(self):
        weak_payload = {
            "username": "weakuser",
            "email": "weak@test.com",
            "password": "123"  # Less than 8 chars, no uppercase
        }
        res = client.post("/api/auth/register", json=weak_payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Password must be at least 8 characters long", res.json()["detail"])

    def test_duplicate_user_registration(self):
        payload = {
            "username": "s1mple",
            "email": "s1mple@navi.gg",
            "password": "Password123!"
        }
        client.post("/api/auth/register", json=payload)

        # Duplicate username
        res_dup_name = client.post("/api/auth/register", json={
            "username": "s1mple",
            "email": "other@navi.gg",
            "password": "Password123!"
        })
        self.assertEqual(res_dup_name.status_code, 400)
        self.assertIn("Username is already taken", res_dup_name.json()["detail"])

        # Duplicate email
        res_dup_email = client.post("/api/auth/register", json={
            "username": "s1mple2",
            "email": "s1mple@navi.gg",
            "password": "Password123!"
        })
        self.assertEqual(res_dup_email.status_code, 400)
        self.assertIn("Email address is already registered", res_dup_email.json()["detail"])


if __name__ == "__main__":
    unittest.main()
