# Starts the loopback-only API with on-page developer OTP enabled for this process.
# Run from any directory. Existing API listeners are left running; restart them explicitly.
$ErrorActionPreference = 'Stop'
$auditRoot = Split-Path -Parent $PSScriptRoot
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Output 'Port 8000 is already running. Restart its AuditAI API with AUDITAI_DEV_OTP=1 to enable OTP.'
    exit 0
}
$auditPreviousOtp = $env:AUDITAI_DEV_OTP
try {
    $env:AUDITAI_DEV_OTP = '1'
    Start-Process -FilePath 'C:\Users\aishi\anaconda3\python.exe' -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $auditRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $auditRoot 'scripts\artifacts\api.stdout.log') -RedirectStandardError (Join-Path $auditRoot 'scripts\artifacts\api.stderr.log')
    Write-Output 'AuditAI local API started with developer OTP.'
} finally {
    $env:AUDITAI_DEV_OTP = $auditPreviousOtp
}
