from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys
import datetime
import dateutil.parser
import time
import asyncio
import requests
import json
from multiprocessing import Process, Queue
from threading import Thread
import click
import apiconnect
from config import config


sixpackAvailable = True
relaisAvailable = True

#Importing the relaisconnector may not work if not run on a Raspberry Pi, hence the try catch
try:
    import relaisconnect
    relaisconnect.setOutput()
except ImportError:
    print('Could not load relaisconnect.py. Power controls will be unavailable')
    relaisAvailable = False

#Check if the API connection is available
try:
    if apiconnect.fetchCurrentUser() is None:
        print('Could not connect to the Sixpack API. Consumptions management will be unavailable.')
        sixpackAvailable = False
except:
    print('Coudl not connect to Sixpack API')
    sixpackAvailable = False

q = Queue()

BUTTON_STYLESHEET = "padding: 10px; background-color: #effffc; border-style: outset; border-radius: 3px; border-width: 1px; border-color: #afb5b4"

class GUIController(QObject):

    updateConsumptionsSignal = pyqtSignal()
    updateUsersSignal = pyqtSignal()
    updateConsumablesSignal = pyqtSignal()
    updateDevicesSignal = pyqtSignal()

    api_url = "https://localhost:8080"
    ws_url = "wss://localhost:8080/ws"

    def __init__(self):
        super().__init__()
        self.qapp = None
        self.gui = None
        self.authenticated = False
        self.user = None
        self.jwt = None
        self.guiProcess = None
        #Devices for which the status will be queries via relaisconnect
        self.selectedDevices = [('amp', 'Versterker'), ('mixer', 'Mixer')]
        self.devices = []
        self.consumptions = []
        self.users = {}
        self.userConsumptions = {}
        self.consumables = {}


    def start(self):
        if not(self.guiProcess is None or self.eventProcess is None):
            print("Still running, not restarting")
            return
        self.guiThread = Thread(target=self.startGUI)
        self.guiThread.start()




    def wait(self):
        self.guiThread.join()
        print('gui done')

    def kill(self):
        print("kill called")
        self.stopGUI()
        print("stopgui called")

    def startGUI(self):
        global sixpackAvailable
        global relaisAvailable
        self.qapp = QApplication(sys.argv)
        screenWidth = self.qapp.desktop().screenGeometry().width()
        screenHeight = self.qapp.desktop().screenGeometry().height()
        self.gui = TouchGui(self, screenWidth, screenHeight, sixpackAvailable, relaisAvailable)
        #self.gui.setGeometry(1024,768,1024, 768)

        #Only load the consumptions part if the API is available
        if sixpackAvailable:
            #Connect the signals
            self.updateConsumptionsSignal.connect(self.gui.loadConsumptions)
            self.updateUsersSignal.connect(self.gui.loadUsers)
            self.updateConsumablesSignal.connect(self.gui.loadConsumables)

            self.updateUsers()
            self.updateConsumables()
            self.updateConsumptions()

        if relaisAvailable:
            self.updateDevicesSignal.connect(self.gui.loadDevices)
            self.gui.loadPowerTab()

            self.updateDevices()

        self.gui.show()
        self.qapp.exec_()
        print('guiloop returned')

    def stopGUI(self):
        QCoreApplication.instance().quit()

    def updateUsers(self):
        result = True
        users = apiconnect.fetchUsers()
        if (not users is None):
            self.users = users
            self.updateUsersSignal.emit()
        else:
            result = False

        return result

    def updateConsumptions(self):
        result = True

        newConsumptions = apiconnect.fetchConsumptions()

        if not newConsumptions is None:
            # clear out previous consumptions
            self.consumptions = []
            self.userConsumptions = {}
            # Add new consumptions
            for k, c in newConsumptions.items():
                self.consumptions.append(c)
                if str(c['userId']) in self.users:
                    if not str(c['userId']) in self.userConsumptions:
                        self.userConsumptions[str(c['userId'])] = []
                    self.userConsumptions[str(c['userId'])].append(c)
            self.consumptions = sorted(self.consumptions, key=lambda con: con['createdAt'], reverse=True)
            self.updateConsumptionsSignal.emit()
        else:
            result = False

        return result

    def updateConsumables(self):
        result = True

        newConsumables = apiconnect.fetchConsumables()

        if not newConsumables is None:
            self.consumables = newConsumables
            self.updateConsumablesSignal.emit()
        else:
            result = False

        return result

    def addConsumption(self, userId, consumableId, name, amount):
        """

        :param user_id: integer
        :param consumable_id: string
        :param amount: integer
        :return:
        """

        result = True
        if apiconnect.createConsumption(userId, consumableId, amount):
            self.gui.showMessage("{} {} gestreept!".format(amount, name))
        else:
            result = False

        return result

    def deleteConsumption(self, consumptionId):
        result = True

        if apiconnect.deleteConsumption(consumptionId):
            self.gui.showMessage('Consumptie verwijderd.')
        else:
            result = False
        return result

    def updateDevices(self):
        newDevices = []
        for d in self.selectedDevices:
            newDevices.append((d[0], d[1], relaisconnect.getStateByLabel(d[0])))
        self.devices = newDevices
        self.updateDevicesSignal.emit()

    def audioDevicesToggle(self):
        print('audioDevicesToggle called')
        if relaisconnect.getStateByLabel('amp') == 0  and relaisconnect.getStateByLabel('mixer') == 0:
            print('enable audio devices')
            relaisconnect.enableAudioDevices()
        elif relaisconnect.getStateByLabel('amp') == 0 or relaisconnect.getStateByLabel('mixer') == 0:
            print('disable audio devices')
            relaisconnect.disableAudioDevices()
        else:
            #Both are on so disable
            print('disable audio devices')
            relaisconnect.disableAudioDevices()
        self.updateDevices()

