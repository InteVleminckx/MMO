import json
import enum


class Action(enum.Enum):
    Chat = enum.auto()
    Ok = enum.auto()
    Deny = enum.auto()
    Register = enum.auto()
    Login = enum.auto()
    ModelDelta = enum.auto()
    Target = enum.auto()


class Packet:
    def __init__(self, action: Action, *payloads):
        self.action: Action = action
        self.payloads: tuple = payloads

    def __str__(self) -> str:
        serialize_dict = {'a': self.action.name}
        for i, payload in enumerate(self.payloads):
            serialize_dict[f'p{i}'] = self.payloads[i]

        data = json.dumps(serialize_dict, separators=(',', ':'))
        return data

    def __bytes__(self) -> bytes:
        return str(self).encode('utf-8')


class ChatPacket(Packet):

    def __init__(self, sender: str, message: str):
        super().__init__(Action.Chat, sender, message)


class OkPacket(Packet):

    def __init__(self):
        super().__init__(Action.Ok)


class DenyPacket(Packet):

    def __init__(self, reason: str):
        super().__init__(Action.Deny, reason)


class LoginPacket(Packet):

    def __init__(self, username: str, password: str):
        super().__init__(Action.Login, username, password)


class RegisterPacket(Packet):

    def __init__(self, username: str, password: str, avatar_id: int):
        super().__init__(Action.Register, username, password, avatar_id)


class ModelDeltaPacket(Packet):

    def __init__(self, model_data: dict):
        super().__init__(Action.ModelDelta, model_data)


class TargetPacket(Packet):
    def __init__(self, t_x: float, t_y: float):
        super().__init__(Action.Target, t_x, t_y)


def from_json(json_str: str) -> Packet:
    obj_dict = json.loads(json_str)

    action = None
    payloads = []

    for key, value in obj_dict.items():
        if key == "a":
            action = value

        elif key[0] == "p":
            index = int(key[1:])
            payloads.insert(index, value)

    class_name = action + "Packet"
    try:
        constructor: type = globals()[class_name]
        return constructor(*payloads)
    except KeyError as e:
        print(f"{class_name} is not a valid packet name. Stacktrace: {e}")
    except TypeError:
        print(f"{class_name} can't handle argument {tuple(payloads)}.")
