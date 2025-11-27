#!/usr/bin/env python3
"""Debug script to test NM.Client initialization."""

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM, GLib
from threading import Thread
import time

print("Testing NM.Client initialization...")

# Test 1: Direct NM.Client.new()
print("\n1. Testing NM.Client.new(None)...")
try:
    client = NM.Client.new(None)
    print(f"   Success! Version: {client.get_version()}")
except Exception as e:
    print(f"   Failed: {e}")

# Test 2: Async initialization (ProtonVPN style)
print("\n2. Testing async initialization...")
try:
    main_context = GLib.MainContext()
    nm_client = NM.Client()
    
    def run_loop():
        main_loop = GLib.MainLoop(main_context)
        main_context.push_thread_default()
        main_loop.run()
    
    Thread(target=run_loop, daemon=True).start()
    time.sleep(0.2)  # Give thread time to start
    
    print("   MainLoop started, calling new_async...")
    
    result_container = []
    
    def callback(source, res, userdata):
        try:
            result = source.new_finish(res)
            result_container.append(result)
            print(f"   Callback received! Result: {result}")
        except Exception as e:
            result_container.append(e)
            print(f"   Callback error: {e}")
    
    def do_async():
        nm_client.new_async(None, callback, None)
    
    main_context.invoke_full(GLib.PRIORITY_DEFAULT, do_async)
    
    # Wait for result
    for i in range(50):  # 5 seconds max
        if result_container:
            break
        time.sleep(0.1)
    
    if result_container:
        if isinstance(result_container[0], Exception):
            print(f"   Failed: {result_container[0]}")
        else:
            print(f"   Success! Version: {result_container[0].get_version()}")
    else:
        print("   Timeout waiting for callback")
        
except Exception as e:
    print(f"   Failed: {e}")
    import traceback
    traceback.print_exc()

print("\nDone!")
