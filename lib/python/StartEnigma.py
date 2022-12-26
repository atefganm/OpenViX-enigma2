import sys
import os
from time import time

from Tools.Profile import profile, profile_final  # This facilitates the start up progress counter.
profile("StartPython")
import Tools.RedirectOutput  # Don't remove this line. This import facilitates connecting stdout and stderr redirections to the log files.

import enigma  # Establish enigma2 connections to processing methods.
import eBaseImpl
import eConsoleImpl
enigma.eTimer = eBaseImpl.eTimer
enigma.eSocketNotifier = eBaseImpl.eSocketNotifier
enigma.eConsoleAppContainer = eConsoleImpl.eConsoleAppContainer

# Session.open:
# * Push current active dialog ("current_dialog") onto stack.
# * Call execEnd for this dialog.
#   * Clear in_exec flag.
#   * Hide screen.
# * Instantiate new dialog into "current_dialog".
#   * Create screens, components.
#   * Read and apply skin.
#   * Create GUI for screen.
# * Call execBegin for new dialog.
#   * Set in_exec.
#   * Show GUI screen.
#   * Call components' / screen's onExecBegin.
# ... Screen is active, until it calls "close"...
#
# Session.close:
# * Assert in_exec.
# * Save return value.
# * Start deferred close handler ("onClose").
# * Call execEnd.
#   * Clear in_exec.
#   * Hide screen.
# .. a moment later:
# Session.doClose:
# * Destroy screen.
#
class Session:
	def __init__(self, desktop=None, summaryDesktop=None, navigation=None):
		self.desktop = desktop
		self.summaryDesktop = summaryDesktop
		self.nav = navigation
		self.delay_timer = enigma.eTimer()
		self.delay_timer.callback.append(self.processDelay)
		self.current_dialog = None
		self.dialog_stack = []
		self.summary_stack = []
		self.summary = None
		self.in_exec = False
		self.screen = SessionGlobals(self)
		for plugin in plugins.getPlugins(PluginDescriptor.WHERE_SESSIONSTART):
			try:
				plugin.__call__(reason=0, session=self)
			except Exception:
				print("[StartEnigma] Error: Plugin raised exception at WHERE_SESSIONSTART!")
				print_exc()

	def processDelay(self):
		callback = self.current_dialog.callback
		retVal = self.current_dialog.returnValue
		if self.current_dialog.isTmp:
			self.current_dialog.doClose()
			# dump(self.current_dialog)
			del self.current_dialog
		else:
			del self.current_dialog.callback
		self.popCurrent()
		if callback is not None:
			callback(*retVal)

	def execBegin(self, first=True, do_show=True):
		if self.in_exec:
			raise AssertionError("[StartEnigma] Error: Already in exec!")
		self.in_exec = True
		currentDialog = self.current_dialog
		# When this is an execbegin after a execEnd of a "higher" dialog,
		# popSummary already did the right thing.
		if first:
			self.instantiateSummaryDialog(currentDialog)
		currentDialog.saveKeyboardMode()
		currentDialog.execBegin()
		# When execBegin opened a new dialog, don't bother showing the old one.
		if currentDialog == self.current_dialog and do_show:
			currentDialog.show()

	def execEnd(self, last=True):
		assert self.in_exec
		self.in_exec = False
		self.current_dialog.execEnd()
		self.current_dialog.restoreKeyboardMode()
		self.current_dialog.hide()
		if last and self.summary is not None:
			self.current_dialog.removeSummary(self.summary)
			self.popSummary()

	def instantiateDialog(self, screen, *arguments, **kwargs):
		return self.doInstantiateDialog(screen, arguments, kwargs, self.desktop)

	def deleteDialog(self, screen):
		screen.hide()
		screen.doClose()

	def deleteDialogWithCallback(self, callback, screen, *retval):
		screen.hide()
		screen.doClose()
		if callback is not None:
			callback(*retval)

	def instantiateSummaryDialog(self, screen, **kwargs):
		if self.summaryDesktop is not None:
			self.pushSummary()
			summary = screen.createSummary() or SimpleSummary
			arguments = (screen,)
			self.summary = self.doInstantiateDialog(summary, arguments, kwargs, self.summaryDesktop)
			self.summary.show()
			screen.addSummary(self.summary)

	def doInstantiateDialog(self, screen, arguments, kwargs, desktop):
		dialog = screen(self, *arguments, **kwargs)  # Create dialog.
		if dialog is None:
			return
		readSkin(dialog, None, dialog.skinName, desktop)  # Read skin data.
		dialog.setDesktop(desktop)  # Create GUI view of this dialog.
		dialog.applySkin()
		return dialog

	def pushCurrent(self):
		if self.current_dialog is not None:
			self.dialog_stack.append((self.current_dialog, self.current_dialog.shown))
			self.execEnd(last=False)

	def popCurrent(self):
		if self.dialog_stack:
			(self.current_dialog, do_show) = self.dialog_stack.pop()
			self.execBegin(first=False, do_show=do_show)
		else:
			self.current_dialog = None

	def execDialog(self, dialog):
		self.pushCurrent()
		self.current_dialog = dialog
		self.current_dialog.isTmp = False
		self.current_dialog.callback = None  # Would cause re-entrancy problems.
		self.execBegin()

	def openWithCallback(self, callback, screen, *arguments, **kwargs):
		dialog = self.open(screen, *arguments, **kwargs)
		if dialog != 'config.crash.bsodpython.value=True':
			dialog.callback = callback
			return dialog

	def open(self, screen, *arguments, **kwargs):
		if self.dialog_stack and not self.in_exec:
			raise RuntimeError("[StartEnigma] Error: Modal open are allowed only from a screen which is modal!")  # ...unless it's the very first screen.
 		self.pushCurrent()
 		if config.crash.bsodpython.value:
 			try:
				dialog = self.current_dialog = self.instantiateDialog(screen, *arguments, **kwargs)
			except:
				self.popCurrent()
				raise
				return 'config.crash.bsodpython.value=True'
		else:
			dialog = self.current_dialog = self.instantiateDialog(screen, *arguments, **kwargs)
		dialog.isTmp = True
		dialog.callback = None
		self.execBegin()
		return dialog

	def close(self, screen, *retVal):
		if not self.in_exec:
			print("[StartEnigma] Close after exec!")
			return

		# Be sure that the close is for the right dialog!  If it's
		# not, you probably closed after another dialog was opened.
		# This can happen if you open a dialog onExecBegin, and
		# forget to do this only once.  After close of the top
		# dialog, the underlying dialog will gain focus again (for
		# a short time), thus triggering the onExec, which opens the
		# dialog again, closing the loop.
		if not screen == self.current_dialog:
			raise AssertionError("[StartEnigma] Error: Attempt to close non-current screen!")
		self.current_dialog.returnValue = retVal
		self.delay_timer.start(0, 1)
		self.execEnd()

	def pushSummary(self):
		if self.summary is not None:
			self.summary.hide()
			self.summary_stack.append(self.summary)
			self.summary = None

	def popSummary(self):
		if self.summary is not None:
			self.summary.doClose()
		if not self.summary_stack:
			self.summary = None
		else:
			self.summary = self.summary_stack.pop()
		if self.summary is not None:
			self.summary.show()

	def reloadSkin(self):
		from Screens.MessageBox import MessageBox
		reloadNotification = self.instantiateDialog(MessageBox, _("Loading skin"), MessageBox.TYPE_INFO,
			simple=True, picon=False, title=_("Please wait"))
		reloadNotification.show()

		# empty any cached resolve lists remaining in Directories.py as these may not relate to the skin being loaded
		import Tools.Directories
		Tools.Directories.skinResolveList = []
		Tools.Directories.lcdskinResolveList = []
		Tools.Directories.fontsResolveList = []

		# close all open dialogs by emptying the dialog stack
		# remove any return values and callbacks for a swift exit
		while self.current_dialog is not None and type(self.current_dialog) is not InfoBar.InfoBar:
			print("[SkinReloader] closing %s" % type(self.current_dialog))
			self.current_dialog.returnValue = None
			self.current_dialog.callback = None
			self.execEnd()
			self.processDelay()
		# need to close the infobar outside the loop as its exit causes a new infobar to be created
		print("[SkinReloader] closing InfoBar")
		InfoBar.InfoBar.instance.close("reloadskin", reloadNotification)


