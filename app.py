from glob import glob
from tabnanny import check
from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import time
import os
import requests
import json
import socket
import traceback
import threading
from threading import *
from sqlalchemy import false
import sys
from random import *

app =  Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.environ.get('DATABASE_FILENAME')}"

db = SQLAlchemy(app)

def readJSONInfo(filename):
    f = open(filename, "r")
    json_obj = json.load(f)
    return json_obj

def getNodeInfo():
    global hb_timeout
    global hb_send_interval
    sav_dict = {
        "leader" : os.environ.get('LEADER_ID'),
        "currentTerm" : os.environ.get('current_term'),
        "votedFor": os.environ.get('voted_for'),
        "timeoutInterval": hb_timeout,
        "heartBeatInterval": hb_send_interval  
    }

    json_obj = json.dumps(sav_dict, indent=4)

    return json_obj

def saveObj(obj,filename):
    with open(f"{filename}_info.json", "w") as f:
        f.write(obj)

def writeJSONInfo(obj, filename):
    json_obj = json.dumps(obj, indent=4)
    saveObj(json_obj, filename)
    
## creating a module to generate message based on request type 
def makeMessage(request_type:str, key, value):
    print('Making message...')    
    pulse_msg = {
        "sender_name" : os.environ.get('NODEID'), 
        "request" : request_type,
        "term": os.environ.get('current_term'),
        "key": key,
        "value": value
        }
    pulse_msg_bytes = json.dumps(pulse_msg).encode()
    return pulse_msg_bytes

def heartBeatSend(skt, hb_interval = 10):
    while True:
        if (os.environ["SHUTDOWN_FLAG"])=="1":
            sys.exit()
        while (os.environ.get("STATE")=="leader"):
            if (os.environ["SHUTDOWN_FLAG"])=="1":
                sys.exit()
            
            # print('Sending HeartBeat...')
            msg = makeMessage("APPEND_RPC", "", "")
            active_node_count = num_of_nodes
            for node in range(1,num_of_nodes+1):
                # to differentiate between sender and target nodes
                if f"Node{node}" != node_name: 
                    try:
                        skt.sendto(msg, (f"Node{node}", 5555))
                        print(f"HEARTBEAT TO Node{node} SENT!")
                    except:
                        print(f"Node{node} not reachable")
                        active_node_count =  active_node_count -1

            os.environ["ACTIVE_NODES"] = str(active_node_count)
            print(active_node_count," nodes are active! ")
            print(f"GONNA SLEEP FOR {hb_interval} secs")

            node_info = getNodeInfo()
            saveObj(node_info, os.environ.get("NODEID"))
            
            time.sleep(hb_interval)

def listener(skt):
    # print(f'Listening for messages... ')
    while True:
        try:
            recv_msg, addr = skt.recvfrom(1024)
        except:
            print(f"Error: Failed while fetching from socket - {traceback.print_exc()}")
        
        decoded_msg = json.loads(recv_msg.decode('utf-8'))
        return decoded_msg
    
def requestVoteRPC(skt, key=0, value=0):
    os.environ["STATE"] = "candidate"
    os.environ["current_term"] = str(int(os.environ.get("current_term"))+1)
    msg = makeMessage("VOTE_REQUEST", "","")
    active_node_count = num_of_nodes
    for node in range(1, num_of_nodes+1):
        if f"Node{node}" != node_name:
            try:
                skt.sendto(msg, (f"Node{node}", 5555))
                print(f"VOTE_REQUEST sent to Node{node} !")
            except:
                print(f"Node{node} not reachable")
                active_node_count = active_node_count -1
    os.environ["ACTIVE_NODES"] = str(active_node_count)
    # print("I also voted for myself.")
    os.environ["voted"] = "1"
    os.environ["voted_for"] = os.environ.get("NODEID")

