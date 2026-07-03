Main GitHub Repo for WhisperLive: 
https://github.com/collabora/WhisperLive

STEPS:
1. Run server
2. Run client

FOR run_server.py:
py -3.12 run_server.py

FOR run_client.py:
# Audio from file
py -3.12 run_client.py --model <model-name> --files <audio-file-name>
OR
# Audio from microphone
py -3.12 run_client.py --model <model-name>

Choice of models:
- tiny #fastest, lowest accuracy
- base
- small
- medium
- large-v1
- large-v2
- large-v3
- large-v3-turbo OR turbo