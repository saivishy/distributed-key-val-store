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


app =  Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.environ.get('DATABASE_FILENAME')}"

db = SQLAlchemy(app)


## creating a module to generate message based on request type 
def makeMessage(request_type:str, key = 0, value = 0):
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
            
            print('Sending HeartBeat...')
            msg = makeMessage("APPEND_RPC")
            for node in range(1,4):
                # to differentiate between sender and target nodes
                if f"Node{node}" != node_name: 
                    skt.sendto(msg, (f"Node{node}", 5555))
                    print(f"HEARTBEAT TO Node{node} SENT!")
            print(f"GONNA SLEEP FOR {hb_interval} secs")
            time.sleep(hb_interval)

def listener(skt):
    print(f'Listening for messages... ')
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
    msg = makeMessage("VOTE_REQUEST")
    for node in range(1, num_of_nodes+1):
        if f"Node{node}" != node_name:
            skt.sendto(msg, (f"Node{node}", 5555))
            print(f"VOTE_REQUEST sent to Node{node} !")
    print("I also voted for myself.")
    os.environ["voted"] = "1"

def voteMessageSend(skt, incoming_RPC_msg):
    # if followers term is less than request term and not voted yet grant vote
    print("Voting Params: Curent Term, IncomingRPC Term , Voted(0/1) :",os.environ.get('current_term'), " ", incoming_RPC_msg["term"]," ", os.environ.get("voted"))
    if (os.environ.get('current_term') < incoming_RPC_msg["term"]) and (os.environ.get("voted") == "0"):
        msg = makeMessage("VOTE_ACK")
        skt.sendto(msg, (incoming_RPC_msg["sender_name"], 5555))
        os.environ["voted"] = "1"
        print("VOTE SENT")

# def requestVoteACK(skt, key=0, value=0):
#     print(f"RequestVoteACK listening ... Will keep listening until majority or until timeout")
#     vote_count=1
#     while True:
#         while ((vote_count<(num_of_nodes/2)) and (os.environ.get("STATE")== "candidate")): 
#             print("Num of Votes =",vote_count)
#             decoded_msg = listener_wrapper(skt, 200)

#             # RPC break condition
#             if (decoded_msg["request"] == "APPEND_RPC"):
#                 os.environ["STATE"] = "follower"
#                 os.environ["LEADER_ID"] = decoded_msg["sender_name"]    
#                 vote_count = -1 
#                 break
            
#             # RPC Voteback condition
#             if (decoded_msg["request"] == "VOTE_ACK"):
#                 # decode vote message if you add negative ACK
#                 print("GOT A VOTE! votecount now ", vote_count+1)
#                 vote_count+=1
#                 continue
            
#             # RPC VOTE_REQUEST condition
#             if (decoded_msg["request"] == "VOTE_REQUEST"):
#                 voteMessageSend(pulse_sending_socket, decoded_msg)
#                 continue
            
#         return vote_count       
# ==============================================

def vote_timeout_function(skt, key=0,val=0):
    # do re-election
    if(os.environ.get("STATE")=="candidate"):
        requestVoteRPC(skt, key, val)
        resetTimerV(skt, key,val, 15) # HARD CODED REELECTION TIME FIX LATER
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
    if(os.environ.get("STATE")=="follower"):
        requestVoteRPC(skt,key,val)
        startTimerV()
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
    print("converting to follower on controller request")
    os.environ["STATE"] = "follower"
    print("my current state is : ", os.environ["STATE"])

def send_leader_info(skt):
    msg = makeMessage("LEADER_INFO","LEADER",os.environ.get("LEADER_ID"))
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

def intant_timeout():
	tE.cancel()
	tV.cancel()
	hb_timeout_function(pulse_sending_socket)

def initiate_node_shutdown():
    os.environ["SHUTDOWN_FLAG"] = "1"
    sys.exit()

