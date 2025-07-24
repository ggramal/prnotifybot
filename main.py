import config
import asyncio

from flask import Flask, abort, make_response, request
from github_webhook import Webhook
from dataclasses import dataclass, fields
from collections import UserDict
from datetime import datetime
from zoneinfo import ZoneInfo
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import MessageNotModifiedError

app = Flask(__name__)
webhook = Webhook(app, endpoint="/webhooks/pr", secret=config.WH_SECRET)
pr_dict = {}
loop = asyncio.get_event_loop()


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


@dataclass(init=False, eq=False)
class PullRequest(GitHubEntity):
    user: GitHubUser
    state: str
    title: str
    merged_at: str

    def __eq__(self, other):
        if isinstance(other, PullRequest):
            return self.html_url == other.html_url
        return NotImplemented

    def __hash__(self):
        return hash((self.html_url))

    def __str__(self):
        now = datetime.now(ZoneInfo(config.TIMEZONE))
        now = now.strftime("%Y-%m-%d %H:%M:%S")
        emoji = ""
        if self.merged_at:
            self.state = "merged"
            emoji = " \U00002935"  #:arrow_heading_down:
        elif self.state == "closed":
            emoji = " \U0000274c"  #:x:
        elif self.state == "open":
            emoji = " \U00002728"  #:sparkles:

        if self.state == "pushed":
            return now + f" {self.user} pushed"

        return f'[{self.state.upper()}{emoji}] "{self.title}" {self.html_url}'


@dataclass(init=False)
class PullRequestReview(GitHubEntity):
    user: GitHubUser
    pull_request: PullRequest
    state: str

    def __str__(self):
        now = datetime.now(ZoneInfo(config.TIMEZONE))
        now = now.strftime("%Y-%m-%d %H:%M:%S")
        emoji = ""
        if self.state == "approved":
            emoji = " \U00002714"  #:heavy_check_mark:

        return now + f" {self.user} {self.state}{emoji}"


@dataclass(init=False)
class PullRequestReviewComment(GitHubEntity):
    user: GitHubUser
    pull_request: PullRequest
    state: str

    def __str__(self):
        now = datetime.now(ZoneInfo(config.TIMEZONE))
        now = now.strftime("%Y-%m-%d %H:%M:%S")
        return now + f" {self.user} {self.state} [comment]({self.html_url})"


@dataclass(init=False)
class IssueComment(GitHubEntity):
    user: GitHubUser
    pull_request: PullRequest
    state: str

    def __str__(self):
        now = datetime.now(ZoneInfo(config.TIMEZONE))
        now = now.strftime("%Y-%m-%d %H:%M:%S")
        return now + f" {self.user} {self.state} [issue comment]({self.html_url})"


class Message:
    def __init__(self, text, telegram=True):
        self.text = text
        self.__message = None
        self.telegram = telegram

    def send(self):
        if self.telegram:
            loop.run_until_complete(self._telegram_send())
        else:
            raise NotImplementedError

    async def _telegram_send(self):
        dialogs = await tg_client.get_dialogs()
        if not self.__message:
            self.__message = await tg_client.send_message(
                config.TG_CHAT_NAME, self.text
            )
        else:
            await tg_client.edit_message(self.__message, self.text)


@webhook.hook("pull_request")
def get_pull_request(data):
    if data["action"] == "synchronize":
        data["pull_request"]["state"] = "pushed"

    data = data["pull_request"]
    data["user"] = GitHubUser(**data["user"])
    pr = PullRequest(**data)
    pr_in_dict = pr in pr_dict.keys()

    if not pr_in_dict:
        pr_dict[pr] = Message(f"{pr}")
    elif pr_in_dict and pr.state == "pushed":
        pr_dict[pr].text = f"{pr_dict[pr].text}\n{pr}"
    elif pr_in_dict:
        message_lines = pr_dict[pr].text.split("\n")
        pr_lines = str(pr).split("\n")
        message_lines[0] = pr_lines[0]
        pr_dict[pr].text = "\n".join(message_lines)

    try:
        pr_dict[pr].send()
    except MessageNotModifiedError:
        app.logger.warning(f"Message was not modified.\n{pr_dict[pr].text}")

    return {"status": "ok"}


@webhook.hook("pull_request_review")
def get_pull_request_review(data):
    user = GitHubUser(**data["review"]["user"])

    data["review"]["user"] = user
    data["pull_request"]["user"] = user

    pr = PullRequest(**data["pull_request"])

    data = data["review"]
    data["pull_request"] = pr

    pr_review = PullRequestReview(**data)

    if pr_review.state == "commented":
        return {"status": "ok"}

    if pr in pr_dict.keys():
        pr_dict[pr].text = f"{pr_dict[pr].text}\n{pr_review}"
    else:
        pr_dict[pr] = Message(f"{pr}\n{pr_review}")

    try:
        pr_dict[pr].send()
    except MessageNotModifiedError:
        app.logger.warning(f"Message was not modified.\n{pr_dict[pr].text}")

    return {"status": "ok"}


@webhook.hook("pull_request_review_comment")
def get_pull_request_review_comment(data):
    user = GitHubUser(**data["comment"]["user"])

    data["comment"]["state"] = data["action"]
    data["comment"]["user"] = user
    data["pull_request"]["user"] = user

    pr = PullRequest(**data["pull_request"])

    data = data["comment"]
    data["pull_request"] = pr

    pr_review_comment = PullRequestReviewComment(**data)

    if pr in pr_dict.keys():
        pr_dict[pr].text = f"{pr_dict[pr].text}\n{pr_review_comment}"
    else:
        pr_dict[pr] = Message(f"{pr}\n{pr_review_comment}")

    try:
        pr_dict[pr].send()
    except MessageNotModifiedError:
        app.logger.warning(f"Message was not modified.\n{pr_dict[pr].text}")

    return {"status": "ok"}


@webhook.hook("issue_comment")
def get_issue_comment(data):
    user = GitHubUser(**data["comment"]["user"])

    data["comment"]["state"] = data["action"]
    data["comment"]["user"] = user
    data["issue"]["pull_request"]["user"] = user
    # data["pull_request"] doesnt have state/title keys
    # so we need to create them. Empty string here
    # in order for state.upper() to work in all cases
    data["issue"]["pull_request"]["state"] = ""
    data["issue"]["pull_request"]["title"] = ""

    pr = PullRequest(**data["issue"]["pull_request"])

    data = data["comment"]
    data["pull_request"] = pr

    issue_comment = IssueComment(**data)

    if pr in pr_dict.keys():
        pr_dict[pr].text = f"{pr_dict[pr].text}\n{issue_comment}"
    else:
        pr_dict[pr] = Message(f"{pr}\n{issue_comment}")

    try:
        pr_dict[pr].send()
    except MessageNotModifiedError:
        app.logger.warning(f"Message was not modified.\n{pr_dict[pr].text}")

    return {"status": "ok"}


if __name__ == "__main__":
    tg_client = TelegramClient(
        "./tgdata/dat", config.TG_API_ID, config.TG_API_HASH, loop=loop
    )
    tg_client.start()
    app.run(host="0.0.0.0")