class PowerKey:
	"""PowerKey code - Handles the powerkey press and powerkey release actions."""

	def __init__(self, session):
		self.session = session
		globalActionMap.actions["power_down"] = self.powerdown
		globalActionMap.actions["power_up"] = self.powerup
		globalActionMap.actions["power_long"] = self.powerlong
		globalActionMap.actions["deepstandby"] = self.shutdown # frontpanel long power button press
		globalActionMap.actions["discrete_off"] = self.standby
		self.standbyblocked = 1

	def MenuClosed(self, *val):
		self.session.infobar = None

	def shutdown(self):
		wasRecTimerWakeup = False
		recordings = self.session.nav.getRecordings()
		if not recordings:
			next_rec_time = self.session.nav.RecordTimer.getNextRecordingTime()
		if recordings or (next_rec_time > 0 and (next_rec_time - time()) < 360):
			if os.path.exists("/tmp/was_rectimer_wakeup") and not self.session.nav.RecordTimer.isRecTimerWakeup():
				f = open("/tmp/was_rectimer_wakeup", "r")
				file = f.read()
				f.close()
				wasRecTimerWakeup = int(file) and True or False
			if self.session.nav.RecordTimer.isRecTimerWakeup() or wasRecTimerWakeup:
				print("StartEnigma] PowerOff (timer wakewup) - Recording in progress or a timer about to activate, entering standby!")
				self.standby()
			else:
				print("StartEnigma] PowerOff - Now!")
				self.session.open(Screens.Standby.TryQuitMainloop, 1)
		elif not Screens.Standby.inTryQuitMainloop and self.session.current_dialog and self.session.current_dialog.ALLOW_SUSPEND:
			print("StartEnigma] PowerOff - Now!")
			self.session.open(Screens.Standby.TryQuitMainloop, 1)

	def powerlong(self):
		if Screens.Standby.inTryQuitMainloop or (self.session.current_dialog and not self.session.current_dialog.ALLOW_SUSPEND):
			return
		self.doAction(action=config.usage.on_long_powerpress.value)

	def doAction(self, action):
		self.standbyblocked = 1
		if action == "shutdown":
			self.shutdown()
		elif action == "show_menu":
			print("StartEnigma] Show shutdown Menu")
			root = mdom.getroot()
			for x in root.findall("menu"):
				y = x.find("id")
				if y is not None:
					id = y.get("val")
					if id and id == "shutdown":
						self.session.infobar = self
						menu_screen = self.session.openWithCallback(self.MenuClosed, MainMenu, x)
						menu_screen.setTitle(_("Standby / restart"))
						return
		elif action == "standby":
			self.standby()

	def powerdown(self):
		self.standbyblocked = 0

	def powerup(self):
		if self.standbyblocked == 0:
			self.doAction(action=config.usage.on_short_powerpress.value)

	def standby(self):
		if not Screens.Standby.inStandby and self.session.current_dialog and self.session.current_dialog.ALLOW_SUSPEND and self.session.in_exec:
			self.session.open(Screens.Standby.Standby)


