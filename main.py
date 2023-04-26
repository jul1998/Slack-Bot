import slack
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
from slack_sdk.errors import SlackApiError
import datetime
from collections import deque
from datetime import datetime, timedelta
import time
import csv
import requests
from io import StringIO


env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(os.environ['SIGNING_SECRET'], "/slack/events", app)

client = slack.WebClient(token=os.environ['SLACK_TOKEN'])
BOT_ID = client.api_call("auth.test")["user_id"]


members_waiting_Q = deque([])
members_with_cases_Q = deque([])
lunch_Q = deque()
other_tasks_Q = deque()

#create a dictionary that conains hours as keys and list with members as values
hours = {
    13: ["Julian", "Julian Andres", "Jonathan", "Tony"],
    14: ["Roger", "Julian Andres", "Marta", "Tony"],
    15: ["Julian", "Julian Andres", "Jonathan", "Tony"],
    16: ["Julian", "Julian Andres", "Allan", "Tony"],
    17: ["Julian", "Julian Andres", "Jonathan", "Tony"],
    18: ["Julian", "Julian Andres", "Jonathan", "Tony"],
    19: ["Julian", "Julian Andres", "Jonathan", "Tony", "arr"], }



def get_current_hour():
    now = datetime.now()
    current_hour = now.hour
    return current_hour
#
# def get_members_starting_shift_in_hour(hour):
#     members = []
#     if hour == 6:
#         members = ["Julian", "Jonathan", "Tony", "Ana", "Adri"]
#     elif hour == 7:
#         members = ["Julian Andres", "Tony", "Dani", "Peter"]
#     elif hour == 14:
#         members = ["Marco", "Allan", "Ale", "Marta"]
#     # add more hours and corresponding members here
#     return members
#
# def update_shift_lists():
#     current_hour = get_current_hour()
#     members_starting_shift = get_members_starting_shift_in_hour(current_hour)
#     for member in members_starting_shift:
#         if member in members_waiting_Q:
#             members_waiting_Q.remove(member)
#     shift_list_text = f"[Members in the {current_hour}am shift]\n" + "\n".join(
#         [f"{i}. {name}" for i, name in enumerate(members_starting_shift, start=1)])
#     client.chat_postMessage(channel="#general", text=shift_list_text)


last_command_times = {}

def execute_command(command_name, user_id):
    current_time = time.time()
    if command_name not in last_command_times:
        last_command_times[command_name] = {}
    if user_id not in last_command_times[command_name]:
        last_command_times[command_name][user_id] = 0
    if current_time - last_command_times[command_name][user_id] > 10:
        # execute the command
        last_command_times[command_name][user_id] = current_time
    else:
        # rate limit exceeded
        print("Rate limit exceeded")
        return True
    return False

def display_text_list():
    list_text = f"************[Members waiting for cases]************ \n" + "\n".join([f"{name}" for name in members_waiting_Q])
    list_text += "\n ************[Waiting after resolving cases/Members with cases]************ \n" + "\n".join([f"{name}" for name in members_with_cases_Q])
    list_text += "\n ************[Members in lunch]************ \n" + "\n".join([f"{name}" for name in lunch_Q])
    list_text += "\n ************[Members with other tasks]************ \n" + "\n".join([f"{name}" for name in other_tasks_Q])
    return list_text

