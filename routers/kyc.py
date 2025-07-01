from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from database.connection import get_db_connection
from schemas.kyc import KYCCreate, KYCUpdate, KYCResponse, KYCStatus
from admin_auth import admin_scheme
from typing import List
import sqlite3
from datetime import datetime

router = APIRouter(
    prefix="/kyc",
    tags=["KYC Verification"]
)


@router.post("/submit", response_model=KYCResponse)
async def submit_kyc(
    kyc_data: KYCCreate,
    admin_data: dict = Depends(admin_scheme)
):
    """Submit a new KYC request"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if there's no pending request for the same user
        cursor.execute("""
            SELECT id FROM kyc_verifications 
            WHERE user_id = ? AND status = 'pending'
        """, (kyc_data.user_id,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a pending KYC request"
            )

        # Insert KYC request
        cursor.execute("""
            INSERT INTO kyc_verifications (
                user_id, document_type, document_number,
                front_image_url, back_image_url, selfie_image_url
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            kyc_data.user_id,
            kyc_data.document_type.value,
            kyc_data.document_number,
            kyc_data.front_image_url,
            kyc_data.back_image_url,
            kyc_data.selfie_image_url
        ))

        # Retrieve the newly inserted data
        kyc_id = cursor.lastrowid
        cursor.execute("""
            SELECT * FROM kyc_verifications WHERE id = ?
        """, (kyc_id,))
        kyc_record = dict(cursor.fetchone())

        conn.commit()
        return kyc_record

    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "FOREIGN KEY constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit KYC request: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/{kyc_id}", response_model=KYCResponse)
def get_kyc_details(
    kyc_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Get KYC request details"""
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM kyc_verifications WHERE id = ?
        """, (kyc_id,))
        kyc_record = cursor.fetchone()

        if not kyc_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KYC request not found"
            )

        return dict(kyc_record)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KYC data: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.put("/{kyc_id}/review", response_model=KYCResponse)
def review_kyc(
    kyc_id: int,
    update_data: KYCUpdate,
    admin_data: dict = Depends(admin_scheme)
):
    """Review and update KYC request status"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if KYC request exists
        cursor.execute("""
            SELECT status FROM kyc_verifications WHERE id = ?
        """, (kyc_id,))
        kyc_record = cursor.fetchone()

        if not kyc_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KYC request not found"
            )

        if kyc_record['status'] != 'pending':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This request has already been reviewed"
            )

        # Update KYC status
        cursor.execute("""
            UPDATE kyc_verifications 
            SET status = ?, 
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = ?,
                rejection_reason = ?
            WHERE id = ?
        """, (
            update_data.status.value,
            admin_data['user_id'],
            update_data.rejection_reason,
            kyc_id
        ))

        # Retrieve updated data
        cursor.execute("""
            SELECT * FROM kyc_verifications WHERE id = ?
        """, (kyc_id,))
        updated_record = dict(cursor.fetchone())

        conn.commit()
        return updated_record

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update KYC status: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get("/user/{user_id}", response_model=List[KYCResponse])
def get_user_kyc_history(
    user_id: int,
    admin_data: dict = Depends(admin_scheme)
):
    """Get KYC history for a specific user"""
    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM kyc_verifications 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

        records = [dict(row) for row in cursor.fetchall()]
        return records

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch KYC history: {str(e)}"
        )
    finally:
        if conn:
            conn.close()
