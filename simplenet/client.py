import socket
import logging

from .wire import Wire

logger = logging.getLogger(__name__)

class Client(object):
    def __init__(self, port, host='127.0.0.1'):
        logger.info("creating client for %s:%d", host, port)

        self.port = port
        self.host = host
        self.wire = None

    def connect(self):
        logger.info("resolving address info")
        methods = socket.getaddrinfo(self.host, self.port, 0,0, socket.SOL_TCP)
        
        for fam, sock_type, proto, canonname, sockaddr in methods:
            logger.info("connecting to %r (fam=%d, type=%d, proto=%d)", sockaddr, fam, sock_type, proto)
            sock = socket.socket(fam, sock_type, proto)
            sock.connect(sockaddr)
            
            logger.info("connected")
            self.wire = Wire(sock)

        return 

    def send(self, obj):
        self.wire.send(obj)

    def read(self):
        message, = self.wire.read()
        return message

    def fileno(self):
        return self.wire.fileno()

    def close(self):
        if self.wire:
            logger.info("closing connection")
            self.wire.socket.shutdown(socket.SHUT_RDWR)
            self.wire.socket.close()
            self.wire = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, type, value, traceback):
        self.close()