def add_to_lunch_queue(username, channel_id):
    if username in members_waiting_Q:
        lunch_Q.append(username)
        members_waiting_Q.remove(username)
    elif username in other_tasks_Q:
        other_tasks_Q.remove(username)
        lunch_Q.append(username)
    elif username in members_with_cases_Q:
        members_with_cases_Q.remove(username)
        lunch_Q.append(username)
    elif username in lunch_Q:
        client.chat_postMessage(channel=channel_id, text=f"{username} is already in the lunch queue")
    else:
        lunch_Q.append(username)
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def add_member_to_waiting_queue(channel_id, username):
    if username in members_waiting_Q:
        client.chat_postMessage(channel=channel_id, text=f"{username} is already in the waiting queue")
    elif username in lunch_Q:
        lunch_Q.remove(username)
        members_waiting_Q.append(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been moved from the lunch queue to the waiting queue")
    elif username in other_tasks_Q:
        other_tasks_Q.remove(username)
        members_waiting_Q.append(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been moved from other tasks to the waiting queue")
    elif username in members_with_cases_Q:
        members_with_cases_Q.remove(username)
        members_waiting_Q.append(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been moved from the cases queue to the waiting queue")
    else:
        members_waiting_Q.append(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been added to the waiting queue")
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def add_member_to_other_tasks_queue(channel_id, username):
    if username in other_tasks_Q:
        client.chat_postMessage(channel=channel_id, text=f"{username} is already in the other tasks queue")
    elif username in members_waiting_Q:
        other_tasks_Q.appendleft(username)
        members_waiting_Q.remove(username)
    elif username in lunch_Q:
        lunch_Q.remove(username)
        other_tasks_Q.appendleft(username)
    elif username in members_with_cases_Q:
        members_with_cases_Q.remove(username)
        other_tasks_Q.appendleft(username)
    else:
        other_tasks_Q.appendleft(username)
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def assign_case(username,channel_id):
    if username in members_waiting_Q:
        members_waiting_Q.remove(username)
        members_with_cases_Q.append(username)
    elif username in members_with_cases_Q:
        client.chat_postMessage(channel=channel_id, text=f"{username} already has a case")
    elif username in other_tasks_Q:
        other_tasks_Q.remove(username)
        members_with_cases_Q.append(username)
    elif username in lunch_Q:
        lunch_Q.remove(username)
        members_with_cases_Q.append(username)
    else:
        members_with_cases_Q.append(username)
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def exit_from_all_queues(username, channel_id):
    if username in members_waiting_Q:
        members_waiting_Q.remove(username)
    elif username in other_tasks_Q:
        other_tasks_Q.remove(username)
    elif username in members_with_cases_Q:
        members_with_cases_Q.remove(username)
    elif username in lunch_Q:
        lunch_Q.remove(username)
    client.chat_postMessage(channel=channel_id, text=f"Member {username} is out")
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def remove_user_from_queue(user_name, channel_id, user_to_removed):
    if user_to_removed in members_waiting_Q:
        members_waiting_Q.remove(user_to_removed)
    elif user_to_removed in other_tasks_Q:
        other_tasks_Q.remove(user_to_removed)
    elif user_to_removed in lunch_Q:
        lunch_Q.remove(user_to_removed)

    else:
        client.chat_postMessage(channel=channel_id, text=f"{user_to_removed} is in no queue any longer")
        client.chat_postMessage(channel=channel_id, text=display_text_list())
    client.chat_postMessage(channel=channel_id, text=f"{user_to_removed} has been removed from all the queues by {user_name}")
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def add_to_top(username, channel_id):
    if username in members_waiting_Q:
        members_waiting_Q.remove(username)
        members_waiting_Q.appendleft(username)
    elif username in lunch_Q:
        lunch_Q.remove(username)
        members_waiting_Q.appendleft(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been moved from the lunch queue to the top of the waiting queue")
    elif username in other_tasks_Q:
        other_tasks_Q.remove(username)
        members_waiting_Q.appendleft(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been moved from other tasks to the top of the waiting queue")
    else:
        members_waiting_Q.appendleft(username)
        client.chat_postMessage(channel=channel_id, text=f"{username} has been added to the top of the waiting queue")
    client.chat_postMessage(channel=channel_id, text=display_text_list())

def add_multiple_users_to_specific_queue(queue,user_who_moved, channel_id, user_names):
    print("Channeld id in function",channel_id)
    for user_name in user_names:
        if queue == "waiting":
            add_member_to_waiting_queue(channel_id, user_name)
        elif queue == "lunch":
            add_to_lunch_queue(user_name, channel_id)
        elif queue == "other":
            add_member_to_other_tasks_queue(channel_id, user_name)
        elif queue == "top":
            add_to_top(user_name, channel_id)
        elif queue == "remove":
            remove_user_from_queue(user_who_moved, channel_id, user_name)
        elif queue == "with_case":
            assign_case(user_name, channel_id)
    return



def reset_list(channel_id):
    members_waiting_Q.clear()
    other_tasks_Q.clear()
    members_with_cases_Q.clear()
    lunch_Q.clear()
    client.chat_postMessage(channel=channel_id, text="The list has been reset")

def move_users_from_with_case_to_waiting(channel_id):
    while members_with_cases_Q:
        members_waiting_Q.append(members_with_cases_Q.pop())
    client.chat_postMessage(channel=channel_id, text=display_text_list())
@app.route("/")
def hello():
    return "Hello World!aa"


@slack_event_adapter.on("message")
def message(payload):
    event = payload.get("event", {})
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text")
    if user_id != BOT_ID:
        # Get the user info using the users_info API method
        user_info = client.users_info(user=user_id)
        username = user_info["user"]["profile"]["real_name"]

        if execute_command(text, user_id):
            client.chat_postMessage(channel=channel_id, text="Wait 5 seconds before using this command again")
            return
        if text.lower() == "list":
            client.chat_postMessage(channel=channel_id, text=display_text_list())
        elif text.lower() == "lunch timer":
            if username not in lunch_Q:
                add_to_lunch_queue(username, channel_id)
            if username in lunch_Q:
                time.sleep(20)
                add_member_to_waiting_queue(channel_id, username)
                return
        elif text.lower() == "lunch":
            add_to_lunch_queue(username, channel_id)
        elif text.lower() == "ready":
            add_member_to_waiting_queue(channel_id, username)
        elif text.lower() == "other":
            add_member_to_other_tasks_queue(channel_id, username)
        elif text.lower() == "done":
            assign_case(username,channel_id)
        elif text.lower() == "top":
            add_to_top(username,channel_id)
        elif text.lower() == "eos":
            exit_from_all_queues(username, channel_id)
        elif text.lower() == "reset":
            reset_list(channel_id)
        elif text.lower() == "move_to_waiting":
            move_users_from_with_case_to_waiting(channel_id)
        else:
           pass



@app.route('/help', methods=['POST'])
def slack_events():
    data = request.form
    channel_id = data.get("channel_id")

    list_of_commands = "List of commands:\n" \
                       "list: List all members waiting for cases\n" \
                       "lunch: Add yourself to the lunch queue\n" \
                       "lunch timer: Add yourself to the lunch queue and return to waiting Q after 1 hour\n" \
                       "ready: Add yourself to the waiting queue\n" \
                       "eos: End of your shift\n" \
                       "done: Say you have assigned your cases in MagnumPi\n" \
                       "other: Add yourself to other tasks queue\n" \
                       "top: Add yourself to the top of the waiting queue\n" \
                        "reset: Reset the list\n" \
                       "move_to_waiting: Move all users in 'with_case' Q to 'waiting' one\n" \
                       "/remove_user: Remove any user from the all the Qs\n" \
                       "/export dd-mm-yyyy dd-mm-yyyy: Export messages within date range\n" \
                        "/add_members_to_specific_queue queue name, *user names in slack separated by comma*\n" \
                       "/help: List all commands\n"
    client.chat_postMessage(channel=channel_id, text=list_of_commands)
    return Response(), 200

@app.route('/export', methods=['POST'])
def export_data_from_channel():
    # Get the text of the command from the request
    text = request.form['text']

    # Get the channel ID from the request
    channel_id = request.form['channel_id']
    print(channel_id)


    # Split the text of the command into two date strings
    start_date_str, end_date_str = text.split()

    # Parse the date strings into datetime objects
    try:
        start_date = datetime.strptime(start_date_str, '%d-%m-%Y')
        end_date = datetime.strptime(end_date_str, '%d-%m-%Y') + timedelta(days=1)
    except ValueError as e:
        client.chat_postMessage(channel=channel_id, text="Error: " + str(e) + " Please try again")
        return f"Error: Please enter the dates in the format dd-mm-yyyy"

    print(start_date, end_date)



    # Call the conversations.history method to retrieve the messages in the specified date range
    messages = []
    try:
        result = client.conversations_history(
            channel=channel_id,
            inclusive=True,
            oldest=str(start_date.timestamp()),
            latest=str(end_date.timestamp()),
            timeout=50
        )
        messages = result['messages']
        print(result)

    except SlackApiError as e:
        client.chat_postMessage(channel=channel_id, text="Error: " + str(e) + " Please try again")
        return f"Error: {e}"

    # # Parse the messages to extract the user and date information
    data = [['Message', 'User', 'Date']]
    for message in messages:
        if 'user' in message:
            user_id = message['user']
            user_info = client.users_info(user=user_id)
            user_name = user_info['user']['real_name']
            print(message)
        else:
            user_name = 'Unknown'

        timestamp = float(message['ts'])
        date = datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y %H:%M:%S')
        #print(timestamp, date)
        message_text = message['text']
        if message_text != '':
            data.append([message_text, user_name, date])

    # Write the data to a CSV file
    file_name = f'export_{start_date_str}_{end_date_str}.csv'
    try:
        with open(file_name, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(data)
        client.chat_postMessage(channel=channel_id, text="Data exported to " + file_name)
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text="Error: " + str(e) + " Please try again")
        return f"Error: {e}"

    # # Write the data to a CSV file
    # csv_string = StringIO()
    # writer = csv.writer(csv_string)
    # writer.writerows(data)

    # Upload the CSV file to Slack
    print("here1")
    files = client.files_list(user=BOT_ID)
    print(files)
    return Response(), 200

@app.route("/remove_user", methods=['POST'])
def remove_user_from_Q():
    data = request.form
    channel_id = data.get("channel_id")
    user_id = data.get("user_id")
    user_to_removed = data['text']
    user_info = client.users_info(user=user_id)
    user_name = user_info['user']['real_name']

    remove_user_from_queue(user_name, channel_id, user_to_removed)
    return Response(), 200

@app.route("/add_members_to_specific_queue", methods=['POST'])
def add_members_to_specific_queue():
    data = request.form
    channel_id = data.get("channel_id")
    user_id = data.get("user_id")
    user_info = client.users_info(user=user_id)
    user_who_moved = user_info['user']['real_name']
    text = data['text']
    raw_list = text.split(",")
    queue = raw_list.pop(0)

    print(raw_list)
    users_to_move = [x.strip() for x in raw_list]
    print(users_to_move)
    client.chat_postMessage(channel=channel_id, text=f"Text {text}, user: {user_who_moved}, queue: {queue} channel: {channel_id}")
    try:
        add_multiple_users_to_specific_queue(queue, user_who_moved, channel_id, users_to_move)
    except Exception as e:
        client.chat_postMessage(channel=channel_id, text="Error: " + str(e) + " Please try again")
        return f"Error: {e}"
    return Response(), 200

@app.route('/')
def index():
    return ("Here asdasd")

if __name__ == "__main__":
    app.run(debug=True)