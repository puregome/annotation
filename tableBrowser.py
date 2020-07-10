#!/usr/bin/python3 -W all
# tableBrowser: browse csv table with labeled tweets
# usage: FLASK_APP=$PWD/tableBrowser.py; flask run
# 20180124 erikt(at)xs4all.nl

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from wtforms import Form, StringField, SelectField, PasswordField, validators
import csv
import datetime
import hashlib
import random
import re
import string
import sys
import os

# start site-dependent variables
URL = "http://145.100.59.103/cgi-bin/puregome/"
BASEDIR = "/home/cloud/projects/puregome/annotation/"
# end site-dependent variables
DATADIR = BASEDIR+"data/"
DATAFILEDEFAULT = "data.csv"
HUMANLABELFILE = "human-labels.txt"
USERFILE = "users.txt"
LOGFILE = "logfile"
LABELFILE = "LABELS.txt"
BORDERPAGES = 2
PASSWORDLENGTH = 8
UNKNOWN = ""
fieldLabels = [ "Human", "Id", "User", "Tweet" ]
fieldsShow = { "Human":True, "Id":False, "User":False, "Tweet":True }
nbrOfItems = 0
TEXTCOLUMNID = 2
IDCOLUMNID = 0
TEXT = "text"
ID = "id_str"
NAME = "user"
CSVSUFFIX = r".csv$"
TWEETS = "tweets"

def useFieldsStatus(fieldsStatus):
    fieldsShow = {}
    fieldsStatusInt = int(fieldsStatus)
    for label in reversed(fieldLabels):
        newFieldsStatusInt = int(fieldsStatusInt/2)
        if fieldsStatusInt > 2*newFieldsStatusInt: fieldsShow[label] = True
        else: fieldsShow[label] = False
        fieldsStatusInt = newFieldsStatusInt
    return(fieldsShow)

def getFieldsStatus(fieldsShow):
    fieldsStatus = 0
    for label in fieldLabels:
        fieldsStatus *= 2
        if fieldsShow[label]: fieldsStatus += 1
    return(fieldsStatus)

def readData(inFileName):
    data = []
    humanLabels = []
    inFile = open(DATADIR+inFileName,"r",encoding="utf-8")
    csvreader = csv.DictReader(inFile,delimiter=',',quotechar='"')
    lineNbr = 0
    for row in csvreader:
        lineNbr += 1
        data.append(row)
        humanLabels.append(UNKNOWN)
    inFile.close()
    if re.search(TWEETS,inFileName):
        data = sorted(data,key=lambda k:k[TEXT])
    return(data,humanLabels)

def readHumanLabels(fileName,humanLabels):
    inFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"r",encoding="utf-8")
    for line in inFile:
        fields = line.rstrip().split()
        username = fields.pop(0)
        date = fields.pop(0)
        tweetId = fields.pop(0)
        index = int(fields.pop(0))
        label = " ".join(fields)
        if "username" in session and username == session["username"]:
            humanLabels[index] = label
    inFile.close()
    return(humanLabels)

def readUsers():
    users = {}
    inFile = open(DATADIR+USERFILE,"r",encoding="utf-8")
    for line in inFile:
        fields = line.rstrip().split(":")
        username = fields.pop(0)
        password = fields.pop(0)
        users[username] = password
    inFile.close()
    return(users)

def writeUsers(users):
    outFile = open(DATADIR+USERFILE,"w",encoding="utf-8")
    for username in users:
        print(":".join([username,users[username]]),file=outFile)    
    outFile.close()

def storeHumanLabel(fileName,index,label,username):
    global data,humanLabels

    if label == "":
        log("warning: refusing to store empty label: "+str(index)+"#"+str(label)+"#"+str(username))
        return()
    print(index,len(humanLabels),len(data),file=sys.stderr)
    humanLabels[index] = label
    tweetId = data[index][ID]
    date = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
    outFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"a",encoding="utf-8")
    outFile.write(username+" "+date+" "+tweetId+" "+str(index)+" "+label+"\n")
    outFile.close()
    return()

def storeAllHumanLabels(fileName):
    inFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"r",encoding="utf-8")
    outFile = open("tmp.txt","w",encoding="utf-8")
    for line in inFile:
        fields = line.rstrip().split()
        index = int(fields[2])
        print(line.strip()+" "+data[index][ID],file=outFile)
    outFile.close()
    inFile.close()
    return()

def generalize(fileName,index,label,username):
    text = data[index][TEXT]
    for i in range(0,len(data)):
        if data[i][TEXT] == text and humanLabels[i] != label:
            storeHumanLabel(fileName,i,label,username)
    return()

def log(message):
    outFile = open(DATADIR+LOGFILE,"a",encoding="utf-8")
    outFile.write(message+"\n")
    outFile.close()
    return()

def computePageBoundaries(nbrOfSelected,page,pageSize):
    minPage = page-BORDERPAGES
    maxPage = page+BORDERPAGES
    lastPage = 1+int((nbrOfSelected-1)/pageSize)
    if minPage < 1: 
        maxPage = maxPage+(1-minPage)
        minPage = 1
    if maxPage > lastPage:
        minPage = minPage-(maxPage-lastPage)
        maxPage = lastPage
    if minPage < 1 :
        minPage = 1
    if page > lastPage: page = lastPage
    return(page,minPage,maxPage)

