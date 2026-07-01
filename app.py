import os
from flask import Flask, request, render_template, session, jsonify
from main import run_agent

app = Flask(__name__)
app.secret_key = os.urandom(24)  # needed to securely sign session cookies


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
    app.run(debug=True)