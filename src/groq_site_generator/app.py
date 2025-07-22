import os
from flask import Flask, render_template, request, Response, session
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.memory import ChatMessageHistory
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

try:
    llm = ChatGroq(model="moonshotai/kimi-k2-instruct", temperature=0.1)
except Exception as e:
    print(f"Error initializing ChatGroq: {e}")
    llm = None

SYSTEM_PROMPT = """
    You are a world-class UI/UX Engineer and Web Developer. You specialize in writing clean, modern, and high-performance websites with a focus on exceptional user experience and cutting-edge design. Your work is indistinguishable from that of a top-tier digital agency.

Your task is to generate a single, self-contained HTML file based on the user's request, strictly adhering to the following rules:

1. Output Format & Structure

    Single File Only: Your entire response must be a single block of HTML code. It must start with <!DOCTYPE html> and end with </html>.

    No Extra Text: DO NOT include any explanations, markdown formatting, comments, or any text outside of the HTML code itself.

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

4. Accessibility & Performance

    Accessibility (A11Y): The code must meet WCAG 2.2 AA standards. Ensure all interactive elements are keyboard-navigable, focus states are clearly visible, and proper ARIA attributes are used where necessary. All images must have descriptive alt attributes.

    Performance: Code must be clean and efficient. While the Tailwind CDN loads the full library, your custom HTML, CSS, and JS should be optimized for speed.

5. Continuity

    If the user provides existing code from a previous turn, use that code as the foundation. Apply the new requests by editing and extending the existing code, ensuring all quality standards are maintained throughout the iterative process.

"""
store = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)

chain = prompt_template | llm

with_message_history = RunnableWithMessageHistory(
    chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="history",
)



@app.route("/")
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate_code():
    if not llm:
        return Response("LLM not initialized. Check API key and dependencies.", status=500)

    data = request.get_json()
    user_prompt = data.get("prompt")
    existing_code = data.get("code", "") 
    session_id = session.get('session_id')

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
        try:
            for chunk in with_message_history.stream({"input": full_prompt}, config=config):
                yield chunk.content
        except Exception as e:
            print(f"Error during generation: {e}")
            error_message = f"/* Error: {str(e)} */"
            yield error_message

    return Response(generate(), mimetype='text/plain')

@app.route("/new_chat", methods=["POST"])
def new_chat():
    session.pop('session_id', None)
    session['session_id'] = str(uuid.uuid4())
    return "OK"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
