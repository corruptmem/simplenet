import logging
import simplenet
import selectors
import socket
import sys

sel = selectors.DefaultSelector()

logger = logging.getLogger(__name__)

def main():
    with simplenet.Client(2131) as client:

        def handle_input():
            line = sys.stdin.readline()
            if line:
                client.send(line.strip())

        def handle_message():
            message = client.read()
            print(message)

        sel.register(client, selectors.EVENT_READ, handle_message)
        sel.register(sys.stdin, selectors.EVENT_READ, handle_input)

        while True:
            socks = sel.select()
            for key, events in socks:
                key.data()

logging.basicConfig(
        format = "%(asctime)-15s %(levelname)-5s [%(threadName)-3s] %(name)s: %(message)s", 
        level = logging.WARN)

main()