class AutoScartControl:
	def __init__(self, session):
		self.force = False
		self.current_vcr_sb = enigma.eAVSwitch.getInstance().getVCRSlowBlanking()
		if self.current_vcr_sb and config.av.vcrswitch.value:
			self.scartDialog = session.instantiateDialog(Scart, True)
		else:
			self.scartDialog = session.instantiateDialog(Scart, False)
		config.av.vcrswitch.addNotifier(self.recheckVCRSb)
		enigma.eAVSwitch.getInstance().vcr_sb_notifier.get().append(self.VCRSbChanged)

	def recheckVCRSb(self, configelement):
		self.VCRSbChanged(self.current_vcr_sb)

	def VCRSbChanged(self, value):
		# print("VCR SB changed to '%s'." % value)
		self.current_vcr_sb = value
		if config.av.vcrswitch.value or value > 2:
			if value:
				self.scartDialog.showMessageBox()
			else:
				self.scartDialog.switchToTV()


def runScreenTest():
	def runNextScreen(session, screensToRun, *result):
		if result:
			print("[StartEnigma.py] quitMainloop #3")
			enigma.quitMainloop(*result)
			return
		screen = screensToRun[0][1]
		args = screensToRun[0][2:]
		if screensToRun:
			session.openWithCallback(boundFunction(runNextScreen, session, screensToRun[1:]), screen, *args)
		else:
			session.open(screen, *args)

	config.misc.startCounter.value += 1
	profile("ReadPluginList")
	enigma.pauseInit()
	plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
	enigma.resumeInit()

	profile("Init:Session")
	nav = Navigation(config.misc.isNextRecordTimerAfterEventActionAuto.value, config.misc.isNextPowerTimerAfterEventActionAuto.value)
	session = Session(desktop=enigma.getDesktop(0), summaryDesktop=enigma.getDesktop(1), navigation=nav)

	CiHandler.setSession(session)
	screensToRun = [p.fnc for p in plugins.getPlugins(PluginDescriptor.WHERE_WIZARD)]
	profile("InitWizards")
	screensToRun += wizardManager.getWizards()
	screensToRun.append((100, InfoBar.InfoBar))
	screensToRun.sort()

	enigma.ePythonConfigQuery.setQueryFunc(configfile.getResolvedKey)

	runNextScreen(session, screensToRun)

	profile("InitVolumeControl")
	vol = VolumeControl(session)
	profile("InitPowerKey")
	power = PowerKey(session)

	# we need session.scart to access it from within menu.xml
	
	if enigma.eAVSwitch.getInstance().haveScartSwitch():
		# we need session.scart to access it from within menu.xml
		session.scart = AutoScartControl(session)

	profile("InitTrashcan")
	import Tools.Trashcan
	Tools.Trashcan.init(session)

	profile("Init:AutoVideoMode")
	import Screens.VideoMode
	Screens.VideoMode.autostart(session)

	profile("RunReactor")
	profile_final()
	runReactor()

	profile("Wakeup")
	nowTime = time()  # Get currentTime.
	wakeupList = [x for x in (
		(session.nav.RecordTimer.getNextRecordingTime(), 0, session.nav.RecordTimer.isNextRecordAfterEventActionAuto()),
		(session.nav.RecordTimer.getNextZapTime(), 1),
		(plugins.getNextWakeupTime(), 2),
		(session.nav.PowerTimer.getNextPowerManagerTime(), 3, session.nav.PowerTimer.isNextPowerManagerAfterEventActionAuto())
	) if x[0] != -1]
	wakeupList.sort()
	recordTimerWakeupAuto = False
	if wakeupList and wakeupList[0][1] != 3:
		startTime = wakeupList[0]
		if (startTime[0] - nowTime) < 270: # no time to switch box back on
			wptime = nowTime + 30  # so switch back on in 30 seconds
		else:
			wptime = startTime[0] - 240
		if not config.misc.SyncTimeUsing.value == "dvb":
			print("[StartEnigma] dvb time sync disabled... so set RTC now to current linux time!", strftime("%Y/%m/%d %H:%M", localtime(nowTime)))
			setRTCtime(nowTime)
		print("[StartEnigma] set wakeup time to", strftime("%Y/%m/%d %H:%M", localtime(wptime)))
		setFPWakeuptime(wptime)
		recordTimerWakeupAuto = startTime[1] == 0 and startTime[2]
		print("[StartEnigma] recordTimerWakeupAuto", recordTimerWakeupAuto)
	config.misc.isNextRecordTimerAfterEventActionAuto.value = recordTimerWakeupAuto
	config.misc.isNextRecordTimerAfterEventActionAuto.save()

	PowerTimerWakeupAuto = False
	if wakeupList and wakeupList[0][1] == 3:
		startTime = wakeupList[0]
		if (startTime[0] - nowTime) < 60: # no time to switch box back on
			wptime = nowTime + 30  # so switch back on in 30 seconds
		else:
			wptime = startTime[0]
		if not config.misc.SyncTimeUsing.value == "dvb":
			print("[StartEnigma] dvb time sync disabled... so set RTC now to current linux time!", strftime("%Y/%m/%d %H:%M", localtime(nowTime)))
			setRTCtime(nowTime)
		print("[StartEnigma] set wakeup time to", strftime("%Y/%m/%d %H:%M", localtime(wptime + 60)))
		setFPWakeuptime(wptime)
		PowerTimerWakeupAuto = startTime[1] == 3 and startTime[2]
		print("[StartEnigma] PowerTimerWakeupAuto", PowerTimerWakeupAuto)
	config.misc.isNextPowerTimerAfterEventActionAuto.value = PowerTimerWakeupAuto
	config.misc.isNextPowerTimerAfterEventActionAuto.save()

	profile("stopService")
	session.nav.stopService()
	profile("nav shutdown")
	session.nav.shutdown()

	profile("configfile.save")
	configfile.save()
	from Screens import InfoBarGenerics
	InfoBarGenerics.saveResumePoints()

	return 0


