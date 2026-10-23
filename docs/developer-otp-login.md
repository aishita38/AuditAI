# Local developer OTP login

Choose a provisioned account on the login page, click **Generate developer OTP**, then **Sign in**. The random six-digit code is displayed and filled in on that page. Existing account roles and the normal session/logout flow still apply.

Codes expire after two minutes, work once, and are replaced when another code is generated for the account. Five incorrect attempts invalidate a code. Generation is limited to 30 requests per minute per API process.

Start the local API with `scripts/start_local_dev_otp.ps1`. Stop an existing AuditAI API first if port 8000 is already occupied. The helper enables `AUDITAI_DEV_OTP=1` only for the API process and binds it to 127.0.0.1.

This is a developer sign-in shortcut, not email verification or production MFA. It is disabled by default and requires a loopback client and host, with an allowed local frontend origin. Without the flag, the existing password login remains available. Restarting the API discards outstanding codes.
