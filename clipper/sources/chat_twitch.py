"""Anonymous read-only Twitch chat over IRC (no account or token needed)."""
import random
import socket
import ssl
import time

from clipper.common import log


def parse_privmsg(line):
    """Return (user, message) for a PRIVMSG line with tags, else None."""
    if " PRIVMSG #" not in line:
        return None
    tags = {}
    rest = line
    if line.startswith("@"):
        raw_tags, rest = line[1:].split(" ", 1)
        for kv in raw_tags.split(";"):
            k, _, v = kv.partition("=")
            tags[k] = v
    try:
        prefix, msg = rest.split(" PRIVMSG #", 1)[0], rest.split(" PRIVMSG #", 1)[1]
        msg = msg.split(" :", 1)[1]
    except IndexError:
        return None
    user = tags.get("display-name") or prefix.lstrip(":").split("!")[0]
    return user.lower(), msg.strip()


def listen(channel, on_message, stop_event):
    """Blocking loop with reconnect. on_message(t, user, msg)."""
    channel = channel.lower().lstrip("#")
    backoff = 2
    while not stop_event.is_set():
        try:
            raw = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=30)
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname="irc.chat.twitch.tv")
            nick = f"justinfan{random.randint(10000, 99999)}"
            for cmd in ("CAP REQ :twitch.tv/tags", "PASS SCHMOOPIIE", f"NICK {nick}", f"JOIN #{channel}"):
                sock.sendall((cmd + "\r\n").encode())
            log(f"Chat connected to #{channel}")
            backoff = 2
            buf = ""
            sock.settimeout(360)
            while not stop_event.is_set():
                data = sock.recv(65536)
                if not data:
                    raise ConnectionError("chat socket closed")
                buf += data.decode("utf-8", errors="replace")
                *lines, buf = buf.split("\r\n")
                for line in lines:
                    if line.startswith("PING"):
                        sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                        continue
                    if " RECONNECT" in line:
                        raise ConnectionError("server asked to reconnect")
                    parsed = parse_privmsg(line)
                    if parsed:
                        on_message(time.time(), parsed[0], parsed[1])
        except Exception as e:
            if stop_event.is_set():
                break
            log(f"Chat disconnected ({e}); retrying in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
