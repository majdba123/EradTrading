from fastapi import FastAPI
from routers import users, admin, kyc ,mt5,admin_mt5
from models.user import create_users_table,create_user_sessions_table,create_user_devices_table
from models.managers import create_managers_table, create_manager_assignments_table
from models.kyc import create_kyc_table 
from models.mt5 import create_mt5_accounts_table 

from resetdb import reset_database
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Phone Authentication API",
    description="API for user authentication using phone and passcode",
    version="1.0.0"
)

# تكوين CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False
)

@app.on_event("startup")
def on_startup():
    create_users_table()
    create_managers_table()
    create_manager_assignments_table()
    create_kyc_table()
    create_mt5_accounts_table()
    create_user_sessions_table()
    create_user_devices_table()  # الجدول الجديد
    print("✅ All tables initialized successfully")

@app.post("/reset-database")
def reset_db():
    reset_database()
    return {"message": "Database has been reset successfully!"}

# تضمين جميع الراوترات
app.include_router(users.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(kyc.router, prefix="/api")  # تم إضافة راوتر KYC
app.include_router(mt5.router, prefix="/api/mt5")  # إضافة هذا السطر
app.include_router(admin_mt5.router, prefix="/api/admin")  # ✅ التصحيح