def localeNotifier(configElement):
	international.activateLocale(configElement.value)


def setLoadUnlinkedUserbouquets(configElement):
	enigma.eDVBDB.getInstance().setLoadUnlinkedUserbouquets(configElement.value)


def useSyncUsingChanged(configelement):
	if config.misc.SyncTimeUsing.value == "0":
		print("[Time By]: Transponder")
		enigma.eDVBLocalTimeHandler.getInstance().setUseDVBTime(True)
		enigma.eEPGCache.getInstance().timeUpdated()
	else:
		print("[Time By]: NTP")
		enigma.eDVBLocalTimeHandler.getInstance().setUseDVBTime(False)
		enigma.eEPGCache.getInstance().timeUpdated()


def NTPserverChanged(configelement):
	if config.misc.NTPserver.value == "pool.ntp.org":
		return
	print("[NTPDATE] save /etc/default/ntpdate")
	f = open("/etc/default/ntpdate", "w")
	f.write('NTPSERVERS="' + config.misc.NTPserver.value + '"')
	f.close()
	os.chmod("/etc/default/ntpdate", 0o755)
	from Components.Console import Console
	Console = Console()
	Console.ePopen('/usr/bin/ntpdate-sync')


def dump(dir, p=""):
	had = dict()
	if isinstance(dir, dict):
		for (entry, val) in dir.items():
			dump(val, p + "(dict)/" + entry)
	if hasattr(dir, "__dict__"):
		for name, value in dir.__dict__.items():
			if str(value) not in had:
				had[str(value)] = 1
				dump(value, p + "/" + str(name))
			else:
				print("%s/%s:%s(cycle)" % (p, str(name), str(dir.__class__)))
	else:
		print("%s:%s" % (p, str(dir)))
		# + ":" + str(dir.__class__)

