from flask import Flask, abort, make_response, request
from github_webhook import Webhook
from dataclasses import dataclass, fields

app = Flask(__name__)
webhook = Webhook(app,endpoint="/webhooks/pr")


@dataclass(init=False)
class GitHubEntity:
    html_url: str

    def __init__(self, **kwargs):
        field_names = set([field.name for field in fields(self)])
        for cls_field, cls_field_value in kwargs.items():
            if cls_field in field_names:
                setattr(self, cls_field, cls_field_value)

@dataclass(init=False)
class GitHubUser(GitHubEntity):
    login: str

    def __str__(self):
        return f"{self.login}"

@dataclass(init=False)
class PullRequest(GitHubEntity):
    user: GitHubUser
    state: str
    title: str
    merged_at: str

    def __str__(self):
        emoji = ""
        if self.merged_at:
            self.state = "merged"
            emoji = " :arrow_heading_down:"
        elif self.state == "closed":
            emoji = " :x:"
        elif self.state == "open":
            emoji = " :sparkles:"

        if self.state == "pushed": return f"{self.user} {self.state}"


        return f"[{self.state}{emoji}] {self.title}\n{self.user} {self.html_url}"

@dataclass(init=False)
class PullRequestReview(GitHubEntity):
    user: GitHubUser
    state: str

    def __str__(self):
        emoji = ""
        if self.state == "approved":
            emoji = " :heavy_check_mark:"

        return f"{self.user} {self.state}{emoji}"

@dataclass(init=False)
class PullRequestReviewComment(GitHubEntity):
    user: GitHubUser
    state: str

    def __str__(self):
        return f"{self.user} {self.state} comment {self.html_url}"



@webhook.hook("pull_request")
def get_pull_request(data):
    if data["action"] == "synchronize":
        data["pull_request"]["state"] = "pushed"

    data = data["pull_request"]
    data["user"] = GitHubUser(**data["user"])
    pr = PullRequest(**data)
    print(pr)
    return {"status":"ok"}

@webhook.hook("pull_request_review")
def get_pull_request_review(data):
    data = data["review"]
    data["user"] = GitHubUser(**data["user"])
    pr_review = PullRequestReview(**data)
    print(pr_review)
    return {"status":"ok"}

@webhook.hook("pull_request_review_comment")
def get_pull_request_review_comment(data):
    data["comment"]["state"] = data["action"]
    data = data["comment"]
    data["user"] = GitHubUser(**data["user"])
    pr_review_comment = PullRequestReviewComment(**data)
    print(pr_review_comment)
    return {"status":"ok"}



if __name__ == "__main__":
    app.run(host="0.0.0.0")