def normalRecv(skt): # Common Recv
    
    vote_count = 0
    createTimerE(skt, key=0,val=0,hb_timeout=10)
    createTimerV(skt, key=0,val=0,vote_timeout=15)
    startTimerE()
    
    while True:
        decoded_msg = listener(skt)
        print("GOT A message here m8!",decoded_msg)
        
        if (decoded_msg["request"]== "APPEND_RPC") and (os.environ.get("STATE")=="follower"): 
            print("HB RECV---")
            resetTimerE(pulse_sending_socket, 0, 0, 7)
        
        if (decoded_msg["request"] == "VOTE_REQUEST"):
            print("RPC RECV---")
            voteMessageSend(pulse_sending_socket, decoded_msg)
        
        if (decoded_msg["request"]== "APPEND_RPC") and (os.environ.get("STATE")=="candidate"):
            print("HB RECV --- CHANGE BACK TO FOLLOWER ---")
            
            resetTimerE(pulse_sending_socket, 0, 0, 7)
            tV.cancel()
            createTimerV(skt, key=0,val=0,vote_timeout=7)
            
            os.environ["STATE"] = "follower"
            os.environ["LEADER_ID"] = decoded_msg["sender_name"]    
            vote_count = 0
            os.environ["voted"] = "0"
        
        if (decoded_msg["request"]== "VOTE_ACK") and (os.environ.get("STATE")=="candidate"):
            print("VOTE RECV ---")
            vote_count+=1

            print("VOTECOUT = "," VOTES NEEDED IS ",)
            # if majority
            if (vote_count>=((num_of_nodes-1)//2)): # n-1 /2  because the node always votes for itself
                print("NEW LEADER =============")
                tV.cancel() # cancel reelection
                os.environ["STATE"] = "leader"
                os.environ["voted"] = "1"

                os.environ["LEADER_ID"] = os.environ.get("NODEID")
        
        ## controller message processing
        if decoded_msg["request"] == "CONVERT_FOLLOWER" and decoded_msg["sender_name"] == "Controller":
            convert_to_follower()
	    
        if decoded_msg["request"] == "TIMEOUT" and decoded_msg["sender_name"] == "Controller":
            intant_timeout()

        if decoded_msg["request"] == "SHUTDOWN" and decoded_msg["sender_name"] == "Controller":
            initiate_node_shutdown()

        if decoded_msg["request"] == "LEADER_INFO" and decoded_msg["sender_name"] == "Controller":
            send_leader_info(pulse_sending_socket)
        
       

        

        

        # while os.environ.get("STATE")== "follower":
        #     print("I am a follower")
        #     try:
        #         # print("inside HBR follower loop after try")
        #         decoded_msg = listener_wrapper(skt, 5)
        #         print("GOT A message here m8!",decoded_msg)
                
        #         # HeartbeatRecv Condition
        #         if (decoded_msg["request"] == "APPEND_RPC"):
        #             print("RECIVED APPEND_RPC")    
        #             os.environ["LEADER_ID"] = decoded_msg["sender_name"]   
        #             print("Who is the leader?", os.environ.get("LEADER_ID"))

        #         # RPC VOTE_REQUEST condition
        #         if (decoded_msg["request"] == "VOTE_REQUEST"):
        #             print("Got an voteRPC from ", decoded_msg["sender_name"])    
        #             voteMessageSend(pulse_sending_socket, decoded_msg)
        #             break
            
        #     except timeout_decorator.TimeoutError:
        #         print("ELECTION TIMEOUT!!!!!")
        #         requestVoteRPC(skt) # Changes state to candidate and sends out RPC
        #         break

        # while os.environ.get("STATE")== "candidate":
        #     print("In candidate state")

        #     # mirror the time argument for receivevite_ACK
        #     try:
        #         print("Waiting for the votes to come in ...")

        #         requestVoteACK_wrapper(skt, 30)
        #     except timeout_decorator.TimeoutError:
        #         print("VOTE WAITING TIMEOUT")
        #         break
            # store decoded_msg to logs
        

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

    node_name = os.environ.get('NODEID')
    print(node_name)

    num_of_nodes = 3
    global pulse_sending_socket
    global pulse_listening_socket
    pulse_sending_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_sending_socket.bind((node_name, 5005))

    pulse_listening_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_listening_socket.bind((node_name, 5555))
    
    # #Starting thread 1
    # change signature heartbeatSend
    send_thread = threading.Thread(target=heartBeatSend, args=[pulse_sending_socket, 20])
    send_thread.start() 

    #Starting thread 2
    # change signature heartbeatRecv
    receive_thread = threading.Thread(target=normalRecv, args= [pulse_listening_socket])
    receive_thread.start()



    # send_thread.join()
    # receive_thread.join()
    # # lambda runs app.run within a function. Function passed to thread
    # threading.Thread(target=lambda: app.run(debug=False, host ='0.0.0.0', port=5000, use_reloader=False)).start()

