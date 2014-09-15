import struct
import json
import logging
import socket

logger = logging.getLogger(__name__)

INT_FMT = "!I"
INT_SIZE = struct.calcsize(INT_FMT)

class WireError(Exception):
    pass

class Wire(object):
    def __init__(self, socket):
        self._socket = socket

    @property
    def socket(self):
        return self._socket

    def read(self):
        logger.debug("reading message")
        payload = self.__recv_payload()
        fields = _extract_payload(payload)

        return fields

    def send(self, *fields):
        logger.debug("sending message with %d fields", len(fields))

        payload = _create_payload(fields)
        self.__send_payload(payload)

    def fileno(self):
        return self.socket.fileno()

    def __recv_payload(self):
        size = _decode_int(self.__recv_bytes(INT_SIZE))
        payload = self.__recv_bytes(size)

        return payload

    def __send_payload(self, payload):
        header = _encode_int(len(payload))

        frame = bytearray()
        frame.extend(header)
        frame.extend(payload)

        self.__send_bytes(frame)

    def __send_bytes(self, frame):
        self._socket.sendall(frame)

    def __recv_bytes(self, size):
        logger.debug("waiting for %d bytes", size)

        recvd = self._socket.recv(size, socket.MSG_WAITALL)
        if not recvd or len(recvd) < size:
            logger.error("did not read all requested bytes. wanted %d, got %d", size, len(recvd))
            raise WireError()

        return recvd

def _marshal(obj):
    js = json.dumps(obj)
    bs = js.encode()

    return bs

def _unmarshal(bs):
    js = bs.decode()
    obj = json.loads(js)

    return obj

def _encode_int(val):
    return struct.pack(INT_FMT, val)

def _decode_int(bs):
    i, = struct.unpack(INT_FMT, bs)
    return i

def _extract_payload(payload):
    pos = 0
    fields = []

    while pos < len(payload):
        size_bs = payload[pos:pos+INT_SIZE]
        size = _decode_int(size_bs)
        field_bs = payload[pos+INT_SIZE:pos+INT_SIZE+size]
        field = _unmarshal(field_bs)
        fields.append(field)

        pos += size + INT_SIZE

    return fields

def _create_payload(fields):
    payload = bytearray()

    for field in fields:
        bs = _marshal(field)
        bs_len = len(bs)
        bs_prefix = _encode_int(bs_len)

        payload.extend(bs_prefix)
        payload.extend(bs)

    return payload
