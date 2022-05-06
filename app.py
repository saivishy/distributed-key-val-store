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
    f.close()
    return json_obj

def writeJSONInfo(filename, json_obj):
    with open(filename, 'w') as f:
        json.dump(json_obj, f, ensure_ascii=False, indent=4)

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

def makeMessage(request_type:str, key= None, value=None, prevLogIndex=None, prevLogTerm=None, lastLogIndex= None, lastLogTerm = None, success=None, entry=None):
    # print('Making message...')
    ## for controller RETRIEVE request since it needs term to be NULL
    if request_type == "RETRIEVE":
        pulse_msg = {
        "sender_name" : os.environ.get('NODEID'), 
        "request" : request_type,
        "term": None,
        "key": key,
        "value": value
            }
    
    ## for APPEND_RPC request since it needs additional parameters

    ## make note to rename APPEND_RPC to APPEND_ENTRY_RPC to be consistent with the handout instructions
    elif request_type =="APPEND_RPC":
        pulse_msg = {
            "sender_name" : os.environ.get('NODEID'), 
            "request" : request_type,
            "term": os.environ.get('current_term'),
            "key": key,
            "value": value,
            "prevLogIndex": prevLogIndex,
            "prevLogTerm": prevLogTerm,
            "commitIndex": int(os.environ.get("commit_index")),
            "success": success,
            "entry": entry
            }

    ## for APPEND_REPLY because of same reasons as APPEND_RPC
    elif request_type == "APPEND_REPLY":
        pulse_msg = {
            "sender_name" : os.environ.get('NODEID'), 
            "request" : request_type,
            "term": os.environ.get('current_term'),
            "key": key,
            "value": value,
            "prevLogIndex": prevLogIndex,
            "prevLogTerm": prevLogTerm,
            "commitIndex": int(os.environ.get("commit_index")),
            "success": success,
            "entry": entry
            }

    elif request_type == "VOTE_REQUEST":
        pulse_msg = {
            "sender_name" : os.environ.get('NODEID'), 
            "request" : request_type,
            "term": os.environ.get('current_term'),
            "key": key,
            "value": value,
            "lastLogIndex": lastLogIndex,
            "lastLogTerm": lastLogTerm
            }
    else:    
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
            # Things to add to heartBeatSend 
                #  term 
                # leaderId 
                # prevLogIndex
                # prevLogTerm
                # new entries[]
                # leadersCommitIndex

            # access leader logs
            global node_logs
            node_logs = retrive_log()                     
            
            #access nextIndex
            global nextIndex
            
            # print(nextIndex)
            # print(type(nextIndex))
            
            active_node_count = num_of_nodes
            
            for node in range(1,num_of_nodes+1):
                # to differentiate between sender and target nodes
                if f"Node{node}" != node_name: 
                    try:
                        ## same message for each node is no longer feasible
                        ## message based on the recorded nextIndex for each node
                        ## determines the prevLogIndex, prevLogTerm, and entry to be added from the Leader's log
                        ## passing all message components explicitly for clarity

                        # print(f"making APPEND message for Node{node}")
                        environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")
                        # nextIndex[Node] has caught up with leader (i.e ==last_applied_)
                        if int(nextIndex[f"Node{node}"]) > int(environ_vars["last_applied_index"]): 
                            entry = {
                                        "term": int(os.environ.get("current_term")),
                                        "key": "NULL",
                                        "value": None
                                    }
                                
                        # nextIndex[node] not caught up with leader
                        else:
                            entry = node_logs[str(nextIndex[f"Node{node}"])]
                        
                        #lower bound cap for prevLogIndex
                        if (int(nextIndex[f"Node{node}"]) -1 <= 0):
                            prev_log_index = "0"
                            if (str(environ_vars["last_applied_index"]) != "0"):
                                entry = node_logs["1"]
                        
                        # normal  prevLogIndex
                        else:
                            prev_log_index = str(int(nextIndex[f"Node{node}"]) -1)
                            
                        msg = makeMessage("APPEND_RPC"
                                        , key=None
                                        , value=None
                                        , prevLogIndex=prev_log_index
                                        , prevLogTerm=node_logs[prev_log_index]["term"]
                                        , success = None
                                        , entry = entry)
                        skt.sendto(msg, (f"Node{node}", 5555))
                        print(f"HEARTBEAT TO Node{node} SENT! msg : {msg}")
                    except:
                        print(f"Node{node} not reachable - {traceback.print_exc()}")
                        active_node_count =  active_node_count -1

            os.environ["ACTIVE_NODES"] = str(active_node_count)
            print(active_node_count," nodes are active! ")
            print(f"GONNA SLEEP FOR {hb_interval} secs")

            node_info = getNodeInfo()
            saveObj(node_info, os.environ.get("NODEID"))
            
            time.sleep(hb_interval)

