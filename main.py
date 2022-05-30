import selectors
from telnetlib import STATUS
from PyQt5 import QtWidgets, QtCore, QtGui
import design
import sys
import socket
import types
import threading
import configparser
import time
import queue
import audioread
import gtts
import os
import playsound
import logging
import datetime
import struct
import json
import servermessage
import io
from pathlib import Path


class Serverapp_Ui(QtWidgets.QMainWindow, design.Ui_MainWindow):

    @staticmethod
    def parse_list(data):
        return list(i.strip() for i in data.replace('"', '').split(','))

    @staticmethod
    def parse_int_list(data):
        return list(int(i.strip()) for i in data.replace('"', '').split(','))


    def update_table_stylesheet_and_resize(self):
        begin_wrap = "QTableWidget {"
        font_size = f'font: {self.application_font_size}px "Helvetica"'
        #bg_color = f"background-color: rgb{', '.join(self.application_background_color)};"
        end_wrap = "}"


        self.table.setStyleSheet(begin_wrap + font_size + end_wrap)
        
        
        self.table.horizontalHeader().setStyleSheet("QHeaderView{" + font_size + end_wrap)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)


        imagepath = 'logo.jpg'
        img_profile = QtGui.QImage(imagepath)
        img_profile = img_profile.scaled(640, 160, aspectRatioMode=QtCore.Qt.KeepAspectRatio, transformMode=QtCore.Qt.SmoothTransformation)
        self.picture_label.setPixmap(QtGui.QPixmap.fromImage(img_profile))


        for i in range(self.table.rowCount()):
            for j in range(self.table.columnCount()):
                self.table.item(i,j).setBackground(QtGui.QColor(200,200,200))
                self.table.item(i, j).setTextAlignment(QtCore.Qt.AlignCenter)


        self.showFullScreen()
        window_width = self.frameGeometry().width()
        
        self.table.horizontalHeader().setMinimumSectionSize(window_width // 4)
        self.table.horizontalHeader().setMaximumSectionSize(window_width // 4)
        self.table.setCurrentCell(-1,-1)
        
        #self.table.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        #for i in range(self.table.rowCount()):
        #    for j in range(self.table.columnCount()):
        #        self.table.item(i, j).setStyleSheet("QTableWidgetItem {" + font_color + "}")


    def apply_config(self, config_name = 'config.ini'):
        #reading the config
        conf = configparser.ConfigParser()
        conf.read(config_name, encoding='utf-8')

        #setting up logging with proper level
        filename_list = str(datetime.datetime.today()).strip().split(' ')
        logging_filename = f"logs/{filename_list[0]}/{filename_list[-1].replace(':','.')}.txt"
        folderpath = '/'.join(logging_filename.split('/')[:-1])
        if not os.path.exists(folderpath):
            os.makedirs(folderpath)
        open(logging_filename, "w+")
        logging.basicConfig(filename = logging_filename, level = int(conf.get('logging_settings', 'logging_level')))
        
        logging.debug('Logger is set up. Reading config...')

        #reading the socket settings
        self.host_value = conf.get('socket_settings', 'host')
        self.port_value = int(conf.get('socket_settings', 'port'))
        self.no_selector_events_timeout = float(conf.get('socket_settings', 'no_selector_events_timeout'))
        self.package_recv_bytesize = int(conf.get('socket_settings', 'package_recv_bytesize'))

        #setting columns to hidden state if required
        self.table.setColumnHidden(1, int(conf.get('frontend_settings', 'hide_doctor_column')))
        self.table.setColumnHidden(2, int(conf.get('frontend_settings', 'hide_study_column')))

        #reading the list of possible values in the table
        self.room_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'room_values'))
        self.is_room_available = [1 for _ in self.room_values]
        #add all room numbers to the table
        self.doctor_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'doctor_values'))
        self.study_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'study_values'))
        self.state_values = ['Нет приема', 'Свободно', 'Занято']
        logging.debug('Have read backend values. Inserting rooms...')
        self.insert_room_numbers()
        logging.debug('Inserted rooms. Applying frontend settings...')
        
        #reading the repeated message and the timeout of its looped playback
        self.reminder_text = conf.get('frontend_settings', 'reminder_text')
        self.reminder_repeat_timeout = int(conf.get('frontend_settings', 'reminder_repeat_timeout'))
        
        
        #reading styling information
        self.application_font_size = int(conf.get('frontend_settings', 'application_font_size'))
        #self.application_background_color = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'application_background_color'))
        
        #apply styling
        self.update_table_stylesheet_and_resize()

        #reading voice delays
        self.voice_delay_between_messages = float(conf.get('frontend_settings', 'voice_delay_between_messages'))
        self.no_voice_messages_timeout = float(conf.get('frontend_settings', 'no_voice_messages_timeout'))

        logging.debug('Config fully applied!')



    def manage_socket_events(self):
        def accept_new(new_socket):
            logging.debug('Accepting new connection')
            connection, address = new_socket.accept()
            connection.setblocking(False)
            message = servermessage.Message(self.selector, connection, address, self.package_recv_bytesize, self.room_values, self.doctor_values, self.study_values)
            events = selectors.EVENT_READ #| selectors.EVENT_WRITE
            #there is nothing for the server to write at this point
            self.selector.register(connection, events, data = message)

       # def service_existing(key, mask):
       #     socket = key.fileobj
       #     data = key.data
       #     if mask & selectors.EVENT_READ: #the socket is ready to be read from
       #         received_data = socket.recv(self.package_recv_bytesize)
       #         if received_data:
       #             data.output_bytes += received_data
       #         else: #no data on read event means the connection was terminated
       #             self.selector.unregister(socket)
       #             socket.close()
       #     if mask & selectors.EVENT_WRITE:
       #         if data.output_bytes:
       #             sent = socket.send(data.output_bytes)
       #             data.output_bytes = data.output_bytes[sent:]
        #The function above would send the client back whatever is messaged to it, left for testing purposes
        #print('in function')
        while True:
            #timeout is 0 to not block even if there is nothing to process
            events = self.selector.select(timeout = 0)
            if events == []:
                time.sleep(self.no_selector_events_timeout)
            else:    
                for key, mask in events:
                    if key.data is None:
                        accept_new(key.fileobj)
                    else:
                        message = key.data
                        try:
                            need_action = message.process_events_and_require_intervention(mask)
                            
                            if need_action:
                                
                                ae_flag = (message.request.get('data').get('room_index') == message.assigned_room_index)
                                av_flag = self.is_room_available[message.request.get('data').get('room_index')]
                                if ae_flag or av_flag:
                                    if Serverapp_Ui.data_from_client_check(message.request.get('data')):
                                        if message.assigned_room_index != -1:
                                            self.is_room_available[message.assigned_room_index] = 1
                                            self.cleanup_table(message.assigned_room_index)
                                        
                                        self.is_room_available[message.request.get('data').get('room_index')] = 0
                                        last_index = message.assigned_room_index
                                        message.assigned_room_index = message.request.get('data').get('room_index')
                                       
                                        self.change_room_status(message.request.get('data'))
                                        logging.debug(f"Successfully changed status for room {message.request.get('data').get('room_index')}, was {last_index}")
                                        message.insertion_buffer.append("Изменения успешно внесены!")
                                    else:
                                        logging.warning("Provided data does not fit the value range")
                                        message.insertion_buffer.append("Данные не прошли проверку. Сообщите IT-отделу")
                                else:
                                    logging.warning(f"The room number {message.request.get('data').get('room_index')} is already occupied by another client!")
                                    message.insertion_buffer.append('Указанный номер кабинета уже используется.')


                        except Exception:
                            logging.error(f"Exception occured while trying to process event for {message.address}", exc_info = True)
                            self.cleanup_table(message.assigned_room_index)
                            if message.assigned_room_index != -1:
                                self.is_room_available[message.assigned_room_index] = 1
                            message.close()
                            

    def cleanup_table(self, index):
        cleanup_data = {
            'room_index': index,
            'doctor_index': 0,
            'study_index': 0,
            'state_index': 0 
        }
        self.change_room_status(cleanup_data)


    @staticmethod
    def data_from_client_check(data):
        return True

    
    def setup_socket_thread(self):
        #using selector to manage multiple connections without GIL
        logging.debug('Setting up socket thread...')
        self.selector = selectors.DefaultSelector()

        #set up the listening socket
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #prevent oserror
        self.listening_socket.bind((self.host_value, self.port_value))
        self.listening_socket.listen()
        self.listening_socket.setblocking(False)

        #register the listening socket with selector to monitor attempts to connect
        self.selector.register(self.listening_socket, selectors.EVENT_READ, data=None)

        #create a thread to monitor any selector events
        self.socket_thread = threading.Thread(target = self.manage_socket_events, daemon = True)
        self.socket_thread.start()
        logging.debug('Socket thread successfully started!')


