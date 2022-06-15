import socket, selectors, struct, io, sys, logging, json


class Message:

    @staticmethod
    def _json_decode(raw_data, encoding):
        text_io_wrapper = io.TextIOWrapper(io.BytesIO(raw_data), encoding = encoding, newline = "")
        object = json.load(text_io_wrapper)
        text_io_wrapper.close()
        return object

    @staticmethod
    def _json_encode(object, encoding):
        return json.dumps(obj = object, ensure_ascii = False).encode(encoding)    

    def __init__ (self, selector: selectors.DefaultSelector, socket: socket.socket, address: any,
     package_size: int, room_values: list, doctor_values: list, study_values: list):
        self.selector = selector
        self.socket = socket
        self.address = address
        self.package_size = package_size

        self.room_values = room_values
        self.doctor_values = doctor_values
        self.study_values = study_values

        self.assigned_room_index = -1

        self.insertion_buffer = []

        self.reset_reading_state(reset_mask=False)

    def process_events_and_require_intervention(self, mask):
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            require_intervention = self.write()
            if require_intervention == True:
                return True



    def process_protoheader(self):
        header_length = 2 #in bytes
        if len(self._receive_buffer) >= header_length:
            self._jsonheader_len = struct.unpack(">H", self._receive_buffer[:header_length])[0]
            self._receive_buffer = self._receive_buffer[header_length:]

    def process_jsonheader(self):
        header_length = self._jsonheader_len
        if len(self._receive_buffer) >= header_length:
            self.jsonheader = Message._json_decode(self._receive_buffer[:header_length], "utf-8")
            self._receive_buffer = self._receive_buffer[header_length:]
            for necessary_element in ('byteorder', 'content-length', 'content-type', 'content-encoding'):
                if necessary_element not in self.jsonheader:
                    raise ValueError(f"Missing required header element: '{necessary_element}'")


    def process_request(self):
        content_length = self.jsonheader['content-length']
        if not len(self._receive_buffer) >= content_length:
            return #if the message hasn't yet accumulated, we wait until it does
        data = self._receive_buffer[:content_length]
        self._receive_buffer = self._receive_buffer[content_length:]
        if self.jsonheader['content-type'] == 'text/json':
            encoding = self.jsonheader['content-encoding']
            self.request = self._json_decode(data, encoding)
            logging.debug(f"Received request {self.request} from {self.address}")
        # else: #This shouldn't be happening
        #     self.request = data
        #     logging.warning(f"Received {self.jsonheader['content-type']} request from {self.address}")
        
        #at this point the message is assembled and is ready to be processed
        #so now we are looking for an opportunity to write back
        self._set_selector_events_mask("w")        

        
    def read(self):
        #self._read()
        def _read():
            try:
                data = self.socket.recv(self.package_size)
            except BlockingIOError:
                pass
            else:
                if data:
                    self._receive_buffer += data
                else:
                    logging.debug(f'Peer at socket {self.socket} closed.')
                    self.close()
                    #raise RuntimeError("Peer closed")  

        _read()

        if self._jsonheader_len is None:
            self.process_protoheader()

        if self._jsonheader_len is not None:
            if self.jsonheader is None:
                self.process_jsonheader()

        if self.jsonheader:
            if self.request is None:
                self.process_request()


    def write(self):
        def _write():
            if self._send_buffer:
                try:
                    sent = self.socket.send(self._send_buffer)
                except BlockingIOError:
                    pass
                else:
                    self._send_buffer = self._send_buffer[sent:]
                    if sent and not self._send_buffer:
                        #at this point the message is fully sent
                        self.reset_reading_state()

                        #self.close()
        if self.request:
            if not self._response_created:
                #self.create_response()
                need_intervention = self.determine_if_intervention_needed()
                if need_intervention:
                    return 1
                else:
                    self.create_response()
                    self.insertion_buffer = []
        _write()


    def buffer_insert(self, *args):
        for a in args:
            self.insertion_buffer.append[a]


    


    def reset_reading_state(self, reset_mask = True):
        if reset_mask:
            self._set_selector_events_mask('r')
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self._response_created = False
        self._send_buffer = b""
        self._receive_buffer = b""

    


    

    


    def _set_selector_events_mask(self, mask_symbol):
        if mask_symbol == 'r':
            events = selectors.EVENT_READ
        elif mask_symbol == 'w':
            events = selectors.EVENT_WRITE
        elif mask_symbol == 'rw':
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Instead of a valid selector events mask, '{mask_symbol}' was provided")
        self.selector.modify(self.socket, events, data = self)

    

    


    def _create_message(self, content_bytes, content_type, content_encoding):
        jsonheader = {
            'byteorder': sys.byteorder,
            'content-type': content_type,
            'content-encoding': content_encoding,
            'content-length': len(content_bytes)
        }
        jsonheader_bytes = Message._json_encode(jsonheader, 'utf-8')
        message_header = struct.pack('>H', len(jsonheader_bytes))
        return message_header + jsonheader_bytes + content_bytes


#incoming json template:
#get_field_values - request to get all possible values to select in the client
#{
#    'action': 'get_field_values'
#}
#post_new_state - post new state of the client, that includes room value, doctor value, study value and room state
#{
#    'action': 'post_new_state',
#    'data': 
#    {
#        'room_index': int,
#        'doctor_index': int,
#        'study_index': int,
#        'state_index': int    #0 - noentry, 1 - occupied, 2 - empty, 3 - await
#    }
#    
#}

    def insert_result(self, description: str, code_value: int):
        self.insertion_buffer.append(description)
        self.insertion_buffer.append(code_value)


    def determine_if_intervention_needed(self) -> bool:
        action = self.request.get('action')
        if action == 'get_field_values':
            return False
            #content = {
            #    'room_values': self.room_values,
            #    'doctor_values': self.doctor_values,
            #    'study_values': self.study_values
            #}
        elif action == 'post_new_state':
            if len(self.insertion_buffer) == 0:
                return True
            else:
                return False
            #self.acquired_data = self.request.get('data')
            #self.is_action_required = Truecreate_response

    #def _create_response_binary_content(self):
    #    pass

    def _create_response(self):
        action = self.request.get('action')
        if action == 'get_field_values':
            content = {
                'room_values': self.room_values,
                'doctor_values': self.doctor_values,
                'study_values': self.study_values
            }
        elif action == 'post_new_state':
            content = {
                'result' : self.insertion_buffer[0],
                'code_value': self.insertion_buffer[1]
            }
        content_encoding = 'utf-8'
        response = {
            'content_bytes': Message._json_encode(content, content_encoding),
            'content_type': 'text/json',
            'content_encoding': content_encoding
        }
        return response


    def close(self):
        try:
            self.selector.unregister(self.socket)
        except Exception:
            logging.error(f'Caught exception while trying to unregister the selector for {self.address}', exc_info = True)


    

    
    def create_response(self):
        if self.jsonheader['content-type'] == 'text/json':
            response = self._create_response()
        else:
            raise TypeError('Server has received an unexpected data type from the peer. Closing connection')
            #response = self._create_response_binary_content()
        message = self._create_message(**response)
        self._response_created = True
        self._send_buffer += message



    

    
