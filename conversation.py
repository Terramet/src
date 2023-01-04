import pyaudio
from ibm_watson import SpeechToTextV1
from ibm_watson.websocket import RecognizeCallback, AudioSource
from threading import Thread, Event
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

from ibm_watson import TextToSpeechV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

import rospy
import configparser
import json

from std_msgs.msg import String
from cob_sound.msg import *
import actionlib
import os
import hashlib

import argparse
import datetime

try:
    from Queue import Queue, Full
except ImportError:
    from queue import Queue, Full

# define callback for pyaudio to store the recording in queue
def pyaudio_callback(in_data, frame_count, time_info, status):
    try:
        q.put(in_data)
    except Full:
        pass # discard
    return (None, pyaudio.paContinue)
    
###############################################
#### Initalize queue to store the recordings ##
###############################################
CHUNK = 1024
# Note: It will discard if the websocket client can't consumme fast enough
# So, increase the max size as per your choice
BUF_MAX_SIZE = CHUNK * 10
# Buffer to store audio
q = Queue(maxsize=int(round(BUF_MAX_SIZE / CHUNK)))

# Create an instance of AudioSource
audio_source = AudioSource(q, True, True)

###############################################
#### Prepare the for recording using Pyaudio ##
###############################################

# Variables for recording the speech
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
# instantiate pyaudio
audio = pyaudio.PyAudio()

# open stream using callback
stream = audio.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
    stream_callback=pyaudio_callback,
    start=False
)

###############################################
#### Prepare Speech to Text Service ########
###############################################

# define callback for the speech to text service
class MyRecognizeCallback(RecognizeCallback):
    def __init__(self, args):
        RecognizeCallback.__init__(self)
        self.prev_val = ''
        self.assistant = Assistant()
        self.args = args
        if (self.args.tts != None):
            self.pub = rospy.Publisher('/watson_say', String, queue_size=10)
        else:
            self.speech = Say()


    def on_transcription(self, transcript):
        print(transcript)

    def on_connected(self):
        print('Connection was successful')

    def on_error(self, error):
        print('Error received: {}'.format(error))

    def on_inactivity_timeout(self, error):
        print('Inactivity timeout: {}'.format(error))

    def on_listening(self):
        print('Service is listening')

    def on_hypothesis(self, hypothesis):
        if self.prev_val != hypothesis:
            if (self.args.tts != None):
                stream.stop_stream()
                self.pub.publish(self.assistant.get_response(hypothesis))
                now = datetime.datetime.now()
                target = now + datetime.timedelta(0,self.args.pause)
                while (now <= target):
                    now = datetime.datetime.now()
                stream.start_stream()
            else:
                self.speech.say(self.assistant.get_response(hypothesis))
            self.prev_val = hypothesis
        print(hypothesis)

    def on_data(self, data):
        print(data)

    def on_close(self):
        print("Connection closed")
class Assistant:
    def __init__(self):
        self.config = WatsonConfig()
        self.config = self.config.getConfig()

        self.authenticator = IAMAuthenticator(self.config['Assistant']['apikey'])
        self.assist = AssistantV2(version='2021-06-14', authenticator=self.authenticator)
        self.assist.set_service_url(self.config['Assistant']['service_url'])

        self.assistant_id = self.config['Assistant']['assistant_id']
        print(self.assistant_id)

        self.session = self.assist.create_session(
            assistant_id=self.assistant_id
        ).get_result()

        self.session_id = self.session['session_id']
        self.context = None

    def get_response(self, text):
        response = self.assist.message(
            assistant_id=self.assistant_id,
            session_id=self.session_id,
            input={
                'message_type': 'text',
                'text': text,
                'return_context': True
            }
        ).get_result()

        print(json.dumps(response, indent=2))

        return response['output']['generic'][0]['text']
        
class Say:
    def __init__(self):
        self.config = WatsonConfig()
        self.config = self.config.getConfig()

        self.authenticator = IAMAuthenticator(self.config['TextToSpeech']['apikey'])
        self.text_to_speech = TextToSpeechV1(authenticator=self.authenticator)

        self.text_to_speech.set_service_url(self.config['TextToSpeech']['service_url'])

        self.aDir = "audio/"
        self.audio_dir = os.path.dirname(os.path.realpath(__file__)) + '/' + self.aDir
        self.voice='en-GB_CharlotteV3Voice' #'en-US_AllisonV3Voice'
        print('Say service setup.')

    def play(self, text):
        stream.stop_stream()
        rospy.loginfo('Sending play action for: ' + str(text))
        client = actionlib.SimpleActionClient('/sound/play', PlayAction)
        client.wait_for_server()

        # Creates a goal to send to the action server.
        goal = PlayGoal()
        goal.filename = text

        # Sends the goal to the action server.
        client.send_goal(goal)

        # Waits for the server to finish performing the action.
        client.wait_for_result()

        stream.start_stream()
        # Prints out the result of executing the action
        return client.get_result()

    def say(self, data):
        to_say = '<break time="1s"/>' + data
        print(to_say)
        hash_obj = hashlib.sha256((to_say + self.voice).encode('utf-8'))
        hash_code = hash_obj.hexdigest()
        fn = hash_code + '.wav'
        if not (os.path.isfile(self.audio_dir + fn)):
            audio_file = open(self.audio_dir + fn, 'wb+')
            try:
                audio_file.write(
                    self.text_to_speech.synthesize(
                        to_say,
                        voice=self.voice,
                        accept='audio/wav'
                        ).get_result().content)
            finally:
                audio_file.close()

        self.play(self.audio_dir + fn)

