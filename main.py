import os
import re
import json
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

VALID_GITHUB_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')


def is_valid_github_name(name):
    """Check if a string is a plausible GitHub username or repo name."""
    return bool(name) and bool(VALID_GITHUB_NAME.match(name))


# ---------- TOOL 1: Get info about a specific repo ----------
def get_repo_info(owner, repo):
    """Fetch basic info about a GitHub repo."""
    if not is_valid_github_name(owner) or not is_valid_github_name(repo):
        return {"error": "Invalid owner or repo name."}
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(url, timeout=10)

        if response.status_code == 403:
            return {"error": "GitHub API rate limit reached. Please try again in a bit."}
        if response.status_code != 200:
            return {"error": f"Could not find repo {owner}/{repo}"}

        data = response.json()
        return {
            "name": data["full_name"],
            "description": data["description"],
            "stars": data["stargazers_count"],
            "open_issues": data["open_issues_count"],
            "language": data["language"],
            "last_updated": data["updated_at"]
        }
    except requests.exceptions.RequestException:
        return {"error": "Couldn't reach GitHub right now. Please try again."}


# ---------- TOOL 2: Summarize a user's whole account ----------
def get_account_summary(username):
    """Summarize a GitHub user's account: bio, total stars, top repo, top language."""
    if not is_valid_github_name(username):
        return {"error": "Invalid username."}
    try:
        profile_url = f"https://api.github.com/users/{username}"
        profile_res = requests.get(profile_url, timeout=10)

        if profile_res.status_code == 403:
            return {"error": "GitHub API rate limit reached. Please try again in a bit."}
        if profile_res.status_code != 200:
            return {"error": f"Could not find user {username}"}
        profile = profile_res.json()

        repos_url = f"https://api.github.com/users/{username}/repos?per_page=100"
        repos_res = requests.get(repos_url, timeout=10)

        if repos_res.status_code == 403:
            return {"error": "GitHub API rate limit reached. Please try again in a bit."}

        repos = repos_res.json()

        if not repos:
            return {"error": f"{username} has no public repos"}

        total_stars = sum(repo["stargazers_count"] for repo in repos)
        top_repo = max(repos, key=lambda r: r["stargazers_count"])

        language_counts = {}
        for repo in repos:
            lang = repo["language"]
            if lang:
                language_counts[lang] = language_counts.get(lang, 0) + 1

        most_used_language = max(language_counts, key=language_counts.get) if language_counts else "Unknown"

        return {
            "username": profile["login"],
            "bio": profile.get("bio"),
            "followers": profile["followers"],
            "public_repos": profile["public_repos"],
            "total_stars_across_repos": total_stars,
            "top_repo": top_repo["name"],
            "top_repo_stars": top_repo["stargazers_count"],
            "most_used_language": most_used_language,
            "account_created": profile["created_at"]
        }
    except requests.exceptions.RequestException:
        return {"error": "Couldn't reach GitHub right now. Please try again."}


# ---------- TOOL 3: List all repos for a user ----------
def list_user_repos(username):
    """List all public repos for a user, sorted by stars, with basic details."""
    if not is_valid_github_name(username):
        return {"error": "Invalid username."}
    try:
        repos_url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
        repos_res = requests.get(repos_url, timeout=10)

        if repos_res.status_code == 403:
            return {"error": "GitHub API rate limit reached. Please try again in a bit."}
        if repos_res.status_code != 200:
            return {"error": f"Could not find user {username}"}

        repos = repos_res.json()

        if not repos:
            return {"error": f"{username} has no public repos"}

        repo_list = sorted(
            [
                {
                    "name": repo["name"],
                    "stars": repo["stargazers_count"],
                    "language": repo["language"],
                    "description": repo["description"]
                }
                for repo in repos
            ],
            key=lambda r: r["stars"],
            reverse=True
        )

        return {"username": username, "repo_count": len(repo_list), "repos": repo_list}
    except requests.exceptions.RequestException:
        return {"error": "Couldn't reach GitHub right now. Please try again."}


# ---------- Tool descriptions for the LLM ----------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_repo_info",
            "description": "Get information about a specific GitHub repository, like stars, issues, and language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {"type": "string", "description": "GitHub username or org, e.g. 'facebook'"},
                    "repo": {"type": "string", "description": "Repository name, e.g. 'react'"}
                },
                "required": ["owner", "repo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_summary",
            "description": "Summarize a GitHub user's entire account: total stars across all their repos, their top repo, most-used programming language, follower count, and bio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The GitHub username, e.g. 'torvalds'"}
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_repos",
            "description": "List all public repositories for a GitHub user, including each repo's name, stars, language, and description. Use this when asked to list, name, or detail individual repos, or their tech stacks, or to compare accounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "The GitHub username, e.g. 'torvalds'"}
                },
                "required": ["username"]
            }
        }
    }
]

available_functions = {
    "get_repo_info": get_repo_info,
    "get_account_summary": get_account_summary,
    "list_user_repos": list_user_repos
}

# ---------- System prompt: defines the agent's scope ----------
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are GitSpy, an AI agent that answers questions about GitHub "
        "accounts and repositories things like stars, top repos, most-used "
        "languages, and comparisons between accounts — using live GitHub data "
        "via your tools.\n\n"
        "If the user asks something unrelated to GitHub (general knowledge, "
        "coding help unrelated to GitHub stats, personal opinions, etc.), "
        "politely explain that you're specialized for GitHub account/repo "
        "questions and ask them to rephrase their question in that context. "
        "Do not answer unrelated questions from general knowledge."
    )
}


# ---------- Core agent loop, reusable + conversation-aware ----------
def run_agent(user_question, history=None):
    """
    Runs the agent loop, allowing multiple rounds of tool calls if needed
    (e.g. comparing two accounts requires calling a tool twice, sequentially).
    Returns: (answer_text, updated_history)
    """
    if history is None:
        history = []

    if not user_question or not user_question.strip():
        return "Please type a question first!", history

    # history never contains the system prompt (see below) - only add it here, fresh, per call
    messages = [SYSTEM_PROMPT] + history + [{"role": "user", "content": user_question}]

    max_rounds = 5  # safety limit so it can never loop forever
    for _ in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=messages,
                tools=tools,
                timeout=20
            )
        except Exception as e:
            print(f"DEBUG ERROR: {e}")
            return "Sorry, I couldn't reach the AI service right now. Please try again in a moment.", history

        response_message = response.choices[0].message

        assistant_msg = {
            "role": "assistant",
            "content": response_message.content
        }
        if response_message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in response_message.tool_calls
            ]
        messages.append(assistant_msg)

        if not response_message.tool_calls:
            # No more tools needed - this is the final answer.
            # Strip the system prompt before saving to history, since we
            # re-add it fresh at the top of every call - without this,
            # the system prompt would duplicate on every turn.
            return response_message.content, messages[1:]

        # Execute every tool call the model asked for this round
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
                function_to_call = available_functions[function_name]
                result = function_to_call(**function_args)
            except Exception as e:
                print(f"DEBUG TOOL ERROR: {e}")
                result = {"error": f"Something went wrong while running {function_name}."}

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })
        # Loop back around - model gets another turn, now with tools still available

    return "Sorry, that request needed too many steps. Try asking something more specific.", history


# ---------- Standalone terminal chat mode ----------
if __name__ == "__main__":
    print("GitSpy is ready! Ask me about a GitHub repo or account. Type 'quit' to exit.\n")
    conversation_history = []
    while True:
        question = input("You: ")
        if question.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break
        answer, conversation_history = run_agent(question, conversation_history)
        print(f"\n🤖 GitSpy: {answer}\n")