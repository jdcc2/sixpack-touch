from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys
import datetime
import time
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from ssl import SSLContext, CERT_NONE, PROTOCOL_TLSv1_2
import asyncio
import requests
import json
from multiprocessing import Process, Queue
from threading import Thread
import click

q = Queue()

BUTTON_STYLESHEET = "padding: 10px; background-color: #effffc; border-style: outset; border-radius: 3px; border-width: 1px; border-color: #afb5b4"

class EventLogger(ApplicationSession):

    def __init__(self, config=None):
        ApplicationSession.__init__(self, config)
        self.sub = None
        self.secret = u'geheim'


    def onJoin(self, details):
        q.put("Eventlogger started")
        self.sub = self.subscribe(self.relayEvent, 'events')

    def onClose(self, wc):
        print("closed")
        asyncio.get_event_loop().stop()

    def relayEvent(*args, **kwargs):
        print("Event received: {} {}".format(kwargs, args))
        q.put(kwargs['event'])

def log(message):
        print("Event received: {}".format(message))

def runWSHandler():
    context = SSLContext(PROTOCOL_TLSv1_2)
    context.verify_mode = CERT_NONE
    runner = ApplicationRunner(url=u"wss://localhost:8080/ws", realm=u"sixpack", ssl=context)
    runner.run(EventLogger)

def loginRequest():
    print(json.dumps({'email' : 'admin@admin.com', 'password' : 'adminadmin'}))
    r = requests.post('https://localhost:8080/login', headers={'content-type' : 'application/json'}, data=json.dumps({'email' : 'admin@admin.com', 'password' : 'adminadmin'}), verify=False)
    print(r.status_code)
    print (r.text)


