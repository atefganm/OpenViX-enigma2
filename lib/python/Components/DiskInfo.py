from os import statvfs

from enigma import eLabel
from Components.GUIComponent import GUIComponent
from Components.Harddisk import bytesToHumanReadable
from Components.VariableText import VariableText


class DiskInfo(VariableText, GUIComponent):
	FREE = 0
	USED = 1
	SIZE = 2

	def __init__(self, path, type, update=True):
		GUIComponent.__init__(self)
		VariableText.__init__(self)
		self.type = type
		self.path = path
		if update:
			self.update()

	def update(self):
		try:
			# print(f"[DiskInfo][totalFree]mediapath:{self.path}")
			stat = statvfs(self.path)
		except OSError:
			return -1

		if self.type == self.FREE:
			try:
				percent = '(' + str((100 * stat.f_bavail) // stat.f_blocks) + '%)'
				# print(f"[DiskInfo][totalFree] stat.f_bfree:{stat.f_bfree} stat.f_bsize:{stat.f_bsize}")
				free = bytesToHumanReadable(stat.f_bfree * stat.f_bsize)
				self.setText(" ".join((free, percent, _("free diskspace"))))
			except:
				# occurs when f_blocks is 0 or a similar error
				self.setText("-?-")

	GUI_WIDGET = eLabel
