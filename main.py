from fastapi import FastAPI
from routers import users
from models.user import create_users_table
from resetdb import reset_database
app = FastAPI()


@app.post("/reset-database")
def reset_db():
    reset_database()
    return {"message": "Database has been reset successfully!"}


# إنشاء الجدول عند بدء التشغيل
create_users_table()

# تضمين نقاط النهاية
app.include_router(users.router)
