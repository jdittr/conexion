# conexion 200 sensor extraction
#
# Tools to integrate the conexion box into a smart home and make use of the sensors and data it extracts from varios heating systems.
#
# As I currently have a new Regula Grandis 650 HK and the conexio 200 module, that only has a webpage with no API or any other 
# real means to integrate it into out smart home systems, I decided to write a small tool, that can extract the sensor data and 
# publish it via MQTT.
#
# Copyright (c) 2021 Julian Dittrich

import json, urllib, argparse
from xml.dom import minidom
from urllib.request import urlopen
import paho.mqtt.publish as publish

parser = argparse.ArgumentParser(description='Tool to get data from a local conexion 200, that is connected to a Grandis 650 or so.')
parser.add_argument('--remote-url', '-r', metavar='N', type=str,
                    help='The base URL of the conexion device.')
parser.add_argument('--user', '-u', metavar='my-username', default='admin', type=str,
                    help='User name for authentication. (default:admin)')
parser.add_argument('--password', '-p', metavar='my-password', type=str,
                    help='Password for authentication with user.')

parser.add_argument('--mqtt-host', '-R', metavar='mqtt-host', type=str,
                    help='Host, that the MQTT broker is running on.')
parser.add_argument('--mqtt-user', '-U', metavar='mqtt-username', type=str,
                    help='MQTT username.')

# TODO: Need to find a better way to deal with the passwords
parser.add_argument('--mqtt-password', '-P', metavar='mqtt-password', type=str,
                    help='Password for authentication with user.')

args = parser.parse_args()

def cutData(string,start,length):
	if start >= len(string):
		return "0"
	if start+length > len(string):
		return string[start:]
	return string[start:start+length]

def convertAtoH(string,start,length):
	return int("0x"+cutData(string, start, length), 16)

def decodeSigned(string,start,length):
	value = convertAtoH(string,start,length)
	if ( value > 32767 ):
		value -= 65536
	return value

def getVar(string,start,length,devider):
	return decodeSigned(string,start,length)/devider

output={}
url = args.remote_url+'/medius_val.xml'

# create a password manager
password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()

# Add the username and password.
top_level_url = args.remote_url
password_mgr.add_password(None, top_level_url, args.user, args.password)

handler = urllib.request.HTTPDigestAuthHandler(password_mgr)

# create "opener" (OpenerDirector instance)
opener = urllib.request.build_opener(handler)
# use the opener to fetch a URL
response = opener.open(url)

urllib.request.install_opener(opener)

# Convert bytes to string type and string type to dict
string = response.read().decode('utf-8')

# Return is some simple XML with a long HEX value, that needs splitting
xmldoc = minidom.parseString(string)
itemlist = xmldoc.getElementsByTagName('data')
fileIn = '%s' % itemlist[0].firstChild.nodeValue

heatingSystem = fileIn[2*convertAtoH(fileIn,0,2)-24:2*convertAtoH(fileIn,0,2)-16]

if heatingSystem == "053803ED":
	# These are in scope['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10','Str','R1','R2','R3','R4','R5','R6','R7','R0','HE1','HE2','Q1','Q2','F1S1','F1S2','F1S3','F1S4','F1R1','F1R2','F1R3','F1HE','F2S1','F2S2','F2S3','F2S4','F2R1','F2R2','F2R3','F2HE']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"S7": getVar(fileIn,34,4,10),
		"S8": getVar(fileIn,38,4,10),
		"S9": getVar(fileIn,42,4,10),
		"S10": getVar(fileIn,46,4,10),
		"Str": decodeSigned(fileIn,50,4),
		"R0": getVar(fileIn,106,4,2),
		"R1": getVar(fileIn,78,4,2),
		"R2": getVar(fileIn,82,4,2),
		"R3": getVar(fileIn,86,4,2),
		"R4": getVar(fileIn,90,4,2),
		"R5": getVar(fileIn,94,4,2),
		"R6": getVar(fileIn,98,4,2),
		"R7": getVar(fileIn,102,4,2),
		"HE1": getVar(fileIn,106,4,100),
		"HE2": getVar(fileIn,110,4,100),
		"HE3": getVar(fileIn,114,4,100),
		"Q1": decodeSigned(fileIn,130,4)+decodeSigned(fileIn,134,4) + decodeSigned(fileIn,182,4)+decodeSigned(fileIn,186,4),
		"Q2": decodeSigned(fileIn,146,4),
		"F1S1": getVar(fileIn,234,4,10),
		"F1S2": getVar(fileIn,238,4,10),
		"F1S3": getVar(fileIn,242,4,10),
		"F1S4": getVar(fileIn,246,4,10),
		"F1R1": getVar(fileIn,250,4,2),
		"F1R2": getVar(fileIn,254,4,2),
		"F1R3": getVar(fileIn,258,4,2),
		"F1HE": getVar(fileIn,262,4,100),
		"F2S1": getVar(fileIn,278,4,10),
		"F2S2": getVar(fileIn,282,4,10),
		"F2S3": getVar(fileIn,284,4,10),
		"F2S4": getVar(fileIn,288,4,10),
		"F2R1": getVar(fileIn,292,4,2),
		"F2R2": getVar(fileIn,296,4,2),
		"F2R3": getVar(fileIn,300,4,2),
		"F2HE": getVar(fileIn,324,4,100),
		"numberOfFlexes": decodeSigned(fileIn,378,4),
		}
