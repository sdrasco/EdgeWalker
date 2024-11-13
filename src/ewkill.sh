# simple script to shutdown the holdings dashboard

# Port number, change this if your Dash server runs on a different port
PORT=8050

# Find the process ID (PID) using lsof
PID=$(lsof -ti :$PORT)

if [ -z "$PID" ]; then
  echo "No process is running on port $PORT."
else
  echo "Killing process with PID $PID on port $PORT..."
  kill -9 $PID
  echo "Process $PID has been terminated."
fi
