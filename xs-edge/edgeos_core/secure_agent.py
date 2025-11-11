import hashlib, os, jwt, time, logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("SecureAgent")

class SecureAgent:
    def __init__(self):
        self.secret = os.getenv("PLUGIN_SIGNING_KEY", "key")
        self.jwt_key = os.getenv("EDGE_TOKEN", None)
        self.dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

        # Automatically issue a token if missing or invalid in dev mode
        if (not self.jwt_key or len(self.jwt_key.split(".")) != 3) and self.dev_mode:
            self.jwt_key = os.getenv("PLUGIN_SIGNING_KEY", "EdgeOSDevSecret")
            self.current_token = self.issue_token()
            log.warning("⚠️  DEV_MODE active — generated a temporary JWT:")
            log.warning(f"   Bearer {self.current_token}")
        else:
            self.current_token = self.jwt_key

    def verify_plugin(self, path):
        if os.getenv("PLUGIN_VERIFY_SHA", "false").lower() != "true":
            return True
        try:
            data = open(path, "rb").read()
            digest = hashlib.sha256(data).hexdigest()
            log.debug(f"SHA256 for {os.path.basename(path)}: {digest[:10]}...")
            return True
        except Exception as e:
            log.error(e)
            return False

    def verify_token(self, token):
        try:
            jwt.decode(token, self.jwt_key, algorithms=["HS256"])
            return True
        except Exception as e:
            log.error(e)
            return False

    def issue_token(self):
        return jwt.encode(
            {"iat": time.time(), "exp": time.time() + 3600},  # 1-hour expiry
            self.jwt_key,
            algorithm="HS256"
        )
