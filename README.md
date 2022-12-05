## Conversation engine for Care-o-bot 4

# Requires atleast python 3.7.15 for pyaudio to work!!

If you are using the Care-o-bot you can install pyenv and swap to python 3.7.15 before creating a venv for the project.

To run create a package with `catkin_create_pkg watson_integration rospy`.

CD into you package and delete the src folder. Using python 3.7.15 create a new venv with `python -m venv src`.

CD into the new folder and `git clone` this repository.

Activate your enviroment with `source bin/activate`

Run `pip install -r requirements.txt`.

Rename `config_example.ini` to `config.ini`. Put in your apikeys and service urls for IBM Watson.

Run the program `python conversation.py` if your robot has its own speech sythesiser then you can use it by doing `python conversation.py --tts <topic_name> --pause <time_in_seconds>`