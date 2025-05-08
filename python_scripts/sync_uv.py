import os

github_token = os.environ.get("GITHUB_TOKEN")
if github_token:
    github_api_headers = {"Authorization": f"Bearer {github_token}"}
else:
    github_api_headers = {}
