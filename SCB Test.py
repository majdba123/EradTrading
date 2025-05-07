from SCBClient import SCBClient, SCBAPIError, AuthenticationError
import json
import getpass

# Initialize the client with custom logger level

client = SCBClient(
    base_url="http://localhost:8000", 
    logger_level="OFF"  # Set to ""INFO" - Standard information , "WARNING" - Only warnings and errors, "ERROR" - Only errors, "CRITICAL" - Only critical errors ,"OFF" - No logging at all
)

# Authenticate
try:
    result = client.authenticate("admin", "nani*&H#*$HDJbhdb3746bybHBSHDJG&3gnfjenjkbyfv76G673G4UBBEKBF8")
    print("Authentication successful")
except AuthenticationError as e:
    print(f"Authentication failed: {e}")
    print(f"Error details: {e.details}")
    exit(1)
# # OTP functionality
# try:
#     phone_number = "+905531673733"

#     #Send OTP verification code
#     print(f"\nSending OTP verification code to {phone_number}...")
#     send_result = client.send_otp(phone_number)
#     print(f"OTP initiated: {json.dumps(send_result, indent=2)}")
    
#     # Get verification code from user
#     verification_code = input("\nEnter the verification code you received: ")
    
#     # Verify the code
#     if verification_code:
#         print(f"\nVerifying code '{verification_code}'...")
#         verify_result = client.check_otp(phone_number, verification_code)
#         print(f"Verification result: {json.dumps(verify_result, indent=2)}")
        
#         # Display a clear message based on the result
#         if verify_result.get("is_approved"):
#             print("\nVerification successful! User identity confirmed.")
#         else:
#             print("\nVerification failed. Code may be incorrect or expired.")
#     else:
#         print("No code entered. Skipping verification.")
        
# except SCBAPIError as e:
#     print(f"OTP operation failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")
# except Exception as e:
#     print(f"Unexpected error: {str(e)}")

# Get configuration to see available account types
# try:
#     config = client.get_config()
#     print("Available account groups in config:")
#     print(json.dumps(config.get("accountGroups", {}), indent=2))
#     valid_types = list(config.get("accountGroups", {}).keys())
#     print(f"Valid account types: {valid_types}")
# except SCBAPIError as e:
#     print(f"Failed to get configuration: {e.message}")
#     print(f"Error details: {e.details}")


# Deposit to specific account
# try:
#     # Deposit $100 to account 80004
#     deposit_result = client.deposit(80004, 100.0, "deposit test")
#     print(f"Deposit successful: ${100.0} added to account 80004")
#     print(f"Deposit details: {json.dumps(deposit_result, indent=2)}")
# except SCBAPIError as e:
#     print(f"Deposit failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")

# Transfer from account  to account 
# try:    
#     # Transfer $100 from 80002 to 80004
#     transfer_amount = 100.0
#     transfer_result = client.transfer(from_login=80004, to_login=80002, amount=transfer_amount) # comment is not required it will be added automatically
#     print(f"Transfer details: {json.dumps(transfer_result, indent=2)}")
         
# except SCBAPIError as e:
#     print(f"Transfer failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")

# Change password for account 
# try:
#     # Define the new password
#     new_password = client.generate_password(8)
    
#     # Change the main password for account 80004
#     change_result = client.change_password(80004, new_password, password_type="MAIN")
#     print(f"Password change successful for account 80004")
#     print(f"Password change details: {json.dumps(change_result, indent=2)}")
# except SCBAPIError as e:
#     print(f"Password change failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")   
#     # Verify the new password works

# # Check if the new password is valid

# try:
#     # Check if the new password is valid
#     check_result = client.check_password(80004, new_password, password_type="MAIN")
#     if check_result:
#         print(f"New password verification successful - Password is valid")
#     else:
#         print(f"New password verification failed - Password is invalid")
# except SCBAPIError as e:
#     print(f"Password verification failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")
        

# Create a cryptocurrency deposit request
# try:
#     # Create a deposit request for Bitcoin
#     currency = "USDT"
#     label = "Test Deposit"
#     confirmations = 2
    
#     deposit_request = client.create_deposit_request(
#         currency_id=currency,
#         label=label,
#         confirmations_needed=confirmations
#     )
    
#     print("\n========== DEPOSIT REQUEST CREATED ==========")
#     print(f"Currency: {currency}")
#     print(f"Label: {label}")
#     print(f"Confirmations needed: {confirmations}")
#     print("---------------------------------------------")
#     print(f"Deposit details: {json.dumps(deposit_request, indent=2)}")
    
