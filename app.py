import os
from dotenv import load_dotenv
from flask import Flask, request, render_template, session, jsonify
from main import run_agent

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set")


@app.route("/")
def home():
    session["history"] = []  # fresh conversation each time the page loads
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    history = session.get("history", [])
    answer, updated_history = run_agent(question, history)
    session["history"] = updated_history

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "False") == "True")