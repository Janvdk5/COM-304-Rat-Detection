import flask as fk
import sys, os
import json

app = fk.Flask(__name__)

current_dir = (os.path.dirname(os.getcwd()))
JERRY_LOG_PATH = os.path.join(current_dir, "src/logs/jerry_log.jsonl")

print(JERRY_LOG_PATH)

# main home page
@app.route("/")
def home():
    return fk.render_template("jerry_gui.html")

# beter to have events page to autoupdate homne
@app.route("/events")
def get_events():
    events = []

    if os.path.exists(JERRY_LOG_PATH):
        with open(JERRY_LOG_PATH, "r") as file:
            for line in file:
                try:
                    events.append(json.loads(line))
                except:
                    pass
    else:
        print("Can't find log file")

    return fk.jsonify(events)

app.run(port=5000)