import pyotp

def generate_secret():
    """Generate a random secret key for TOTP"""
    return pyotp.random_base32()

def generate_url_otp(secret, app_name="Clandestine", username="user"):
    """Generate QR code for Google Authenticator"""
    # Create the provisioning URI
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(username, issuer_name=app_name)
    return provisioning_uri, secret

def verify_totp(secret, token):
    """Verify a TOTP token against a secret"""
    if not secret or not token:
        return False
        
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(token)
    except Exception as e:
        print(f"Error verifying token: {e}")
        return False