class WatsonConfig:
    def __init__(self):
        # load our config file
        self.config = configparser.ConfigParser()
        self.config.read('./config.ini')

    def getConfig(self):
        return self.config

class Conversation():
    def __init__(self):
        self.config = WatsonConfig()
        self.config = self.config.getConfig()
        # initialize speech to text service
        self.authenticator = IAMAuthenticator(self.config['SpeechToText']['apikey'])
        self.speech_to_text = SpeechToTextV1(authenticator=self.authenticator)

        self.speech_to_text.set_service_url(self.config['SpeechToText']['service_url'])

    def str2bool(self, v):
        return v.lower() in ("yes", "true", "t", "1")

# this function will initiate the recognize service and pass in the AudioSource
    def recognize_using_weboscket(self, *args):
        mycallback = MyRecognizeCallback(args[0])
        #Model connection configs
        base_model                = self.config["SpeechToText"]["base_model_name"]
        #language_customization_id = self.config["SpeechToText"]["language_model_id"]
        #acoustic_customization_id = self.config["SpeechToText"]["acoustic_model_id"]
        #grammar_name              = self.config["SpeechToText"]["grammar_name"]

        #Float parameter configs
        end_of_phrase_silence_time   = float(self.config["SpeechToText"]["end_of_phrase_silence_time"])
        inactivity_timeout           =   int(self.config["SpeechToText"]["inactivity_timeout"])
        speech_detector_sensitivity  = float(self.config["SpeechToText"]["speech_detector_sensitivity"])
        background_audio_suppression = float(self.config["SpeechToText"]["background_audio_suppression"])
        character_insertion_bias     = float(self.config["SpeechToText"]["character_insertion_bias"])

        #Boolean configs
        interim_results              = self.str2bool(self.config["SpeechToText"]["interim_results"])
        audio_metrics                = self.str2bool(self.config["SpeechToText"]["audio_metrics"])
        smart_formatting             = self.str2bool(self.config["SpeechToText"]["smart_formatting"])
        low_latency                  = self.str2bool(self.config["SpeechToText"]["low_latency"])
        skip_zero_len_words          = self.str2bool(self.config["SpeechToText"]["skip_zero_len_words"])
        custom_transaction_id        = self.str2bool(self.config["SpeechToText"]["custom_transaction_id"])

        self.speech_to_text.recognize_using_websocket(audio=audio_source,
                                                content_type='audio/l16; rate=44100',
                                                recognize_callback=mycallback,
                                                model=base_model,
                                                end_of_phrase_silence_time=end_of_phrase_silence_time,
                                                inactivity_timeout=inactivity_timeout,
                                                speech_detector_sensitivity=speech_detector_sensitivity,
                                                background_audio_suppression=background_audio_suppression,
                                                smart_formatting=smart_formatting,
                                                low_latency=low_latency,
                                                skip_zero_len_words=skip_zero_len_words,
                                                #At most one of interim_results and audio_metrics can be True
                                                interim_results=interim_results,
                                                audio_metrics=audio_metrics)

def main(args):
    #########################################################################
    #### Start the recording and start service to recognize the stream ######
    #########################################################################

    print("Enter CTRL+C to end recording...")
    stream.start_stream()

    convo = Conversation()

    try:
        node_thread = Thread(target=rospy.init_node('conversation', disable_signals=True))
        node_thread.start()
        recognize_thread = Thread(target=convo.recognize_using_weboscket, args=([args]))
        recognize_thread.start()

        while True:
            pass
    except KeyboardInterrupt:
        # stop recording
        stream.stop_stream()
        stream.close()
        audio.terminate()
        audio_source.completed_recording()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Uses Watson Assistant to build a HRI system with conversation.')
    
    parser.add_argument('--tts', help='If your robot has a built in speech synthesiser, provide the topic that is needed to publish to it. example: python conversation.py --tts /speech/say')
    parser.add_argument('--pause', type=int, help='The timeout before the robot starts listening for the next part of the conversation. This is only required if you have your own speech sythesiser')
    args = parser.parse_args()
    if(args.tts and args.pause is None):
        parser.error('Argument --tts requires --pause')
    main(args)