app = Flask(__name__)
data = []
humanLabels = []

def encode(password):
    import random
    algorithm = "sh1"
    encoded = hashlib.sha1(password.encode("utf-8")).hexdigest()
    return(encoded)

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method == "POST":
        formdata = request.form
        username = formdata["username"]
        password = formdata["password"]
        users = readUsers()
        if username in users and users[username] == encode(password):
            session["username"] = username
            return(redirect(URL))
        else: return(render_template("login.html", message="Incorrect user name or password"))
    else:
        return(render_template('login.html', message=""))

def makePassword():
    return("".join(random.choice(string.ascii_lowercase) for i in range(0,PASSWORDLENGTH)))

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method == "POST":
        formdata = request.form
        username = formdata["email"].lower()
        users = readUsers()
        if username in users:
           return(render_template("register.html", message="Email address "+username+" is already used, choose another address",success=""))
        password = makePassword()
        users[username] = encode(password)
        writeUsers(users)
        return(render_template("register.html", message="An account has been created for email address "+username+" with password: "+password,success="yes"))
    else:
        return(render_template('register.html', message="", success=""))

def select(human,labelH):
    if human == "" or human == labelH: return(True)
    else: return(False)

def readLabels(fileName):
    inFile = open(DATADIR+fileName+"."+LABELFILE,"r")
    counter = 0
    labels = {}
    for line in inFile:
        line = line.strip()
        if line != "":
            labels[str(counter)] = str(line)
            counter += 1
    inFile.close()
    return(labels)

def getFileNames():
    allFiles = sorted(os.listdir(DATADIR))
    dataFiles = []
    for fileName in allFiles:
        if re.search(CSVSUFFIX,fileName): dataFiles.append(fileName)
    return(dataFiles)   

@app.route('/',methods=['GET','POST'])
def process():
    global data,fieldsShow,humanLabels

    if not "username" in session: return(redirect(URL+"login"))
    username = session["username"]
    human = ""
    page = 1
    selected = {}
    nbrOfSelected = 0
    pageSize = 10
    formdata = {}
    changeFieldsStatus = ""
    fieldsStatus = getFieldsStatus(fieldsShow)
    fileNames = getFileNames()
    fileName = fileNames[0]
    lastFileName = ""
    if request.method == "GET": formdata = request.args
    elif request.method == "POST": formdata = request.form
    for key in formdata:
        if key == "human": human = formdata["human"]
        elif key == "page" and formdata["page"] != "": 
            page = int(formdata["page"])
        elif key == "fields" and formdata["fields"] != "": 
            changeFieldsStatus = formdata["fields"]
        elif key == "fieldsStatus" and formdata["fieldsStatus"] != "": 
            fieldsStatus = formdata["fieldsStatus"]
            fieldsShow = useFieldsStatus(fieldsStatus)
        elif key == "size": pageSize = int(formdata["size"])
        elif key == "pageSize" and formdata["pageSize"] != "": 
            pageSize = int(formdata["pageSize"])
        elif key == "fileName" and formdata["fileName"] in fileNames: 
            fileName = formdata["fileName"]
        elif key == "lastFileName" and formdata["lastFileName"] in fileNames: 
            lastFileName = formdata["lastFileName"]
        elif key == "logout":
            session.pop("username")
            return(redirect(URL))
    data, humanLabels = readData(fileName)
    labels = readLabels(fileName)
    humanLabels = readHumanLabels(fileName,humanLabels)
    if lastFileName != "" and fileName != lastFileName:
        page = 1
    else:
        for key in formdata:
            if re.match("^data",key):
                if formdata[key] != "":
                    fields = formdata[key].split()
                    index = int(fields.pop(0))
                    label = " ".join(fields)
                    if humanLabels[index] != label:
                        storeHumanLabel(fileName,index,label,username)
                        generalize(fileName,index,label,username)
    if changeFieldsStatus != "":
        fieldsShow[changeFieldsStatus] = not fieldsShow[changeFieldsStatus]
        fieldsStatus = getFieldsStatus(fieldsShow)
    for d in range(0,len(data)):
        if select(human,humanLabels[d]):
            nbrOfSelected += 1
    page, minPage, maxPage = computePageBoundaries(nbrOfSelected,page,pageSize)
    counter = 0
    for d in range(0,len(data)):
        if select(human,humanLabels[d]):
            if counter >= pageSize*(page-1) and \
               counter < pageSize*page: selected[d] = True 
            counter += 1
    nbrOfLabeled = len([l for l in humanLabels if l != UNKNOWN])
    return(render_template('template.html', data=data, labels=labels, fieldsShow=fieldsShow , human=human, selected=selected, nbrOfSelected=nbrOfSelected, nbrOfLabeled=nbrOfLabeled, humanLabels=humanLabels, page=page, minPage=minPage, maxPage=maxPage, pageSize=pageSize, URL=URL, username=username, fieldsStatus=fieldsStatus, fileNames=fileNames, fileName=fileName))

app.secret_key = "PLEASEREPLACETHIS"
