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
import timeout_decorator

app =  Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.environ.get('DATABASE_FILENAME')}"

db = SQLAlchemy(app)

## creating a module to generate message based on request type 
def makeMessage(request_type:str, key = 0, value = 0):
    print('inside MPM ======MAKING MESSAGE=========')    
    pulse_msg = {
        "sender_name" : os.environ.get('NODEID'), 
        "request" : request_type,
        "term": os.environ.get('current_term'),
        "key": key,
        "value": value
        }
    pulse_msg_bytes = json.dumps(pulse_msg).encode()
    return pulse_msg_bytes

# module to send heartbeats if the node is a leader node
# utilizes makeMessage module to generate heartbeat specific message
def heartBeatSend(skt, hb_interval = 10):
    print('inside HBS =======SENDING MESSAGE========')
    #print(os.environ.get("STATE"))
    #print(type(os.environ.get("STATE")))
    while (os.environ.get("STATE")=="leader"):
        msg = makeMessage("appendRPC")
        for node in range(1,4):
            # to differentiate between sender and target nodes
            if f"node{node}" != node_name: 
                skt.sendto(msg, (f"node{node}", 5006))
                print(f"HEARTBEAT TO node{node} SENT!")
        print(f"GONNA SLEEP FOR {hb_interval} secs")
        time.sleep(hb_interval)


# listener wrapper to listen for the heartbeat from leader
def listener_wrapper(skt, election_timeout_interval=5):
    @timeout_decorator.timeout(election_timeout_interval, use_signals=False)
    def listener(skt):
        print('inside listener ======LISTENING FOR MESSAGES=======')
        while True:
            try:
                recv_msg, addr = skt.recvfrom(1024) # may need to change byte size - find out
            except:
                print(f"Error: Failed while fetching from socket - {traceback.print_exc()}")
            
            decoded_msg = json.loads(recv_msg.decode('utf-8'))  ## shouldn't this be in the try block
            return decoded_msg
    
    return listener(skt)

# 
def requestVoteRPC(skt, key=0, value=0):
    print("Before Voting State: ", os.environ.get("STATE"))
    os.environ["STATE"] = "candidate"
    os.environ["current_term"] = str(int(os.environ.get("current_term"))+1)
    print(os.environ.get("current_term"))
    print(os.environ.get("STATE"))
    msg = makeMessage("requestVoteRPC")
    for node in range(1, num_of_nodes+1):
        if f"node{node}" != node_name:
            skt.sendto(msg, (f"node{node}", 5006))
            print(f"requestVoteRPC sent to node{node} !")

def voteMessageSend(skt, incoming_RPC_msg):
    # if followers term is less than request term and not voted yet grant vote
    print("INSIDE voteMESSAGE SEND")
    print("INSIDE this node cuureent term, incoming rpce term and voted :",os.environ.get('current_term'),incoming_RPC_msg["term"],os.environ.get("voted"))
    if (os.environ.get('current_term') < incoming_RPC_msg["term"]) and (os.environ.get("voted") == "0"):
        msg = makeMessage("voteMessage")
        skt.sendto(msg, (incoming_RPC_msg["sender_name"], 5006))
        os.environ["voted"] = "1"
        print("VOTE SENT")


## change timeout_interval
def requestVoteACK_wrapper(skt, timeout_interval=30):
    @timeout_decorator.timeout(timeout_interval, use_signals=False)
    def requestVoteACK(skt, key:int, value:int):
        print("INSIDE RVRPC")
        vote_count=1
        while (vote_count<(num_of_nodes/2)): 
            print("INSIDE while RVPC numbotes=",vote_count)
            try:
                decoded_msg = listener_wrapper(skt, 200)

                # RPC break condition
                if (decoded_msg["request"] == "appendRPC"):
                    os.environ["STATE"] = "follower"
                    os.environ["LEADER_ID"] = decoded_msg["sender_name"]    
                    vote_count = -1 
                    break
                
                # RPC Voteback condition
                if (decoded_msg["request"] == "voteMessage"):
                    # decode vote message if you add negative ACK
                    print("GOT A VOTE! votecount now ", vote_count+1)
                    vote_count+=1
                    continue
                
                # RPC requestVoteRPC condition
                if (decoded_msg["request"] == "requestVoteRPC"):
                    voteMessageSend(pulse_sending_socket, decoded_msg)
                    continue
                
            except timeout_decorator.TimeoutError:
                    print("timed out listening for a single vote in requestVoteACK")
                    break
        return vote_count   
    return requestVoteACK(skt, timeout_interval)             
   
def heartBeatRecv(skt):
    print('inside HBR ======RECV MESSAGE=========')
    while True:
        while os.environ.get("STATE")== "follower":
            print("inside HBR follower loop before try")
            try:
                print("inside HBR follower loop after try")
                decoded_msg = listener_wrapper(skt, 3)
                print("GOT A message here m8!",decoded_msg)

                if (decoded_msg["request"] == "appendRPC"):
                    print("RECIVED APPENDRPC")    
                    os.environ["LEADER_ID"] = decoded_msg["sender_name"]   
                    print(os.environ.get("LEADER_ID"))

                # RPC requestVoteRPC condition
                if (decoded_msg["request"] == "requestVoteRPC"):
                    print("RECIVED requestVOTERPC")    
                    voteMessageSend(pulse_sending_socket, decoded_msg)
                    break
            
            except timeout_decorator.TimeoutError:
                print("ELECTION TIMEOUT!!!!!")
                requestVoteRPC(skt) # Changes state to candidate and sends out RPC
                break

        while os.environ.get("STATUS")== "candidate":
            print("inside HBR candidate loop before try")

            # mirror the time argument for receivevite_ACK
            try:
                print("inside HBR candidate loop inside try")

                requestVoteACK_wrapper(skt, 30)
            except timeout_decorator.TimeoutError:
                print("VOTE WAITING TIMEOUT")
                break
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
            url1 = 'http://node2:5000/'
            log1 = requests.post(url1,  files =files)
            url2 = 'http://node3:5000/'
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
            url = f"http://node{node}:5000/delete/{id}"
            log = requests.get(url)
            print(f"SENT to delete GET to node{node}")
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
                url = f"http://node{node}:5000//update/{id}"
                get_log = requests.get(url)
                print(f"SENT to update GET to node{node}")
                print(get_log)
                
                files= {"name": (None,record_name)}
                post_log = requests.post(url,  files =files)
                print(f"SENT to update POST to node{node}")
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

    pulse_sending_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_sending_socket.bind((node_name, 5005))

    pulse_listening_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    pulse_listening_socket.bind((node_name, 5006))
    
    # #Starting thread 1
    # change signature heartbeatSend
    threading.Thread(target=heartBeatSend, args=[pulse_sending_socket, 100]).start() 

    #Starting thread 2
    # change signature heartbeatRecv
    threading.Thread(target=heartBeatRecv, args= [pulse_listening_socket]).start()

    # lambda runs app.run within a function. Function passed to thread
    # threading.Thread(target=lambda: app.run(debug=False, host ='0.0.0.0', port=5000, use_reloader=False)).start()

