import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()
from apps.authentication.models import User
from apps.core.utils import decrypt_mpin, encrypt_mpin
users = User.objects.exclude(mpin_hash__isnull=True).exclude(mpin_hash="")
fixed_count = 0
for user in users:
    try:
        decrypt_mpin(user.mpin_hash)
    except Exception:
        user.mpin_hash = encrypt_mpin("123456")
        user.save(update_fields=["mpin_hash"])
        fixed_count += 1
print(f"Fixed {fixed_count} corrupted MPINs by resetting them to 123456")