elif heatingSystem == "053703EA": # FWRC 400
	# These are in scope['S1','S2','S3','S4','S5','S6','R3','R0','HE1','HE2','S1S1','S1S2','S1S3','S1S4','S1DL','S1P','S1V','S2S1','S2S2','S2S3','S2S4','S2DL','S2P','S2V','S3S1','S3S2','S3S3','S3S4','S3DL','S3P','S3V','S4S1','S4S2','S4S3','S4S4','S4DL','S4P','S4V']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"R3": getVar(fileIn,42,4,2),
		"R0": getVar(fileIn,46,4,2),
		"HE1": getVar(fileIn,50,4,100),
		"HE2": getVar(fileIn,54,4,100),
		"S1S1": getVar(fileIn,74,4,10),
		"S1S2": getVar(fileIn,78,4,10),
		"S1S3": getVar(fileIn,82,4,10),
		"S1S4": getVar(fileIn,86,4,10),
		"S1DL": getVar(fileIn,90,4,10),
		"S1P": getVar(fileIn,94,4,1),
		"S1V": getVar(fileIn,98,4,1)*100,
		"S2S1": getVar(fileIn,122,4,10),
		"S2S2": getVar(fileIn,126,4,10),
		"S2S3": getVar(fileIn,130,4,10),
		"S2S4": getVar(fileIn,134,4,10),
		"S2DL": getVar(fileIn,138,4,10),
		"S2P": getVar(fileIn,142,4,1),
		"S2V": getVar(fileIn,146,4,1)*100,
		"S3S1": getVar(fileIn,170,4,10),
		"S3S2": getVar(fileIn,174,4,10),
		"S3S3": getVar(fileIn,178,4,10),
		"S3S4": getVar(fileIn,182,4,10),
		"S3DL": getVar(fileIn,186,4,10),
		"S3P": getVar(fileIn,190,4,1),
		"S3V": getVar(fileIn,194,4,1)*100,
		"numberOfFlexes": decodeSigned(fileIn,218,4),
		}
elif heatingSystem == "05371771": # FWR400
	# These are in scope['S1','S2','S3','S4','S5','S6','R3','R0','HE1','HE2']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"R0": getVar(fileIn,46,4,2),
		"R3": getVar(fileIn,42,4,2),
		"HE1": getVar(fileIn,50,4,100),
		"HE2": getVar(fileIn,54,4,100),
		}
elif heatingSystem == "053803F2": # FWR 1336
	# These are in scope['S1','S2','S3','S4','S5','S6','R1','R2','R3','R4','R5','R6','R7','R0','HE1','HE2']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"R0": getVar(fileIn,74,4,2),
		"R1": getVar(fileIn,46,4,2),
		"R2": getVar(fileIn,50,4,2),
		"R3": getVar(fileIn,54,4,2),
		"R4": getVar(fileIn,58,4,2),
		"R5": getVar(fileIn,62,4,2),
		"R6": getVar(fileIn,66,4,2),
		"R7": getVar(fileIn,70,4,2),
		"HE1": getVar(fileIn,78,4,100),
		"HE2": getVar(fileIn,82,4,100),
		}
