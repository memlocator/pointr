#!/usr/bin/env python
"""Shared development server with hot reload support for gRPC services"""

import sys
import time
import subprocess
import signal
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class GrpcServerHandler(FileSystemEventHandler):
    """Handler for file changes that restarts the gRPC server"""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.process = None
        self.restart_server()

    def restart_server(self):
        """Stop the current server and start a new one"""
        if self.process:
            print("🔄 Restarting server due to file changes...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

        print(f"🚀 Starting {self.service_name} gRPC server...")
        self.process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=sys.stdout,
            stderr=sys.stderr
        )

    def on_modified(self, event):
        """Called when a file is modified"""
        if event.src_path.endswith('.py'):
            print(f"📝 File changed: {event.src_path}")
            self.restart_server()

    def on_created(self, event):
        """Called when a file is created"""
        if event.src_path.endswith('.py'):
            print(f"📝 File created: {event.src_path}")
            self.restart_server()

    def stop(self):
        """Stop the server process"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()


def run_dev_server(service_name: str):
    """Run the development server with file watching"""
    handler = GrpcServerHandler(service_name)
    observer = Observer()
    observer.schedule(handler, path=".", recursive=False)
    observer.start()

    print("👀 Watching for file changes... (Press Ctrl+C to stop)")

    def signal_handler(sig, frame):
        print("\n🛑 Stopping development server...")
        handler.stop()
        observer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handler.stop()
        observer.stop()

    observer.join()
