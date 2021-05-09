from PyQt5 import QtGui
from PyQt5 import QtCore
from can.interfaces.vector import *
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow, QTreeWidgetItem
from MainWindow import Ui_MainWindow
import threading
import can
from datetime import datetime
import queue
import logging, logging.config

import os
from os import path
default_log_config_file = path.join(path.dirname(path.abspath(__file__)), 'logging.conf')

if not path.exists('./LogFile'):
    os.makedirs('./LogFile')

LOGGING_NAME = "MAINWINDOWS"


class Stream(QtCore.QObject):

    newText = QtCore.pyqtSignal(str)
        
    def write(self, text):
        
        self.newText.emit(str(text))
        
    def flush(self):
        pass


class MainWindows(Ui_MainWindow, QMainWindow):
    
    def __init__(self) -> None:
        super().__init__()
        
        # sys.stdout = Stream(newText=self.onUpdateText)
        self.setUpLogging("./logging.conf")
        self.logger = logging.getLogger(LOGGING_NAME)
        self.setupUi(self)
        self.stopReceive = False
        self.canBus = None
        self.channe_lists_backups = None
        self.BitratecomboBox.setCurrentText("500000")
        self.canMsgRecQueue = queue.Queue()
        self.addInforTimeer = QtCore.QTimer()
        self.addInforTimeer.timeout.connect(self.addCanInforMation)
        self.devieDetTimeer = QtCore.QTimer()
        self.devieDetTimeer.timeout.connect(self.devieDetection)
        self.periodSendCanMsgTimeer = QtCore.QTimer()
        self.periodSendCanMsgTimeer.timeout.connect(self.SendCanMsg)
        
        self.devieDetTimeer.start(1000)
        self.MsgtreeWidget.setHeaderLabels(['TimeStamp','DT','Channel', 'ID','DLC', 'Data'])

        reg = QtCore.QRegExp('[A-Fa-f0-9 ]{23}')
        validator = QtGui.QRegExpValidator(self)
        validator.setRegExp(reg)
        self.DatalineEdit.setValidator(validator)
        self.IdlineEdit.setValidator(QtGui.QIntValidator(0, 0x7ff))
        self.TlineEdit.setValidator(QtGui.QIntValidator(0,100000000))

        self.checkBox.setEnabled(False)
        self.checkBox.stateChanged.connect(self.checkBoxStateChanged)

        self.SendpushButton.setEnabled(False)
        self.SendpushButton.clicked.connect(self.SendCanMsg)

        self.GitpushButton.clicked.connect(self.visitGit)

        self.CleanpushButton.clicked.connect(self.CleanCanMsg)
        
        self.FrameFormatcomboBox.currentIndexChanged.connect(self.iDValidator)


        
        self.channe_lists =  VectorBus._detect_available_configs()
        self.channe_lists_backups =self.channe_lists
        if self.channe_lists:
            for channe_list in self.channe_lists:
                
                self.ChannelcomboBox.addItem(channe_list['vector_channel_config'].name)

            index = self.ChannelcomboBox.currentIndex()
            self.IsFdlabel.setText("Supports fd: " + str(self.channe_lists[index]['supports_fd']))
            self.HwChannellabel.setText("HW channel: " + str(self.channe_lists[index]['hw_channel']))
            self.SerialNumlabel.setText("SerialNumber: " + str(self.channe_lists[index]['vector_channel_config'].serialNumber))
            self.TransceiverNamelabel.setText("transceiver:\n" + str(self.channe_lists[index]['vector_channel_config'].transceiverName))

            self.ChannelcomboBox.currentIndexChanged.connect(self.displayVectorInfor)
        else:
            QMessageBox.information(self,"error","未检测到Canoe")

        self.InitpushButton.clicked.connect(self.InitCanoe)
        
        self.thr = threading.Thread(name='ReceiveMsg',target=self.ReceiveCanMsg,daemon=True)
        
    def setUpLogging(self,configFile = default_log_config_file):
        
        """
        This function setup the logger accordingly to the module provided cfg file
        """
        try:
            logging.config.fileConfig(configFile)
        except Exception as e:
            logging.warning('Cannot load logging configuration from %s. %s:%s' % (configFile, e.__class__.__name__, str(e)))

        
    def iDValidator(self,index):

        if index == 0:
            self.IdlineEdit.setValidator(QtGui.QIntValidator(0, 0x7ff))
        elif index == 1:
            self.IdlineEdit.setValidator(QtGui.QIntValidator(0, 0x1FFFFFFF))

    def CleanCanMsg(self):
        self.MsgtreeWidget.clear()

    def SendCanMsg(self):
        dat_list = []
        FormatcurrentIndex = self.FrameFormatcomboBox.currentIndex()
        FrameTypecurrentIndex = self.FrameTypecomboBox.currentIndex()
        Channelindex = self.ChannelcomboBox.currentIndex()
        sendtPdu_strs = self.DatalineEdit.text().replace(' ','')
        
        if sendtPdu_strs:
            PduLength = len(sendtPdu_strs)
            if len(sendtPdu_strs) <= 16 :
                if len(sendtPdu_strs) %2 == 0:
                    pass
                else:
                    PduLength  = PduLength + 1

            for index in range(0,PduLength,2):
                dat_list.append(int(sendtPdu_strs[index:index + 2],16))
            
        msg = can.Message(
                is_extended_id=FormatcurrentIndex,
                is_remote_frame = FrameTypecurrentIndex,
                data=dat_list,
                dlc=len(dat_list),
                channel=Channelindex,
                arbitration_id=int(self.IdlineEdit.text(),16),
                is_rx=False,
                timestamp = datetime.timestamp(datetime.now()),
            )
        self.drawCanMsg(msg)
        try:
            self.canBus.send(msg)
        except:
            QMessageBox.information(self,"error","发送失败")
            self.SendpushButton.setEnabled(False)

    def ReceiveCanMsg(self):
        while 1:
            try:
                msg = self.canBus.recv()               
            except:
                self.stopReceive =True
                break
            
            if msg:
                self.canMsgRecQueue.put(msg)

            if self.stopReceive:
                break
                
    def addCanInforMation(self):
        """
        (['TimeStamp','DT','Channel', 'ID','DLC', 'Data'])
        """
        data_string = ''
        while not self.canMsgRecQueue.empty():
            
            msg = self.canMsgRecQueue.get()
            self.drawCanMsg(msg)
            
                
    def drawCanMsg(self,msg):
        
        arbitration_id_string = '0x{0:0{1}X}'.format(msg.arbitration_id, 8 if msg.is_extended_id else 3)

        if msg.dlc > 0:
            data_string = ' '.join('{:02X}'.format(x) for x in msg.data)

        MsgWidgetItem =  QTreeWidgetItem(self.MsgtreeWidget)
        datatime = datetime.fromtimestamp(msg.timestamp).strftime('%H:%M:%S')
        MsgWidgetItem.setText(0,str(datatime))
        MsgWidgetItem.setText(1," ".join("Rx" if msg.is_rx else "Tx"))
        MsgWidgetItem.setText(2,str(msg.channel))
        MsgWidgetItem.setText(3,arbitration_id_string)
        MsgWidgetItem.setText(4,str(msg.dlc))
        MsgWidgetItem.setText(5,data_string)

    def displayVectorInfor(self,index):
        
        self.IsFdlabel.setText("Supports fd: " + str(self.channe_lists[index]['supports_fd']))
        self.HwChannellabel.setText("HW channel: " + str(self.channe_lists[index]['hw_channel']))
        self.SerialNumlabel.setText("SerialNumber: " + str(self.channe_lists[index]['vector_channel_config'].serialNumber))
        self.TransceiverNamelabel.setText("transceiver:\n" + str(self.channe_lists[index]['vector_channel_config'].transceiverName))

    def visitGit(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/xinkunlong/can-bus-view"))
    def InitCanoe(self):

        index = self.ChannelcomboBox.currentIndex()
        bitrate = int(self.BitratecomboBox.currentText())
        
        self.logger.info("bitrate = %d",bitrate)
        try:
            self.canBus = VectorBus(channel=index,bitrate=bitrate)

            self.ChannelcomboBox.setEnabled(False)

            self.BitratecomboBox.setEnabled(False)
            
            self.InitpushButton.setEnabled(False)

            self.SendpushButton.setEnabled(True)

            self.checkBox.setEnabled(True)

            self.thr.start()

            self.addInforTimeer.start(10)

        except:
            
            QMessageBox.information(self,"error","初始化失败")

    def devieDetection(self):
        # self.channe_lists =  VectorBus._detect_available_configs()
        # if self.channe_lists_backups != self.channe_lists:
        #     self.channe_lists_backups = self.channe_lists
        #     self.ChannelcomboBox.clear()
        #     if self.channe_lists:
        #         for channe_list in self.channe_lists:   
        #             self.ChannelcomboBox.addItem(channe_list['vector_channel_config'].name)
        pass

    def checkBoxStateChanged(self, index):
        if index:
            if self.TlineEdit.text(): 
                self.periodSendCanMsgTimeer.start(int(self.TlineEdit.text()))
            else :
                self.periodSendCanMsgTimeer.start(1000)
        else:
            self.periodSendCanMsgTimeer.stop()

    def closeEvent(self, a0: QtGui.QCloseEvent) -> None:
        try:
            self.stopReceive = True
            self.addInforTimeer.stop()
            self.devieDetTimeer.stop()
            if self.periodSendCanMsgTimeer.isActive():
                self.periodSendCanMsgTimeer.stop()
            self.canBus.stop_all_periodic_tasks()
            self.canBus.shutdown()
        except:
            pass
            
            


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    Form = MainWindows()
    Form.show()
    sys.exit(app.exec_())

        