elif heatingSystem == "053803F1": # HC680
	# These are in scope['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10','R1','R2','R3','R4','R5','R6','R7','R0','HE1','HE2','HE3','Q1','F1S1','F1S2','F1S3','F1S4','F1R1','F1R2','F1R3','F1HE','F2S1','F2S2','F2S3','F2S4','F2R1','F2R2','F2R3','F2HE','F3S1','F3S2','F3S3','F3S4','F3R1','F3R2','F3R3','F3HE','F4S1','F4S2','F4S3','F4S4','F4R1','F4R2','F4R3','F4HE']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"S7": getVar(fileIn,34,4,10),
		"S8": getVar(fileIn,38,4,10),
		"S9": getVar(fileIn,42,4,10),
		"S10": getVar(fileIn,46,4,10),
		"R0": getVar(fileIn,106,4,2),
		"R1": getVar(fileIn,78,4,2),
		"R2": getVar(fileIn,82,4,2),
		"R3": getVar(fileIn,86,4,2),
		"R4": getVar(fileIn,90,4,2),
		"R5": getVar(fileIn,94,4,2),
		"R6": getVar(fileIn,98,4,2),
		"R7": getVar(fileIn,102,4,2),
		"HE1": getVar(fileIn,106,4,100),
		"HE2": getVar(fileIn,110,4,100),
		"HE3": getVar(fileIn,114,4,100),
		"Q1": decodeSigned(fileIn,334,4)*65536+decodeSigned(fileIn,338,4),
		"F1Q": decodeSigned(fileIn,342,4)*65536+decodeSigned(fileIn,346,4),
		"F2Q": decodeSigned(fileIn,350,4)*65536+decodeSigned(fileIn,354,4),
		"F3Q": decodeSigned(fileIn,358,4)*65536+decodeSigned(fileIn,362,4),
		"F1S1": getVar(fileIn,154,4,10),
		"F1S2": getVar(fileIn,158,4,10),
		"F1S3": getVar(fileIn,162,4,10),
		"F1S4": getVar(fileIn,166,4,10),
		"F1R1": getVar(fileIn,170,4,2),
		"F1R2": getVar(fileIn,174,4,2),
		"F1R3": getVar(fileIn,178,4,2),
		"F1HE": getVar(fileIn,182,4,100),
		"F2S1": getVar(fileIn,198,4,10),
		"F2S2": getVar(fileIn,202,4,10),
		"F2S3": getVar(fileIn,206,4,10),
		"F2S4": getVar(fileIn,210,4,10),
		"F2R1": getVar(fileIn,214,4,2),
		"F2R2": getVar(fileIn,218,4,2),
		"F2R3": getVar(fileIn,222,4,2),
		"F2HE": getVar(fileIn,226,4,100),
		"F3S1": getVar(fileIn,242,4,10),
		"F3S2": getVar(fileIn,246,4,10),
		"F3S3": getVar(fileIn,250,4,10),
		"F3S4": getVar(fileIn,254,4,10),
		"F3R1": getVar(fileIn,258,4,2),
		"F3R2": getVar(fileIn,262,4,2),
		"F3R3": getVar(fileIn,266,4,2),
		"F3HE": getVar(fileIn,270,4,100),
		"F4S1": getVar(fileIn,286,4,10),
		"F4S2": getVar(fileIn,290,4,10),
		"F4S3": getVar(fileIn,294,4,10),
		"F4S4": getVar(fileIn,298,4,10),
		"F4R1": getVar(fileIn,302,4,2),
		"F4R2": getVar(fileIn,306,4,2),
		"F4R3": getVar(fileIn,310,4,2),
		"F4HE": getVar(fileIn,314,4,100),
		"RT1": getVar(fileIn,370,4,10),
		"RT2": getVar(fileIn,374,4,10),
		"RT3": getVar(fileIn,378,4,10),
		"RT4": getVar(fileIn,382,4,10),
		"numberOfFlexes": decodeSigned(fileIn,330,4),
		}
