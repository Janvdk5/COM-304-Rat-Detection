import flask as fk
import sys, os
import json

app = fk.Flask(__name__)

CURRENT_DIR = (os.path.dirname(os.getcwd()))
JERRY_LOG_PATH = os.path.join(CURRENT_DIR, "src/logs/jerry_log.jsonl")
SIGNAL_LOG_PATH = os.path.join(CURRENT_DIR, "src/logs/signal_log.jsonl")   # bf


# main home page
@app.route("/")
def home():
    return fk.render_template("jerry_gui.html")

# beter to have events page to autoupdate homne
@app.route("/events")
def get_events():
    return _read_jsonl(JERRY_LOG_PATH)


@app.route("/signal")
def get_signal():
    return _read_jsonl(SIGNAL_LOG_PATH, tail=100)

def _read_jsonl(path, tail=None):
    events = []

    if os.path.exists(path):
        with open(path, "r") as file:
            for line in file:
                try:
                    events.append(json.loads(line))
                except:
                    pass
    else:
        print("Can't find log file")

    if tail:
        events = events[-tail:]
    return fk.jsonify(events)

app.run(port=5000, debug=False)