#demo code for use of standby enter leave callbacks
#def leaveStandby():
#	print "!!!!!!!!!!!!!!!!!leave standby"

#def standbyCountChanged(configelement):
#	print "!!!!!!!!!!!!!!!!!enter standby num", configelement.value
#	from Screens.Standby import inStandby
#	inStandby.onClose.append(leaveStandby)

#config.misc.standbyCounter.addNotifier(standbyCountChanged, initial_call = False)
####################################################

#################################
#                               #
#  Code execution starts here!  #
#                               #
#################################

from sys import stdout
from Components.config import config, ConfigYesNo, ConfigSubsection, ConfigInteger, ConfigText

MODULE_NAME = __name__.split(".")[-1]

profile("Twisted")
try:  # Configure the twisted processor
	from twisted.python.runtime import platform
	platform.supportsThreads = lambda: True
	from e2reactor import install
	install()
	from twisted.internet import reactor

	def runReactor():
		reactor.run(installSignalHandlers=False)

except ImportError:
	print("[StartEnigma] Error: Twisted not available!")

	def runReactor():
		enigma.runMainloop()


def quietEmit(self, eventDict):
	text = log.textFromEventDict(eventDict)
	if text is None:
		return
	if "/api/statusinfo" in text: # do not log OWF statusinfo
		return

	timeStr = self.formatTime(eventDict["time"])
	fmtDict = {"system": eventDict["system"], "text": text.replace("\n", "\n\t")}
	msgStr = log._safeFormat("[%(system)s] %(text)s\n", fmtDict)
	util.untilConcludes(self.write, timeStr + " " + msgStr)
	util.untilConcludes(self.flush)

from twisted.python import log, uti
config.misc.enabletwistedlog = ConfigYesNo(default=False)
if config.misc.enabletwistedlog.value == True:
	log.startLogging(open('/tmp/twisted.log', 'w'))
else:
	logger = log.FileLogObserver(stdout)
	log.FileLogObserver.emit = quietEmit
	log.startLoggingWithObserver(logger.emit)


from boxbranding import getBoxType, getBrandOEM, getMachineBuild, getImageArch, getMachineBrand
boxtype = getBoxType()

if getImageArch() in ("aarch64"):
	import usb.core
	import usb.backend.libusb1
	usb.backend.libusb1.get_backend(find_library=lambda x: "/lib64/libusb-1.0.so.0")

from traceback import print_exc

profile("Geolocation")
import Tools.Geolocation
Tools.Geolocation.InitGeolocation()

