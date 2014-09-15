import socket 
import threading
import json
import struct
import logging

from select import select

from .wire import Wire

logger = logging.getLogger(__name__)

class Server(object):
    def __init__(self, port, host = '127.0.0.1'):
        logger.info("creating server on %s:%d", host, port)

        self.port = port
        self.host = host
        self.ipc_socket = None
    
    def start(self):
        left_sock, right_sock = socket.socketpair()
        self.ipc_socket = Wire(left_sock)
        self.thread = ServerThread(self.host, self.port, right_sock)
        self.thread.start()

    def stop(self):
        logger.debug("sending quit message over ipc_socket")
        self.ipc_socket.send('stop')
        self.thread.join()
        
        self.server_socket = None
        self.ipc_socket = None

    def fileno():
        return self.ipc_socket.fileno()

    def send(self, obj, connection_id):
        self.ipc_socket.send('msg', connection_id, obj)

    def read(self):
        handlers = {
            'connect': self.__handle_connect,
            'disconnect': self.__handle_disconnect,
            'msg': self.__handle_message
        }

        msg_type, *data = self.ipc_socket.read()

        handler = handlers.get(msg_type)
        if handler is not None:
            logger.debug("handling message type %s", msg_type)
            event = handler(data)
            logger.info("read message %r", event)
            return event

        logger.warn("message type %s is unhandled", msg_type)
        return None #not quite sure how we got here...
        
    def __handle_connect(self, data):
        client_id, host, port = data
        return NewConnectionEvent(client_id, host, port)


    def __handle_disconnect(self, data):
        client_id, = data
        return DisconnectionEvent(client_id)

    def __handle_message(self, data):
        client_id, obj = data
        return MessageEvent(client_id, obj)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

class MessageEvent(object):
    def __init__(self, from_client_id, data):
        self.from_client_id = from_client_id
        self.data = data

    def __str__(self):
        return "message from {0}: {1}".format(self.from_client_id, self.data)

class NewConnectionEvent(object):
    def __init__(self, client_id, host, port):
        self.client_id = client_id
        self.host = host 
        self.port = port
    
    def __str__(self):
        return "connection from {0}:{1} - assigned id {2}".format(self.host, self.port, self.client_id)

class DisconnectionEvent(object):
    def __init__(self, client_id):
        self.client_id = client_id
    
    def __str__(self):
        return "disconnection from {0}".format(self.client_id)

class ServerThread(threading.Thread):
    def __init__(self, host, port, ipc):
        logger.info("creating socket and binding")
        super().__init__(name="Server")

        self.ipc = Wire(ipc)
        self.host = Wire(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self.host.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.host.socket.bind((host, port))
        self.host.socket.listen(1)
        self.client_sockets = {}
        self.client_ids = {}
        self.current_client_id = 0

        self.daemon = True

    def run(self):
        logger.info("socket now ready and listening for connections")
        host = self.host
        ipc = self.ipc

        while True:
            all_sockets = [host, ipc] + list(self.client_sockets.keys())
            r, w, x = select(all_sockets, [], [])

            if len(r) == 0:
                logger.warn("accept returned empty sets - server shutting down")
                self.ipc_socket.shutdown(socket.SHUT_RDWR)
                self.ipc_socket.close()
                break

            for sock in r:
                if sock == host:
                    self.__handle_host_event()
                elif sock == ipc:
                    self.__handle_ipc_event()
                else:
                    self.__handle_client_event(sock)

    def __handle_host_event(self):
        logger.debug("accepting connection")

        client_socket, addr = self.host.socket.accept()
        client_id = self.__get_new_client_id()
        client_wire = Wire(client_socket)

        self.client_sockets[client_wire] = (client_id, addr)
        self.client_ids[client_id] = client_wire 

        host, port = addr
        self.ipc.send('connect', client_id, host, port)

        logger.info("client %d connected: %r", client_id, addr)

    def __handle_ipc_message(self, message):
        client_id, *data = message

        dest_wire = self.client_ids.get(client_id)

        if dest_wire:
            logger.info("sending message to client %d", client_id)
            dest_wire.send(*data)
        else:
            logger.warn("tried to send message to client %d which doesn't exist, ignoring", client_id)

    def __handle_ipc_event(self):
        logger.debug("new data on ipc socket")

        msg_type, *data = self.ipc.read()

        if msg_type == 'quit':
            self.__shutdown()
        elif msg_type == 'msg':
            self.__handle_ipc_message(data)
        else:
            logger.warn("ipc message type %s not understood", msg_type)

    def __shutdown(self):
        logger.info("shutting down")
        for wire in self.client_sockets.keys():
            self.__destroy_socket(wire)

        self.__destroy_socket(host)
        self.__destroy_socket(ipc)

    
    def __handle_client_event(self, wire):
        logger.debug("new data on client socket")
        
        client_id, addr = self.client_sockets[wire]
        try:
            message, = wire.read()
        except Exception as ex:
            logger.error("client %d socket error", client_id)
            logger.exception(ex)

            self.__destroy_socket(wire, client_id)
        else: 
            self.ipc.send('msg', client_id, message)
    
    def __destroy_socket(self, wire, client_id):
        try:
            wire.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            logger.info("couldn't shut down socket, was probably already dead")

        try:
            wire.socket.close()
        except Exception as ex:
            logger.warn("error closing client %d socket", client_id)
            logger.exception(ex)

        del self.client_sockets[wire]
        del self.client_ids[client_id]

        self.ipc.send("disconnect", client_id)

    def __get_new_client_id(self):
        client_id = self.current_client_id + 1
        self.current_client_id += 1
        return client_id

