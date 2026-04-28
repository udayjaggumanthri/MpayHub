from datetime import datetime
import random
import string


def generate_billavenue_request_id() -> str:
    """
    35-char request ID format: <27 random> + <YDDDhhmm>
    - Y: last digit of current year
    - DDD: day of year
    - hhmm: 24h time
    """
    now = datetime.now()
    suffix = f"{now.year % 10}{now.timetuple().tm_yday:03d}{now:%H%M}"
    prefix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=27))
    return f"{prefix}{suffix}"[:35]
