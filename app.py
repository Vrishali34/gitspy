import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, jsonify
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