def voteMessageSend(skt, incoming_RPC_msg):
    # if followers term is less than request term and not voted yet grant vote
    print("Voting Params: Curent Term, IncomingRPC Term , Voted(0/1) :",os.environ.get('current_term'), " ", incoming_RPC_msg["term"]," ", os.environ.get("voted"))
    if (os.environ.get('current_term') < incoming_RPC_msg["term"]): # and (os.environ.get("voted") == "0")
        
        if(os.environ.get('STATE')=="candidate"):
            tV.cancel()
            
        # Convert to follower
        os.environ["STATE"] = "follower"
        
        

        msg = makeMessage("VOTE_ACK", "", "")
        skt.sendto(msg, (incoming_RPC_msg["sender_name"], 5555))
        os.environ["voted"] = "1"
        os.environ["voted_for"] = incoming_RPC_msg["sender_name"]
        print("VOTE SENT")

def vote_timeout_function(skt, key=0,val=0):
    # do re-election
    # print("REELECTION STARTED")
    os.environ["voted"] = "0"

    if(os.environ.get("STATE")=="candidate"):
        requestVoteRPC(skt, key, val)
        resetTimerV(skt, key,val, hb_timeout) # HARD CODED REELECTION TIME FIX LATER
# Timer V Class Stand in
    

def createTimerV(skt, key=0,val=0,vote_timeout=7):
    global tV
    tV = Timer(vote_timeout, vote_timeout_function, [skt, key, val])

def startTimerV():
    tV.start()

def resetTimerV(skt, key=0,val=0,vote_timeout=7):
    tV.cancel()
    createTimerV(skt, key, val, vote_timeout)
    tV.start()

# =========================

def hb_timeout_function(skt, key=0,val=0):
    # print("HB TIMEOUT! Will check if I am a follower ...")
    if(os.environ.get("STATE")=="follower"):
        print("I am a follower ... Gonna start my candidacy !")
        requestVoteRPC(skt,key,val)
        resetTimerV(skt,key,val,hb_timeout)
# Timer E Class Stand in

def createTimerE(skt, key=0,val=0, hb_timeout=7):
    global tE
    tE = Timer(hb_timeout, hb_timeout_function, [skt, key,val])

def startTimerE():
    tE.start()

def resetTimerE(skt, key=0,val=0, hb_timeout=7):
    tE.cancel()
    createTimerE(skt, key, val, hb_timeout)
    tE.start()

# Controller request function
def convert_to_follower():
    # print("converting to follower on controller request")
    os.environ["STATE"] = "follower"
    # print("my current state is : ", os.environ["STATE"])

def send_leader_info(skt):
    msg = makeMessage("LEADER_INFO","LEADER",os.environ.get("LEADER_ID")    )
    target = "Controller"
    port = 5555
    try:
        # Encoding and sending the message
        skt.sendto(msg, (target, port))
        # print("leader info sent to controller")
    except:
	    # socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")
        pass

def send_all_info(skt):
    val_load = {
        "leader" : os.environ.get('LEADER_ID'), 
        "current_term" : os.environ.get('current_term'),
        "voted_for": os.environ.get('voted_for')
        }
    msg = makeMessage("ALL_INFO","ENV_VAR",json.dumps(val_load))
    target = "Controller"
    port = 5555
    try:
        # Encoding and sending the message
        skt.sendto(msg, (target, port))
        print("leader info sent to controller")
    except:
	    # socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")
        pass

def store_log(key, value):
    # Add to persistant to log 
    log_file_name = os.environ.get("NODEID") + "_logs.json"
    log_entry = {
        "term" : int(os.environ.get("current_term")),
        "key" :value["key"],
        "value": value["value"]
    }
    
    try:
        logs = readJSONInfo(log_file_name)
    except:
        logs = {}
0
1
    logs[key] = log_entry
    writeJSONInfo(logs, log_file_name)
    os.environ["next_log_index"] = str(int(os.environ.get("next_log_index"))+1)
    print("log stored to node")

def retrive_log(key):
    # retrive log info 
    log_file_name = os.environ.get("NODEID") + "_logs.json"
    logs = readJSONInfo(log_file_name)
    print("log retrived")
    return logs 

def instant_timeout():
	tE.cancel()
	tV.cancel()
	hb_timeout_function(pulse_sending_socket)

def initiate_node_shutdown():

    os.environ["SHUTDOWN_FLAG"] = "1"
    sys.exit()

