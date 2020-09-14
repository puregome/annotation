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
from sklearn.metrics import confusion_matrix
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
HUMANLABELFILE = "human-labels.txt"
USERFILE = "users.txt"
REGISTERFILE = "register.txt"
LOGFILE = "logfile"
LABELFILE = "LABELS.txt"
BORDERPAGES = 4
PASSWORDLENGTH = 8
UNLABELED = ""
UNLABELEDTEXT = "UNLABELED"
fieldLabels = [ "Label", "Id", "User", "Tweet" ]
fieldsShow = { "Label":True, "Id":False, "User":False, "Tweet":True }
nbrOfItems = 0
TEXTCOLUMNID = 2
IDCOLUMNID = 0
TEXT = "text"
ID = "id"
IDSTR = "id_str"
NAME = "user"
CSVSUFFIX = r".csv$"
TWEETS = "tweets"
HELPFILE = "help.txt"
TOTAL = "total"
ACCURACY = "accuracy"
ANONYMOUS = "anonymous"
UNKNOWNUSER = "unknown user"
NBROFTESTCASES = 100
WEBMASTERMAIL = "erikt@xs4all.nl"

app = Flask(__name__)
data = []
humanLabels = {}

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

def readHelpText(inFileName):
    helpText = ""
    inFile = open(DATADIR+inFileName+"."+HELPFILE)
    for line in inFile: helpText += line
    inFile.close()
    return(helpText)

def readData(inFileName,query=""):
    data = []
    humanLabels = {}
    seen = {}
    inFile = open(DATADIR+inFileName,"r",encoding="utf-8")
    csvreader = csv.DictReader(inFile,delimiter=',',quotechar='"')
    lineNbr = 0
    for row in csvreader:
        lineNbr += 1
        row[TEXT] = re.sub(r"\\n"," ",row[TEXT])
        row[TEXT] = re.sub(r"https*://\S+"," ",row[TEXT])
        row[TEXT] = re.sub(r"\s+"," ",row[TEXT])
        row[TEXT] = row[TEXT].strip()
        if IDSTR in row and not ID in row:
            row[ID] = row[IDSTR]
        if not row[TEXT] in seen and (query == "" or re.search(query,row[TEXT],flags=re.IGNORECASE)):
            data.append(row)
            humanLabels[row[ID]] = (UNLABELED,0)
            seen[row[TEXT]] = True
    inFile.close()
    if re.search(TWEETS,inFileName):
        data = sorted(data,key=lambda k:k[TEXT])
    return(data,humanLabels)

def getFirstAnnotator(fileName):
    username = ""
    inFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"r",encoding="utf-8")
    for line in inFile:
        fields = line.rstrip().split()
        username = fields.pop(0)
        break
    inFile.close()
    return(username)

def readHumanLabels(fileName,humanLabelsIn,targetUserName=""):
    humanLabelsOut = dict(humanLabelsIn)
    inFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"r",encoding="utf-8")
    for line in inFile:
        fields = line.rstrip().split()
        username = fields.pop(0)
        date = fields.pop(0)
        tweetId = fields.pop(0)
        index = int(fields.pop(0))
        label = " ".join(fields)
        if (targetUserName != "" and username == targetUserName) or \
           (targetUserName == "" and "username" in session and username == session["username"]):
            humanLabelsOut[tweetId] = (label,index)
    inFile.close()
    return(humanLabelsOut)

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

def writeRegisterFile(email,password):
    outFile = open(DATADIR+REGISTERFILE,"a",encoding="utf-8")
    print(email,password,file=outFile)
    outFile.close()

def readRegisterFile():
    inFile = open(DATADIR+REGISTERFILE,"r",encoding="utf-8")
    text = ""
    for line in inFile: text += line
    inFile.close()
    return(text)

def storeHumanLabel(fileName,index,label,username):
    global data,humanLabels

    if label == "":
        log("warning: refusing to store empty label: "+str(index)+"#"+str(label)+"#"+str(username))
        return()
    tweetId = data[index][ID]
    humanLabels[tweetId] = (label,index)
    date = datetime.datetime.today().strftime("%Y%m%d%H%M%S")
    outFile = open(DATADIR+fileName+"."+HUMANLABELFILE,"a",encoding="utf-8")
    outFile.write(username+" "+date+" "+tweetId+" "+str(index)+" "+label+"\n")
    outFile.close()
    return()

def generalize(fileName,index,label,username):
    global data,humanLabels

    text = data[index][TEXT]
    for i in range(0,len(data)):
        if data[i][TEXT] == text and humanLabels[data[i][ID]][0] != label:
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
           return(render_template("register.html", message="E-mailadres "+username+" wordt al gebruikt, kies een ander adres",success=""))
        password = makePassword()
        users[username] = encode(password)
        writeUsers(users)
        writeRegisterFile(username,password)
        return(render_template("register.html", message=f"Bedankt! Een account is aangemaakt voor emailadres {username}. U ontvangt binnen 24 uur het wachtwoord. Mail anders {WEBMASTERMAIL} voor meer informatie.",success="yes"))
    else:
        return(render_template('register.html', message="", success=""))

def select(human,labelH):
    if human == "" or human == labelH or \
       (human == UNLABELEDTEXT and labelH == UNLABELED): return(True)
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

def anonymize(users,userName):
    if userName == session["username"]: return(userName)
    counter = 0
    for un in users:
        counter += 1
        if un == userName: return(ANONYMOUS+str(counter))
    return(UNKNOWNUSER)

