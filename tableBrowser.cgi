#!/usr/local/bin/python3.6
from wsgiref.handlers import CGIHandler
from tableBrowser import app

CGIHandler().run(app)
