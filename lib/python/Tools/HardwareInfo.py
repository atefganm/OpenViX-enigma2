from boxbranding import getBoxType, getBrandOEM, getMachineName
from Components.About import about


class HardwareInfo:
	device_name = None
	device_version = None

	def __init__(self):
		if HardwareInfo.device_name is not None:
			# print "using cached result"
			return

		HardwareInfo.device_name = "unknown"
		try:
			file = open("/proc/stb/info/model", "r")
			HardwareInfo.device_name = file.readline().strip()
			if getBrandOEM() == "dags":
				HardwareInfo.device_name = "dm800se"
			file.close()
			try:
				file = open("/proc/stb/info/version", "r")
				HardwareInfo.device_version = file.readline().strip()
				file.close()
			except:
				pass
		except:
			print("----------------")
			print("you should upgrade to new drivers for the hardware detection to work properly")
			print("----------------")
			print("fallback to detect hardware via /proc/cpuinfo!!")
			try:
				rd = open("/proc/cpuinfo", "r").read()
				if "Brcm4380 V4.2" in rd:
					HardwareInfo.device_name = "dm8000"
					print("dm8000 detected!")
				elif "Brcm7401 V0.0" in rd:
					HardwareInfo.device_name = "dm800"
					print("dm800 detected!")
				elif "MIPS 4KEc V4.8" in rd:
					HardwareInfo.device_name = "dm7025"
					print("dm7025 detected!")
			except:
				pass

	def get_device_name(self):
		return HardwareInfo.device_name

	def get_device_version(self):
		return HardwareInfo.device_version

	def get_device_model(self):
		return getBoxType()

	def get_vu_device_name(self):
		return getBoxType()

	def get_friendly_name(self):
		return getMachineName()

	def has_hdmi(self):
		from Components.SystemInfo import SystemInfo
		return SystemInfo["brand"] in ('xtrend', 'gigablue', 'dags', 'ixuss', 'odin', 'vuplus', 'ini', 'ebox', 'ceryon') or (SystemInfo["boxtype"] in ('dm7020hd', 'dm800se', 'dm500hd', 'dm8000') and HardwareInfo.device_version is not None)

	def linux_kernel(self):
		try:
			return open("/proc/version", "r").read().split(' ', 4)[2].split('-', 2)[0]
		except:
			return "unknown"

	def has_deepstandby(self):
		# from Components.SystemInfo import SystemInfo
		return True  # SystemInfo["boxtype"] != 'dm800'

	def is_nextgen(self):
		if about.getCPUString() in ('BCM7346B2', 'BCM7425B2', 'BCM7429B0'):
			return True
		return False
