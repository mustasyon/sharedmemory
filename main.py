from shared_memory_bridge.bridge import SharedMemoryBridge
import time
import random

shared_memory_file = "shared_memory.bin"
shared_memory_size = 4096
lock_file = "lockfile"

def file_changed(fileobject):
    print(f"filechanged: the data:{fileobject}")

def main():
    with SharedMemoryBridge(shared_memory_file, shared_memory_size, file_changed) as bridge:
        therands = random.randint(0, 100)
        print(therands)
        for i in range(0,50):
            time.sleep(0.1)
            data=dict()
            data["name"]="mustafa"
            data["data"]=therands
            bridge.write(data)
if __name__ == "__main__":
    main()