from datetime import datetime
import json
import logging
from .extensions import db

logger = logging.getLogger(__name__)

class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), unique=True, nullable=False)
    messages = db.Column(db.Text, nullable=False, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_messages(self):
        try:
            return json.loads(self.messages)
        except json.JSONDecodeError as e:
            logger.exception("Failed to decode messages field for session_id: %s", self.session_id)
            return []

    def set_messages(self, messages_list):
        self.messages = json.dumps(messages_list)

class SiteVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), nullable=False, index=True)
    html_content = db.Column(db.Text, nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