profile("SetupDevices")
import Components.SetupDevices
Components.SetupDevices.InitSetupDevices()

# Initialize the country, language and locale data.
#
profile("InternationalLocalization")
from Components.International import international

config.osd = ConfigSubsection()
if getMachineBrand() == 'Atto.TV':
	defaultLanguage = "pt_BR"
elif getMachineBrand() == 'Zgemma':
	defaultLanguage = "en_US"
elif getMachineBrand() == 'Beyonwiz':
	defaultLanguage = "en_GB"
else:
	defaultLanguage = "de_DE"

defaultCountry = defaultLanguage[-2:]
defaultShortLanguage = defaultLanguage[0:2]

config.osd.language = ConfigText(default=defaultLanguage)
config.osd.language.addNotifier(localeNotifier)

config.misc.country = ConfigText(default=defaultCountry)
config.misc.language = ConfigText(default=defaultShortLanguage)
config.misc.locale = ConfigText(default=defaultLanguage)
# TODO
# config.misc.locale.addNotifier(localeNotifier)


# These entries should be moved back to UsageConfig.py when it is safe to bring UsageConfig init to this location in StartEnigma2.py.
#
config.crash = ConfigSubsection()
config.crash.debugActionMaps = ConfigYesNo(default=False)
config.crash.debugKeyboards = ConfigYesNo(default=False)
config.crash.debugRemoteControls = ConfigYesNo(default=False)
config.crash.debugScreens = ConfigYesNo(default=False)

# config.plugins needs to be defined before InputDevice < HelpMenu < MessageBox < InfoBar
config.plugins = ConfigSubsection()
config.plugins.remotecontroltype = ConfigSubsection()
config.plugins.remotecontroltype.rctype = ConfigInteger(default=0)


profile("SimpleSummary")
from Screens import InfoBar
from Screens.SimpleSummary import SimpleSummary

profile("Bouquets")
config.misc.load_unlinked_userbouquets = ConfigYesNo(default=False)
config.misc.load_unlinked_userbouquets.addNotifier(setLoadUnlinkedUserbouquets)
enigma.eDVBDB.getInstance().reloadBouquets()

profile("ParentalControl")
import Components.ParentalControl
Components.ParentalControl.InitParentalControl()

profile("LOAD:Navigation")
from Navigation import Navigation

profile("LOAD:skin")
from skin import readSkin

profile("LOAD:Tools")
from Components.config import configfile, ConfigSelection, NoSave, ConfigSubsection
from Tools.Directories import InitFallbackFiles, resolveFilename, SCOPE_PLUGINS, SCOPE_ACTIVE_SKIN, SCOPE_CURRENT_SKIN, SCOPE_CONFIG
import Components.RecordingConfig
InitFallbackFiles()

profile("config.misc")
config.misc.boxtype = ConfigText(default=boxtype)
config.misc.blackradiopic = ConfigText(default=resolveFilename(SCOPE_ACTIVE_SKIN, "black.mvi"))
radiopic = resolveFilename(SCOPE_ACTIVE_SKIN, "radio.mvi")
if os.path.exists(resolveFilename(SCOPE_CONFIG, "radio.mvi")):
	radiopic = resolveFilename(SCOPE_CONFIG, "radio.mvi")
config.misc.radiopic = ConfigText(default=radiopic)
#config.misc.isNextRecordTimerAfterEventActionAuto = ConfigYesNo(default=False)
#config.misc.isNextPowerTimerAfterEventActionAuto = ConfigYesNo(default=False)
config.misc.nextWakeup = ConfigText(default="-1,-1,-1,0,0,-1,0")	#last shutdown time, wakeup time, timer begins, set by (0=rectimer,1=zaptimer, 2=powertimer or 3=plugin), go in standby, next rectimer, force rectimer
config.misc.SyncTimeUsing = ConfigSelection(default="0", choices=[("0", _("Transponder Time")), ("1", _("NTP"))])
config.misc.NTPserver = ConfigText(default='pool.ntp.org', fixed_size=False)

config.misc.startCounter = ConfigInteger(default=0) # number of e2 starts...
config.misc.standbyCounter = NoSave(ConfigInteger(default=0)) # number of standby
config.misc.DeepStandby = NoSave(ConfigYesNo(default=False)) # detect deepstandby

