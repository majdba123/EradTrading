from fastapi import FastAPI
from routers import users
from models.user import create_users_table
from resetdb import reset_database
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Phone Authentication API",
    description="API for user authentication using phone and passcode",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # السماح لجميع الأصول
    allow_methods=["*"],  # السماح لجميع الطرق
    allow_headers=["*"],  # السماح لجميع الرؤوس
    allow_credentials=False,  # مثل إعداد لارفل
)


@app.on_event("startup")
def on_startup():
    create_users_table()
    print("✅ Users table initialized")


@app.post("/reset-database")
def reset_db():
    reset_database()
    return {"message": "Database has been reset successfully!"}


app.include_router(users.router, prefix="/api")