def heartBeatReplySend(skt=None, success = None,prevLogIndex = None, prevLogTerm= None, entry= None):
    # Send Reply
    # msg = makeMessage(request_type= "APPEND_REPLY",success=success)
    msg = makeMessage(request_type="APPEND_REPLY"
                    ,key= None
                    ,value=None
                    ,prevLogIndex=str(prevLogIndex)
                    ,prevLogTerm=str(prevLogTerm)
                    ,success = success
                    ,entry = entry)
    try:
        skt.sendto(msg, (os.environ.get("LEADER_ID"), 5555))
        print(f'HEARTBEAT REPLY SENT TO {os.environ.get("LEADER_ID")} SENT!')
    except:
        print(f'ERROR WHILE SENDING HEARTBEAT REPLY TO {os.environ.get("LEADER_ID")} : {traceback.format_exc()}')
        
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
    # change state to candidate
    os.environ["STATE"] = "candidate"
    # update term
    os.environ["current_term"] = str(int(os.environ.get("current_term"))+1)
    # make VOTE_REQUEST msg

    environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")
    msg = makeMessage("VOTE_REQUEST",
                        key="", value="",
                        lastLogTerm=retrive_log()[str(environ_vars["last_applied_index"])]["term"], 
                        lastLogIndex=str(environ_vars["last_applied_index"]))
    # 
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

    environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")

    # if followers term is less than request term and not voted yet grant vote
    print("Voting Params: Curent Term, IncomingRPC Term , Voted(0/1) :",os.environ.get('current_term'), " ", incoming_RPC_msg["term"]," ", os.environ.get("voted"))

    if int(incoming_RPC_msg["term"]) < int(os.environ.get('current_term')):
        print(f'denied vote : incoming_RPC_msg["term"] < os.environ.get("current_term")')

    elif (int(incoming_RPC_msg["lastLogTerm"])<int(retrive_log()[str(environ_vars["last_applied_index"])]["term"])) :
        print(f'denied vote :incoming_RPC_msg["lastLogTerm"]<retrive_log()[str(environ_vars["last_applied_index"])]["term"]')
    
    elif ((int(incoming_RPC_msg["lastLogTerm"])==int(retrive_log()[str(environ_vars["last_applied_index"])]["term"]) ) 
    and (int(incoming_RPC_msg["lastLogIndex"]) < int(environ_vars["last_applied_index"]))):
        print(f'denied vote :incoming_RPC_msg["lastLogTerm"]<retrive_log()[environ_vars["last_applied_index"]]["term"]')

    elif (int(os.environ.get("voted")=="0")): 
        if int(os.environ.get("current_term")) < int(incoming_RPC_msg["term"]):
            print("vote granted")
            msg = makeMessage("VOTE_ACK", "", "")
            skt.sendto(msg, (incoming_RPC_msg["sender_name"], 5555))
            os.environ["voted"] = "1"
            os.environ["voted_for"] = incoming_RPC_msg["sender_name"]
        
        elif (int((incoming_RPC_msg["lastLogTerm"]) == int(retrive_log()[str(environ_vars["last_applied_index"])]["term"])) 
        and (int(incoming_RPC_msg["lastLogIndex"]) >= int(environ_vars["last_applied_index"]))):
            print("vote granted")
            msg = makeMessage("VOTE_ACK", "", "")
            skt.sendto(msg, (incoming_RPC_msg["sender_name"], 5555))
            os.environ["voted"] = "1"
            os.environ["voted_for"] = incoming_RPC_msg["sender_name"]

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
    # print("converting to follower")
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

