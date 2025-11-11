import jwt, time, os, logging
log = logging.getLogger("Security")

class SecureAgent:
    def __init__(self):
        self.master_key = os.getenv("CTRL_MASTER_KEY", "CtrlMasterKey")
        self.secret = os.getenv("CTRL_JWT_SECRET", "ControllerSecret")

    def issue_token(self):
        payload = {"iat": time.time(), "exp": time.time() + 3600}
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify_token(self, token):
        try:
            jwt.decode(token, self.secret, algorithms=["HS256"])
            return True
        except Exception as e:
            log.error(e)
            return False