class StreepLijst(QObject):

    updateConsumptionsSignal = pyqtSignal()
    updateUsersSignal = pyqtSignal()
    updateConsumablesSignal = pyqtSignal()

    api_url = "https://localhost:8080"
    ws_url = "wss://localhost:8080/ws"

    def __init__(self):
        super().__init__()
        self.qapp = None
        self.gui = None
        self.eventHandler = None
        self.authenticated = False
        self.user = None
        self.jwt = None
        self.guiProcess = None
        self.listening = True
        self.consumptions = []
        self.users = []
        self.userConsumptions = {}
        self.consumables = {}

        self.eventThread = None
        self.eventLoop = None






    def start(self):
        if not(self.guiProcess is None or self.eventProcess is None):
            print("Still running, not restarting")
            return
        self.guiThread = Thread(target=self.startGUI)
        self.listenerThread = Thread(target=self.startListening)
        self.eventProcess = Process(target=runWSHandler)
        #self.eventThread = Thread(target=self.startEventHandler)
        #self.eventThread.start()

        self.guiThread.start()
        self.eventProcess.start()
        self.listenerThread.start()



    def wait(self):
        self.guiThread.join()
        print('gui done')
        self.listenerThread.join()
        print('listener done')

    def kill(self):
        print("kill called")
        self.stopGUI()
        print("stopgui called")
        self.stopListening()
        print("stoplistening called")
        self.stopEventHandler()
        print("stopeventhandler called")


    def startEventHandler(self):
        self.eventLoop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.eventLoop)
        context = SSLContext(PROTOCOL_TLSv1_2)
        context.verify_mode = CERT_NONE
        runner = ApplicationRunner(url=self.ws_url, realm=u"sixpack", ssl=context)
        runner.run(EventLogger)


    def startGUI(self):
        self.qapp = QApplication(sys.argv)
        screenWidth = self.qapp.desktop().screenGeometry().width()
        screenHeight = self.qapp.desktop().screenGeometry().height()
        self.gui = StreepGui(self, screenWidth, screenHeight)
        #self.gui.setGeometry(1024,768,1024, 768)

        #Connect the signales
        self.updateConsumptionsSignal.connect(self.gui.loadConsumptions)
        self.updateUsersSignal.connect(self.gui.loadUsers)
        self.updateConsumablesSignal.connect(self.gui.loadConsumables)

        self.updateUsers()
        self.updateConsumables()
        self.updateConsumptions()
        self.gui.show()
        self.qapp.exec_()
        print('guiloop returned')

    def startListening(self):
        print('listening')
        while self.listening:
            message = q.get()
            if message == 'CONSUMPTIONS_UPDATE':
                print('consumptions update received')
                self.updateConsumptions()
        print('listening done')

    def stopListening(self):
        self.listening = False
        q.put("stop")

    def stopEventHandler(self):
        self.eventProcess.terminate()

    def stopGUI(self):
        QCoreApplication.instance().quit()

    def login(self, email, password):
        result = True
        r = requests.post(self.api_url + '/login', headers={'content-type' : 'application/json'},
                          data=json.dumps({'email' : email, 'password' : password}), verify=False)
        if r.status_code == 200:
            data = r.json()
            self.user = data['user_id']
            self.jwt = data['jwt']
        else:
            result = False
        return result

    def updateUsers(self):
        result = True
        try:
            r = requests.get(self.api_url + '/users', headers={'content-type' : 'application/json', 'bearer' : self.jwt}, verify=False)
            if r.status_code == 200:
                data = r.json()
                self.users = data['users']
                self.updateUsersSignal.emit()

            else:
                print("Error during user fetch")
                result = False
        except ConnectionError as e:
            print("Could not connect to server")
            result = False


        return result

    def updateConsumptions(self):
        result = True
        try:
            r = requests.get(self.api_url +'/consumptions', headers={'content-type' : 'application/json', 'bearer' : self.jwt}, verify=False)
            if r.status_code == 200:
                data = r.json()
                #clear out previous consumptions
                self.consumptions = []
                self.userConsumptions = {}
                #Add new consumptions
                for k, c in data['consumptions'].items():
                    self.consumptions.append(c)
                    if str(c['user_id']) in self.users:
                        if not str(c['user_id']) in self.userConsumptions:
                            self.userConsumptions[str(c['user_id'])] = []
                        self.userConsumptions[str(c['user_id'])].append(c)
                self.consumptions = sorted(self.consumptions, key=lambda con: con['time'], reverse=True)
                self.updateConsumptionsSignal.emit()
                #self.gui.loadConsumptions(data['consumptions'])
            else:
                print("Error during consumptions fetch")
                result = False
        except ConnectionError as e:
            print("Could not connect to server")
            result = False


        return result

    def updateConsumables(self):
        result = True
        try:
            r = requests.get(self.api_url + '/consumables', headers={'content-type' : 'application/json', 'bearer' : self.jwt}, verify=False)
            if r.status_code == 200:
                data = r.json()
                self.consumables = data['consumables']
                self.updateConsumablesSignal.emit()
            else:
                print("Error during consumables fetch")
                result = False
        except ConnectionError as e:
            print("Could not connect to server")
            result = False


        return result

    def addConsumption(self, user_id, consumable_id, amount):
        """

        :param user_id: integer
        :param consumable_id: string
        :param amount: integer
        :return:
        """

        result = True
        try:
            r = requests.post(self.api_url + '/consumptions',
                              headers={'content-type' : 'application/json', 'bearer' : self.jwt},
                              data=json.dumps({'user_id' : user_id, 'consumable_id' : consumable_id, 'amount' : amount}),
                              verify=False)
            if r.status_code == 200:
                response = r.json()
                if response['success'] is True:
                    self.gui.showMessage("{} {} gestreept!".format(amount, consumable_id))
                    print('Successfully added consumption')
                else:
                    print('Error adding consumption')
                    print(response)

            else:
                print("Error adding consumption")
                result = False
        except ConnectionError as e:
            print("Could not connect to server")
            result = False


        return result

    def deleteConsumption(self, consumption_id):
        result = True
        try:
            r = requests.delete(self.api_url + '/consumptions/' + str(consumption_id),
                              headers={'content-type' : 'application/json', 'bearer' : self.jwt},
                              verify=False)
            if r.status_code == 200:
                response = r.json()
                if response['success']is True:
                    print('Successfully deleted consumption')
                    self.gui.showMessage('Consumptie verwijderd.')
                else:
                    print("Error deleteing consumption")
                    print(response)
            else:
                print("Error deleting consumption")
                result = False
        except ConnectionError as e:
            print("Could not connect to server")
            result = False


        return result