def store_log(log_key, value):
    
    """
        store_log
            Params:

                int log_key,
                json_obj value
                
    """
    log_file_name = os.environ.get("NODEID") + "_logs.json"
    try: 
        json_obj = json.load(open(log_file_name, "r"))
        if value["sender_name"] == "Controller":
            log_entry = {
                "term" : int(os.environ.get("current_term")),
                "key" :value["key"],
                "value": value["value"]
            }
        else:
            log_entry = {
                "term" : value["entry"]["term"],
                "key" :value["entry"]["key"],
                "value": value["entry"]["value"]
            }
        json_obj[str(log_key)] = log_entry
        with open(log_file_name, 'w') as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=4)


    except FileNotFoundError:
        # json_obj = json.load(open(log_file_name, "r"))
        json_obj = {}
        if value["sender_name"] == "Controller":
            log_entry = {
                "term" : int(os.environ.get("current_term")),
                "key" :value["key"],
                "value": value["value"]
            }
        else:
            log_entry = {
                "term" : value["entry"]["term"],
                "key" :value["entry"]["key"],
                "value": value["entry"]["value"]
            }
        json_obj[str(log_key)] = log_entry
        with open(log_file_name, 'w') as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=4)
    
    # Update next_log_index
    environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")
    environ_vars["next_log_index"] = environ_vars["next_log_index"] + 1
    environ_vars["last_applied_index"] = environ_vars["last_applied_index"] + 1
    writeJSONInfo(os.environ.get("NODEID") + "_environ_vars.json" ,environ_vars)

    # os.environ["next_log_index"] = str(int(os.environ.get("next_log_index"))+1)

def store_ack(skt):
    value = int(readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")["next_log_index"])
    msg = makeMessage("STORE_ACK","STORING_INDEX",value)
    target = "Controller"
    port = 5555
    try:
        # Encoding and sending the message
        skt.sendto(msg, (target, port))
        # print("stored index info sent to controller")
    except:
	    # socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")
        pass


def retrive_log():
    # retrive log info 
    log_file_name = os.environ.get("NODEID") + "_logs.json"
    logs = readJSONInfo(log_file_name)
    # print("log retrived")
    return logs

def send_log(skt, logs_retrived):
    msg = makeMessage(request_type = "RETRIEVE",key="COMMITED_LOGS",value=logs_retrived)
    target = "Controller"
    port = 5555
    try:
        # Encoding and sending the message
        skt.sendto(msg, (target, port))
        # print("stored index info sent to controller")
    except:
	    # socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")
        pass


def instant_timeout():
	tE.cancel()
	tV.cancel()
	hb_timeout_function(pulse_sending_socket)

def initiate_node_shutdown():

    os.environ["SHUTDOWN_FLAG"] = "1"
    sys.exit()


def decrease_nextIndex(node_name):
    global nextIndex
    nextIndex = readJSONInfo(os.environ.get("NODEID") + "_commit_index.json")
    
    if int(nextIndex[node_name]) == 1:
        print(node_name, " next index is at minimum=1. decrement failed.")

    else:
        nextIndex[node_name] = str(int(nextIndex[node_name]) - 1) 
        with open(os.environ.get("NODEID") + "_commit_index.json", 'w') as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=4)

