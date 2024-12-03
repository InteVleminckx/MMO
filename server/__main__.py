import manage  # Keep it on line 1
import sys

from twisted.internet.interfaces import IAddress

import protocol
from twisted.python import log
from twisted.internet import reactor, task
from autobahn.twisted.websocket import WebSocketServerFactory


class GameFactory(WebSocketServerFactory):

    def __init__(self, hostname: str, port: int):
        self.protocol = protocol.GameServerProtocol
        super().__init__(f"ws://{hostname}:{port}")

        self.players: set[protocol.GameServerProtocol] = set()
        self.tick_rate: int = 20

        tick_loop = task.LoopingCall(self.tick)
        tick_loop.start(1 / self.tick_rate)  # 20 times per second

    def tick(self):
        for p in self.players:
            p.tick()

    def buildProtocol(self, addr: IAddress):
        p = super().buildProtocol(addr)
        self.players.add(p)
        return p


if __name__ == '__main__':
    log.startLogging(sys.stdout)

    port: int = 8081
    factory = GameFactory('127.0.0.1', port)

    reactor.listenTCP(port, factory)
    reactor.run()
