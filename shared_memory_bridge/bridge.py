import mmap
import os
import struct
import threading
import pickle
import time
import atexit

class SharedMemoryBridge:
    def __init__(self, shared_memory_path, shared_memory_size=4096, file_changed_callback=None):
        self.shared_memory_path = shared_memory_path
        self.shared_memory_size = shared_memory_size
        self.number_of_clients = 256
        self.lock_byte_index = 0
        self.client_registration_start_index = self.lock_byte_index + 1
        self.client_registration_end_index = self.client_registration_start_index + 256
        self.client_modified_start_index = self.client_registration_end_index
        self.client_modified_end_index = self.client_modified_start_index + 256
        self.datalength_start_index = self.client_modified_end_index
        self.datalength_end_index = self.client_modified_end_index+4
        self.payload_start_index =  self.datalength_end_index

        self.callback = file_changed_callback
        self.listener_thread = None
        self.thread_running = True
        self.client_index = None
        self.permission_index = None
        self.data_dict = dict()
        # Create the shared memory if it doesn't exist
        if not os.path.exists(self.shared_memory_path):
            self.create_shared_memory()
        
        # Get an available client index
        self.get_available_client_index()
        
        
        # Start listening for permission changes
        self.start_listening()
        # atexit.register(self.close)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        # Terminate the listener thread
        self.thread_running = False
        if self.listener_thread is not None and self.listener_thread.is_alive():
            self.listener_thread.join()
        try:
            thereareclients = False
            with open(self.shared_memory_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                while mm[self.lock_byte_index] != 0:
                    pass
                mm[self.lock_byte_index] = 1
                mm[self.client_index] = 0
                for i in range(self.client_registration_start_index,self.client_registration_end_index):
                    if(mm[i]==1):
                        thereareclients = True
                # Release the write lock
                mm[self.lock_byte_index] = 0
                mm.close()

            if(thereareclients==False):
                # Unlink the shared memory file
                self.unlink_shared_memory()
        except Exception as e:
            print(f"Error while closing shared memory: {str(e)} may be already closed")

    
    def create_shared_memory(self):
        creationOK = True
        try:
            with open(self.shared_memory_path, 'w+b') as f:
                # Set the size of the memory-mapped file
                f.write(b'\x00' * self.shared_memory_size)
        except Exception as e:
            print(f"Error while creating shared memory: {str(e)}")
            creationOK = False
            

    def get_available_client_index(self):
        try:
            with open(self.shared_memory_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                self.client_index = self.client_registration_start_index
                # Acquire the write lock
                while mm[self.lock_byte_index] != 0:
                    pass
                mm[self.lock_byte_index] = 1
                # Find the first available client index
                for i in range(self.client_registration_start_index, self.client_registration_end_index):
                    if mm[i] == 0:
                        mm[i] = 1
                        self.client_index = i
                        self.permission_index = self.client_index + self.client_modified_start_index - 1
                        break
                # Release the write lock
                mm[self.lock_byte_index] = 0
                mm.close()
        except Exception as e:
            print(f"Error while getting available client index: {str(e)}")
            self.create_shared_memory()
            self.get_available_client_index()
    
    def file_changed_callback(self):
        if self.callback is not None:
            self.callback(self.data_dict)

    def write(self,data):
        try:
            with open(self.shared_memory_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                # Acquire the write lock
                while mm[self.lock_byte_index] != 0:
                    pass
                mm[self.lock_byte_index] = 1

                for i in range(self.client_registration_start_index,self.client_registration_end_index):
                    if((mm[i]==1)and(i!=self.client_index)):
                        mm[i+self.client_modified_start_index-1] = 1
                data_bytes = pickle.dumps(data)
                # Update the data length
                length = len(data_bytes)
                mm[self.datalength_start_index:self.datalength_end_index] = struct.pack('I', length)
            
                # Update the payload data
                mm[self.payload_start_index:self.payload_start_index+length] = data_bytes
                
                # Release the write lock
                mm[self.lock_byte_index] = 0
                
                mm.close()
        except Exception as e:
            print(f"Error while writing to shared memory: {str(e)}")
            print(f"Memory has been recently closed!")

    def listen_permission_changes(self):
        try:
            with open(self.shared_memory_path, 'r+b') as f:
                mm = mmap.mmap(f.fileno(), 0)
                while self.thread_running:
                    if (mm[self.permission_index] == 1):
                        while mm[self.lock_byte_index] != 0:
                            pass
                        mm[self.lock_byte_index] = 1
                        data_len = struct.unpack('I', mm[self.datalength_start_index:self.datalength_end_index])[0]
                        data_bytes = mm[self.payload_start_index:self.payload_start_index+data_len]
                        mm[self.permission_index] = 0
                        mm[self.lock_byte_index] = 0
                        self.data_dict = pickle.loads(data_bytes)  
                        self.file_changed_callback()
                    time.sleep(0.0001)
                mm.close()
        except Exception as e:
            print(f"Error while listening for permission changes: {str(e)}")
    
    
    def start_listening(self):
        self.listener_thread = threading.Thread(target=self.listen_permission_changes)
        self.listener_thread.daemon = True
        self.listener_thread.start()
    
    def unlink_shared_memory(self):
        try:
            os.unlink(self.shared_memory_path)
        except Exception as e:
            print(f"Error while unlinking shared memory: {str(e)}")
