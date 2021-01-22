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
BORDERPAGES = 5
PASSWORDLENGTH = 8
UNLABELED = ""
UNLABELEDTEXT = "UNLABELED"
fieldLabels = [ "Label", "Id", "User", "Tweet" ]
fieldsShow = { "Label":True, "Id":False, "User":False, "Tweet":True }
nbrOfItems = 0
TEXTCOLUMNID = 2
IDCOLUMNID = 0
TEXT = "text"
INCLUDED = "included"
TYPE = "type"
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
MAINUSER = "mainUser"

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

def splitText(text):
    thisDict = {TEXT:[],TYPE:[]}
    if re.search(r">",text):
        startChar = 0
        for i in range(0,len(text)):
            if text[i] == ">":
                for j in range(i+1,len(text)):
                    if text[j] == "[" and text[j-1:j+10] == " [NL] [NL] ":
                        if i > startChar:
                            thisDict[TEXT].append(text[startChar:i])
                            thisDict[TYPE].append(TEXT)
                        thisDict[TEXT].append(text[i:j+10])
                        thisDict[TYPE].append(INCLUDED)
                        startChar = j+10
                        break
                if startChar <= i:
                    if i > startChar:
                        thisDict[TEXT].append(text[startChar:i])
                        thisDict[TYPE].append(TEXT)
                    thisDict[TEXT].append(text[i:])
                    thisDict[TYPE].append(INCLUDED)
                    startChar = len(text)
                i = startChar
        if startChar < len(text):
            thisDict[TEXT].append(text[startChar:])
            thisDict[TYPE].append(TEXT)
        return(thisDict)
    thisDict[TEXT].append(text)
    thisDict[TYPE].append(TEXT)
    return(thisDict)

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
        rowText = row[TEXT]
        row[TEXT] = splitText(row[TEXT])
        # row[TEXT] = re.sub(r"(>[^[]*\[NL\] \[NL\])",r'<font color="#888888">\1</font>',row[TEXT])
        if IDSTR in row and not ID in row:
            row[ID] = row[IDSTR]
        if not rowText in seen and (query == "" or re.search(query,row[TEXT],flags=re.IGNORECASE)):
            data.append(row)
            humanLabels[row[ID]] = (UNLABELED,0)
            seen[rowText] = True
    inFile.close()
    if re.search(TWEETS,inFileName):
        data = [row for row in sorted(data,key=lambda k:" ".join(k[TEXT][TEXT]))]
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
        if not re.search(".+@.+\..+",username):
           return(render_template("register.html", message="ongeldig e-mailadres "+username,success=""))
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
    displayNames = {"distance-twitter-202003.csv":"1,5m: maart 2020 (1000 tweets)",
                    "distance-twitter-202004.csv":"1,5m: april 2020 (1000 tweets)",
                    "distance-twitter-202005.csv":"1,5m: mei 2020 (1000 tweets)",
                    "distance-twitter-202006.csv":"1,5m: juni 2020 (1000 tweets)",
                    "distance-twitter-202007.csv":"1,5m: juli 2020 (1000 tweets)",
                    "distance-twitter-202008.csv":"1,5m: augustus 2020 (1000 tweets)",
                    "distance-twitter-202009.csv":"1,5m: september 2020 (1000 tweets)",
                    "distance-twitter-202010.csv":"1,5m: oktober 2020 (1000 tweets)",
                    "distance-twitter-oefen.csv":"1,5m: oefenen (100 tweets)"}
    allFiles = sorted(os.listdir(DATADIR))
    dataFiles = {}
    for fileName in allFiles:
        if re.search(CSVSUFFIX,fileName): 
            if re.search("^202009",fileName) or re.search("^distance-twitter",fileName) or re.search("^testing", fileName):
                if fileName in displayNames: dataFiles[fileName] = displayNames[fileName]
                else: dataFiles[fileName] = fileName
    dataFiles = {f:dataFiles[f] for f in sorted(dataFiles.keys(),reverse=True)}
    return(dataFiles)

def anonymize(users,userName):
    if userName == session["username"]: return(userName)
    counter = 0
    for un in users:
        counter += 1
        if un == userName: return(ANONYMOUS+str(counter))
    return(UNKNOWNUSER)

def anonymizeAllUsers(users):
    anonymizedUsers = {}
    for user in users:
        anonymizedUsers[anonymize(users,user)] = user
    return(anonymizedUsers)

def findId(data,tweetId):
    for i in range(0,len(data)):
        if data[i][ID] == tweetId: return(i)
    return()

