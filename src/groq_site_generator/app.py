from importlib import reload
import os
import uuid
from flask import Flask, render_template, request, Response, session, jsonify
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from .extensions import db, csrf
from .models import ChatHistory, SiteVersion

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site_generator.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
csrf.init_app(app)

with app.app_context():
    db.create_all()

try:
    llm = ChatGroq(model="moonshotai/kimi-k2-instruct", temperature=0.1)
except Exception as e:
    print(f"Error initializing ChatGroq: {e}")
    llm = None

SYSTEM_PROMPT = """
    You are a world-class UI/UX Engineer and Web Developer. You specialize in writing clean, modern, and high-performance websites with a focus on exceptional user experience and cutting-edge design. Your work is indistinguishable from that of a top-tier digital agency.
Your task is to generate a single, self-contained HTML file based on the user's request, strictly adhering to the following rules:

1. Output Format & Structure
    Single File Only: Your entire response must be a single block of HTML code. Your output must start with <!DOCTYPE html> and end with </html>.
    No Extra Text: DO NOT include any explanations, markdown formatting, comments, or any text outside of the HTML code.
    Structure: Use semantic HTML5 elements (<main>, <section>, <nav>, <article>, etc.). The document structure must be logical and well-organized.

2. Styling & Design
    Framework: Use the Tailwind CSS v3 Play CDN for all utility-first styling. Do not use any other frameworks like Bootstrap. The Tailwind script tag should be placed in the <head>.
    Custom CSS: All custom CSS—including CSS variables, keyframe animations, and complex grid/flex layouts—must be placed within a single <style> tag inside the <head>. This custom CSS should complement Tailwind, not override it.
    Design Quality: The design must be visually stunning, aesthetically pleasing, and adhere to modern UI principles. Prioritize a clean layout, strong visual hierarchy, and a sophisticated color palette.
    Responsiveness: Implement a fully responsive, mobile-first design that looks flawless on all screen sizes. Use CSS Flexbox and Grid for robust layouts.
    Advanced Techniques: Demonstrate expert-level CSS skills. Employ techniques like clamp() for fluid typography/spacing, CSS custom properties for theme management (especially for dark mode), backdrop-filter for glassmorphism effects, and scroll-driven animations (animation-timeline: scroll()) for engaging user experiences.

3. Interactivity & Functionality
    JavaScript Placement: All necessary JavaScript must be placed within a single <script> tag just before the closing </body> tag.
    Modern Vanilla JS: Write clean, efficient, and modern vanilla JavaScript (ES6+). Do not use external libraries like jQuery.
    Dark/Light Mode: If the design calls for it, include a functional dark/light mode toggle. The user's preference should be saved to localStorage to persist across sessions.
    Animations: Implement smooth, purposeful micro-animations and transitions on user interactions (e.g., hover, focus, click). Animations should be performant, primarily using transform and opacity.

4. Continuity
    If the user provides existing code from a previous turn, use that code as the foundation. Apply the new requests by editing and extending the existing code, ensuring all quality standards are maintained throughout the iterative process.
"""

class PersistentChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages = []
        self.load_messages()

    def load_messages(self):
        with app.app_context():
            history = ChatHistory.query.filter_by(session_id=self.session_id).first()
            if history:
                self.messages = messages_from_dict(history.get_messages())

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
        self.save_messages()

    def save_messages(self):
        with app.app_context():
            history = ChatHistory.query.filter_by(session_id=self.session_id).first()
            if not history:
                history = ChatHistory(session_id=self.session_id)
                db.session.add(history)
            
            history.set_messages(messages_to_dict(self.messages))
            db.session.commit()

    def clear(self) -> None:
        self.messages = []
        self.save_messages()

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    return PersistentChatMessageHistory(session_id)


prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

chain = prompt_template | llm

runnable_with_message_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)


