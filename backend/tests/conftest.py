import os

# Tests only: never supply a default signing secret to the application itself.
os.environ.setdefault('AUTH_SECRET_KEY', 'test-only-signing-secret-not-for-deployment')