def update_nextIndex(node_name):
    global nextIndex
    nextIndex = readJSONInfo(os.environ.get("NODEID") + "_commit_index.json")

    environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")

    # if nextIndex[node] Within bounds of leaders last_applied+1
    if int(nextIndex[node_name])<= int(environ_vars["last_applied_index"]):
        nextIndex[node_name] = str(int(nextIndex[node_name]) + 1) 
        with open(os.environ.get("NODEID") + "_commit_index.json", 'w') as f:
            json.dump(json_obj, f, ensure_ascii=False, indent=4)

    # else - nextIndex[node] is all caught up

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
        print("GOT A message here :",decoded_msg)

        ## retrieve logs
        global node_logs
        node_logs = retrive_log()

        # if os.environ.get("state")== "leader":
        #     global nextIndex
        #     nextIndex = readJSONInfo(os.environ.get("NODEID") + "_commit_index.json")
 
        if (decoded_msg["request"] == "APPEND_RPC") and (os.environ.get("STATE")=="follower"): 
            print("HB RECV---")
            
            # Reply False conditions (if so) 
                # Term< currentTerm
                # prevLogIndex[prevTerm] ! = prevLogterm
            #  Else 
                # update commit index locally. add it to reply message
                # add logs to log .json heartBeatReply(skt, true)
            
            # CHECK AND UPDATE 
                

            # ===================================push umderneth if 
            # ========================add diff state --------- 
            resetTimerE(pulse_sending_socket, 0, 0, hb_timeout)

            os.environ["LEADER_ID"] = decoded_msg["sender_name"]
            
            
            
            node_info = getNodeInfo()

            saveObj(node_info, os.environ.get("NODEID"))

            ## check if follower is of higher term and send False if so
            if int(decoded_msg["term"]) < int(os.environ.get("current_term")):
                ## have to change the placeholder HBREPLYSEND
                heartBeatReplySend(skt=pulse_sending_socket, success = False,prevLogIndex = decoded_msg["prevLogIndex"], prevLogTerm= decoded_msg["prevLogTerm"], entry= decoded_msg["entry"])

            ## check if Leader's prevLogIndex is inside the followers's log and send False if not so
            elif decoded_msg["prevLogIndex"] not in node_logs:
                heartBeatReplySend(skt=pulse_sending_socket, success = False,prevLogIndex = decoded_msg["prevLogIndex"], prevLogTerm= decoded_msg["prevLogTerm"], entry= decoded_msg["entry"])

            ## check if Leader's prevLogIndex is inside the follower's log but prevLogTerm is not matching and send False if so
            elif (decoded_msg["prevLogIndex"] in node_logs 
            and decoded_msg["prevLogTerm"] != node_logs[decoded_msg["prevLogIndex"]]["term"]):
                heartBeatReplySend(skt=pulse_sending_socket, success = False,prevLogIndex = decoded_msg["prevLogIndex"], prevLogTerm= decoded_msg["prevLogTerm"], entry= decoded_msg["entry"])

            ## check if Leader's prevLogIndex and prevLogTerm are both matching and send True to Leader
            elif (decoded_msg["prevLogIndex"] in node_logs 
            and int(decoded_msg["prevLogTerm"]) == int(node_logs[decoded_msg["prevLogIndex"]]["term"])):
                ## placeholder for value argument in store_log
                # this should be index + 1
                
                # NULL Entry heartbeat (leader last log+1)
                # if dummy entry which implies an empty heartbeat then send a True without storing any log
                if decoded_msg["entry"]["key"] == "NULL":
                    heartBeatReplySend( skt=pulse_sending_socket, 
                                        success = True, 
                                        prevLogIndex = decoded_msg["prevLogIndex"], 
                                        prevLogTerm= decoded_msg["prevLogTerm"], 
                                        entry= decoded_msg["entry"])    

                # Normal heart beat (leader log to write exists) with entry to be appended to the Followers' log
                else:
                    print(f"message to be stored is {decoded_msg}")
                    store_log(int(decoded_msg["prevLogIndex"]) + 1 , decoded_msg)
                    heartBeatReplySend(skt=pulse_sending_socket, 
                                        success = True,
                                        prevLogIndex = decoded_msg["prevLogIndex"], 
                                        prevLogTerm= decoded_msg["prevLogTerm"], 
                                        entry= decoded_msg["entry"])                    

        if (decoded_msg["request"] == "APPEND_REPLY") and (os.environ.get("STATE")=="leader"):
            
            ## if a APPEND_REPLY is requested by a higher term follower, then the leader has gone stale
            ## hence it updates its state to follower 
            if decoded_msg["success"] == False:
                if int(decoded_msg['term'])> int(os.environ.get("current_term")):
                    # print("follower replied with higher term ｡ﾟ( ﾟஇ‸இﾟ)ﾟ｡ ; converting to follower")
                    # converting to follower
                    convert_to_follower()
                else:
                    # log mismatch
                    # decrease log
                    print(f'inconsistent log, decrease nextIndex for {decoded_msg["sender_name"]}')
                    decrease_nextIndex(decoded_msg["sender_name"])
            
            
            else:
                if decoded_msg["entry"]["key"] == "NULL":
                    print(f'log is consistent ʖ ; for {decoded_msg["sender_name"]}')
                else:
                    print(f'log accepted ( ͡° ͜ʖ ͡°) ; increasing nextIndex for {decoded_msg["sender_name"]}')
                    update_nextIndex(decoded_msg["sender_name"])
                        

            
        
        if (decoded_msg["request"] == "APPEND_RPC") and (os.environ.get("STATE")=="candidate"):
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
        
        # if (decoded_msg["request"] == "APPEND_REPLY") and (os.environ.get("STATE")=="leader"):
        #     # listen to append reply
        #     print("append reply")

        if (decoded_msg["request"] == "VOTE_REQUEST"):
            # print("VOTE RPC RECV---")
            voteMessageSend(pulse_sending_socket, decoded_msg)
        
        if (decoded_msg["request"] == "VOTE_ACK") and (os.environ.get("STATE")=="candidate"):
            vote_count+=1
            num_active_nodes = int(os.environ.get("ACTIVE_NODES"))
            print("VOTE RECV --- CURRENT VOTE COUNT:", vote_count + 1 , " ToT VOTES REQUIRED :", ((num_active_nodes-1)//2) + 1)
            
            # if majority
            if (vote_count>=((num_active_nodes-1)//2)): # n-1 /2  because the node always votes for itself
                print("NEW LEADER =============")
                tV.cancel() # cancel reelection
                # print("timer cancelled after being declared leader==================================")
                
                # read environ variables json to get last_applied_index
                environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")
                # Initialize nextIndex[]
                json_obj = {
                    "Node1" : (environ_vars["last_applied_index"] + 1),
                    "Node2" : (environ_vars["last_applied_index"] + 1),
                    "Node3" : (environ_vars["last_applied_index"] + 1),
                    "Node4" : (environ_vars["last_applied_index"] + 1),
                    "Node5" : (environ_vars["last_applied_index"] + 1),
                }
                
                # print("json_obj initialized for nextIndex ==========================")
                writeJSONInfo(f'{os.environ.get("NODEID")}_commit_index.json',json_obj)

                # print("json_obj written=============================")

                global nextIndex

                # print("global nextIndex invoked=================================")

                nextIndex = json_obj
                # print("nextIndex assigned json_obj==================================")

                os.environ["STATE"] = "leader"
                
                os.environ["voted"] = "0"
                
                os.environ["LEADER_ID"] = os.environ.get("NODEID")
                # print("env vars updated============================")

                # with open(os.environ.get("NODEID") + "_commit_index.json", 'w') as f:
                #     json.dump(json_obj, f,  indent=4)
                
                # Initialize matchIndex[]
                json_obj = {
                    "Node2" : str(0),
                    "Node1" : str(0),
                    "Node3" : str(0),
                    "Node4" : str(0),
                    "Node5" : str(0),
                }
                with open(os.environ.get("NODEID") + "_match_index.json", 'w') as f:
                    json.dump(json_obj, f,  indent=4)

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
            environ_vars = readJSONInfo(os.environ.get("NODEID") + "_environ_vars.json")
            store_log(int(environ_vars["next_log_index"]), decoded_msg)
            store_ack(pulse_sending_socket)         
        
        if decoded_msg["request"] == "STORE" and decoded_msg["sender_name"] == "Controller" and os.environ.get("STATE")!="leader":
            send_leader_info(pulse_sending_socket)

        if decoded_msg["request"] == "RETRIEVE" and decoded_msg["sender_name"] == "Controller" and os.environ.get("STATE")=="leader":
            logs_retrive = retrive_log()
            print(logs_retrive)
            send_log(pulse_sending_socket,logs_retrive)

        if decoded_msg["request"] == "RETRIEVE" and decoded_msg["sender_name"] == "Controller" and os.environ.get("STATE")!="leader":
            send_leader_info(pulse_sending_socket)


if __name__ == "__main__":
    ## initializing log_file_name
    log_file_name = os.environ.get("NODEID") + "_logs.json"

    # Init node_id_logs.json
    try: 
        ## load log data
        json_obj = json.load(open(log_file_name, "r"))
        ## if empty log then give one dummy value
        if json_obj == {}:
            json_obj = {'0':{"term" :1,"key" :"dummy","value": "dummy"}}
            writeJSONInfo(log_file_name,json_obj)
            os.environ.get("next_log_index") == "1"    
    
    except FileNotFoundError:
        # json_obj = json.load(open(log_file_name, "r"))
        json_obj = {'0':{"term" :1,"key" :"dummy","value": "dummy"}}
        writeJSONInfo(log_file_name,json_obj)
        
    # Init node_id_environ_vars.json  
    log_file_name = os.environ.get("NODEID") + "_environ_vars.json"  
    try: 
        ## load log data
        json_obj = readJSONInfo(log_file_name)
        ## if empty log then give one dummy value
        if json_obj == {}:
            json_obj = {
                    "next_log_index":1,
                    "last_applied_index":0,
                    "voted":0, 
                    "voted_for":os.environ.get("NODEID"), 
                    "leader_id":os.environ.get("NODEID"), 
                    "state": "follower"
                    }
            writeJSONInfo(log_file_name,json_obj)    
    
    except FileNotFoundError:
        json_obj = json_obj = {
                    "next_log_index":1,
                    "last_applied_index":0,
                    "voted":0, 
                    "voted_for":os.environ.get("NODEID"), 
                    "leader_id":os.environ.get("NODEID"), 
                    "state": "follower"
                    }
        writeJSONInfo(log_file_name,json_obj)

    
    # Init next_index[]
    json_obj = {
                    "Node1" : str(1),
                    "Node2" : str(1),
                    "Node3" : str(1),
                    "Node4" : str(1),
                    "Node5" : str(1),
                }
    
    global nextIndex
    nextIndex = json_obj


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

