"""Application config. INTENTIONALLY VULNERABLE fixture for Sentinel tests."""

# SECRETS/MISCONFIG: hardcoded credentials and API keys committed to source.
DATABASE_PASSWORD = "SuperSecret123!"
STRIPE_API_KEY = "EXAMPLE-hardcoded-payment-api-key-do-not-use-000000"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# MISCONFIG: debug mode enabled in production configuration.
DEBUG = True
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "django-insecure-hardcoded-key-do-not-use"
