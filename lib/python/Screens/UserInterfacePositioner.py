from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.config import config, configfile, getConfigListEntry, ConfigSelectionNumber, ConfigSelection, ConfigSlider, ConfigYesNo, NoSave, ConfigNumber
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.SystemInfo import SystemInfo, BoxInfo
from Components.Sources.StaticText import StaticText
from Components.Pixmap import Pixmap
from Components.Console import Console
from enigma import getDesktop
from os import access, R_OK
import traceback
from Tools.Directories import fileWriteLine, fileCheck, fileExists

MODULE_NAME = __name__.split(".")[-1]

BRAND = BoxInfo.getItem("brand")

from boxbranding import getBoxType


def getFilePath(setting):
	return "/proc/stb/fb/dst_%s" % (setting)


def setPositionParameter(parameter, configElement):
	f = open(getFilePath(parameter), "w")
	f.write('%08X\n' % configElement.value)
	f.close()
	if fileExists(getFilePath("apply")):
		f = open(getFilePath("apply"), "w")
		f.write('1')
		f.close()
	# This is a horrible hack to work around a problem with Vu+ not updating the background properly
	# when changing height. Previously the background only updated after changing the width fields.
	elif parameter != "width" and fileExists(getFilePath("width")):
		f = open(getFilePath("width"), "w")
		f.write('%08X\n' % config.osd.dst_width.value)
		f.close()


def InitOsd():
	BoxInfo.setItem("CanChange3DOsd", access("/proc/stb/fb/3dmode", R_OK))

	config.osd.dst_left = ConfigSelectionNumber(default=0, stepwidth=1, min=0, max=720, wraparound=False)
	config.osd.dst_width = ConfigSelectionNumber(default=720, stepwidth=1, min=0, max=720, wraparound=False)
	config.osd.dst_top = ConfigSelectionNumber(default=0, stepwidth=1, min=0, max=576, wraparound=False)
	config.osd.dst_height = ConfigSelectionNumber(default=576, stepwidth=1, min=0, max=576, wraparound=False)
	config.osd.alpha = ConfigSelectionNumber(default=255, stepwidth=1, min=0, max=255, wraparound=False)
	config.av.osd_alpha = NoSave(ConfigNumber(default=255))
	config.osd.threeDmode = ConfigSelection([("off", _("Off")), ("auto", _("Auto")), ("sidebyside", _("Side by Side")), ("topandbottom", _("Top and Bottom"))], "auto")
	config.osd.threeDznorm = ConfigSlider(default=50, increment=1, limits=(0, 100))
	config.osd.show3dextensions = ConfigYesNo(default=False)

	def set3DMode(configElement):
		if BoxInfo.getItem("CanChange3DOsd"):
			value = configElement.value
			print("[UserInterfacePositioner] Setting 3D mode: %s" % str(value))
			try:
				if BoxInfo.getItem("CanUse3DModeChoices"):
					f = open("/proc/stb/fb/3dmode_choices", "r")
					choices = f.readlines()[0].split()
					f.close()
					if value not in choices:
						if value == "sidebyside":
							value = "sbs"
						elif value == "topandbottom":
							value = "tab"
						elif value == "auto":
							value = "off"
				fileWriteLine("/proc/stb/fb/3dmode", value, source=MODULE_NAME)
			except OSError:
				pass
	config.osd.threeDmode.addNotifier(set3DMode)

	def set3DZnorm(configElement):
		if BoxInfo.getItem("CanChange3DOsd"):
			print("[UserInterfacePositioner] Setting 3D depth: %s" % str(configElement.value))
			fileWriteLine("/proc/stb/fb/znorm", "%d" % int(configElement.value), source=MODULE_NAME)
	config.osd.threeDznorm.addNotifier(set3DZnorm)


