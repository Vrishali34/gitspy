import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, jsonify
from flask_session import Session
from main import run_agent

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set")

# Session cookie security flags
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

# --- Server-side sessions ---
# Previously, the entire conversation history was stored inside the
# session cookie itself (client-side), which has a hard ~4093-byte
# browser limit - large answers (e.g. listing 90+ repos) blew past that.
# With Flask-Session, only a small session ID is stored in the cookie;
# the actual history is saved in a file on the server instead. This
# removes the byte-size ceiling entirely, regardless of answer size.
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(__file__), ".flask_session")
app.config["SESSION_PERMANENT"] = False
Session(app)

MAX_QUESTION_LENGTH = 500  # characters


@app.route("/")
def home():
    session["history"] = []  # fresh conversation each time the page loads
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"error": "No question provided"}), 400

    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"error": f"Question too long. Please keep it under {MAX_QUESTION_LENGTH} characters."}), 400

    history = session.get("history", [])
    answer, updated_history = run_agent(question, history)
    session["history"] = updated_history

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "False") == "True")