import sys
import argparse
import json
import socket
import traceback
import time


def sock_bind():
    # Socket creation and binding
    global skt
    skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    skt.bind((sender, port))


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
    # Load message template
    msg = json.load(open("Message.json"))

    # initialize
    sender = "Controller"
    port = 5555

    create_socket = str(input("create socket? (Y/N)"))

    if create_socket == "Y" or create_socket =="y":
        sock_bind()
        global skt
    else:
        sys.exit()

    while True:
        request_input = str(input("Select request to send: \n Press 1 for CONVERT_FOLLOWER \n Press 2 for TIMEOUT \n Press 3 for SHUTDOWN \n Press 4 for LEADER_INFO \n Press 5 for ALL_INFO \n Press anything else to exit \n"))
        request_target_node = str(input("Select which node to target. Press numbers from 1-5 to select from Node1-Node5 respectively \n"))
    
        msg['sender_name'] = sender
    
        if request_input == "1":
            msg['request']="CONVERT_FOLLOWER"
        elif request_input == "2":
            msg['request']="TIMEOUT"
        elif request_input == "3":
            msg['request']="SHUTDOWN"
        elif request_input == "4":
            msg['request']="LEADER_INFO"
        elif request_input == "5":
            msg['request']="ALL_INFO"   
        else:
            break
        
        try:
            # Encoding and sending the message
            skt.sendto(json.dumps(msg).encode('utf-8'), (f"Node{request_target_node}", port))
            print(f"{msg['request']} sent to Node{request_target_node} \n")

            if request_input =="4" or request_input == "5":
                print(f"Waiting for reply from Node{request_target_node}\n")
                reply =  listener(skt)
                print(reply)
            
        except:
        #  socket.gaierror: [Errno -3] would be thrown if target IP container does not exist or exits, write your listener
            print(f"ERROR WHILE SENDING REQUEST ACROSS : {traceback.format_exc()}")

        
