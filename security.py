from cryptography.fernet import Fernet, InvalidToken
from typing import Optional

class PasswordCipher:
    """
    فئة لعمليات التشفير وفك التشفير باستخدام Fernet
    يجب توفير مفتاح ثابت عند إنشاء الكائن للحفاظ على إمكانية فك تشفير البيانات القديمة
    """
    
    def __init__(self, key: bytes) -> None:
        """
        تهيئة كائن التشفير
        
        :param key: مفتاح Fernet ثابت (يجب حفظه بشكل آمن)
        :type key: bytes
        """
        self.key = key
        self.cipher = Fernet(self.key)

    def encrypt_password(self, password: str) -> str:
        """
        تشفير كلمة المرور
        
        :param password: كلمة المرور النصية
        :return: كلمة المرور المشفرة
        :rtype: str
        """
        return self.cipher.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted_password: str) -> Optional[str]:
        """
        فك تشفير كلمة المرور
        
        :param encrypted_password: كلمة المرور المشفرة
        :return: كلمة المرور النصية أو None إذا فشل فك التشفير
        :rtype: Optional[str]
        """
        try:
            return self.cipher.decrypt(encrypted_password.encode()).decode()
        except InvalidToken:
            print("فشل فك التشفير: المفتاح غير صالح أو البيانات تالفة")
            return None
        except Exception as e:
            print(f"حدث خطأ أثناء فك التشفير: {str(e)}")
            return None


# مفتاح التشفير الثابت (يجب حفظه في مكان آمن)
# يمكن إنشاؤه مرة واحدة باستخدام Fernet.generate_key() ثم حفظه
ENCRYPTION_KEY = b'2xgchEDOPMIqyu2oKeDS1yO_ik7iB6rUVUfsTMDHOzQ='  # استبدل هذا بالمفتاح الفعلي

# إنشاء كائن التشفير
cipher = PasswordCipher(ENCRYPTION_KEY)