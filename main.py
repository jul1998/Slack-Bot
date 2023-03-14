import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import datetime

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], "/slack/events", app)

client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
BOT_ID = client.api_call("auth.test")["user_id"]


@slack_event_adapter.on("message")
def message(payload):
    event = payload.get("event", {})
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text")
    names_incoming = []
    names_lunch = []
    names_break = []
    names = ["Julian", "Julian Andres", "Jonathan", "Tony"]
    if user_id != BOT_ID:
        # Get the user info using the users_info API method
        user_info = client.users_info(user=user_id)
        username = user_info["user"]["profile"]["real_name"]
        new_text = f"The user:{username} said: {text}"
        #client.chat_postMessage(channel=channel_id, text=new_text)
        list_text = "[Members waiting for next turn]\n" + "\n".join([f"* {name}" for name in names])
        if text.lower() == "morning shift":
            list_text = "[Members in the morning shift]\n" + "\n".join(
                [f"{i}. {name}" for i, name in enumerate(names, start=1)])
            client.chat_postMessage(channel=channel_id, text=list_text)
        elif text.lower() == "ready":
            names_incoming.append(username)
        elif text.lower() == "lunch":
            names_lunch.append(username)
        elif text.lower() == "break":
            names_break.append(username)
                # Create message with updated lists
            list_text = "[Members incoming]\n" + "\n".join([f"* {name}" for name in names_incoming])
            list_text += "\n\n[Members at lunch]\n" + "\n".join([f"* {name}" for name in names_lunch])
            list_text += "\n\n[Members on break]\n" + "\n".join([f"* {name}" for name in names_break])
            # Send message to channel with updated lists
            client.chat_postMessage(channel=channel_id, text=list_text)
        elif text.lower() == "members waiting":
            now = datetime.datetime.now()
            if now.weekday() == 1:

                client.chat_postMessage(channel=channel_id, text=list_text)
        elif text.lower() == "lunch":
            for name in names:
                if name == username:
                    #delete name from names and adde it to the end of the list
                    names.remove(name)
                    names.append(name)
                    break
            # update list_text after removing the user's name from the list
            list_text = "[Members waiting for next turn]\n" + "\n".join([f"* {name}" for name in names])
            client.chat_postMessage(channel=channel_id, text=list_text)

        elif text.lower() == "break":
            pass

        else:
            pass
            # client.chat_postMessage(channel=channel_id, text=text)



@app.route('/help', methods=['POST'])
def slack_events():
    data = request.form
    channel_id = data.get("channel_id")

    list_of_commands = "List of commands:\n" \
                        "1. morning shift - list of members in the morning shift\n" \
                        "2. members waiting - list of members waiting for next turn\n" \
                        "3. lunch - remove your name from the list and add it to the end of the list\n" \
                        "4. help - list of commands\n"
    client.chat_postMessage(channel=channel_id, text=list_of_commands)
    return Response(), 200



if __name__ == "__main__":
    app.run(debug=True)
