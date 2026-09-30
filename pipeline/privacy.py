import hashlib,hmac
def plate_token(plate,salt):
    if not salt:raise ValueError('A secret salt is required')
    value=''.join(c for c in plate.upper() if c.isalnum())
    return hmac.new(salt.encode(),value.encode(),hashlib.sha256).hexdigest()