class TouchGui(QWidget):

    def __init__(self, controller, screenWidth, screenHeight, sixpackAvailable, relaisAvailable):
        super().__init__()
        self.controller = controller
        self.screenWidth = screenWidth
        self.screenHeight = screenHeight
        #UserGrid component
        self.userGrid = None
        #Devices component
        self.powerTab = None

        #Layout of the home screen
        self.mainLayout = QVBoxLayout()
        #Tabbed panel
        self.tabPane= QTabWidget()
        self.tabPane.setFocusPolicy(Qt.NoFocus)
        self.mainLayout.addWidget(self.tabPane)
        #Statusbar
        self.statusbar = QStatusBar()
        self.mainLayout.addWidget(self.statusbar)
        #Set the main layout as the current layout
        self.setLayout(self.mainLayout)

        self.users = {}
        self.userDialogs = {}
        self.userConsumptions = {}
        self.consumptions = []
        self.setGeometry(0,0,self.screenWidth, self.screenHeight)
        #Stylesheet
        self.setStyleSheet("font-size: 50px; background-color : white")

    def keyPressEvent(self, e):

        if e.key() == Qt.Key_F:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif e.key() == Qt.Key_Escape:
            self.controller.kill()
        elif e.key() == Qt.Key_Q:
            self.controller.kill()

    def mousePressEvent(self, e):
        self.hideConsumptionDialogs()

    #Loads the devices tab
    def loadPowerTab(self):
        self.tabPane.removeTab(1)
        self.powerTab = PowerTab(self.controller)
        self.tabPane.insertTab(1, self.powerTab, 'Apparaten')

    #Loads the device statuses in the devices tab
    def loadDevices(self):
        print('loadDevices called')
        self.powerTab.loadStatusLabels()

    def loadUsers(self):
        #Load the users tab
        selectedUsers = []
        for id, user in self.controller.users.items():
            if user['human'] and user['active']:
                # Create the user dialogs
                if not id in self.userDialogs:
                    self.userDialogs[str(id)] = ConsumptionDialog(user['name'], str(id), self, parent=self)
                    #self.userDialogs[str(id)].setParent(self)
                #Select users for which consumptions can be added
                selectedUsers.append(user)
        #Create usergrid
        self.userGrid = UserGrid(selectedUsers, self.controller)
        self.tabPane.removeTab(0)
        self.tabPane.insertTab(0, self.userGrid, 'Strepen')


    def loadConsumptions(self):
        #Load the consumptions in the user dialogs
        for id, ud in self.userDialogs.items():
            if id in self.controller.userConsumptions:
                ud.loadConsumptions(self.controller.userConsumptions[id], self.controller.consumables)
            else:
                ud.loadConsumptions([], self.controller.consumables)

    def showMessage(self, message):
        self.statusbar.showMessage(message, 3000)

    def loadConsumables(self):
        #Load available consumables in UserDialogs
        for id, ud in self.userDialogs.items():
            ud.loadConsumables(self.controller.consumables)

    def showConsumptionDialog(self, user_id):
        for id, ud in self.userDialogs.items():
            #print('looping')
            #print(type(id), id)
            #print(type(user_id), user_id)
            if id == user_id:
                ud.show()
            else:
                ud.hide()

    def hideConsumptionDialogs(self):
        for id, ud in self.userDialogs.items():
            ud.hide()

    def closeEvent(self, event):
        print("going down")
        #QCoreApplication.instance().quit()
        self.controller.kill()

