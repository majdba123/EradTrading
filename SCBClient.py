"""
MT5 Client Portal API

A client library for interacting with the MT5 Client Portal API.
This library provides a clean interface for all operations supported by the API,
including authentication, account management, balance operations, and payment processing.

"""

import requests
import json
import hashlib
from datetime import datetime
import time
import logging
import string
import random
from typing import Dict, List, Optional, Any, Union, Tuple

class SCBAPIError(Exception):
    """Exception raised for MT5 API errors"""
    def __init__(self, code: int, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"MT5 API Error ({code}): {message}")

class AuthenticationError(SCBAPIError):
    """Exception raised for authentication errors"""
    pass

class SCBClient:
    """
    MT5 Client Portal API Client
    
    A client for interacting with the MT5 Client Portal API. This client provides
    methods for all operations supported by the API, including authentication,
    account management, balance operations, and payment processing.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", debug: bool = False, logger_level: str = "INFO"):
        """
        Initialize the MT5 Client API
        
        Args:
            base_url: The base URL of the MT5 Client Portal API
            debug: Whether to enable debug logging (deprecated, use logger_level instead)
            logger_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', or 'OFF')
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.authenticated = False
        
        # Set up logging
        self.logger = logging.getLogger("MT5ClientAPI")
        
        # Clear existing handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
            
        # Set logging level based on parameter
        if logger_level.upper() == "OFF":
            self.logger.setLevel(logging.CRITICAL + 1)  # Above all levels
        else:
            # Map string level to logging constant
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL
            }
            # Default to INFO if invalid level
            level = level_map.get(logger_level.upper(), logging.INFO)
            
            # For backward compatibility
            if debug:
                level = logging.DEBUG
                
            self.logger.setLevel(level)
            
            # Add handler if level is not OFF
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    @staticmethod
    def generate_password(length: int = 8) -> str:
        """
        Generate a random password with:
        - 5 numbers
        - 1 symbol
        - 1 uppercase letter
        - 1 lowercase letter
        
        Args:
            length: The length of the password (fixed at 8 characters)
            
        Returns:
            A random password matching the requirements
        """
        # Generate components
        numbers = ''.join(random.choice(string.digits) for _ in range(5))
        symbol = random.choice("!@#$%^&*()_+-=[]{}|;:,.<>?")
        uppercase = random.choice(string.ascii_uppercase)
        lowercase = random.choice(string.ascii_lowercase)
        
        # Combine and shuffle
        password_list = list(numbers + symbol + uppercase + lowercase)
        random.shuffle(password_list)
        return ''.join(password_list)
    
    @staticmethod
    def calculate_auth_hash(password: str, srv_rand: str) -> str:
        """
        Calculate the authentication hash for the given password and server random
        
        Args:
            password: The password to hash
            srv_rand: The server random value
            
        Returns:
            The authentication hash
        """
        # First hash the original password
        password_md5 = hashlib.md5(password.encode()).hexdigest()
        # Then hash the password hash again
        double_hashed = hashlib.md5(password_md5.encode()).hexdigest()
        # Combine with 'BEST' and srv_rand
        combined = double_hashed + 'BEST' + srv_rand
        # Finally hash the combined string
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _request(self, method: str, endpoint: str, 
                 params: Optional[Dict] = None, 
                 data: Optional[Dict] = None, 
                 json_data: Optional[Dict] = None,
                 check_auth: bool = True) -> Dict:
        """
        Make a request to the MT5 Client Portal API
        
        Args:
            method: The HTTP method to use
            endpoint: The API endpoint to request
            params: Query parameters to include in the request
            data: Form data to include in the request
            json_data: JSON data to include in the request
            check_auth: Whether to check if the client is authenticated first
            
        Returns:
            The parsed JSON response
            
        Raises:
            AuthenticationError: If the client is not authenticated and check_auth is True
            SCBAPIError: If the API returns an error
        """
        if check_auth and not self.authenticated and not endpoint.startswith('/api/auth'):
            raise AuthenticationError(401, "Not authenticated")
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            self.logger.debug(f"Request: {method} {url}")
            if json_data:
                self.logger.debug(f"JSON data: {json_data}")
                
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data
            )
            
            self.logger.debug(f"Response status: {response.status_code}")
            
            # Check if the response is JSON
            try:
                result = response.json()
                self.logger.debug(f"Response: {result}")
            except json.JSONDecodeError:
                result = {"text": response.text}
                self.logger.debug(f"Non-JSON response: {response.text}")
            
            # Check for errors
            if response.status_code >= 400:
                raise SCBAPIError(
                    response.status_code, 
                    result.get("detail", "Unknown error"),
                    result
                )
                
            return result
        except requests.RequestException as e:
            self.logger.error(f"Request error: {str(e)}")
            raise SCBAPIError(500, f"Request error: {str(e)}")
            
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with the MT5 Client Portal API
        
        Args:
            username: The username to authenticate with
            password: The password to authenticate with
            
        Returns:
            True if authentication was successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        self.logger.info(f"Authenticating as {username}")
        
        # Start authentication
        auth_start = self._request(
            "POST", 
            "/api/auth/start", 
            json_data={"username": username},
            check_auth=False
        )
        
        srv_rand = auth_start.get("srv_rand")
        if not srv_rand:
            raise AuthenticationError(401, "Failed to get server random value")
        
        # Calculate the client response
        cli_res = self.calculate_auth_hash(password, srv_rand)
        
        # Complete authentication
        try:
            auth_end = self._request(
                "POST", 
                "/api/auth/end", 
                json_data={"cli_res": cli_res},
                check_auth=False
            )
            
            self.authenticated = True
            self.logger.info("Authentication successful")
            return True
        except SCBAPIError as e:
            self.logger.error(f"Authentication failed: {e.message}")
            raise AuthenticationError(401, "Authentication failed", e.details)
    
    def test_connection(self) -> bool:
        """
        Test the connection to the MT5 Client Portal API
        
        Returns:
            True if the connection is successful
        """
        try:
            self._request("GET", "/api/test")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {str(e)}")
            return False
    
    def get_config(self) -> Dict:
        """
        Get the MT5 Client Portal API configuration
        
        Returns:
            The configuration dictionary
        """
        return self._request("GET", "/api/configs/get")
    
    def get_language_settings(self, language_code: str = "en") -> Dict:
        """
        Get language settings
        
        Args:
            language_code: The language code to get settings for
            
        Returns:
            The language settings dictionary
        """
        result = self._request("GET", f"/api/configs/language/{language_code}")
        return result.get("language", {})
    
    def update_config(self, config_updates: Dict) -> Dict:
        """
        Update the MT5 Client Portal API configuration
        
        Args:
            config_updates: Dictionary of configuration updates
            
        Returns:
            The updated configuration
        """
        return self._request("POST", "/api/configs/update", json_data=config_updates)
    
    def update_language_settings(self, language_code: str, settings: Dict) -> Dict:
        """
        Update language settings
        
        Args:
            language_code: The language code to update settings for
            settings: Dictionary of language settings
            
        Returns:
            The updated language settings
        """
        return self._request("POST", f"/api/configs/language/{language_code}", json_data=settings)
    
    def create_account(self, first_name: str, last_name: str, account_type: str, 
                       password: Optional[str] = None, investor_password: Optional[str] = None) -> int:
        """
        Create a new MT5 account
        
        Args:
            first_name: The first name of the account holder
            last_name: The last name of the account holder
            account_type: The type of account to create: 'standard', 'pro', 'invest', 'micro', or 'wallet'
            password: The password for the account (generated if not provided)
            investor_password: The investor password for the account (generated if not provided)
            
        Returns:
            The login ID of the created account
            
        Raises:
            SCBAPIError: If the account creation fails
        """
        # Generate passwords if not provided
        if not password:
            password = self.generate_password()
        if not investor_password:
            investor_password = self.generate_password()
            
        self.logger.info(f"Creating {account_type} account for {first_name} {last_name}")
        
        response = self._request(
            "POST",
            "/api/user/newuser",
            json_data={
                "name": first_name,
                "lastname": last_name,
                "password": password,
                "investor": investor_password,
                "type": account_type
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Account creation failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Account creation failed: {error_message}")
        
        # Get the login ID from the response
        result = response.get("answer", {})
        if result.get("retcode") != "0 Done":
            error_message = result.get("retcode", "Unknown error")
            self.logger.error(f"Account creation failed: {error_message}")
            raise SCBAPIError(500, f"Account creation failed: {error_message}")
            
        login = result.get("answer", {}).get("Login")
        
        self.logger.info(f"Account created successfully with login: {login}")
        self.logger.info(f"Password: {password}")
        self.logger.info(f"Investor password: {investor_password}")
        
        # Return account details so the caller can store them
        return {
            "login": login,
            "password": password,
            "investor_password": investor_password,
            "type": account_type,
            "name": f"{first_name} {last_name}"
        }
    
    def get_account_info(self, login: int) -> Dict:
        """
        Get information about an MT5 account
        
        Args:
            login: The login ID of the account
            
        Returns:
            The account information
            
        Raises:
            SCBAPIError: If the account is not found
        """
        self.logger.info(f"Getting account info for login {login}")
        
        response = self._request("GET", f"/api/user/getinfo?login={login}")
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Failed to get account info: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Failed to get account info: {error_message}")
            
        return response.get("answer", {})
    
    def check_password(self, login: int, password: str, password_type: str = "MAIN") -> bool:
        """
        Check if a password is valid for an MT5 account
        
        Args:
            login: The login ID of the account
            password: The password to check
            password_type: The type of password to check (MAIN or INVESTOR)
            
        Returns:
            True if the password is valid
            
        Raises:
            SCBAPIError: If the password check fails
        """
        self.logger.info(f"Checking {password_type} password for login {login}")
        
        response = self._request(
            "POST",
            "/api/user/password",
            json_data={
                "login": login,
                "password": password,
                "type": password_type,
                "ischeck": True
            }
        )
        
        # Check for errors
        if response.get("code") == 404 and response.get("detail") == "Account Password Wrong":
            return False
            
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Password check failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Password check failed: {error_message}")
            
        return True
    
    def change_password(self, login: int, new_password: str, password_type: str = "MAIN") -> bool:
        """
        Change a password for an MT5 account
        
        Args:
            login: The login ID of the account
            new_password: The new password
            password_type: The type of password to change (MAIN or INVESTOR)
            
        Returns:
            True if the password was changed successfully
            
        Raises:
            SCBAPIError: If the password change fails
        """
        self.logger.info(f"Changing {password_type} password for login {login}")
        
        response = self._request(
            "POST",
            "/api/user/password",
            json_data={
                "login": login,
                "password": new_password,
                "type": password_type,
                "ischeck": False
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Password change failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Password change failed: {error_message}")
            
        return True
    
    def update_user_rights(self, login: int, rights: Dict[str, int], params: Optional[Dict[str, Any]] = None) -> Dict:
        """
        Update user rights and parameters
        
        Args:
            login: The login ID of the account
            rights: Dictionary of rights to update (key: right name, value: 0 or 1)
            params: Dictionary of parameters to update
            
        Returns:
            The updated user information
            
        Raises:
            SCBAPIError: If the user update fails
        """
        if params is None:
            params = {}
            
        self.logger.info(f"Updating rights for login {login}")
        
        response = self._request(
            "POST",
            "/api/user/update",
            json_data={
                "login": login,
                "rights": rights,
                "params": params
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"User update failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"User update failed: {error_message}")
            
        return response.get("answer", {})
    
    def enable_trading(self, login: int) -> Dict:
        """
        Enable trading for an MT5 account
        
        Args:
            login: The login ID of the account
            
        Returns:
            The updated user information
            
        Raises:
            SCBAPIError: If the update fails
        """
        return self.update_user_rights(login, {
            "USER_RIGHT_TRADE_DISABLED": 0,
            "USER_RIGHT_ENABLED": 1
        })
    
    def disable_trading(self, login: int) -> Dict:
        """
        Disable trading for an MT5 account
        
        Args:
            login: The login ID of the account
            
        Returns:
            The updated user information
            
        Raises:
            SCBAPIError: If the update fails
        """
        return self.update_user_rights(login, {
            "USER_RIGHT_TRADE_DISABLED": 1
        })
    
    def deposit(self, login: int, amount: float, comment: str = "Deposit") -> Dict:
        """
        Deposit funds into an MT5 account
        
        Args:
            login: The login ID of the account
            amount: The amount to deposit
            comment: A comment for the deposit
            
        Returns:
            The deposit result
            
        Raises:
            SCBAPIError: If the deposit fails
        """
        self.logger.info(f"Depositing {amount} to login {login}")
        
        response = self._request(
            "POST",
            "/api/deals/balance",
            json_data={
                "login": login,
                "amount": amount,
                "istransfer": False,
                "comment": comment
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Deposit failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Deposit failed: {error_message}")
            
        return response.get("answer", {})
    
    def withdraw(self, login: int, amount: float, comment: str = "Withdrawal") -> Dict:
        """
        Withdraw funds from an MT5 account
        
        Args:
            login: The login ID of the account
            amount: The amount to withdraw (positive number)
            comment: A comment for the withdrawal
            
        Returns:
            The withdrawal result
            
        Raises:
            SCBAPIError: If the withdrawal fails
        """
        # Use negative amount for withdrawal
        return self.deposit(login, -amount, comment)
    
    def transfer(self, from_login: int, to_login: int, amount: float) -> Dict:
        """
        Transfer funds between MT5 accounts
        
        Args:
            from_login: The login ID of the source account
            to_login: The login ID of the destination account
            amount: The amount to transfer
            comment: A comment for the transfer
            
        Returns:
            The transfer result
            
        Raises:
            SCBAPIError: If the transfer fails
        """
        self.logger.info(f"Transferring {amount} from login {from_login} to {to_login}")
        
        response = self._request(
            "POST",
            "/api/deals/balance",
            json_data={
                "login": from_login,
                "amount": amount,
                "istransfer": True,
                "loginto": to_login,
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Transfer failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Transfer failed: {error_message}")
            
        return response.get("answer", {})
    
    def send_sms(self, phone: str, message: str) -> Dict:
        """
        Send an SMS message
        
        Args:
            phone: The phone number to send the SMS to
            message: The message to send
            
        Returns:
            The SMS result
            
        Raises:
            SCBAPIError: If the SMS fails
        """
        self.logger.info(f"Sending SMS to {phone}")
        
        response = self._request(
            "POST",
            "/api/sms/send",
            json_data={
                "phone": phone,
                "message": message
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"SMS failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"SMS failed: {error_message}")
            
        return response.get("answer", {})
    
    def send_otp(self, phone: str) -> Dict:
        """
        Send an OTP verification code to a phone number
        
        Args:
            phone: The phone number to send the OTP code to
            
        Returns:
            The OTP send result with verification status details
            
        Raises:
            SCBAPIError: If the OTP code sending fails
        """
        self.logger.info(f"Sending OTP verification code to {phone}")
        
        response = self._request(
            "POST",
            "/api/sms/otp/send",
            json_data={
                "phone": phone
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"OTP sending failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"OTP sending failed: {error_message}")
            
        return response.get("answer", {})
    
    def check_otp(self, phone: str, code: str) -> Dict:
        """
        Verify an OTP code
        
        Args:
            phone: The phone number that received the OTP code
            code: The verification code to check
            
        Returns:
            The verification result, including whether the code was approved
            
        Raises:
            SCBAPIError: If the OTP verification fails
        """
        self.logger.info(f"Verifying OTP code for {phone}")
        
        response = self._request(
            "POST",
            "/api/sms/otp/check",
            json_data={
                "phone": phone,
                "code": code
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"OTP verification failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"OTP verification failed: {error_message}")
            
        result = response.get("answer", {})
        
        # Log the verification status
        if result.get("is_approved"):
            self.logger.info(f"OTP verification approved for {phone}")
        else:
            self.logger.warning(f"OTP verification not approved for {phone}: {result.get('status')}")
            
        return result
    
    def create_deposit_request(self, currency_id: str, tracking_id: Optional[str] = None, 
                              label: str = "Deposit", confirmations_needed: int = 3) -> Dict:
        """
        Create a deposit request for cryptocurrency
        
        Args:
            currency_id: The currency ID to deposit
            tracking_id: A unique tracking ID (generated if not provided)
            label: A label for the deposit
            confirmations_needed: Number of confirmations needed
            
        Returns:
            The deposit request result
            
        Raises:
            SCBAPIError: If the deposit request fails
        """
        # Generate a tracking ID if not provided
        if not tracking_id:
            tracking_id = f"deposit_{int(time.time())}_{random.randint(1000, 9999)}"
            
        self.logger.info(f"Creating deposit request for {currency_id}, tracking ID: {tracking_id}")
        
        response = self._request(
            "POST",
            "/api/payment/deposit/coinsbuy",
            json_data={
                "currency_id": currency_id,
                "tracking_id": tracking_id,
                "label": label,
                "confirmations_needed": confirmations_needed
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Deposit request failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Deposit request failed: {error_message}")
            
        return response.get("answer", {})
    
    def create_withdrawal_request(self, amount: float, address: str, currency_id: str,
                                 tracking_id: Optional[str] = None, label: str = "Withdrawal",
                                 confirmations_needed: int = 3, is_fee_included: bool = True) -> Dict:
        """
        Create a withdrawal request for cryptocurrency
        
        Args:
            amount: The amount to withdraw
            address: The address to withdraw to
            currency_id: The currency ID to withdraw
            tracking_id: A unique tracking ID (generated if not provided)
            label: A label for the withdrawal
            confirmations_needed: Number of confirmations needed
            is_fee_included: Whether the fee is included in the amount
            
        Returns:
            The withdrawal request result
            
        Raises:
            SCBAPIError: If the withdrawal request fails
        """
        # Generate a tracking ID if not provided
        if not tracking_id:
            tracking_id = f"withdraw_{int(time.time())}_{random.randint(1000, 9999)}"
            
        self.logger.info(f"Creating withdrawal request for {amount} {currency_id}, tracking ID: {tracking_id}")
        
        response = self._request(
            "POST",
            "/api/payment/withdraw/coinsbuy",
            json_data={
                "amount": amount,
                "address": address,
                "currency_id": currency_id,
                "tracking_id": tracking_id,
                "label": label,
                "confirmations_needed": confirmations_needed,
                "is_fee_included": is_fee_included
            }
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Withdrawal request failed: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Withdrawal request failed: {error_message}")
            
        return response.get("answer", {})
    
    def get_currencies(self) -> Dict:
        """
        Get available cryptocurrencies for deposits and withdrawals
        
        Returns:
            Dictionary containing available cryptocurrencies and their codes
            
        Raises:
            SCBAPIError: If retrieving the currencies fails
        """
        self.logger.info("Getting available currencies")
        
        response = self._request(
            "GET",
            "/api/payment/coinsbuy/currencies"
        )
        
        # Check for errors
        if response.get("code") != 200:
            error_message = response.get("answer", "Unknown error")
            self.logger.error(f"Failed to get currencies: {error_message}")
            raise SCBAPIError(response.get("code", 500), f"Failed to get currencies: {error_message}")
            
        return response.get("answer", {})
    
    def logout(self) -> bool:
        """
        Log out from the MT5 Client Portal API
        
        Returns:
            True if the logout was successful
        """
        try:
            self._request("GET", "/api/logout")
            self.authenticated = False
            self.logger.info("Logged out successfully")
            return True
        except Exception as e:
            self.logger.error(f"Logout failed: {str(e)}")
            return False 