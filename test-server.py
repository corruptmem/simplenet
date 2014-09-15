import logging

import simplenet

users = {}

def handle(server, msg):
    if isinstance(msg, simplenet.NewConnectionEvent):
        friendly_name = msg.host + ":" + str(msg.port)
        users[msg.client_id] = friendly_name
        send_all(server, friendly_name + " has joined")

    if isinstance(msg, simplenet.DisconnectionEvent):
        friendly_name = users[msg.client_id]
        send_all(server, friendly_name + " has left")
        del users[msg.client_id]

    if isinstance(msg, simplenet.MessageEvent):
        friendly_name = users[msg.from_client_id]
        send_all(server, friendly_name + ": " + str(msg.data))

def send_all(server, text):
    for client_id, _ in users.items():
        server.send(text, client_id)

def main():
    with simplenet.Server(2131) as server:
        while True:
            try:
                msg = server.read()
                handle(server, msg)
            except KeyboardInterrupt:
                logging.info("Keyboard interrupt recieved, terminating server")
                return
            except Exception as ex:
                logging.exception(ex)
                return

logging.basicConfig(
        format = "%(asctime)-15s %(levelname)-5s [%(threadName)-3s] %(name)s: %(message)s", 
        level = logging.DEBUG)

main()