@app.route("/guidelines",methods=["GET","POST"])
def guidelines():
    return(render_template('guidelines.html'))

@app.route("/overview",methods=["GET","POST"])
def overview():
    global data,humanLabels

    if not "username" in session: return(redirect(URL+"login"))
    username = session["username"]
    fileNames = getFileNames()
    fileName = list(fileNames.keys())[0]
    users = readUsers()
    anonymizedUsers = anonymizeAllUsers(users)
    page = ""
    pageSize = ""
    if request.method == "GET": formdata = request.args
    elif request.method == "POST": formdata = request.form
    for key in formdata:
        if key == "fileName" and formdata["fileName"] in fileNames.keys():
            fileName = formdata["fileName"]
        elif key == "page" and formdata["page"] != "":
            page = int(formdata["page"])
        elif key == "pageSize" and formdata["pageSize"] != "":
            pageSize = int(formdata["pageSize"])
    data, humanLabels = readData(fileName)
    labels = readLabels(fileName)
    if MAINUSER in formdata and formdata[MAINUSER] in anonymizedUsers:
        mainUserName = anonymizedUsers[formdata[MAINUSER]]
    else:
        mainUserName = getFirstAnnotator(fileName)
    mainUserLabels = readHumanLabels(fileName,humanLabels,targetUserName=mainUserName)
    scores = {}
    suggestions  = []
    suggestionsCritical  = []
    confusionMatrix = []
    for un in users:
        total = {"":0}
        totalIncludingNonMainUser = 0
        correct = {"":0}
        userLabels = readHumanLabels(fileName,humanLabels,targetUserName=un)
        comparisonLabels = []
        for tweetId in userLabels:
            label = userLabels[tweetId][0]
            if label == "NEUTRAL" or label == "NOTCLEAR": label = "IRRELEVANT"
            if label != UNLABELED:
                totalIncludingNonMainUser += 1
                if tweetId in mainUserLabels and mainUserLabels[tweetId][0] != UNLABELED:
                    total[""] += 1
                    if not label in total:
                        total[label] = 0
                        correct[label] = 0
                    total[label] += 1
                    if label == mainUserLabels[tweetId][0]: 
                        correct[""] += 1
                        correct[label] += 1
                    elif total[""] <= NBROFTESTCASES and un == username:
                        if label != "ANDERS" and mainUserLabels[tweetId][0] != "ANDERS":
                            suggestionsCritical.append((mainUserLabels[tweetId][0],label,data[findId(data,tweetId)][TEXT],1+mainUserLabels[tweetId][1]))
                        else:
                            suggestions.append((mainUserLabels[tweetId][0],label,data[findId(data,tweetId)][TEXT],1+mainUserLabels[tweetId][1]))
                    if total[""] <= NBROFTESTCASES:
                        comparisonLabels.append((mainUserLabels[tweetId][0],label))
        if total[""] > 0: 
            accuracies = {}
            for label in total: 
                accuracies[label] = round(100*correct[label]/total[label])
            if total[""] >= NBROFTESTCASES:
                total[""] = totalIncludingNonMainUser
                scores[anonymize(users,un)] = {TOTAL:total,ACCURACY:accuracies}
            else:
                total[""] = totalIncludingNonMainUser
                scores[anonymize(users,un)] = {TOTAL:total,ACCURACY:{}}
        if un == username:
            if total[""] < NBROFTESTCASES: 
                suggestions = {}
                suggestionsCritical = {}
            if len(comparisonLabels) >= NBROFTESTCASES:
                confusionMatrix = confusion_matrix([x[0] for x in comparisonLabels],[x[1] for x in comparisonLabels],labels=list(labels.values()))
    scores = {key:scores[key] for key in sorted(scores.keys(),key=lambda k:scores[k][TOTAL][""],reverse=True)}
    outFile = open("/tmp/xxx","w")
    print(total[""],len(mainUserLabels),file=outFile)
    outFile.close()
    return(render_template('overview.html',URL=URL,username=username,fileNames=fileNames,fileName=fileName,labels=labels,scores=scores,suggestionsCritical=suggestionsCritical,suggestions=suggestions,confusionMatrix=confusionMatrix,page=page,pageSize=pageSize,text=""))

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
    fileName = list(fileNames.keys())[0]
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
        elif key == "fileName" and formdata["fileName"] in fileNames.keys(): 
            fileName = formdata["fileName"]
        elif key == "lastFileName" and formdata["lastFileName"] in fileNames.keys(): 
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
