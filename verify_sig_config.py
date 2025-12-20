
import config
import os
import sys

print(f"Checking signature config...")
sig_path = getattr(config, 'SIGNATURE_IMAGE_PATH', None)
print(f"Configured path: {sig_path}")

if not sig_path:
    print("FAILURE: SIGNATURE_IMAGE_PATH is not set.")
    sys.exit(1)

if not os.path.exists(sig_path):
    print(f"FAILURE: File not found at {sig_path}")
    sys.exit(1)

print("SUCCESS: Signature file configured and found.")