def findId(data,tweetId):
    for i in range(0,len(data)):
        if data[i][ID] == tweetId: return(i)
    return()

@app.route("/overview",methods=["GET","POST"])
def overview():
    global data,humanLabels

    if not "username" in session: return(redirect(URL+"login"))
    username = session["username"]
    fileNames = getFileNames()
    fileName = fileNames[0]
    users = readUsers()
    if request.method == "GET": formdata = request.args
    elif request.method == "POST": formdata = request.form
    for key in formdata:
        if key == "fileName" and formdata["fileName"] in fileNames:
            fileName = formdata["fileName"]
    data, humanLabels = readData(fileName)
    labels = readLabels(fileName)
    mainUserName = getFirstAnnotator(fileName)
    mainUserLabels = readHumanLabels(fileName,humanLabels,targetUserName=mainUserName)
    scores = {}
    suggestions  = []
    confusionMatrix = []
    for un in users:
        total = {"":0}
        correct = {"":0}
        userLabels = readHumanLabels(fileName,humanLabels,targetUserName=un)
        comparisonLabels = []
        for tweetId in userLabels:
            label = userLabels[tweetId][0]
            if label == "NEUTRAL" or label == "NOTCLEAR": label = "IRRELEVANT"
            if label != UNLABELED and tweetId in mainUserLabels:
                total[""] += 1
                if not label in total:
                    total[label] = 0
                    correct[label] = 0
                total[label] += 1
                if label == mainUserLabels[tweetId][0]: 
                    correct[""] += 1
                    correct[label] += 1
                elif total[""] <= NBROFTESTCASES and un == username:
                    suggestions.append((mainUserLabels[tweetId][0],label,data[findId(data,tweetId)][TEXT],1+mainUserLabels[tweetId][1]))
                if un == username:
                    comparisonLabels.append((mainUserLabels[tweetId][0],label))
        if total[""] > 0: 
            accuracies = {}
            for label in total: 
                accuracies[label] = round(100*correct[label]/total[label])
            if total[""] >= NBROFTESTCASES:
                scores[anonymize(users,un)] = {TOTAL:total,ACCURACY:accuracies}
            else:
               scores[anonymize(users,un)] = {TOTAL:total,ACCURACY:{}}
        if un == username:
            if total[""] < NBROFTESTCASES: suggestions = {}
            if len(comparisonLabels) > 0:
                confusionMatrix = confusion_matrix([x[0] for x in comparisonLabels],[x[1] for x in comparisonLabels],labels=list(labels.values()))
    scores = {key:scores[key] for key in sorted(scores.keys(),key=lambda k:scores[k][TOTAL][""],reverse=True)}
    outFile = open("/tmp/xxx","w")
    print(total[""],len(mainUserLabels),file=outFile)
    outFile.close()
    if ANONYMOUS+"1" in scores: del(scores[ANONYMOUS+"1"])
    return(render_template('overview.html',URL=URL,username=username,fileNames=fileNames,fileName=fileName,labels=labels,scores=scores,suggestions=suggestions,confusionMatrix=confusionMatrix))

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
    query = ""
    lastQuery = ""
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
        elif key == "query": 
            query = formdata["query"]
        elif key == "lastQuery": 
            lastQuery = formdata["lastQuery"]
        elif key == "logout":
            session.pop("username")
            return(redirect(URL))
    data, humanLabels = readData(fileName,query)
    labels = readLabels(fileName)
    humanLabels = readHumanLabels(fileName,humanLabels)
    helpText = readHelpText(fileName)
    if (lastFileName != "" and fileName != lastFileName) or query != lastQuery:
        page = 1
    else:
        for key in formdata:
            if re.match("^data",key):
                if formdata[key] != "":
                    fields = formdata[key].split()
                    index = int(fields.pop(0))
                    label = " ".join(fields)
                    if humanLabels[data[index][ID]][0] != label:
                        storeHumanLabel(fileName,index,label,username)
                        generalize(fileName,index,label,username)
    if changeFieldsStatus != "":
        fieldsShow[changeFieldsStatus] = not fieldsShow[changeFieldsStatus]
        fieldsStatus = getFieldsStatus(fieldsShow)
    for d in range(0,len(data)):
        if select(human,humanLabels[data[d][ID]][0]):
            nbrOfSelected += 1
    page, minPage, maxPage = computePageBoundaries(nbrOfSelected,page,pageSize)
    counter = 0
    for d in range(0,len(data)):
        if select(human,humanLabels[data[d][ID]][0]):
            if counter >= pageSize*(page-1) and \
               counter < pageSize*page: selected[d] = True 
            counter += 1
    nbrOfLabeled = len([i for i in range(0,len(data)) if humanLabels[data[i][ID]][0] != UNLABELED])
    if len(readRegisterFile()) > 0 and username == WEBMASTERMAIL:
        helpText = "ALERT: NEW REGISTERED USERS!"
    return(render_template('template-nl.html', data=data, labels=labels, fieldsShow=fieldsShow , human=human, selected=selected, nbrOfSelected=nbrOfSelected, nbrOfLabeled=nbrOfLabeled, humanLabels=humanLabels, page=page, minPage=minPage, maxPage=maxPage, pageSize=pageSize, URL=URL, username=username, fieldsStatus=fieldsStatus, fileNames=fileNames, fileName=fileName, helpText=helpText, query=query))

app.secret_key = "PLEASEREPLACETHIS"
