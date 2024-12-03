import math
import queue
import time

import utils

from server.models import *
from autobahn.websocket import ConnectionRequest
from server.packet import *
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.exception import Disconnected
from django.contrib.auth import authenticate


class GameServerProtocol(WebSocketServerProtocol):

    def __init__(self):
        super().__init__()
        self._packet_queue: queue.Queue[tuple['GameServerProtocol', Packet]] = queue.Queue()
        self._state: callable = None
        self._actor: Actor | None = None
        self._player_target: list[float] | None = None
        self._last_delta_time_checked: float | None = None
        self._known_others: set['GameServerProtocol'] = set()

    def PLAY(self, sender: 'GameServerProtocol', p: Packet):
        if p.action == Action.Chat:
            if sender == self:
                self.broadcast(p, exclude_self=True)
            else:
                self.send_client(p)

        elif p.action == Action.ModelDelta:
            self.send_client(p)

            if sender not in self._known_others:
                sender.onPacket(self, ModelDeltaPacket(create_dict(self._actor)))
                self._known_others.add(sender)

        elif p.action == Action.Target:
            self._player_target = p.payloads

    def LOGIN(self, sender: 'GameServerProtocol', p: Packet):
        if p.action == Action.Login:
            username, password = p.payloads

            user = authenticate(username=username, password=password)
            if user:
                self._actor = Actor.objects.get(user=user)

                self.send_client(OkPacket())

                # Send full model data the first time we log in
                self.broadcast(ModelDeltaPacket(create_dict(self._actor)))

                self._state = self.PLAY
            else:
                self.send_client(DenyPacket("Username or password incorrect"))

        elif p.action == Action.Register:
            username, password, avatar_id = p.payloads

            if not username or not password:
                self.send_client(DenyPacket("Username or password must not be empty"))
                return

            if User.objects.filter(username=username).exists():
                self.send_client(DenyPacket("This username is already taken"))
                return

            user = User.objects.create_user(username=username, password=password)
            user.save()
            player_entity = Entity(name=username)
            player_entity.save()
            player_ientity = InstancedEntity(entity=player_entity, x=0, y=0)
            player_ientity.save()
            player = Actor(instanced_entity=player_ientity, user=user, avatar_id=avatar_id)
            player.save()
            self.send_client(OkPacket())

    def _update_position(self) -> bool:
        """Attempt to update the actor's position and return true only if the position was changed"""
        if not self._player_target:
            return False
        pos = [self._actor.instanced_entity.x, self._actor.instanced_entity.y]

        now: float = time.time()
        delta_time: float = 1 / self.factory.tick_rate
        if self._last_delta_time_checked:
            delta_time = now - self._last_delta_time_checked
        self._last_delta_time_checked = now

        # Use delta time to calculate distance to travel this time
        dist: float = 70 * delta_time

        # Early exit if we are already within an acceptable distance of the target
        if math.dist(pos, self._player_target) < dist:
            return False

        # Update our model if we're not already close enough to the target
        d_x, d_y = utils.direction_to(pos, self._player_target)
        self._actor.instanced_entity.x += d_x * dist
        self._actor.instanced_entity.y += d_y * dist
        self._actor.instanced_entity.save()

        return True

    def tick(self):
        if not self._packet_queue.empty():
            s, p = self._packet_queue.get()
            self._state(s, p)

        # To do when there are no packets to process
        elif self._state == self.PLAY:
            actor_dict_before: dict = create_dict(self._actor)
            if self._update_position():
                actor_dict_after: dict = create_dict(self._actor)
                self.broadcast(ModelDeltaPacket(get_delta_dict(actor_dict_before, actor_dict_after)))

    def broadcast(self, p: Packet, exclude_self: bool = False):
        for other in self.factory.players:
            if other == self and exclude_self:
                continue
            other.onPacket(self, p)

    def onPacket(self, sender: 'GameServerProtocol', p: Packet):
        self._packet_queue.put((sender, p))
        print(f"Queued packet: {p}")

    def onConnect(self, request: ConnectionRequest):
        print(f"Client connecting: {request.peer}")

    def onOpen(self):
        print(f"Websocket connection open.")
        self._state = self.LOGIN

    def onClose(self, was_clean, code, reason):
        if self._actor:
            self._actor.save()
        self.factory.players.remove(self)
        print(
            f"Websocket connection closed{' unexpectedly' if not was_clean else ' cleanly'} with code {code}: {reason}")

    def onMessage(self, payload, is_binary):
        decoded_payload = payload.decode('utf-8')

        try:
            p: Packet = from_json(decoded_payload)
            self.onPacket(self, p)
        except Exception as e:
            print(f"Could not load message as packet: {e}. Message was: {payload.decode('utf-8')}")

    def send_client(self, p: Packet):
        try:
            self.sendMessage(bytes(p))
        except Disconnected:
            print(f"Couldn't send {p} because client disconnected.")
