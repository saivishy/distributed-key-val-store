import sys
import argparse
import json
import socket
import traceback
import time


def listener(skt):
    print(f'Listening for messages... ')

    while True:
        try:
            recv_msg, addr = skt.recvfrom(1024)
        except:
            print(f"Error: Failed while fetching from socket - {traceback.print_exc()}")
    
        decoded_msg = json.loads(recv_msg.decode('utf-8'))
        return decoded_msg



if __name__ == "__main__":
    time.sleep(30)
    # Load message template
    msg = json.load(open("Message.json"))

    # initialize
    sender = "Controller"
    # port=int(input("give port number"))
    port = 5555

    # Socket creation and binding
    skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    skt.bind((sender, port))

    request_target_node = "Node4" #str(input("Select which node to target. Press numbers from 1-5 to select from Node1-Node5 respectively \n"))

    msg['sender_name'] = sender
    msg['request']="LEADER_INFO"

    
    try:
        # Encoding and sending the message
        skt.sendto(json.dumps(msg).encode('utf-8'), (request_target_node, port))
        print(f"{msg['request']} sent to {request_target_node} \n")

        print(f"Waiting for reply from {request_target_node}\n")
        reply =  listener(skt)
        print(f"Leader info received {reply['sender_name']} : {reply}")
        
    except:
    #  socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")

    

    

    # retargeting leader for conversion to follower
    msg['request']="CONVERT_FOLLOWER"
    
    request_target_node = reply['value']
    
    
    try:
        # Encoding and sending the message
        skt.sendto(json.dumps(msg).encode('utf-8'), (request_target_node, port))
        print(f"{msg['request']} sent to Node{request_target_node} \n")

        # print(f"Waiting for reply from Node{request_target_node}\n")
        # reply =  listener(skt)
        # print(f"Leader info received from {reply['sender_name']} : {reply}")
        
    except:
    #  socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")


    time.sleep(20)

    
    # timeout the converted follower

    msg['request']="TIMEOUT"
    
    try:
        # Encoding and sending the message
        skt.sendto(json.dumps(msg).encode('utf-8'), (request_target_node, port))
        print(f"{msg['request']} sent to Node{request_target_node} \n")

        # print(f"Waiting for reply from Node{request_target_node}\n")
        # reply =  listener(skt)
        # print(f"Leader info received from {reply['sender_name']} : {reply}")
        
    except:
    #  socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")


    time.sleep(15)

    msg['request']="SHUTDOWN"
    
    try:
        # Encoding and sending the message
        skt.sendto(json.dumps(msg).encode('utf-8'), (request_target_node, port))
        print(f"{msg['request']} sent to Node{request_target_node} \n")

        # print(f"Waiting for reply from Node{request_target_node}\n")
        # reply =  listener(skt)
        # print(f"Leader info received from {reply['sender_name']} : {reply}")
        
    except:
    #  socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
        print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")








        
