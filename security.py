from cryptography.fernet import Fernet, InvalidToken
from typing import Optional


class PasswordCipher:
    """
    Class for encryption and decryption operations using Fernet.
    A constant key must be provided when creating the object to maintain 
    the ability to decrypt old data.
    """

    def __init__(self, key: bytes) -> None:
        """
        Initialize the cipher object.

        :param key: Constant Fernet key (must be stored securely)
        :type key: bytes
        """
        self.key = key
        self.cipher = Fernet(self.key)

    def encrypt_password(self, password: str) -> str:
        """
        Encrypt a password.

        :param password: Plain text password
        :return: Encrypted password
        :rtype: str
        """
        return self.cipher.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted_password: str) -> Optional[str]:
        """
        Decrypt a password.

        :param encrypted_password: Encrypted password
        :return: Plain text password or None if decryption fails
        :rtype: Optional[str]
        """
        try:
            return self.cipher.decrypt(encrypted_password.encode()).decode()
        except InvalidToken:
            print("Decryption failed: Invalid key or corrupted data")
            return None
        except Exception as e:
            print(f"Error during decryption: {str(e)}")
            return None


# Constant encryption key (must be stored securely)
# Can be generated once using Fernet.generate_key() and then stored
# Replace this with your actual key
ENCRYPTION_KEY = b'2xgchEDOPMIqyu2oKeDS1yO_ik7iB6rUVUfsTMDHOzQ='

# Create cipher object
cipher = PasswordCipher(ENCRYPTION_KEY)