class PowerTab(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.gridLayout = None
        self.controller = controller
        self.labelsGroup = None
        self.initUI()

    def initUI(self):
        self.gridLayout = QVBoxLayout()
        self.labelsGroup = QWidget()
        #Add button to turn on/off mixer and amp
        b = QPushButton('Audio apparaten')
        b.clicked.connect(self.onMixerAmpClick)
        self.gridLayout.addWidget(b)
        #Add the button on position 0, 1
        self.setLayout(self.gridLayout)        


    def loadStatusLabels(self):
        """
        Load labels for the power status of each device
        :return:
        """
        #Remove the previous labels
        self.labelsGroup.setParent(None)
        #Create a new labels group
        self.labelsGroup = QWidget()
        layout = QHBoxLayout()
        for device in self.controller.devices:
            #Device is a 3-tuple (id, name, status)
            layout.addWidget(QLabel('{} is {}'.format(device[1], 'aan' if device[2] else 'uit')))
        #Add the layout to the widget
        self.labelsGroup.setLayout(layout)
        #Add the widget to the grid on position 0,0
        self.gridLayout.addWidget(self.labelsGroup)

    def onDeviceClick(self):
        pass

    def onMixerAmpClick(self):
        self.controller.audioDevicesToggle()

class PowerButton(QPushButton):
    def __init__(self, device_label, name):
        super().__init__(name)
        self.device_label = str(device_label)

class UserGrid(QWidget):
    def __init__(self, users, controller):
        super().__init__()
        self.grid = None
        self.users = users
        self.controller = controller
        self.initUI()

    def initUI(self):

        self.grid = QGridLayout()
        pos = 0
        maxcols = 3
        for b in self.users:
            tb = UserButton(b)
            tb.setFocusPolicy(Qt.NoFocus)
            tb.setStyleSheet("width: 200px; height: 200px;" + BUTTON_STYLESHEET)
            tb.setGeometry(200,200,200,200)
            tb.clicked.connect(self.onClick)
            self.grid.addWidget(tb, pos//3, pos%3)
            pos += 1
        self.setLayout(self.grid)

    def onClick(self):
        source = self.sender()
        self.controller.updateConsumptions()
        self.controller.gui.showConsumptionDialog(source.user_id)


class UserButton(QPushButton):
    def __init__(self, user):
        super().__init__(user['name'])
        self.user_id = str(user['id'])

class DeleteButton(QPushButton):
    def __init__(self, consumption_id):
        super().__init__('Delete')
        self.consumption_id = consumption_id


class ConsumptionDialog(QDialog):

    def __init__(self, user_name, user_id, gui, parent=None):
        super(ConsumptionDialog, self).__init__(parent, Qt.FramelessWindowHint)
        self.gui = gui
        self.topLayout = QVBoxLayout()
        # self.setStyleSheet("""
        #     QSlider {
        #         height: 30px;
        #     }
        #
        #     QSlider::groove:horizontal {
        #         height: 40px;
        #         background-color: red;
        #     }
        #     """)

        #Label
        self.user_name = user_name
        self.user_id = user_id
        self.label = QLabel("Hoi {}, neem er nog een!".format(user_name))

        #Slider
        self.amount = 1
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.setStyleSheet("height: 30px; height: 80%; width: 80%")
        self.slider.setMinimum(1)
        self.slider.setMaximum(5)
        self.slider.setSingleStep(1)
        self.slider.setTickInterval(1)
        self.slider.setPageStep(1)
        self.slider.setValue(self.amount)
        self.slider.valueChanged[int].connect(self.setAmount)

        #ConsumableButtons
        self.consumableButtonsLayout = QVBoxLayout()
        self.consumableButtonsGroup = QWidget()
        self.buttonsLayout = QHBoxLayout()
        self.consumableButtons = {}
        self.consumableButtonsGroup.setLayout(self.buttonsLayout)
        self.consumableButtonsLayout.addWidget(self.consumableButtonsGroup)

        #Consumptions
        self.consumptionGroupLayout = QVBoxLayout()
        self.consumptionList = QWidget()
        self.consumptionLayout = QVBoxLayout()

        #Cancel button
        self.cancelButton = QPushButton('Cancel')
        self.cancelButton.setStyleSheet(BUTTON_STYLESHEET)
        self.cancelButton.setFocusPolicy(Qt.NoFocus)
        self.cancelButton.clicked.connect(self.onCancelClick)

        #Putting it together
        self.topLayout.addWidget(self.label)
        self.topLayout.addWidget(self.slider)
        self.topLayout.addLayout(self.consumableButtonsLayout)
        self.topLayout.addLayout(self.consumptionGroupLayout)
        self.topLayout.addStretch(1)
        self.topLayout.addWidget(self.cancelButton)
        self.topLayout.setSpacing(50)
        self.setLayout(self.topLayout)

        #Set dialog size to 80% of screen size
        self.setGeometry(int(self.gui.screenWidth * 0.1),int(self.gui.screenHeight * 0.1), int(self.gui.screenWidth * 0.8), int(self.gui.screenHeight*0.8))

    def loadConsumables(self, consumables):
        #Add buttons for the consumables
        self.consumableButtonsGroup.setParent(None) #This removes the widget
        self.consumableButtons = {}
        self.consumableButtonsGroup = QWidget()
        self.buttonsLayout = QHBoxLayout()
        for k, c in consumables.items():
            print(c)
            b = QPushButton(c['name'])
            b.consumableId = c['id']
            b.setStyleSheet(BUTTON_STYLESHEET)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(self.onConsumableClick)
            self.consumableButtons[c['id']] = b
            self.buttonsLayout.addWidget(b)
        self.buttonsLayout.addStretch(1)
        self.consumableButtonsGroup.setLayout(self.buttonsLayout)
        self.consumableButtonsLayout.addWidget(self.consumableButtonsGroup)
        #self.topLayout.addWidget(self.consumableButtonsGroup)

        #Repaint
        self.repaint()

    def loadConsumptions(self, consumptions, consumables):
        #Add latest consumptions
        #self.topLayout.removeWidget(self.consumptionList)
        self.consumptionList.setParent(None)
        self.consumptionList = QWidget()
        self.consumptionLayout = QVBoxLayout()
        #Sort the consumptions
        sorted_consumptions = sorted(consumptions, key=lambda con: con['createdAt'], reverse=True)
        #Select the top four consumptions
        sorted_consumptions = sorted_consumptions[:3]
        print(consumptions)
        print(consumables)
        for c in sorted_consumptions:
            cw = QWidget()
            cl = QHBoxLayout()
            cl.setSpacing(20)
            time = dateutil.parser.parse(c['createdAt'])
            cl.addWidget(QLabel("{} {} op {}".format(c['amount'], consumables[str(c['consumableId'])]['name'], time.strftime("%a %d %B om %X"))))
            dl = DeleteButton(c['id'])
            dl.setStyleSheet(BUTTON_STYLESHEET)
            dl.setFocusPolicy(Qt.NoFocus)
            dl.clicked.connect(self.onDeleteClick)
            cl.addWidget(dl)
            cw.setLayout(cl)
            self.consumptionLayout.addWidget(cw)
        self.consumptionList.setLayout(self.consumptionLayout)
        self.consumptionGroupLayout.addWidget(self.consumptionList)

        #Repaint
        self.repaint()

    def setAmount(self, value):
        self.amount = value

    def onConsumableClick(self):
        print('onConsumableClick')
        source = self.sender()
        #TODO check if source.consumableId exists
        self.gui.controller.addConsumption(int(self.user_id), source.consumableId, source.text(), self.amount)
        self.gui.controller.updateConsumptions()

    def onDeleteClick(self):
        print('onDeleteClick')
        source = self.sender()
        self.gui.controller.deleteConsumption(source.consumption_id)

    def onCancelClick(self):
        self.gui.hideConsumptionDialogs()

@click.group()
def cli():
    pass

@click.command()
@click.option('--email', default='admin@admin.com')
@click.option('--password', default='adminadmin')
@click.option('--api_url', default='https://localhost:8080')
@click.option('--ws_url', default='wss://localhost:8080/ws')
def run(api_url, ws_url, email, password):
    s = GUIController()
    s.start()
    try:
        s.wait()
    except:
        s.kill()

if __name__ == '__main__':
    cli.add_command(run)
    cli()