config.misc.SyncTimeUsing.addNotifier(useSyncUsingChanged)
config.misc.NTPserver.addNotifier(NTPserverChanged, immediate_feedback=True)

profile("LOAD:Plugin")
# initialize autorun plugins and plugin menu entries
from Components.PluginComponent import plugins

profile("LOAD:Wizard")
config.misc.rcused = ConfigInteger(default=1)
from Screens.StartWizard import *
from Tools.BoundFunction import boundFunction
from Plugins.Plugin import PluginDescriptor

# display
profile("LOAD:ScreenGlobals")
from Screens.Globals import Globals
from Screens.SessionGlobals import SessionGlobals
from Screens.Screen import Screen

profile("Screen")
Screen.globalScreen = Globals()

profile("Standby,PowerKey")
import Screens.Standby
from Screens.Menu import MainMenu, mdom
from GlobalActions import globalActionMap

profile("Scart")
from Screens.Scart import Scart

profile("Load:CI")
from Screens.Ci import CiHandler

profile("Load:VolumeControl")
from Components.VolumeControl import VolumeControl

profile("Load:StackTracePrinter")
from Components.StackTrace import StackTracePrinter
StackTracePrinterInst = StackTracePrinter()

from time import time, localtime, strftime
from Tools.StbHardware import setFPWakeuptime, setRTCtime

profile("Init:skin")
print("[StartEnigma] Initialising Skins.")
import skin
skin.InitSkins()
print("[StartEnigma] Initialisation of Skins complete.")

profile("InputDevice")
import Components.InputDevice
Components.InputDevice.InitInputDevices()
import Components.InputHotplug

profile("UserInterface")
import Screens.UserInterfacePositioner
Screens.UserInterfacePositioner.InitOsd()

profile("AVSwitch")
import Components.AVSwitch
Components.AVSwitch.InitAVSwitch()
Components.AVSwitch.InitiVideomodeHotplug()

profile("EpgConfig")
import Components.EpgConfig
Components.EpgConfig.InitEPGConfig()

profile("RecordingConfig")
import Components.RecordingConfig
Components.RecordingConfig.InitRecordingConfig()

profile("UsageConfig")
import Components.UsageConfig
Components.UsageConfig.InitUsageConfig()

profile("TimeZones")
import Components.Timezones
Components.Timezones.InitTimeZones()

profile("Init:DebugLogCheck")
import Screens.LogManager
Screens.LogManager.AutoLogManager()

profile("Init:OnlineCheckState")
import Components.OnlineUpdateCheck
Components.OnlineUpdateCheck.OnlineUpdateCheck()

profile("Init:NTPSync")
import Components.NetworkTime
Components.NetworkTime.AutoNTPSync()

profile("keymapparser")
import keymapparser
keymapparser.readKeymap(config.usage.keymap.value)
keymapparser.readKeymap(config.usage.keytrans.value)

profile("Network")
import Components.Network
Components.Network.InitNetwork()

profile("HdmiCec")
print("[StartEnigma]  Initialising hdmiCEC.")
import Components.HdmiCec
Components.HdmiCec.HdmiCec()

profile("LCD")
import Components.Lcd
Components.Lcd.InitLcd()
# ------------------>Components.Lcd.IconCheck()

profile("UserInterface")
import Screens.UserInterfacePositioner
Screens.UserInterfacePositioner.InitOsdPosition()

profile("EpgCacheSched")
import Components.EpgLoadSave
Components.EpgLoadSave.EpgCacheSaveCheck()
Components.EpgLoadSave.EpgCacheLoadCheck()

profile("RFMod")
import Components.RFmod
Components.RFmod.InitRFmod()

profile("Init:CI")
import Screens.Ci
Screens.Ci.InitCiConfig()


if config.clientmode.enabled.value:
	import Components.ChannelsImporter
	Components.ChannelsImporter.autostart()

#from enigma import dump_malloc_stats
#t = eTimer()
#t.callback.append(dump_malloc_stats)
#t.start(1000)

# first, setup a screen
print("[StartEnigma]  Starting User Interface.")
try:
	runScreenTest()
	plugins.shutdown()
	Components.ParentalControl.parentalControl.save()
except Exception:
	print("StartEnigma] EXCEPTION IN PYTHON STARTUP CODE:")
	print("-" * 60)
	print_exc(file=stdout)
	enigma.quitMainloop(5)
	print("-" * 60)
