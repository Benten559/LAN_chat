import socket
import threading
import sys
import re
import json
from typing import Dict, List
import signal

class ChatPeer:
    def __init__(self, port: int):
        self.port = port
        self.connections: Dict[int, tuple[socket.socket, str, int]] = {}
        self.connection_counter = 0
        self.lock = threading.Lock()
        self.running = True
        
        # Create listener socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Set timeout for the server socket
        self.server_socket.settimeout(1.0)  # 1 second timeout
        self.server_socket.bind(('', port))
        self.server_socket.listen(5)
        
        # Start listener thread
        self.listener_thread = threading.Thread(target=self.accept_connections)
        self.listener_thread.daemon = True
        self.listener_thread.start()
        
        # Handle graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
    
    def get_my_ip(self) -> str:
        """Get the non-localhost IP address of this machine"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    
    def accept_connections(self):
        """Accept incoming connections and start handler threads"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                # Set timeout for client socket
                client_socket.settimeout(1.0)  # 1 second timeout
                
                # Exchange port information
                their_port = int(client_socket.recv(1024).decode())
                client_socket.send(str(self.port).encode())
                
                with self.lock:
                    self.connection_counter += 1
                    self.connections[self.connection_counter] = (client_socket, addr[0], their_port)
                
                print(f"\nNew connection from {addr[0]}:{their_port}")
                print(">> ", end='', flush=True)
                
                # Start handler thread for this connection
                handler = threading.Thread(
                    target=self.handle_connection,
                    args=(self.connection_counter, client_socket, addr[0])
                )
                handler.daemon = True
                handler.start()
                
            except socket.timeout:
                # This is expected, just continue the loop
                continue
            except Exception as e:
                if self.running:  # Only print error if we're still running
                    print(f"Error accepting connection: {e}")

    
    def handle_connection(self, conn_id: int, client_socket: socket.socket, addr: str):
        """Handle messages from a connected peer"""
        while self.running:
            try:
                message = client_socket.recv(1024).decode()
                if not message:
                    # Connection closed by peer
                    self.handle_disconnect(conn_id)
                    break
                
                _, their_port = self.connections[conn_id][1:]
                print(f"\nMessage received from {addr}")
                print(f"Sender's Port: {their_port}")
                print(f'Message: "{message}"')
                print(">> ", end='', flush=True)
                
            except socket.timeout:
                # This is expected, just continue the loop
                continue
            except Exception:
                if self.running:  # Only handle disconnect if we're still running
                    self.handle_disconnect(conn_id)
                break
    
    def handle_disconnect(self, conn_id: int):
        """Handle a peer disconnecting"""
        with self.lock:
            if conn_id in self.connections:
                socket, addr, port = self.connections[conn_id]
                socket.close()
                del self.connections[conn_id]
                print(f"\nConnection {conn_id} ({addr}:{port}) has been terminated")
                print(">> ", end='', flush=True)
    
    def connect_to_peer(self, ip: str, port: int) -> bool:
        """Establish connection to another peer"""
        # Validate IP address
        try:
            socket.inet_aton(ip)
        except socket.error:
            print("Invalid IP address")
            return False
        
        # Check for self-connection
        if ip == self.get_my_ip() and port == self.port:
            print("Self-connection is not allowed")
            return False
        
        # Check for duplicate connection
        for _, addr, their_port in self.connections.values():
            if addr == ip and their_port == port:
                print("Duplicate connection is not allowed")
                return False
        
        try:
            # Create new socket and connect
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.connect((ip, port))
            
            # Exchange port information
            new_socket.send(str(self.port).encode())
            their_port = int(new_socket.recv(1024).decode())
            
            with self.lock:
                self.connection_counter += 1
                self.connections[self.connection_counter] = (new_socket, ip, their_port)
            
            # Start handler thread
            handler = threading.Thread(
                target=self.handle_connection,
                args=(self.connection_counter, new_socket, ip)
            )
            handler.daemon = True
            handler.start()
            
            print(f"Connected to {ip}:{port}")
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def list_connections(self):
        """Display all active connections"""
        if not self.connections:
            print("No active connections")
            return
            
        print("id: IP address      Port No.")
        for conn_id, (_, addr, port) in self.connections.items():
            print(f"{conn_id}: {addr:<15} {port}")
    
    def terminate_connection(self, conn_id: int) -> bool:
        """Terminate a specific connection"""
        with self.lock:
            if conn_id not in self.connections:
                print(f"Connection {conn_id} does not exist")
                return False
            
            socket, addr, port = self.connections[conn_id]
            socket.close()
            del self.connections[conn_id]
            print(f"Connection {conn_id} ({addr}:{port}) terminated")
            return True
    
    def send_message(self, conn_id: int, message: str) -> bool:
        """Send a message to a specific peer"""
        if len(message) > 100:
            print("Message too long (max 100 characters)")
            return False
            
        with self.lock:
            if conn_id not in self.connections:
                print(f"Connection {conn_id} does not exist")
                return False
            
            try:
                self.connections[conn_id][0].send(message.encode())
                print(f"Message sent to {conn_id}")
                return True
            except Exception as e:
                print(f"Failed to send message: {e}")
                self.handle_disconnect(conn_id)
                return False
    
    def handle_shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        print("\nShutting down...")
        self.running = False
        
        # Close all connections
        with self.lock:
            for conn_id in list(self.connections.keys()):
                try:
                    socket, addr, port = self.connections[conn_id]
                    socket.shutdown(socket.SHUT_RDWR)
                    socket.close()
                except Exception:
                    pass  # Ignore errors during shutdown
                del self.connections[conn_id]
        
        # Close server socket
        try:
            self.server_socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass  # Ignore errors during shutdown
        self.server_socket.close()
        
        sys.exit(0)
    
    def print_help(self):
        """Display help information"""
        help_text = """
Available commands:
  help                           - Display this help message
  myip                          - Display your IP address
  myport                        - Display your port number
  connect <ip> <port>           - Connect to a peer
  list                          - List all active connections
  terminate <id>                - Terminate a connection
  send <id> <message>           - Send a message to a peer
  exit                          - Close all connections and exit
"""
        print(help_text)
    
    def run(self):
        """Main command loop"""
        print(f"Chat application started on port {self.port}")
        self.print_help()
        
        while True:
            try:
                command = input(">> ").strip()
                
                if not command:
                    continue
                    
                parts = command.split(maxsplit=2)
                cmd = parts[0].lower()
                
                if cmd == "help":
                    self.print_help()
                    
                elif cmd == "myip":
                    print(self.get_my_ip())
                    
                elif cmd == "myport":
                    print(self.port)
                    
                elif cmd == "connect":
                    if len(parts) != 3:
                        print("Usage: connect <ip> <port>")
                        continue
                    try:
                        self.connect_to_peer(parts[1], int(parts[2]))
                    except ValueError:
                        print("Invalid port number")
                    
                elif cmd == "list":
                    self.list_connections()
                    
                elif cmd == "terminate":
                    if len(parts) != 2:
                        print("Usage: terminate <connection_id>")
                        continue
                    try:
                        self.terminate_connection(int(parts[1]))
                    except ValueError:
                        print("Invalid connection ID")
                    
                elif cmd == "send":
                    if len(parts) < 3:
                        print("Usage: send <connection_id> <message>")
                        continue
                    try:
                        self.send_message(int(parts[1]), parts[2])
                    except ValueError:
                        print("Invalid connection ID")
                    
                elif cmd == "exit":
                    self.handle_shutdown(None, None)
                    
                else:
                    print("Unknown command. Type 'help' for available commands.")
                    
            except EOFError:
                self.handle_shutdown(None, None)
            except KeyboardInterrupt:
                print()  # Move to next line
                continue

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python chat.py <port>")
        sys.exit(1)
        
    try:
        port = int(sys.argv[1])
        if port < 1024 or port > 65535:
            raise ValueError
    except ValueError:
        print("Port must be a number between 1024 and 65535")
        sys.exit(1)
        
    chat = ChatPeer(port)
    chat.run()