from .otp_session import otp_session_manager
import requests
from typing import Optional, Dict
from fastapi import HTTPException, status
from SCBClient import SCBClient, SCBAPIError, AuthenticationError
import json
from Securityy.permission_checker import check_permission
from Securityy.user_permission_checker import UserPermissionChecker

SCB_BASE_URL = "https://scb.erad-markets.com"
SCB_ADMIN_USER = "admin"
SCB_ADMIN_PASS = "nani*&H#*$HDJbhdb3746bybHBSHDJG&3gnfjenjkbyfv76G673G4UBBEKBF8"


def get_mt5_client():
    """Helper function to get authenticated MT5 client"""
    client = SCBClient(base_url=SCB_BASE_URL, logger_level="OFF")
    try:
        client.authenticate(SCB_ADMIN_USER, SCB_ADMIN_PASS)
        return client
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to MT5 service: {str(e)}"
        )


class OTPHelper:
    """
    Helper class for OTP (One-Time Password) operations including:
    - Sending OTP codes
    - Verifying OTP codes
    - Managing OTP sessions
    """

    @staticmethod
    def send_and_store_otp(user_id: int, phone_number: str) -> str:
        """
        Send OTP and store it in session

        Args:
            user_id: ID of the user requesting OTP
            phone_number: Phone number to send OTP to

        Returns:
            str: Session ID for the OTP verification

        Raises:
            HTTPException: If OTP sending fails
        """
        try:
            # Try to get OTP from external service
            otp = OTPHelper._get_otp_from_external_service(phone_number)
        except Exception as e:
            # Fallback to default OTP if external service fails
            print(
                f"Using default OTP due to external service failure: {str(e)}")
            otp = "1234567"  # In production, use a more secure fallback method

        # Store OTP in session regardless of its source
        session_id = otp_session_manager.create_otp_session(user_id, otp)
        return session_id

    @staticmethod
    def _get_otp_from_external_service(phone_number: str) -> str:
        """
        Get OTP from external SMS service

        Args:
            phone_number: Phone number to send OTP to

        Returns:
            str: OTP reference code

        Raises:
            HTTPException: If phone number is invalid or service fails
        """
        try:
            if not phone_number:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number must be provided."
                )

            client = get_mt5_client()
            result = client.send_otp(phone_number)
            print(result)  # Consider using proper logging instead
            return result.get("otp_ref")  # Reference for later verification

        except SCBAPIError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to send verification code: {e}"
            )

    @staticmethod
    def verify_otp_for_user(user_id: int, otp: str) -> bool:
        """
        Verify OTP for specified user

        Args:
            user_id: ID of the user to verify
            otp: One-Time Password to verify

        Returns:
            bool: True if verification succeeds, False otherwise
        """
        return otp_session_manager.validate_otp(user_id, otp)

    @staticmethod
    def get_user_otp_session(user_id: int) -> Optional[Dict]:
        """
        Get OTP session for specified user if exists

        Args:
            user_id: ID of the user to check

        Returns:
            Optional[Dict]: OTP session data if exists, None otherwise
        """
        return otp_session_manager.get_user_otp_session(user_id)