def InitOsdPosition():
	BoxInfo.setItem("CanChangeOsdAlpha", access("/proc/stb/video/alpha", R_OK))
	BoxInfo.setItem("CanChangeOsdPlaneAlpha", access("/sys/class/graphics/fb0/osd_plane_alpha", R_OK))
	BoxInfo.setItem("CanChangeOsdPosition", access("/proc/stb/fb/dst_left", R_OK))
	BoxInfo.setItem("CanChangeOsdPositionAML", access("/sys/class/graphics/fb0/free_scale", R_OK))
	BoxInfo.setItem("OsdSetup", BoxInfo.getItem("CanChangeOsdPosition"))
	if BoxInfo.getItem("CanChangeOsdAlpha") is True or BoxInfo.getItem("CanChangeOsdPosition") is True or BoxInfo.getItem("CanChangeOsdPositionAML") is True or BoxInfo.getItem("CanChangeOsdPlaneAlpha") is True:
		BoxInfo.setItem("OsdMenu", True)
	else:
		BoxInfo.setItem("OsdMenu", False)

	if BRAND == "fulan":
		BoxInfo.setItem("CanChangeOsdPosition", False)
		BoxInfo.setItem("CanChange3DOsd", False)

	if BoxInfo.getItem("CanChangeOsdPosition"):
		def setPositionParameter(parameter, configElement):
			fileWriteLine("/proc/stb/fb/dst_%s" % parameter, "%08X\n" % configElement.value, source=MODULE_NAME)
			fileName = "/proc/stb/fb/dst_apply"
			if exists(fileName):
				fileWriteLine(fileName, "1", source=MODULE_NAME)
	elif BoxInfo.getItem("CanChangeOsdPositionAML"):
		def setPositionParameter(parameter, configElement):
			value = "%s %s %s %s" % (config.osd.dst_left.value, config.osd.dst_top.value, config.osd.dst_width.value, config.osd.dst_height.value)
			fileWriteLine("/sys/class/graphics/fb0/window_axis", value, source=MODULE_NAME)
			fileWriteLine("/sys/class/graphics/fb0/free_scale", "0x10001", source=MODULE_NAME)

	else:
		def setPositionParameter(parameter, configElement):
			# dummy else case
			pass

	def setOSDLeft(configElement):
		setPositionParameter("left", configElement)
	config.osd.dst_left.addNotifier(setOSDLeft)

	def setOSDWidth(configElement):
		setPositionParameter("width", configElement)
	config.osd.dst_width.addNotifier(setOSDWidth)

	def setOSDTop(configElement):
		setPositionParameter("top", configElement)
	config.osd.dst_top.addNotifier(setOSDTop)

	def setOSDHeight(configElement):
		setPositionParameter("height", configElement)
	config.osd.dst_height.addNotifier(setOSDHeight)

	print("[UserInterfacePositioner] Setting OSD position: %s %s %s %s" % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

	def setOSDAlpha(configElement):
		if BoxInfo.getItem("CanChangeOsdAlpha"):
			print("[UserInterfacePositioner] Setting OSD alpha:%s" % str(configElement.value))
			config.av.osd_alpha.setValue(configElement.value)
			fileWriteLine("/proc/stb/video/alpha", str(configElement.value), source=MODULE_NAME)
	config.osd.alpha.addNotifier(setOSDAlpha)

	def setOSDPlaneAlpha(configElement):
		if BoxInfo.getItem("CanChangeOsdPlaneAlpha"):
			print("[UserInterfacePositioner] Setting OSD plane alpha:%s" % str(configElement.value))
			config.av.osd_alpha.setValue(configElement.value)
			fileWriteLine("/sys/class/graphics/fb0/osd_plane_alpha", hex(configElement.value), source=MODULE_NAME)
	config.osd.alpha.addNotifier(setOSDPlaneAlpha)


class UserInterfacePositioner(ConfigListScreen, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setup_title = _("Position Setup")
#		self.Console = Console()
		self["status"] = StaticText()
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText(_("Defaults"))
		self["key_blue"] = StaticText()

		self["title"] = StaticText(_("OSD Adjustment"))
		self["text"] = Label(_("Please setup your user interface by adjusting the values till the edges of the red box are touching the edges of your TV.\nWhen you are ready press green to continue."))

		self["actions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"cancel": self.keyCancel,
				"save": self.keySave,
				"left": self.keyLeft,
				"right": self.keyRight,
				"yellow": self.keyDefault,
			}, -2)

		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=session, on_change=self.changedEntry)
		if BoxInfo.getItem("CanChangeOsdAlpha") or BoxInfo.getItem("CanChangeOsdPlaneAlpha"):
			self.list.append(getConfigListEntry(_("User interface visibility"), config.osd.alpha, _("This option lets you adjust the transparency of the user interface")))
			self.list.append(getConfigListEntry(_("Teletext base visibility"), config.osd.alpha_teletext, _("Base transparency for teletext, more options available within teletext screen.")))
			self.list.append(getConfigListEntry(_("Web browser base visibility"), config.osd.alpha_webbrowser, _("Base transparency for OpenOpera web browser")))
		if BoxInfo.getItem("CanChangeOsdPosition"):
			self.list.append(getConfigListEntry(_("Move Left/Right"), config.osd.dst_left, _("Use the Left/Right buttons on your remote to move the user interface left/right")))
			self.list.append(getConfigListEntry(_("Width"), config.osd.dst_width, _("Use the Left/Right buttons on your remote to adjust the size of the user interface. Left button decreases the size, Right increases the size.")))
			self.list.append(getConfigListEntry(_("Move Up/Down"), config.osd.dst_top, _("Use the Left/Right buttons on your remote to move the user interface up/down")))
			self.list.append(getConfigListEntry(_("Height"), config.osd.dst_height, _("Use the Left/Right buttons on your remote to adjust the size of the user interface. Left button decreases the size, Right increases the size.")))
		if BoxInfo.getItem("CanChangeOsdPositionAML"):
			self.list.append(getConfigListEntry(_("Left"), config.osd.dst_left, _("Use the Left/Right buttons on your remote to move the user interface left")))
			self.list.append(getConfigListEntry(_("Right"), config.osd.dst_width, _("Use the Left/Right buttons on your remote to move the user interface right")))
			self.list.append(getConfigListEntry(_("Top"), config.osd.dst_top, _("Use the Left/Right buttons on your remote to move the user interface top")))
			self.list.append(getConfigListEntry(_("Bottom"), config.osd.dst_height, _("Use the Left/Right buttons on your remote to move the user interface bottom")))

		self["config"].list = self.list
		self["config"].l.setList(self.list)

		self.serviceRef = None
		if "wizard" not in str(traceback.extract_stack()).lower():
			self.onClose.append(self.__onClose)
		if self.welcomeWarning not in self.onShow:
			self.onShow.append(self.welcomeWarning)
		if self.selectionChanged not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def selectionChanged(self):
		self["status"].setText(self["config"].getCurrent()[2])

	def welcomeWarning(self):
		if self.welcomeWarning in self.onShow:
			self.onShow.remove(self.welcomeWarning)
		popup = self.session.openWithCallback(self.welcomeAction, MessageBox, _("NOTE: This feature is intended for people who cannot disable overscan "
			"on their television / display.  Please first try to disable overscan before using this feature.\n\n"
			"USAGE: Adjust the screen size and position settings so that the shaded user interface layer *just* "
			"covers the test pattern in the background.\n\n"
			"Select Yes to continue or No to exit."), type=MessageBox.TYPE_YESNO, timeout=-1, default=False)
		popup.setTitle(_("OSD position"))

	def welcomeAction(self, answer):
		if answer:
			self.serviceRef = self.session.nav.getCurrentlyPlayingServiceReference()
			self.session.nav.stopService()
			if self.restoreService not in self.onClose:
				self.onClose.append(self.restoreService)
			self.ConsoleB.ePopen('/usr/bin/showiframe /usr/share/enigma2/hd-testcard.mvi')
		else:
			self.close()

	def restoreService(self):
		try:
			self.session.nav.playService(self.serviceRef)
		except:
			pass

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.setPreviewPosition()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.setPreviewPosition()

	def keyDefault(self):
		config.osd.alpha.setValue(255)
		config.osd.dst_left.setValue(0)
		config.osd.dst_width.setValue(720)
		config.osd.dst_top.setValue(0)
		config.osd.dst_height.setValue(576)
		for item in self["config"].list:
			self["config"].invalidate(item)
		print('[UserInterfacePositioner] Setting default OSD position: %s %s %s %s' % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

	def setPreviewPosition(self):
		size_w = getDesktop(0).size().width()
		size_h = getDesktop(0).size().height()
		dsk_w = int(float(size_w)) / float(720)
		dsk_h = int(float(size_h)) / float(576)
		dst_left = int(config.osd.dst_left.value)
		dst_width = int(config.osd.dst_width.value)
		dst_top = int(config.osd.dst_top.value)
		dst_height = int(config.osd.dst_height.value)
		while dst_width + (dst_left / float(dsk_w)) >= 720.5 or dst_width + dst_left > 720:
			dst_width = int(dst_width) - 1
		while dst_height + (dst_top / float(dsk_h)) >= 576.5 or dst_height + dst_top > 576:
			dst_height = int(dst_height) - 1
		config.osd.dst_left.setValue(dst_left)
		config.osd.dst_width.setValue(dst_width)
		config.osd.dst_top.setValue(dst_top)
		config.osd.dst_height.setValue(dst_height)
		for item in self["config"].list:
			self["config"].invalidate(item)
		print('[UserInterfacePositioner] Setting OSD position: %s %s %s %s' % (config.osd.dst_left.value, config.osd.dst_width.value, config.osd.dst_top.value, config.osd.dst_height.value))

	def __onClose(self):
		self.ConsoleB.ePopen('/usr/bin/showiframe /usr/share/backdrop.mvi')

# This is called by the Wizard...

	def run(self):
		config.osd.dst_left.save()
		config.osd.dst_width.save()
		config.osd.dst_top.save()
		config.osd.dst_height.save()
		configfile.save()
		self.close()


class OSD3DSetupScreen(ConfigListScreen, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "Setup"
		self.setTitle(_("3D"))
		self["description"] = StaticText()

		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.changedEntry, fullUI=True)
		self.list.append(getConfigListEntry(_("3D Mode"), config.osd.threeDmode, _("This option lets you choose the 3D mode")))
		self.list.append(getConfigListEntry(_("Depth"), config.osd.threeDznorm, _("This option lets you adjust the 3D depth")))
		self.list.append(getConfigListEntry(_("Show in extensions list ?"), config.osd.show3dextensions, _("This option lets you show the option in the extension screen")))
		self["config"].list = self.list
		self["config"].l.setList(self.list)
