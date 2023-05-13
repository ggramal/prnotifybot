from flask import Flask, abort, make_response, request


@app.route("/api/v1/webhooks/pr", methods=["POST"])
def get_pull_request():
  pr = request.json
  print(pr)
