import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()
from apps.authentication.models import User
from apps.core.utils import decrypt_mpin, _get_encryption_key
try:
    print("KEY:", _get_encryption_key())
except Exception as e:
    print("Error getting key:", e)
users = User.objects.exclude(mpin_hash__isnull=True).exclude(mpin_hash="")[:5]
for user in users:
    print("Testing user", user.phone)
    try:
        mp = decrypt_mpin(user.mpin_hash)
        print("Success for", user.phone)
    except Exception as e:
        print("Decryption Failed for", user.phone, ":", e)
