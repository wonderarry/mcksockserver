import selectors

from PyQt5 import QtWidgets, QtCore, QtGui
import design

import socket

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
import shutil

import servermessage

APP_VERSION = 10





# wanted items in cfg: 
# names of state options,
# custom voiceover template for announcer,
# option to switch to/from per-letter numbers reading,
# font size of the header description,
# border size of the horizontal header,
# color palette for states

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


        self.table.horizontalHeader().setStyleSheet("QHeaderView::section{" + "border: 1px solid black;" + font_size  + end_wrap)
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

    def show_next_ad(self):
        if self.ad_image_timer.isActive():
            return
        self.movie.stop()
        self.ad_index += 1
        if self.ad_index == len(self.ad_filenames):
            self.ad_index = 0
        print('here!', self.ad_index)
        self.movie.setFileName(self.ad_filenames[self.ad_index])
        
        if self.movie.frameCount() == 1:
            self.ad_image_timer.start(1000 * self.ad_timeout)
            self.movie.start()
        else:
            self.ad_image_timer.start(int(1000 * self.movie.frameCount() / self.ad_estimated_frame_count) + self.ad_estimated_frame_count)
            self.movie.start()



    def apply_config(self, config_name = 'config.ini'):
        #reading the config
        conf = configparser.ConfigParser()
        conf.read(config_name, encoding='utf-8')
        if not os.path.exists('audio_resources/'):
            os.makedirs('audio_resources')
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

        #setting up the ad window
        if not os.path.exists('ads/'):
            logging.debug('Created ad folder')
            os.makedirs('ads')
        self.ad_height = int(conf.get('frontend_settings' , 'ad_height'))
        self.ad_estimated_frame_count = float(conf.get('frontend_settings', 'ad_estimated_frame_count'))

        # imagepath = 'logo.jpg'
        # img_profile = QtGui.QImage(imagepath)
        # img_profile = img_profile.scaled(640, 160, aspectRatioMode=QtCore.Qt.KeepAspectRatio, transformMode=QtCore.Qt.SmoothTransformation)
        # self.picture_label.setPixmap(QtGui.QPixmap.fromImage(img_profile))
        self.ad_filenames = ['ads/' + item for item in os.listdir('ads')]
        self.ad_timeout = int(conf.get('frontend_settings', 'ad_timeout'))
        self.ad_index = len(self.ad_filenames) - 1
        if len(self.ad_filenames) == 0:
            logging.debug('No ads found in the folder, omitting ad block')
            self.ad_label.hide()
        else:
            self.ad_label.setMinimumHeight(0)
            self.ad_label.setMaximumHeight(166666)
            self.ad_label.resize(self.ad_label.width(), self.ad_height)
            self.ad_label.setMinimumHeight(self.ad_height)
            self.ad_label.setMaximumHeight(self.ad_height)
            self.ad_label.resize(self.ad_label.width(), self.ad_height)

            self.movie = QtGui.QMovie()
            self.ad_label.setMovie(self.movie)
            self.movie.setFileName(self.ad_filenames[0])
            self.movie.start()
            self.ad_image_timer = QtCore.QTimer(self)
            self.ad_image_timer.setSingleShot(True)
            self.ad_image_timer.timeout.connect(self.show_next_ad)
            self.movie.finished.connect(self.show_next_ad)
            
            #self.ad_thread = threading.Thread(target = self.show_next_ad, daemon = True)
            #self.ad_thread.start()
            

        #self.socket_thread = threading.Thread(target = self.manage_socket_events, daemon = True)
        #self.socket_thread.start()

        
        # if adheight > 0:
        #     adfilename = conf.get('frontend_settings', 'ad_file_name').strip('"').rstrip('"')
        #     self.ad_label.setMaximumHeight(adheight)
        #     self.ad_label.setMinimumHeight(adheight)
        #     self.ad_label.setFixedHeight(adheight)
        #     movie = QtGui.QMovie(adfilename)
        #     self.ad_label.setMovie(movie)
        #     self.ad_label.start()

        #setting columns to hidden state if required
        self.table.setColumnHidden(1, int(conf.get('frontend_settings', 'hide_doctor_column')))
        self.table.setColumnHidden(2, int(conf.get('frontend_settings', 'hide_study_column')))

        #reading the list of possible values in the table
        self.room_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'room_values'))
        self.is_room_available = [1 for _ in self.room_values]
        #add all room numbers to the table
        self.doctor_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'doctor_values'))
        self.study_values = Serverapp_Ui.parse_list(conf.get('frontend_settings', 'study_values'))
        
        noentry = conf.get('frontend_settings', 'status_no_entry_nickname').replace('"','')
        occup = conf.get('frontend_settings', 'status_occupied_nickname').replace('"','')
        empt = conf.get('frontend_settings', 'status_empty_nickname').replace('"','')
        waiting = conf.get('frontend_settings', 'status_await_nickname').replace('"','')
        self.state_values = [noentry, occup, empt, waiting]

        self.message_no_entry = conf.get('frontend_settings', 'message_no_entry')
        self.message_occupied = conf.get('frontend_settings', 'message_occupied')
        self.message_empty = conf.get('frontend_settings', 'message_empty')
        self.message_await = conf.get('frontend_settings', 'message_await')


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
            events = selectors.EVENT_READ #| selectors.EVENT_WRITE
            #there is nothing for the server to write at this point
            self.selector.register(connection, events, data = servermessage.Message(self.selector, connection, address, self.package_recv_bytesize, self.room_values, self.doctor_values, self.study_values, APP_VERSION))

        def process_message(message):
            is_action_needed = message.process_events_and_require_intervention(mask)
            if is_action_needed:
                #if message.request.get('version') < APP_VERSION:
                #    print('versionissue')
                #    message.insert_result('Версия клиента устарела', 2)
                #    logging.warning(f"Client version mismatch. Client's address - {message.address}")
                #    return
                    
                request_room_index = message.request.get('data').get('room_index')
                is_changing_status_same_room = (request_room_index == message.assigned_room_index)
                is_room_unoccupied = self.is_room_available[request_room_index]

                if (is_changing_status_same_room or is_room_unoccupied):
                    if message.assigned_room_index != -1 and (not is_changing_status_same_room): #already was connected, attempts new room
                        self.is_room_available[message.assigned_room_index] = 1 #Cleaning up the slot for any other user
                        self.cleanup_table(message.assigned_room_index)         #

                    old_index = message.assigned_room_index
                    message.assigned_room_index = request_room_index
                    if message.request.get('data').get('state_index') != 0:
                        self.is_room_available[request_room_index] = 0      #Occupy the room, update the info attached to the user
                        self.change_room_status(message.request.get('data'))#Fill in the data
                    else:
                        self.is_room_available[message.assigned_room_index] = 1 #Cleaning up the slot for any other user
                        self.cleanup_table(message.assigned_room_index) 
                        self.assigned_room_index = -1 

                    logging.debug(f"Successfully changed status for room {message.request.get('data').get('room_index')}, was {old_index}")
                    message.insert_result("Изменения успешно внесены!", 0)

                else: #both flags are false, means an attempt to connect to a preoccupied room. do nothing and say it's used.
                    logging.warning(f"The room number {message.request.get('data').get('room_index')} is already occupied by another client!")
                    
                    message.insert_result("Этот кабинет уже занят.", 1)
                        


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
                            process_message(message)
                        except ConnectionResetError: #happens when remote host closes
                            logging.warning(f"Host closed the connection: {message.address}", exc_info = True)
                            #If this happens with index == -1, that means the user has not yet occupied a room
                            #In this case we just close the message
                            if message.assigned_room_index != -1:   #If this user has been using the application, we need to clean up after them
                                self.is_room_available[message.assigned_room_index] = 1
                                self.cleanup_table(message.assigned_room_index)
                            message.close()
                        #except ValueError:
                        #    logging.warning(f"Client version mismatch. Client's address - {message.address}", exc_info = True)
                        #    message.insert_result('Версия клиента устарела', 2)
                        #    message.close()
                        except Exception:
                            logging.error(f"Exception occured while trying to process event for {message.address}", exc_info = True)
                            if message.assigned_room_index != -1:
                                self.is_room_available[message.assigned_room_index] = 1
                                self.cleanup_table(message.assigned_room_index)
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
        #to be implemented in case we need protection from malicious intervention
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
#        'state_index': int    #0 - noentry, 1 - occupied, 2 - ready, 3 - await
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
            #voiceover_text = f"В кабинете {' '.join([i + ' ' for i in self.room_values[room_index]])} {self.state_values[data.get('state_index')]}"
            st = data.get('state_index')
            if st == 0:
                text = self.message_no_entry
            elif st == 1:
                text = self.message_occupied
            elif st == 2:
                text = self.message_empty
            elif st == 3:
                text = self.message_await
            text = text.replace('[]', ' '.join([i + ' ' for i in self.room_values[room_index]]))
            self.enqueue_text(text)

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
            cl = [233,133,135]
        elif state == 2:
            cl = [207,253,188]
        elif state == 3:
            cl = [255, 255, 167]
        for i in range(4):
            self.table.item(room_index, i).setBackground(QtGui.QColor(cl[0],cl[1],cl[2]))
            self.table.item(room_index,i).setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setCurrentItem(self.table.item(room_index, i))
            self.table.setCurrentItem(None)


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
        tts = gtts.gTTS(data, lang = 'ru')
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
        try:
            filename = Serverapp_Ui.convert_text_to_speech(data)
        except Exception:
            logging.error('Could not create a voiceover file.', exc_info=True)
        else:
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
        if os.path.exists('audio_resources/'):
            logging.debug('Had audio_resources folder, removing older instance')
            shutil.rmtree('audio_resources')
        self.setupUi(self)
        self.audio_queue = queue.Queue()
        self.apply_config('config.ini')

        self.setup_audio_thread()

        self.setup_socket_thread()









def main():
    
    app = QtWidgets.QApplication([])
    splashscreen = QtWidgets.QSplashScreen(QtGui.QPixmap('splashscreen.png'))
    splashscreen.show()

    window = Serverapp_Ui()
    splashscreen.hide()
    window.show()
    app.exec_()

if __name__ == '__main__':
    main()