class StreepGui(QWidget):

    def __init__(self, controller, screenWidth, screenHeight):
        super().__init__()
        self.controller = controller
        self.screenWidth = screenWidth
        self.screenHeight = screenHeight
        self.tabPane= QTabWidget()
        self.tabPane.setFocusPolicy(Qt.NoFocus)
        self.userGrid = None
        #self.tabPane.addTab(self.userGrid, 'Strepen')
        self.tabLayout1 = QVBoxLayout()
        self.tabLayout1.addWidget(self.tabPane)

        #Statusbar
        self.statusbar = QStatusBar()
        self.tabLayout1.addWidget(self.statusbar)
        self.setLayout(self.tabLayout1)
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

    def mousePressEvent(self, e):
        self.hideConsumptionDialogs()

    def loadUsers(self):
        #Create the user dialogs
        for id, user in self.controller.users.items():
            if not id in self.userDialogs:
                self.userDialogs[str(id)] = ConsumptionDialog(user['name'], str(id), self, parent=self)
                #self.userDialogs[str(id)].setParent(self)
        #Create usergrid
        self.userGrid = UserGrid([x for k, x in self.controller.users.items()], self.controller)
        self.tabPane.removeTab(0)
        self.tabPane.insertTab(0, self.userGrid, 'Strepen')
        #Connect buttons and shit

    def loadConsumptions(self):
        #Load the consumptions in the user dialogs
        for id, ud in self.userDialogs.items():
            if id in self.controller.userConsumptions:
                ud.loadConsumptions(self.controller.userConsumptions[id])
            else:
                ud.loadConsumptions([])

    def showMessage(self, message):
        self.statusbar.showMessage(message, 3000)

    def loadConsumables(self):
        for id, ud in self.userDialogs.items():
            ud.loadConsumables([x['id'] for k, x in self.controller.consumables.items()])

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

    def loadConsumables(self, consumable_ids):
        #Add buttons for the consumables
        self.consumableButtonsGroup.setParent(None) #This removes the widget
        self.consumableButtons = {}
        self.consumableButtonsGroup = QWidget()
        self.buttonsLayout = QHBoxLayout()
        for c in consumable_ids:
            b = QPushButton(c)
            b.setStyleSheet(BUTTON_STYLESHEET)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(self.onConsumableClick)
            self.consumableButtons[c] = b
            self.buttonsLayout.addWidget(b)
        self.buttonsLayout.addStretch(1)
        self.consumableButtonsGroup.setLayout(self.buttonsLayout)
        self.consumableButtonsLayout.addWidget(self.consumableButtonsGroup)
        #self.topLayout.addWidget(self.consumableButtonsGroup)

        #Repaint
        self.repaint()

    def loadConsumptions(self, consumptions):
        #Add latest consumptions
        #self.topLayout.removeWidget(self.consumptionList)
        self.consumptionList.setParent(None)
        self.consumptionList = QWidget()
        self.consumptionLayout = QVBoxLayout()
        #Sort the consumptions
        sorted_consumptions = sorted(consumptions, key=lambda con: con['time'], reverse=True)
        #Select the top four consumptions
        sorted_consumptions = sorted_consumptions[:3]

        for c in sorted_consumptions:
            cw = QWidget()
            cl = QHBoxLayout()
            cl.setSpacing(20)
            time = datetime.datetime.fromtimestamp(c['time'])
            cl.addWidget(QLabel("{} {} op {}".format(c['amount'], c['consumable_id'], time.strftime("%a %d %B om %X"))))
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
        self.gui.controller.addConsumption(int(self.user_id), source.text(), self.amount)

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
    s = StreepLijst()
    s.api_url = api_url
    s.ws_url = ws_url
    if not s.login('admin@admin.com', 'adminadmin'):
        print('Login failed. Exiting...')
        return
    s.start()
    try:
        s.wait()
    except:
        s.kill()

if __name__ == '__main__':
    cli.add_command(run)
    cli()

