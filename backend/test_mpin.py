import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()
from django.conf import settings
from apps.authentication.models import User
from cryptography.fernet import Fernet
print("Current ENCRYPTION_KEY length:", len(settings.ENCRYPTION_KEY), settings.ENCRYPTION_KEY)
user = User.objects.exclude(mpin_hash__isnull=True).exclude(mpin_hash="").first()
if user:
    print(f"Testing user {user.phone} with hash {user.mpin_hash[:10]}...")
    try:
        f = Fernet(settings.ENCRYPTION_KEY.encode("utf-8")[:32].ljust(32, b"=").decode("utf-8").encode())
        f.decrypt(user.mpin_hash.encode())
        print("Success: MPIN valid")
    except Exception as e:
        print("Failed to decrypt with current key:", e)
        old_key = settings.SECRET_KEY[:32]
        old_f = Fernet(old_key.encode("utf-8").ljust(32, b"=").decode("utf-8").encode())
        try:
            old_f.decrypt(user.mpin_hash.encode())
            print("Success: MPIN works with old SECRET_KEY fallback!")
        except Exception as e2:
            print("Also failed with old key:", e2)