def normalRecv(skt): # Common Recv
    global hb_timeout
    hb_timeout = randint (12,20)
    
    # hb_timeout = round(random.uniform(0.30, 0.50), 2)
    # hb_timeout = 6

    print("Heartbeat timeout generated randomly = ", hb_timeout)

    vote_count = 0
    createTimerE(skt, 0, 0, hb_timeout)
    createTimerV(skt, key=0,val=0,vote_timeout=hb_timeout)
    startTimerE()
    
    while True:
        global num_of_nodes 
        decoded_msg = listener(skt)
        print("GOT A message here m8!",decoded_msg)
         
        if (decoded_msg["request"]== "APPEND_RPC") and (os.environ.get("STATE")=="follower"): 
            print("HB RECV---")
            os.environ["LEADER_ID"] = decoded_msg["sender_name"]
            resetTimerE(pulse_sending_socket, 0, 0, hb_timeout)
            os.environ["current_term"] = decoded_msg["term"]
            node_info = getNodeInfo()
            saveObj(node_info, os.environ.get("NODEID"))
        
        if (decoded_msg["request"] == "VOTE_REQUEST"):
            print("VOTE RPC RECV---")
            voteMessageSend(pulse_sending_socket, decoded_msg)
        
        if (decoded_msg["request"]== "APPEND_RPC") and (os.environ.get("STATE")=="candidate"):
            print("HB RECV --- CHANGE BACK TO FOLLOWER ---")
            
            resetTimerE(pulse_sending_socket, 0, 0, hb_timeout)
            tV.cancel()
            createTimerV(skt, key=0,val=0,vote_timeout=10)
            resetTimerE(pulse_sending_socket, 0, 0, hb_timeout)
            os.environ["STATE"] = "follower"
            os.environ["LEADER_ID"] = decoded_msg["sender_name"]
            os.environ["current_term"] = decoded_msg["term"]
            vote_count = 0
            os.environ["voted"] = "0"
        
        if (decoded_msg["request"]== "VOTE_ACK") and (os.environ.get("STATE")=="candidate"):
            vote_count+=1
            num_active_nodes = int(os.environ.get("ACTIVE_NODES"))
            print("VOTE RECV --- CURRENT VOTE COUNT:", vote_count + 1 , " ToT VOTES REQUIRED :", ((num_active_nodes-1)//2) + 1)
            
            # if majority
            if (vote_count>=((num_active_nodes-1)//2)): # n-1 /2  because the node always votes for itself
                print("NEW LEADER =============")
                tV.cancel() # cancel reelection
                os.environ["STATE"] = "leader"
                os.environ["voted"] = "0"

                os.environ["LEADER_ID"] = os.environ.get("NODEID")
        
        ## controller message processing
        if decoded_msg["request"] == "CONVERT_FOLLOWER" and decoded_msg["sender_name"] == "Controller":
            convert_to_follower()
	    
        if decoded_msg["request"] == "TIMEOUT" and decoded_msg["sender_name"] == "Controller":
            instant_timeout()

        if decoded_msg["request"] == "SHUTDOWN" and decoded_msg["sender_name"] == "Controller":
            tE.cancel()
            tV.cancel()
            initiate_node_shutdown()

        if decoded_msg["request"] == "LEADER_INFO" and decoded_msg["sender_name"] == "Controller":
            send_leader_info(pulse_sending_socket)
        
        if decoded_msg["request"] == "ALL_INFO" and decoded_msg["sender_name"] == "Controller":
            send_all_info(pulse_sending_socket)
        
        if decoded_msg["request"] == "STORE" and decoded_msg["sender_name"] == "Controller" and os.environ.get("STATE")=="leader":
            store_log(int(os.environ.get("next_log_index")), decoded_msg)

        if decoded_msg["request"] == "STORE" and decoded_msg["sender_name"] == "Controller":
            send_leader_info(pulse_sending_socket)

        if decoded_msg["request"] == "RETRIEVE" and decoded_msg["sender_name"] == "Controller" and os.environ.get("STATE")=="leader":
            retrive_log()

        if decoded_msg["request"] == "RETRIEVE" and decoded_msg["sender_name"] == "Controller":
            send_leader_info()

class Person(db.Model):
    id = db.Column(db.Integer, primary_key= True)
    name = db.Column(db.String(200), nullable = False)
    hash = db.Column(db.Integer, nullable = False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return '<Record %r' % self.id

db.create_all()

## index route
@app.route('/', methods=['POST', 'GET'])
def index():
    if request.method == 'POST':
        record_name = request.form['name']
        record_hash = request.form['hash']
        lead = os.environ.get('LEADER')
        if  lead == '1':
            files= {"name": (None,record_name) , "hash": (None,record_hash)}
            url1 = 'http://Node2:5000/'
            log1 = requests.post(url1,  files =files)
            url2 = 'http://Node3:5000/'
            log2 = requests.post(url2, files =files)
        else:
            print('NOT LEADER-------------------')
            print(os.environ.get('LEADER'))
        new_record = Person(name=record_name,hash=record_hash) 
        try:
            db.session.add(new_record)            
            db.session.commit()
            return redirect('/')
        except:
            return 'There was an issue adding the record'
    else:
        records = Person.query.order_by(Person.date_created).all()
        return render_template('index.html', records = records)

@app.route('/delete/<int:id>')
def delete(id):
    record_to_delete = Person.query.get_or_404(id)

    lead = os.environ.get('LEADER')
    if  lead == '1': 
        for node in range(2,4):
            url = f"http://Node{node}:5000/delete/{id}"
            log = requests.get(url)
            print(f"SENT to delete GET to Node{node}")
            print(log)
    else:
        print('NOT LEADER-------------------')
        print(os.environ.get('LEADER'))

    try:
        db.session.delete(record_to_delete)
        db.session.commit()
        return redirect('/')
    except:
        return 'There was an issue deleting that record'

@app.route('/update/<int:id>', methods= ['GET','POST'])
def update(id):
    record = Person.query.get_or_404(id)

    lead = os.environ.get('LEADER')
    if  lead == '1': 
        if request.method == 'POST':
            record.name = request.form['name']
            record_name = request.form['name']
            for node in range(2,4):
                url = f"http://Node{node}:5000//update/{id}"
                get_log = requests.get(url)
                print(f"SENT to update GET to Node{node}")
                print(get_log)
                
                files= {"name": (None,record_name)}
                post_log = requests.post(url,  files =files)
                print(f"SENT to update POST to Node{node}")
                print(post_log)
            
            try:
                db.session.commit()
                return redirect('/')
            except:
                return 'There was an issue updating the record'
        else:
            return render_template('update.html', record = record )
            
            
    else:
        print('NOT LEADER-------------------')
        print(os.environ.get('LEADER'))
    
    
    
        if request.method == 'POST':
            record.name = request.form['name']
            
            try:
                db.session.commit()
                return redirect('/')
            except:
                return 'There was an issue updating the record'
        else:
            return render_template('update.html', record = record )


if __name__ == "__main__":
    global hb_send_interval
    hb_send_interval = 4
    node_name = os.environ.get('NODEID')
    print(node_name)
    global num_of_nodes
    num_of_nodes = 5
    os.environ["ACTIVE_NODES"] = str(num_of_nodes)
    global pulse_sending_socket
    global pulse_listening_socket
    pulse_sending_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_sending_socket.bind((node_name, 5005))

    pulse_listening_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_listening_socket.bind((node_name, 5555))
    
    # #Starting thread 1
    # change signature heartbeatSend
    send_thread = threading.Thread(target=heartBeatSend, args=[pulse_sending_socket, hb_send_interval])
    send_thread.start() 

    #Starting thread 2
    # change signature heartbeatRecv
    receive_thread = threading.Thread(target=normalRecv, args= [pulse_listening_socket])
    receive_thread.start()



    # send_thread.join()
    # receive_thread.join()
    # # lambda runs app.run within a function. Function passed to thread
    # threading.Thread(target=lambda: app.run(debug=False, host ='0.0.0.0', port=5000, use_reloader=False)).start()