@app.route("/")
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate_code():
    if not llm:
        return Response(
            "LLM not initialized. Check API key and dependencies.", status=500
        )

    data = request.get_json()
    user_prompt = data.get("prompt")
    existing_code = data.get("code", "")
    session_id = session.get("session_id")

    if not user_prompt:
        return Response("Prompt is required.", status=400)
    if not session_id:
        return Response("Session not found.", status=400)

    if existing_code and len(existing_code) > 50:
        full_prompt = f"""**User's Request:**
{user_prompt}

**Existing Code to Modify:**
```html
{existing_code}
```
and continue the flow and follow the instructions in system prompt do not add any extra text or comments
"""
    else:
        full_prompt = user_prompt

    config = {"configurable": {"session_id": session_id}}

    def generate():
        full_response = ""
        try:
            for chunk in runnable_with_message_history.stream(
                {"input": full_prompt}, config=config
            ):
                content = chunk.content
                full_response += content
                yield content
            
            # Save version after successful generation
            with app.app_context():
                 version = SiteVersion(session_id=session_id, html_content=full_response, prompt=user_prompt)
                 db.session.add(version)
                 db.session.commit()

        except Exception as e:
            print(f"Error during generation: {e}")
            error_message = f"/* Error: {str(e)} */"
            yield error_message

    return Response(generate(), mimetype="text/plain")


@app.route("/new_chat", methods=["POST"])
def new_chat():
    session.pop("session_id", None)
    session["session_id"] = str(uuid.uuid4())
    return "OK"


@app.route("/api/versions", methods=["GET"])
def get_versions():
    session_id = session.get("session_id")
    if not session_id:
        return Response("Session not found", status=400)
    
    versions = SiteVersion.query.filter_by(session_id=session_id).order_by(SiteVersion.created_at.desc()).all()
    return jsonify([{
        "id": v.id,
        "prompt": v.prompt,
        "created_at": v.created_at.isoformat()
    } for v in versions])


@app.route("/api/versions/<int:version_id>", methods=["GET"])
def get_version(version_id):
    session_id = session.get("session_id")
    if not session_id:
        return Response("Session not found", status=400)

    version = SiteVersion.query.get_or_404(version_id)
    if version.session_id != session_id:
        return Response("Unauthorized", status=403)
        
    return jsonify({
        "id": version.id,
        "html_content": version.html_content,
        "prompt": version.prompt
    })


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """List all chat sessions with metadata"""
    # Get all unique session_ids from ChatHistory
    sessions = db.session.query(ChatHistory.session_id).distinct().all()
    
    session_list = []
    for (session_id,) in sessions:
        # Get session metadata
        history = ChatHistory.query.filter_by(session_id=session_id).first()
        if history:
            # Count messages in this session
            message_count = len(history.get_messages())
            
            # Count versions in this session
            version_count = SiteVersion.query.filter_by(session_id=session_id).count()
            
            session_list.append({
                "id": session_id,
                "created_at": history.created_at.isoformat(),
                "updated_at": history.updated_at.isoformat(),
                "message_count": message_count,
                "version_count": version_count
            })
    
    # Sort by creation date, newest first
    session_list.sort(key=lambda x: x["created_at"], reverse=True)
    
    return jsonify(session_list)


@app.route("/api/sessions/<session_id>/switch", methods=["POST"])
def switch_session(session_id):
    """Switch to a specific session"""
    # Validate that the session exists
    history = ChatHistory.query.filter_by(session_id=session_id).first()
    if not history:
        return Response("Session not found", status=404)
    
    # Update Flask session
    session["session_id"] = session_id
    
    return jsonify({
        "success": True,
        "session_id": session_id,
        "message": "Successfully switched to session"
    })


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session_details(session_id):
    """Get detailed session information including messages and versions"""
    # Validate that the session exists
    history = ChatHistory.query.filter_by(session_id=session_id).first()
    if not history:
        return Response("Session not found", status=404)
    
    # Get session metadata
    message_count = len(history.get_messages())
    versions = SiteVersion.query.filter_by(session_id=session_id).order_by(SiteVersion.created_at.desc()).all()
    version_count = len(versions)
    
    # Prepare versions list with basic info
    version_list = []
    for version in versions:
        version_list.append({
            "id": version.id,
            "prompt": version.prompt,
            "created_at": version.created_at.isoformat()
        })
    
    return jsonify({
        "id": session_id,
        "created_at": history.created_at.isoformat(),
        "updated_at": history.updated_at.isoformat(),
        "message_count": message_count,
        "version_count": version_count,
        "versions": version_list,
        "messages": history.get_messages()
    })


if __name__ == "__main__":
    debug_mode = os.environ.get("DEBUG", os.environ.get("FLASK_DEBUG", "false")).lower() in ("true", "1", "yes", "on")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    
    app.run(debug=debug_mode, host=host, port=port)
