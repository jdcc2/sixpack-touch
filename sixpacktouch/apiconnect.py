import requests
from config import config
import json

headers = {'content-type' : 'application/json', 'bearer' : config['jwtToken']}


def fetchCurrentUser():
    result = None
    try:
        r = requests.get('{}/currentuser'.format(config['apiURL']), headers=headers)
        res = r.json()
        if res['ok']:
            result = res['data']
    except ConnectionError as e:
        pass
    return result

def fetchUsers():
    result = None
    try:
        r = requests.get('{}/users'.format(config['apiURL']), headers=headers)
        res = r.json()
        if res['ok']:
            result = res['data']
    except ConnectionError as e:
        pass
    return result

def fetchConsumptions():
    result = None
    try:
        r = requests.get('{}/consumptions'.format(config['apiURL']), headers=headers)
        res = r.json()
        if res['ok']:
            result = res['data']
    except ConnectionError as e:
        pass
    return result

def fetchConsumables():
    result = None
    try:
        r = requests.get('{}/consumables'.format(config['apiURL']), headers=headers)
        res = r.json()
        if res['ok']:
            result = res['data']
    except ConnectionError as e:
        pass
    return result

def createConsumption(userId, consumableId, amount):
    result = True
    try:
        r = requests.post(config['apiURL'] + '/consumptions',
                          headers=headers,
                          data=json.dumps({'userId': userId, 'consumableId': consumableId, 'amount': amount})
                          )
        if r.status_code == 200:
            response = r.json()
            if response['ok'] is True:
                print('Successfully added consumption')
            else:
                print('Error adding consumption')
                print(response)
                result = False
        else:
            print("Error adding consumption")
            result = False
    except ConnectionError as e:
        print("Could not connect to server")
        result = False

    return result

def deleteConsumption(consumptionId):
    result = True
    try:
        r = requests.delete('{}/consumptions/{}'.format(config['apiURL'], consumptionId),
                            headers=headers)
        if r.status_code == 200:
            response = r.json()
            if response['ok'] is True:
                print('Successfully deleted consumption')
            else:
                print("Error deleteing consumption")
                result = False
        else:
            print("Error deleting consumption")
            result = False
    except ConnectionError as e:
        print("Could not connect to server")
        result = False

    return result






if __name__ == "__main__":
    #Run some tests
    fetchCurrentUser()