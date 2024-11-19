# LAN_chat
Simple Peer to Peer Chat Application

## Overview
This uses TCP Sockets to implement a peer connection within your LAN.
Multiple socket connections can be made, and both the client and server side code is implemented in a singular program.

## Dependencies
This only utilizes the standard python modules and should work with any python environment. The version used during development is 3.12 , however any 3.6+ should work.
<br><br>
You may however need to assure that ports are opened up or proper permissions are enabled.

### Example usage:

```python
python chat_peer.py 8000
```

You should be prompted with the following display within your CLI
```bash
Available commands:
  help                          - Display this help message
  myip                          - Display your IP address
  myport                        - Display your port number
  connect <ip> <port>           - Connect to a peer
  list                          - List all active connections
  terminate <id>                - Terminate a connection
  send <id> <message>           - Send a message to a peer
  exit                          - Close all connections and exit
```
