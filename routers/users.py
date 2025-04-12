import sqlite3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.connection import get_db_connection

router = APIRouter()

# نموذج بيانات المستخدم


class User(BaseModel):
    phone_number: str


@router.post("/register")
def register_user(user: User):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (phone_number) VALUES (?)", (user.phone_number,))
            conn.commit()
            return {"message": "User registered successfully!"}
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400, detail="Phone number already exists.")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal Server Error: {e}")
