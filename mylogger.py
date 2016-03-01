# -*- coding: utf-8 -*-  
import logging, socket, cPickle, struct, os, re, errno, threading

"""此选项用于指定unix domain socket file文件存储的位置
"""
unixDomainServerPath = 'logger.sock'

override = False

def setUnixDomainServerPath(path):
	unixDomainServerPath = path


"""The logging module is intended to be thread-safe 
without any special work needing to be done by its clients. 
这里基于logging模块所实现的日志系统是相当于是进程安全的
"""

class unixDomainSocketHandler(logging.Handler):
	"""这里是实现了一个基于unix domain socket的logging handler
	一些关键的模块，比如说struct、cPickle等的使用，在日志服务端程序里面只要对应的处理接收到的数据即可
	"""
	def __init__(self, unixDomainServerPath):
		logging.Handler.__init__(self)
		self.unixDomainServerPath = unixDomainServerPath
		self.sock = None
		self.closeOnError = True
	def makeSocket(self):
		s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		s.connect(self.unixDomainServerPath)
		return s
	def createSocket(self):
		try:
			self.sock = self.makeSocket()
		except socket.error:
			raise
	def send(self, s):
		if self.sock is None:
			print 'use new connection'
			self.createSocket()
		if self.sock:
			try:
				if hasattr(self.sock, 'sendall'):
					self.sock.sendall(s)
			except socket.error:
				self.sock.close()
				self.sock = None
	def makePickle(self, record):
		ei = record.exc_info
		if ei:
			dummy = self.format(record)
			record.exc_info = None
		d = dict(record.__dict__)
		d['msg'] = record.getMessage()
		d['args'] = None
		s = cPickle.dumps(d)#s = cPickle.dump(d, 1)
		#print s
		if ei:
			record.exc_info = ei
		slen = struct.pack(">L", len(s))
		return slen+s
	def handleError(self, record):
		if self.closeOnError and self.sock:
			self.sock.close()
			self.sock = None
		else:
			logging.Handler.handleError(self, record)
	def emit(self, record):
		try:
			s = self.makePickle(record)
			self.send(s)
		except (KeyboardInterrupt, SystemExit):
			raise
		except:
			self.handleError(record)

	def close(self):
		self.acquire()
		try:
			sock = self.sock
			if sock:
				self.sock = None
				sock.close()
		finally:
			self.release()
		logging.Handler.close(self)





class LoggerServer(object):
	"""这是日志的服务器端程序，用来做日志聚合的
	"""
	@staticmethod
	def handler(conn, logger):
		while True:
			try:
				recordlen = conn.recv(4)
				if not recordlen:
					break
				continueBytes = long(struct.unpack('>L', recordlen)[0])
				#print continueBytes
				pickleData = conn.recv(continueBytes)
				if not pickleData:
				    break 
				attrdict = cPickle.loads(pickleData)
				logrecord = logging.makeLogRecord(attrdict)
			except:
				pass
			else:
				logger.handle(logrecord)
	def __init__(self, logfile, unixDomainServerFile):
		self.logfile = logfile
		self.unixDomainServerPath = unixDomainServerPath
	def createLogger(self):
		"""用于日志汇聚
		"""
		self.logger = logging.getLogger()
		self.logger.setLevel(logging.INFO)
		fd = logging.FileHandler(self.logfile)
		fm = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
		fd.setFormatter(fm)
		self.logger.addHandler(fd)
	def createLogSource(self):
		"""建立unix domain server用以接受发来的序列化的对象
		"""
		try:
			self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			try:
				if os.path.exists(self.unixDomainServerPath):
					os.remove(self.unixDomainServerPath)
			except OSError:
				raise
			self.sock.bind(self.unixDomainServerPath)
			self.sock.listen(5)
		except socket.error:
			raise
	def servForver(self):
		while True:
			conn, addr = self.sock.accept()
			"""logger is thread safety
			"""
			t = threading.Thread(target=LoggerServer.handler, args=(conn, self.logger))
			t.start()


import time
if __name__ == '__main__':
	pid = os.fork()
	if pid:
		num = 0
		while True:	
			#print 'log...'
			#print num
			logger = logging.getLogger()
			fd = unixDomainSocketHandler(unixDomainServerPath)
			fm = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
			fd.setFormatter(fm)
			logger.addHandler(fd)
			time.sleep(2)
			logger.warning(str(num))
			num = num + 1
	else:
		logserver = LoggerServer('mylog.log', unixDomainServerPath)
		logserver.createLogger()
		logserver.createLogSource()
		logserver.servForver()
