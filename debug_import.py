import sys
import traceback

print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

try:
    import ownerrez_api
    print("Successfully imported ownerrez_api")
except Exception:
    traceback.print_exc()
