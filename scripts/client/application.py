import json
import os
import sys
import threading
import time
import datetime
import wx
from server import start_server_thread
from trayicon import OpenPortItTaskBarIcon
from dbhandler import DBHandler
from shares_frame import SharesFrame
from osinteraction import OsInteraction
from globals import Globals
import urllib, urllib2

class OpenPortItFrame(wx.Frame):

    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, -1, title, size = (200, 150),
            style=wx.DEFAULT_FRAME_STYLE|wx.FRAME_NO_TASKBAR|wx.NO_FULL_REPAINT_ON_RESIZE)

        self.share_processes = {}
        self.dbhandler = DBHandler()

        self.addTrayIcon()
        start_server_thread(onNewShare=self.onNewShare)
        self.shares_frame = SharesFrame(self, -1, "Shares")
        self.os_interaction = OsInteraction()
        self.globals = Globals()
        self.start_account_checking()

    def addTrayIcon(self):
        self.tbicon = OpenPortItTaskBarIcon(self)
        self.tbicon.addItem('View shares', self.viewShares)
        self.tbicon.menu.AppendSeparator()
        self.tbicon.addItem('Exit', self.exitApp)
        self.tbicon.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.viewShares)

    def exitApp(self,event):
        self.tbicon.RemoveIcon()
        self.tbicon.Destroy()
        for pid in self.share_processes:
            self.os_interaction.kill_pid(pid)
        sys.exit()

    def restart_sharing(self):
        shares = self.dbhandler.get_shares()
        for share in shares:
            if self.os_interaction.pid_is_running(share.pid):
                self.onNewShare(share)
            else:
                p = self.os_interaction.start_openport_process(share.filePath)
                self.share_processes[p.pid]=p

    def stop_sharing(self,share):
        print "stopping %s" % share.id
        self.os_interaction.kill_pid(share.pid)
        self.dbhandler.stop_share(share)
        self.shares_frame.remove_share(share)

    def viewShares(self, event):
        self.shares_frame.Show(True)

    def onNewShare(self, share):
        print "adding share %s" % share.id
        callbacks = {'stop': self.stop_sharing}
        self.shares_frame.add_share(share, callbacks=callbacks)
        self.share_processes[share.pid]=None

    def start_account_checking(self):

        def check_account_loop():
            while True:
                self.check_account()
                time.sleep(60)
        t = threading.Thread(target=check_account_loop)
        t.setDaemon(True)
        t.start()

    def check_account(self):
        if self.globals.account_id == -1:
            return

        url = 'http://www.openport.be/api/v1/account/%s/%s' %(self.globals.account_id, self.globals.key_id)
        try:
            req = urllib2.Request(url)
            response = urllib2.urlopen(req).read()
            print response
            dict = json.loads(response)
            if 'error' in dict:
                print dict['error']
            else:
                self.shares_frame.update_account(
                    bytes_this_month = dict['bytes_this_month'],
                    next_counter_reset_time = utc_epoch_to_local_datetime(dict['next_counter_reset_time']),
                    max_bytes = dict['max_bytes'],
                )
        except Exception, detail:
            print "An error has occurred while communicating the the openport servers. ", detail
            sys.exit(9)

def main():
    print 'server pid:%s' % os.getpid()

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--restart-shares', action='store_true', help='Restart all active shares.')
#    parser.add_argument('--tray-port', type=int, default=8001, help='Specify the port to run on.')
    args = parser.parse_args()
    start_app(args.restart_shares)

def utc_epoch_to_local_datetime(utc_epoch):
    return datetime.datetime(*time.localtime(utc_epoch)[0:6])

def start_app(restart_shares):
    app = wx.App(False)
    frame = OpenPortItFrame(None, -1, ' ')

    if restart_shares:
        frame.restart_sharing()

    import signal
    def handleSigTERM():
        frame.exitApp(None)
    signal.signal(signal.SIGTERM, handleSigTERM)

    app.MainLoop()

if __name__ == '__main__':
    main()