#     # Save important information for reference
#     if "address" in deposit_request:
#         print(f"\nIMPORTANT: Send {currency} to this address to complete the deposit:")
#         print(f"Deposit address: {deposit_request.get('address')}")
    
#     if "deposit_id" in deposit_request:
#         print(f"Deposit ID: {deposit_request.get('deposit_id')}")
        
#     print("================================================\n")
    
# except SCBAPIError as e:
#     print(f"Create deposit request failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")

# Create a cryptocurrency withdrawal request
# try:
#     # Create a withdrawal request
#     currency = "USDT"
#     amount = 0.001  # Small amount for testing
#     address = "TKKHiTgiPzZQkjVPKy4zAm7cgkkoiaQiiN"  # Example Tether (USDT-TRC20) address
#     label = "Test Withdrawal"
    
#     withdrawal_request = client.create_withdrawal_request(
#         amount=amount,
#         address=address,
#         currency_id=currency,
#         label=label,
#         is_fee_included=True
#     )
    
#     print("\n========== WITHDRAWAL REQUEST CREATED ==========")
#     print(f"Currency: {currency}")
#     print(f"Amount: {amount}")
#     print(f"Address: {address}")
#     print(f"Label: {label}")
#     print("-----------------------------------------------")
#     print(f"Withdrawal details: {json.dumps(withdrawal_request, indent=2)}")
    
#     # Save important information for reference
#     if "payout_id" in withdrawal_request:
#         print(f"\nWithdrawal ID: {withdrawal_request.get('payout_id')}")
    
#     if "status" in withdrawal_request:
#         print(f"Status: {withdrawal_request.get('status')}")
        
#     if "txid" in withdrawal_request:
#         print(f"Transaction ID: {withdrawal_request.get('txid')}")
        
#     print("==================================================\n")
    
# except SCBAPIError as e:
#     print(f"Create withdrawal request failed: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")

# # Get account information for account 80004
# try:
#     # Get detailed account information
#     account_info = client.get_account_info(80004)
    
#     # Print the account details in a readable format
#     print("\n========== ACCOUNT 80004 INFORMATION ==========")
#     print(f"Login: {account_info.get('Login', 'N/A')}")
#     print(f"Balance: {account_info.get('Balance', 'N/A')}")
#     print(f"Equity: {account_info.get('Equity', 'N/A')}")
#     print(f"Margin: {account_info.get('Margin', 'N/A')}")
#     print(f"Free Margin: {account_info.get('MarginFree', 'N/A')}")
#     print(f"Margin Level: {account_info.get('MarginLevel', 'N/A')}")
#     print(f"Group: {account_info.get('Group', 'N/A')}")
#     print(f"Name: {account_info.get('Name', 'N/A')}")
#     print(f"Account Type: {account_info.get('Account', 'N/A')}")
#     print(f"Client ID: {account_info.get('ClientID', 'N/A')}")
#     print(f"ZIP Code: {account_info.get('ZipCode', 'N/A')}")
#     print(f"Agent: {account_info.get('Agent', 'N/A')}")
#     print("================================================\n")
    
#     # Also print the raw JSON for reference
#     print("Raw account data:")
#     print(json.dumps(account_info, indent=2))
    
# except SCBAPIError as e:
#     print(f"Failed to get account information: {e.message}")
#     print(f"Error code: {e.code}")
#     if hasattr(e, 'details') and e.details:
#         print(f"Error details: {json.dumps(e.details, indent=2)}")

# Get available cryptocurrencies
try:
    print("\n========== AVAILABLE CURRENCIES ==========")
    currencies = client.get_currencies()
    
    print(f"Found {len(currencies)} available cryptocurrencies:")
    
    # Print in a table-like format
    print(f"{'CURRENCY ID':<12} {'NAME':<20} {'CODE':<8}")
    print("-" * 40)
    
    # Sort currencies by ID for better readability
    for currency_id, details in sorted(currencies.items()):
        name = details.get('name', 'Unknown')
        code = details.get('code', 'Unknown')
        print(f"{currency_id:<12} {name:<20} {code:<8}")
    
    print("\nRaw currencies data:")
    print(json.dumps(currencies, indent=2))
    print("==========================================\n")
    
except SCBAPIError as e:
    print(f"Failed to get currencies: {e.message}")
    print(f"Error code: {e.code}")
    if hasattr(e, 'details') and e.details:
        print(f"Error details: {json.dumps(e.details, indent=2)}")

# Logout
try:
    client.logout()
    print("\nLogged out successfully")
except SCBAPIError as e:
    print(f"Logout failed: {e.message}")
    print(f"Error details: {e.details}") 