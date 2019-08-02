from flask import Flask, jsonify, session
from flask_cors import CORS, cross_origin
import json
import random

app = Flask(__name__)
app.secret_key = "super_secret_key"
CORS(app)

steps = [ 'Copying data', 'Reading dycoms', 'Classificating images', 'Creating images for segmentation', 'Creating mask', 'Applying mask', 'Creating clips', 'Finished' ]

@app.route('/health/', methods=['GET'])
def hello():
    return jsonify({"data": 'API works'})

@app.route('/start', methods=['POST'])
def start_process():
     session['stage_number'] = 0
     session['total'] = random.randint(25, 99)
     return jsonify({ 'success': 'true'})

@app.route('/check', methods=['GET'])
def check_execution():
     stage_number = session['stage_number']
     total = session['total']

     done = stage_number == len(steps) - 1
     percent = ( 100 / len(steps) ) * stage_number
     rnd = random.randint(0, 10)
     percent = 100 if done else percent + rnd
     processed = round(total * ( percent / 100 ))

     session['stage_number'] = stage_number + 1
     

     return jsonify({ 'total': total, 'stageName': steps[stage_number], 'percent': percent, 'processedCount': processed, 'done': done })