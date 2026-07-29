# Bind on all interfaces *inside* the container. The published port is pinned
# to 127.0.0.1 by docker-compose, which is what keeps it off the internet.
bind = "0.0.0.0:8080"

# One process, many threads -- deliberately, and for two reasons.
#
# SQLite allows one writer at a time. With a single process every write goes
# through one connection behind one lock, so there is no cross-process
# contention to lose a game state to. A second worker would buy nothing here
# (three friends, not three thousand) and would introduce exactly the class of
# bug that is miserable to reproduce.
#
# Threads matter because the naming call to the Anthropic API takes about a
# second and blocks whichever thread it is on. Eight threads means eight
# players can be mid-discovery without anyone queueing.
workers = 1
threads = 8
worker_class = "gthread"

# Comfortably longer than the naming call's own 20s client timeout, so a slow
# API response is handled by our fallback path rather than by a worker kill.
timeout = 60
keepalive = 65

accesslog = "-"
errorlog = "-"
