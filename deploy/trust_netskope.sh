#!/bin/sh
# Make THIS venv trust the corporate Netskope TLS-inspection CA (verification stays ON).
# Appends only the Netskope root + Zomato tenant CA from /etc/netskope/netskope-cert-bundle.pem
# to .venv's certifi bundle (Modal's gRPC client reads certifi, not SSL_CERT_FILE).
# Re-run after any `pip install -U certifi`. Idempotent.
set -e
cd "$(dirname "$0")/.."
CA=$(.venv/bin/python -c "import certifi; print(certifi.where())")
grep -q "caadmin.netskope.com\|NETSKOPE-SAYDO" "$CA" && { echo "already trusted: $CA"; exit 0; }
.venv/bin/python - "$CA" <<'PY'
import re, subprocess, sys
pem = open("/etc/netskope/netskope-cert-bundle.pem").read()
certs = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.S)
keep = [c for c in certs if "etskope" in subprocess.run(["openssl", "x509", "-noout", "-subject", "-issuer"],
                                                         input=c, capture_output=True, text=True).stdout]
with open(sys.argv[1], "a") as f:
    f.write("\n# NETSKOPE-SAYDO corporate TLS inspection CA\n" + "\n".join(keep) + "\n")
print(f"appended {len(keep)} Netskope CA cert(s) to {sys.argv[1]}")
PY