#left here for easier reference in change_room_status
#'data': 
#    {
#        'room_index': int,
#        'doctor_index': int,
#        'study_index': int,
#        'state_index': int    #0 - standby, 1 - not ready, 2 - ready
#    }
    
    @staticmethod
    def soft_wrap_line(data, charcount = 15):
        data = data.split(' ')
        count = 0
        res = []
        for item in data:
            count += len(item)
            if count > charcount:
                count = count - charcount
                res.append('\n')
            res.append(item)
        return ' '.join(res)


    
    def change_room_status(self, data, is_from_start = False):
        room_index = data.get('room_index')

        if not is_from_start:
            voiceover_text = f"В кабинете {' '.join([i + ' ' for i in self.room_values[room_index]])} {self.state_values[data.get('state_index')]}"
            self.enqueue_text(voiceover_text)

        doctor = Serverapp_Ui.soft_wrap_line(self.doctor_values[data.get('doctor_index')])
        study = Serverapp_Ui.soft_wrap_line(self.study_values[data.get('study_index')])
        state = Serverapp_Ui.soft_wrap_line(self.state_values[data.get('state_index')])
        #study = self.
        self.table.setItem(room_index, 1, QtWidgets.QTableWidgetItem(doctor))
        
        self.table.setItem(room_index, 2, QtWidgets.QTableWidgetItem(study))
        self.table.setItem(room_index, 3, QtWidgets.QTableWidgetItem(state))
        self.table.resizeRowsToContents()
        state = data.get('state_index')
        cl = [200,200,200]
        if state == 1:
            cl = [207,253,188]
        elif state == 2:
            cl = [233,133,135]
        for i in range(4):
            self.table.item(room_index, i).setBackground(QtGui.QColor(cl[0],cl[1],cl[2]))
            self.table.item(room_index,i).setTextAlignment(QtCore.Qt.AlignCenter)


    def insert_room_numbers(self):
        for room in self.room_values:
            self.table.insertRow(self.table.rowCount())
            #print('inserted ' + str(self.table.rowCount()))
            item = QtWidgets.QTableWidgetItem(room)
            self.table.setItem(self.table.rowCount() - 1, 0, item)
            for i in range(3):
                self.table.setItem(self.table.rowCount() - 1, i + 1, QtWidgets.QTableWidgetItem(""))
            self.change_room_status({'room_index': self.table.rowCount() - 1, 'doctor_index': 0, 'study_index': 0, 'state_index': 0}, False)


    def audio_thread_function(self):
        while True:
            if self.audio_queue.empty():
                #check at least every second for a new file to be played
                time.sleep(self.no_voice_messages_timeout)
            else:
                #filename structure is:
                #audio_resources/<unix_time_of_file_creation>.<duration in seconds>.mp3
                filename = self.audio_queue.get()
                #sound is played asyncronously to avoid blocking the application
                print(filename)
                playsound.playsound(filename, block = False)
                #since 1:00.99 is still 60 seconds, in the worst case with 1 second delay added
                #we would have the files play one right after another -> unwanted behaviour
                time.sleep(int(filename.split('.')[-2]) + 1 + self.voice_delay_between_messages)
                


    @staticmethod
    def convert_text_to_speech(data):
        tts = gtts.gTTS(data, lang = 'ru', tld = 'cn')
        #we want to include the file duration later on
        filename_incomplete = f'audio_resources//{time.time()}.mp3'
        tts.save(filename_incomplete)
        duration_data = 0
        with audioread.audio_open(filename_incomplete) as f:
            duration_data = f.duration
        filename_complete = filename_incomplete[:-3] + str(int(duration_data) + 1) + '.mp3'
        os.rename(filename_incomplete, filename_complete)
        return filename_complete
        #audio_resources/123.mp3 -> audio_resources/123.100.mp3, means unix time == 123 and duration == 100 seconds


    def enqueue_text(self, data):
        filename = Serverapp_Ui.convert_text_to_speech(data)
        self.audio_queue.put(filename)


    def enqueue_reminder(self):
        while True:
            self.enqueue_text(self.reminder_text)
            time.sleep(self.reminder_repeat_timeout)


    def setup_audio_thread(self):
        logging.debug('Setting up audio thread...')
        #setting up a thread responsible for playing audio
        self.audio_thread = threading.Thread(target = self.audio_thread_function, daemon = True)
        

        #setting up a timer to enqueue a reminder every set period of time 
        #self.reminder_timer = QtCore.QTimer()
        #self.reminder_timer.setInterval(self.reminder_repeat_timeout)
        #self.reminder_timer.timeout.connect(self.enqueue_reminder)
        #self.reminder_timer.start()
        self.reminder_thread = threading.Thread(target = self.enqueue_reminder, daemon=True)
        self.reminder_thread.start()

        #thread takes generated audio samples and plays them in the order in which they were enqueued
        self.audio_thread.start()
        logging.debug('Audio thread successfully started!')

    

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.audio_queue = queue.Queue()
        self.apply_config('config.ini')

        self.setup_audio_thread()
        
        self.setup_socket_thread()









def main():
    app = QtWidgets.QApplication([])
    
    window = Serverapp_Ui()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()