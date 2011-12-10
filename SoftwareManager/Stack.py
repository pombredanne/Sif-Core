from enigma import *
from Screens.Standby import TryQuitMainloop
from Components.PluginComponent import plugins
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

from SIFTeam.Extra.SAPCL import SAPCL
from SIFTeam.Extra.ExtraMessageBox import ExtraMessageBox

class SMStack(object):
	INSTALL = 0
	REMOVE = 1
	UPGRADE = 2
	DOWNLOAD = 3
	
	WAIT = 0
	PROGRESS = 1
	DONE = 2
	ERROR = 3
	
	stack = []
	current = None
	
	callbacks = []
	
	session = None
	
	def __init__(self):
		pass
	
	def setSession(self, session):
		self.session = session
		
	def add(self, cmd, package):
		if not self.clearPackage(package):
			return False
		
		self.stack.append({
			"cmd": cmd,
			"package": package,
			"status": self.WAIT,
			"message": "Waiting...",
			"log": "",
			"systemcmd": ""
		})
		if not self.current:
			self.processNextCommand()
		return True
		
	def clear(self):
		newstack = []
		for item in self.stack:
			if item["status"] < 2:
				newstack.append(item)
		self.stack = newstack
		
	def doCallbacks(self):
		for cb in self.callbacks:
			cb()
			
	def clearPackage(self, package):
		for item in self.stack:
			if item["package"] == package:
				if item["status"] < 2:
					return False
				self.stack.remove(item)
				return True
		
		return True
		
	def checkIfPending(self, package):
		for item in self.stack:
			if item["package"] == package:
				return item["status"] < 2
		
		return False
		
	def getMessage(self, package):
		for item in self.stack:
			if item["package"] == package:
				return item["message"]
				
		return ""
		
	def processNextCommand(self):
		for item in self.stack:
			if item["status"] == self.WAIT:
				self.current = item
				break
				
		if not self.current:
			self.processComplete()
			return
			
		self.app = eConsoleAppContainer()
		self.app.appClosed.append(self.cmdFinished)
		self.app.dataAvail.append(self.cmdData)
		
		self.current["status"] = self.PROGRESS
		
		if self.current["cmd"] == self.INSTALL:
			cmd = "opkg -V2 install " + self.current["package"]
			print "Installing package %s (%s)" % (self.current["package"], cmd)
			self.current["message"] = "Installing " + self.current["package"]
		elif self.current["cmd"] == self.REMOVE:
			cmd = "opkg -V2 remove " + self.current["package"]
			print "Removing package %s (%s)" % (self.current["package"], cmd)
			self.current["message"] = "Removing " + self.current["package"]
		elif self.current["cmd"] == self.DOWNLOAD:
			cmd = "cd /tmp && opkg -V2 download " + self.current["package"]
			print "Downloading package %s (%s)" % (self.current["package"], cmd)
			self.current["message"] = "Downloading " + self.current["package"]
		elif self.current["cmd"] == self.UPGRADE:
			cmd = "opkg -V2 upgrade"
			print "Upgrading (%s)" % cmd
			self.current["message"] = "Upgrading"
		else:
			self.cmdFinished(-1)
			
		self.current["systemcmd"] = cmd
		if self.app.execute(cmd):
			self.cmdFinished(-1)
			
	def rebootCallback(self, ret):
		if ret == 0:
			self.session.open(TryQuitMainloop, 3)
		
	def processComplete(self):
		for item in self.stack:
			if item["cmd"] == self.UPGRADE:
				self.session.openWithCallback(self.rebootCallback, ExtraMessageBox, "", _("A reboot is required"),
											[ [ "Reboot now", "reboot.png" ],
											[ "Reboot manually later", "cancel.png" ],
											], 1, 0)
				return
		
	def cmdData(self, data):
		self.current["log"] += data
		
		rows = data.split("\n")
		for row in rows:
			if row[:16] == "opkg_install_pkg":
				self.current["message"] = row[17:].strip()
				self.doCallbacks()
			elif row[:11] == "Installing ":
				self.current["message"] = row.strip()
				self.doCallbacks()
			elif row[:12] == "Downloading ":
				self.current["message"] = row.strip()
				self.doCallbacks()
			elif row[:12] == "Configuring ":
				self.current["message"] = row.strip()
				self.doCallbacks()
				
	def cmdFinished(self, result):
		plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
		if result == 0:
			print "Cmd '%s' done" % self.current["systemcmd"]
			self.current["status"] = self.DONE
			self.current["message"] = "Done."
		else:
			print "Error on cmd '%s' (return code %d)" % (self.current["systemcmd"], result)
			self.current["status"] = self.ERROR
			self.current["message"] = "Error!"
		self.current = None
		self.doCallbacks()
		self.processNextCommand()
		
		
smstack = SMStack()