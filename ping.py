#!/usr/bin/env python3
"""Measure round-trip time (client -> server -> client) over TCP or UDP.

Server:  python rtt.py server --port 9000 [--udp]
Client:  python rtt.py client --host 127.0.0.1 --port 9000 [--udp] [-n 100] [--size 64]

The server simply echoes whatever it receives. The client times each
send/receive cycle with a monotonic high-resolution clock.

Note: one-way latency can't be measured accurately without synchronised
clocks, so it is reported as RTT / 2, which assumes a symmetric path.
"""
import argparse
import socket
import statistics
import struct
import time

LEN = struct.Struct("!I")  # TCP framing: 4-byte payload length
SEQ = struct.Struct("!I")  # payload starts with a sequence number


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes from a TCP socket."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return bytes(buf)


# ---------------------------------------------------------------- server ----
def serve_tcp(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen()
        print(f"TCP echo server listening on {host}:{port}")
        while True:
            conn, addr = srv.accept()
            print(f"client connected: {addr[0]}:{addr[1]}")
            with conn:
                # Disable Nagle so small messages are sent immediately.
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                try:
                    while True:
                        header = recv_exact(conn, LEN.size)
                        (length,) = LEN.unpack(header)
                        conn.sendall(header + recv_exact(conn, length))
                        print(f"echoed {length} bytes to {addr[0]}:{addr[1]}")
                except ConnectionError:
                    print("client disconnected")


def serve_udp(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as srv:
        srv.bind((host, port))
        print(f"UDP echo server listening on {host}:{port}")
        while True:
            data, addr = srv.recvfrom(65535)
            srv.sendto(data, addr)


# ---------------------------------------------------------------- client ----
def make_payload(seq: int, size: int) -> bytes:
    return SEQ.pack(seq).ljust(size, b"\0")


def ping_tcp(sock: socket.socket, seq: int, size: int) -> None:
    payload = make_payload(seq, size)
    sock.sendall(LEN.pack(len(payload)) + payload)
    (length,) = LEN.unpack(recv_exact(sock, LEN.size))
    reply = recv_exact(sock, length)
    if SEQ.unpack(reply[:SEQ.size])[0] != seq:
        raise RuntimeError("sequence mismatch")


def ping_udp(sock: socket.socket, seq: int, size: int) -> None:
    sock.send(make_payload(seq, size))
    while True:  # skip stale replies from earlier timed-out pings
        reply = sock.recv(65535)
        if SEQ.unpack(reply[:SEQ.size])[0] == seq:
            return


def run_client(args: argparse.Namespace) -> None:
    kind = socket.SOCK_DGRAM if args.udp else socket.SOCK_STREAM
    sock = socket.socket(socket.AF_INET, kind)
    sock.settimeout(args.timeout)
    sock.connect((args.host, args.port))  # for UDP this just fixes the peer
    if not args.udp:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    ping = ping_udp if args.udp else ping_tcp

    proto = "UDP" if args.udp else "TCP"
    print(f"{proto} RTT to {args.host}:{args.port}, "
          f"{args.size}-byte payload, {args.count} pings\n")

    rtts_ms: list[float] = []
    lost = 0
    for seq in range(args.warmup + args.count):
        measured = seq >= args.warmup  # first few pings warm up caches/ARP
        start = time.perf_counter_ns()
        try:
            ping(sock, seq, args.size)
        except socket.timeout:
            if measured:
                lost += 1
                print(f"seq={seq - args.warmup:<4} timeout")
            continue
        rtt_ms = (time.perf_counter_ns() - start) / 1e6
        if measured:
            rtts_ms.append(rtt_ms)
            print(f"seq={seq - args.warmup:<4} rtt={rtt_ms:8.3f} ms")
        time.sleep(args.interval)
    sock.close()

    print(f"\n--- {args.host} {proto} statistics ---")
    print(f"sent={args.count} received={len(rtts_ms)} lost={lost} "
          f"({100 * lost / args.count:.1f}% loss)")
    if rtts_ms:
        mean = statistics.fmean(rtts_ms)
        stdev = statistics.stdev(rtts_ms) if len(rtts_ms) > 1 else 0.0
        print(f"rtt min/avg/median/max/stdev = {min(rtts_ms):.3f}/{mean:.3f}/"
              f"{statistics.median(rtts_ms):.3f}/{max(rtts_ms):.3f}/{stdev:.3f} ms")
        print(f"estimated one-way (RTT/2)    = {mean / 2:.3f} ms")


# ------------------------------------------------------------------ main ----
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["server", "client"])
    p.add_argument("--host", default="127.0.0.1",
                   help="server: address to bind (use 0.0.0.0 for all); client: server address")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--udp", action="store_true", help="use UDP instead of TCP")
    p.add_argument("-n", "--count", type=int, default=20, help="number of pings")
    p.add_argument("--size", type=int, default=64, help="payload bytes (min 4)")
    p.add_argument("--interval", type=float, default=0.05, help="seconds between pings")
    p.add_argument("--timeout", type=float, default=1.0, help="seconds to wait for a reply")
    p.add_argument("--warmup", type=int, default=3, help="unmeasured warm-up pings")
    args = p.parse_args()
    args.size = max(args.size, SEQ.size)

    try:
        if args.mode == "server":
            (serve_udp if args.udp else serve_tcp)(args.host, args.port)
        else:
            run_client(args)
    except KeyboardInterrupt:
        pass
    except (ConnectionError, socket.timeout, OSError) as e:
        raise SystemExit(f"error: {e}")


if __name__ == "__main__":
    main()