else: # grandis 650 HK und 650 WN
	# These are in scope['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10','Str','R1','R2','R3','R4','R5','R6','R7','R0','HE1','HE2','HE3','Q1','Q2','F1S1','F1S2','F1S3','F1S4','F1R1','F1R2','F1R3','F1HE','F2S1','F2S2','F2S3','F2S4','F2R1','F2R2','F2R3','F2HE','F3S1','F3S2','F3S3','F3S4','F3R1','F3R2','F3R3','F3HE','F4S1','F4S2','F4S3','F4S4','F4R1','F4R2','F4R3','F4HE']);
	atOnce = {
		"completeSize": convertAtoH(fileIn,0,2),
		"S1": getVar(fileIn,10,4,10),
		"S2": getVar(fileIn,14,4,10),
		"S3": getVar(fileIn,18,4,10),
		"S4": getVar(fileIn,22,4,10),
		"S5": getVar(fileIn,26,4,10),
		"S6": getVar(fileIn,30,4,10),
		"S7": getVar(fileIn,34,4,10),
		"S8": getVar(fileIn,38,4,10),
		"S9": getVar(fileIn,42,4,10),
		"S10": getVar(fileIn,46,4,10),
		"Str": decodeSigned(fileIn,50,4),
		"R0": getVar(fileIn,106,4,2),
		"R1": getVar(fileIn,78,4,2),
		"R2": getVar(fileIn,82,4,2),
		"R3": getVar(fileIn,86,4,2),
		"R4": getVar(fileIn,90,4,2),
		"R5": getVar(fileIn,94,4,2),
		"R6": getVar(fileIn,98,4,2),
		"R7": getVar(fileIn,102,4,2),
		"HE1": getVar(fileIn,110,4,100),
		"HE2": getVar(fileIn,114,4,100),
		"HE3": getVar(fileIn,118,4,100),
		"Q1": decodeSigned(fileIn,138,4)+decodeSigned(fileIn,142,4),
		"Q2": decodeSigned(fileIn,154,4),
		"F1S1": getVar(fileIn,202,4,10),
		"F1S2": getVar(fileIn,206,4,10),
		"F1S3": getVar(fileIn,210,4,10),
		"F1S4": getVar(fileIn,214,4,10),
		"F1R1": getVar(fileIn,218,4,2),
		"F1R2": getVar(fileIn,222,4,2),
		"F1R3": getVar(fileIn,226,4,2),
		"F1HE": getVar(fileIn,230,4,100),
		"F2S1": getVar(fileIn,246,4,10),
		"F2S2": getVar(fileIn,250,4,10),
		"F2S3": getVar(fileIn,254,4,10),
		"F2S4": getVar(fileIn,258,4,10),
		"F2R1": getVar(fileIn,262,4,2),
		"F2R2": getVar(fileIn,266,4,2),
		"F2R3": getVar(fileIn,270,4,2),
		"F2HE": getVar(fileIn,274,4,100),
		"F3S1": getVar(fileIn,290,4,10),
		"F3S2": getVar(fileIn,294,4,10),
		"F3S3": getVar(fileIn,298,4,10),
		"F3S4": getVar(fileIn,302,4,10),
		"F3R1": getVar(fileIn,306,4,2),
		"F3R2": getVar(fileIn,310,4,2),
		"F3R3": getVar(fileIn,314,4,2),
		"F3HE": getVar(fileIn,318,4,100),
		"F4S1": getVar(fileIn,334,4,10),
		"F4S2": getVar(fileIn,338,4,10),
		"F4S3": getVar(fileIn,342,4,10),
		"F4S4": getVar(fileIn,346,4,10),
		"F4R1": getVar(fileIn,350,4,2),
		"F4R2": getVar(fileIn,354,4,2),
		"F4R3": getVar(fileIn,358,4,2),
		"F4HE": getVar(fileIn,362,4,100),
		"RT1": getVar(fileIn,402,4,10),
		"RT2": getVar(fileIn,406,4,10),
		"RT3": getVar(fileIn,410,4,10),
		"RT4": getVar(fileIn,414,4,10),
		"numberOfFlexes": decodeSigned(fileIn,378,4),
		}

msgs = []
for k in atOnce:
	msgs.append( {'topic':"conexio-%s/%s" % (heatingSystem, k), 'payload': atOnce[k], 'qos': 0, 'retain': False})

publish.multiple(msgs, hostname=args.mqtt_host, auth = {'username':args.mqtt_user, 'password':args.mqtt_password})