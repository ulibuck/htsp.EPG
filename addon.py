# coding=utf-8
#
# Copyright (C) 2016 Ulrich Buck
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
A basic Tvheadend client without live TV functionality.
Get EPG and manage recordings on a Tvheadend server.
Basic user interface with separate selection lists for channels and EPG entries and yes/no dialogs for scheduling/cancelling/deleting recordings.
Recording indications in front of list entries:
[error message, if any]-[recording status]
  [R] = recording
  [S] = scheduled
  [C] = completed
  [M] = missed
"""
# import xbmc
import xbmc, xbmcgui, xbmcaddon
import os, sys, threading, time, re
from operator import itemgetter
import locale
# Tvh imports
from tvh.htsp import HTSPClient
# import tvh.log as log

# define EPG genre names
def genre_names ( mcat, scat ):
  epg_genre_names = [
  [ "Undefined content" ],
  
  [ "Movie / Drama",
    "Detective / Thriller",
    "Adventure / Western / War",
    "Science fiction / Fantasy / Horror",
    "Comedy",
    "Soap / Melodrama / Folkloric",
    "Romance",
    "Serious / Classical / Religious / Historical movie / Drama",
    "Adult movie / Drama" ],

  [ "News / Current affairs",
    "News / Weather report",
    "News magazine",
    "Documentary",
    "Discussion / Interview / Debate" ],

  [ "Show / Game show",
    "Game show / Quiz / Contest",
    "Variety show",
    "Talk show" ],

  [ "Sports",
    "Special events (Olympic Games, World Cup, etc.)",
    "Sports magazines",
    "Football / Soccer",
    "Tennis / Squash",
    "Team sports (excluding football)",
    "Athletics",
    "Motor sport",
    "Water sport",
    "Winter sports",
    "Equestrian",
    "Martial sports" ],

  [ "Children's / Youth programmes",
    "Pre-school children's programmes",
    "Entertainment programmes for 6 to 14",
    "Entertainment programmes for 10 to 16",
    "Informational / Educational / School programmes",
    "Cartoons / Puppets" ],

  [ "Music / Ballet / Dance",
    "Rock / Pop",
    "Serious music / Classical music",
    "Folk / Traditional music",
    "Jazz",
    "Musical / Opera",
    "Ballet" ],

  [ "Arts / Culture (without music)",
    "Performing arts",
    "Fine arts",
    "Religion",
    "Popular culture / Traditional arts",
    "Literature",
    "Film / Cinema",
    "Experimental film / Video",
    "Broadcasting / Press",
    "New media",
    "Arts / culture magazines",
    "Fashion" ],

  [ "Social / Political issues / Economics",
    "Magazines / Reports / Documentary",
    "Economics / Social advisory",
    "Remarkable people" ],

  [ "Education / Science / Factual topics",
    "Nature / Animals / Environment",
    "Technology / Natural sciences",
    "Medicine / Physiology / Psychology",
    "Foreign countries / Expeditions",
    "Social / Spiritual sciences",
    "Further education",
    "Languages" ],

  [ "Leisure hobbies",
    "Tourism / Travel",
    "Handicraft",
    "Motoring",
    "Fitness and health",
    "Cooking",
    "Advertisement / Shopping",
    "Gardening" ]
  ]
  if len(epg_genre_names) <= mcat : mcat = 0
  if len(epg_genre_names[mcat]) <= scat: scat = 0
  return epg_genre_names[mcat][scat]

# format date and time for output
def datetime (structtime):
  return time.strftime('%a %d %b %Y %H:%M',structtime)
  # return time.strftime('%s %s' % (date_long_format, time_format),structtime)

def srcf (sdic,sky,val,rky):
  end = ''
  for p in sdic:
    if p[sky] == val:
      if now < int(p['stop']):
        if rky in p: end = p[rky]
        break
  return end

def srch (sdic,sky,val,rky):
  end = []
  for p in sdic:
    if p[sky] == val:
      if now < int(p['stop']):
        if rky in p: end.append (p[rky])
        else: end.append ('')
  return end

def srcre (sdic,sky,val):
  end = []
  for p in sdic:
    if re.search(re.escape(val), p[sky], flags=re.I):
      if now < int(p['stop']):
        end.append (p)
  return end

def srcd (sdic,sky,val):
  end = {}
  for p in sdic:
    if p[sky] == val:
      end = p
      return end

def srcind (sdic,sky,val):
  ind = -1
  for i, dic in enumerate(sdic):
    if dic[sky] == val:
      ind = i
      return ind

def proc_mthd (msg, chanAdd, evenAdd, dvreAdd, Log):
  if msg['method'] == 'channelAdd':
    chanNam[msg['channelId']]=msg['channelName']
    chanNum[msg['channelId']]=msg['channelNumber']
    chanAdd.append(msg)    # store 'channelAdd' message
    if Log: xbmc.log ('[%s] %s  channelId = %s' % (addonname, msg['method'],msg['channelId']))
  elif msg['method'] == 'eventAdd':
    msg['channelName']=chanNam[msg['channelId']]
    msg['channelNumber']=chanNum[msg['channelId']]
    if not 'title' in msg:
      msg['title'] = 'no-title'
    evenAdd.append(msg)    # store 'eventAdd' message
    if Log: xbmc.log ('[%s] %s  eventId = %s' % (addonname, msg['method'],msg['eventId']))
  elif msg['method'] == 'dvrEntryAdd':
    if 'channel' in msg:
      msg['channelName']=chanNam[msg['channel']]
      msg['channelNumber']=chanNum[msg['channel']]
    dvreAdd.append(msg)    # store 'eventAdd' message
    if Log: xbmc.log ('[%s] %s  id = %s' % (addonname, msg['method'],msg['id']))
  elif msg['method'] == 'channelUpdate':
    ndx = srcind (chanAdd,'channelId',msg['channelId'])
    for key in msg:
      chanAdd[ndx][key] = msg[key]
    if Log: xbmc.log ('[%s] %s  channelId = %s' % (msg['method'],msg['channelId']))
  elif msg['method'] == 'channelDelete':
    ndx = srcind (chanAdd,'channelId',msg['channelId'])
    del chanAdd[ndx]
    if Log: xbmc.log ('[%s] %s  channelId = %s' % (addonname, msg['method'],msg['channelId']))
  elif msg['method'] == 'eventUpdate':
    ndx = srcind (evenAdd,'eventId',msg['eventId'])
    for key in msg:
      evenAdd[ndx][key] = msg[key]
    if Log: xbmc.log ('[%s] %s  eventId = %s' % (addonname, msg['method'],msg['eventId']))
  elif msg['method'] == 'eventDelete':
    ndx = srcind (evenAdd,'eventId',msg['eventId'])
    del evenAdd[ndx]
    if Log: xbmc.log ('[%s] %s  eventId = %s' % (addonname, msg['method'],msg['eventId']))
  elif msg['method'] == 'dvrEntryUpdate':
    ndx = srcind (dvreAdd,'id',msg['id'])
    if 'error' in dvreAdd[ndx]: del dvreAdd[ndx]['error']
    for key in msg:
      dvreAdd[ndx][key] = msg[key]
    if Log: xbmc.log ('[%s] %s  id = %s' % (addonname, msg['method'],msg['id']))
  elif msg['method'] == 'dvrEntryDelete':
    ndx = srcind (dvreAdd,'id',msg['id'])
    del dvreAdd[ndx]
    if Log: xbmc.log ('[%s] %s  id = %s' % (addonname, msg['method'],msg['id']))
  return (chanAdd, evenAdd, dvreAdd)

def stup_lsts (chanAdd, evenAdd, dvreAdd):
  # create channels list
  global now
  now = int(time.time())    # seconds since the epoch
  chnl = ['Recordings' ,'Search EPG']
  chnk = ['Recordings' ,'Search EPG']
  chid = ['', '']
  rlst=[]
  dvid=[]
  chanAdd.sort (key=itemgetter('channelNumber'))
  for msg in chanAdd:
    chnl.append ('%s  %s' % (msg['channelNumber'], msg['channelName']))
    tit = srcf(evenAdd, 'channelId', msg['channelId'], 'title')
    chnk.append ('%s  %s\n    %s' % (msg['channelNumber'], msg['channelName'], tit))
    chid.append (msg['channelId'])
  # sort events
  evenAdd.sort (key=itemgetter('channelNumber', 'start'))
  # sort dvr entries
  dvreAdd.sort(key=itemgetter('start'))
  # create recordings list
  for dvr in dvreAdd:
    chn = '--'
    tit = '--'
    if 'eventId' in dvr:
      even = srcd(evenAdd, 'eventId', dvr['eventId'])
      if even:
        for i, it in enumerate(chid):
          if 'channelId' in even and chid[i] == even['channelId']:
            chn = chnl[i]
            if dvr['start'] < now < dvr['stop']:
              if dvr['state'] in dvr_sta_tex: chnk[i] = chnk[i].replace ('\n    ', '\n    %s' % dvr_sta_tex[dvr['state']])
              if 'error' in dvr: chnk[i] = chnk[i].replace ('\n    ', '\n    [%s]-' %  dvr['error'])
            break
        if 'title' in even: tit = even['title']
    elif 'channel' in dvr:
      for i, it in enumerate(chid):
        if chid[i] == dvr['channel']:
          chn = chnl[i]
          break
    if 'title' in dvr: tit = dvr['title']
    if dvr['state'] in dvr_sta_tex: tit = dvr_sta_tex[dvr['state']] + tit
    if 'error' in dvr: tit = '[%s]-%s' % (dvr['error'], tit)
    dtm = datetime(time.localtime(dvr['start']))
    rlst.append ('%s\n    %s -- %s' % (tit, chn, dtm))
    dvid.append (dvr['id'])
  return (chnl, chnk, chid, rlst, dvid)

class Asynch (threading.Thread):
  def __init__(self):
    threading.Thread.__init__(self)
    self.chanAdd=chanAdd
    self.evenAdd=evenAdd
    self.dvreAdd=dvreAdd
    self.seqmsg=seqmsg
    self.ctsM=ctsM
    self.ctsA=ctsA
    self.last=last
  def run(self):
    # Connect
    try:
      htsp = HTSPClient((host, port))
      msg  = htsp.hello()
      sernam = msg['servername']
      server = msg['serverversion']
      xbmc.log ('[%s] %s connected to [%s] / %s [%s] / HTSP v%d' % (addonname, htsp._name, host, sernam, server, htsp._version))
      # msg = '%s connected to [%s] / %s [%s] / HTSP v%d' % (htsp._name, host, sernam, server, htsp._version)
      # xbmcgui.Dialog().notification(addonname, msg, xbmcgui.NOTIFICATION_INFO, 2000)
    except Exception, e:
      constngs = addon.getLocalizedString(30000)
      tvhehost = 'TVh Host'    # addon.getLocalizedString(30001)
      htspport = 'HTSP Port'    # addon.getLocalizedString(30002)
      # notify user of error
      xbmc.log ('[%s] %s  %s [%s]  %s [%s]  %s' % (addonname, constngs, tvhehost, host, htspport, port, str(e)))
      xbmcgui.Dialog().ok(addonname, '%s\n%s [%s]  %s [%s]\n%s' % (constngs, tvhehost, host, htspport, port, str(e)))
      isc.set()    # set event flag for indication to the main thread
      return
    # Authenticate
    if user:
      try:
        htsp.authenticate(user, passwd)
        xbmc.log ('[%s] authenticated as %s' % (addonname, user))
      except Exception, e:
        constngs = addon.getLocalizedString(30000)
        username = addon.getLocalizedString(30004)
        password = addon.getLocalizedString(30005)
        # notify user of error
        xbmc.log ('[%s] %s  %s [%s]  %s [%s]  %s' % (addonname, constngs, username, user, password, passwd, str(e)))
        xbmcgui.Dialog().ok(addonname, '%s\n%s [%s]  %s [%s]\n%s' % (constngs, username, user, password, passwd, str(e)))
        isc.set()    # set event flag for indication to the main thread
        return
    # Enable async
    args = {}
    args['epg'] = 1    # enable EPG
    htsp.enableAsyncMetadata(args)
    # Process messages from server
    while True:
      msg = htsp.recv()
      if 'method' in msg:
        if msg['method'] == 'initialSyncCompleted': break
        self.chanAdd, self.evenAdd, self.dvreAdd = proc_mthd (msg, self.chanAdd, self.evenAdd, self.dvreAdd, False)
    msg = '%d channels and %d events and %d dvr entries' % (len(chanAdd), len(evenAdd), len(dvreAdd))
    xbmcgui.Dialog().notification(addonname, msg, xbmcgui.NOTIFICATION_INFO, 5000, False)
    xbmc.log ('[%s] %s' % (addonname, msg))
    isc.set()    # set event flag to indicate that initial synch is complete
    htsp._sock.settimeout(sock_timeout)
    while not self.last:
      try:
        msg = htsp.recv()
        if 'method' in msg: self.chanAdd, self.evenAdd, self.dvreAdd = proc_mthd (msg, self.chanAdd, self.evenAdd, self.dvreAdd, True)
        elif 'seq' in msg:
          self.seqmsg = msg
      except Exception, e:
        # xbmc.log ('[%s] socket %s -- self.isAlive=%s' % (addonname, e, self.isAlive()))
        if 'seq' in self.ctsA:
          xbmc.log ('[%s] %s  %s' % (addonname, self.ctsM, self.ctsA))
          htsp.send(self.ctsM, self.ctsA)
          self.ctsM=''
          self.ctsA={}
# __main__
# Parameters
addon = xbmcaddon.Addon()
addonname = addon.getAddonInfo('name')
locale.setlocale(locale.LC_ALL, '')
host = addon.getSetting ('host')    # '192.168.1.103'
port = int(addon.getSetting ('htsp_port'))    # int(9982)
user = addon.getSetting ('user') 
passwd = addon.getSetting ('pass') 
sock_timeout = float(addon.getSetting ('sock_timeout'))
# sock_long_timeout = float(addon.getSetting ('sock_long_timeout'))
# date_long_format = xbmc.getRegion('datelong')
# log.info (date_long_format)
# time_format = xbmc.getRegion('time')
# log.info(time_format)
dvr_sta_tex = {'recording' : '[R]  ', 'scheduled' : '[S]  ', 'completed' : '[C]  ', 'missed' : '[M]  '}
dvr_sta_act = {'recording' : 'Cancel', 'scheduled' : 'Delete', 'completed' : 'Delete', 'missed' : 'Delete'}
prio = {'Important' : 0, 'High': 1, 'Normal' : 2, 'Low' : 3, 'Unimportant' : 4, 'Not set' : 5}

chanNum={}
chanNam={}
chanAdd=[]
evenAdd=[]
dvreAdd=[]
ctsM=''
ctsA={}
seqmsg={}
last = False
isc = threading.Event()
thread = Asynch()    # Create thread for processing asynch metadata from Tvh server
thread.start()    # Start Thread for processing asynch metadata from Tvh server
isc.clear()    # clear event flag 
isc.wait()    # wait until thread has completed initial synch
# Setup required lists
chnl=[]
chnk=[]
chid=[]
rlst=[]
dvid=[]

# Dialog
inpp = ''
try:
  while thread.isAlive():    # run dialog as long as thread is alive
    chnl, chnk, chid, rlst, dvid = stup_lsts (chanAdd, evenAdd, dvreAdd)
    item = xbmcgui.Dialog().select(addonname, chnk)    # entry dialog, have user select recordings, search or a channel
    if item == -1: break    # user did not select anything, script exits from here
    if item == 0:
      # user selected recordings
      chnl, chnk, chid, rlst, dvid = stup_lsts (chanAdd, evenAdd, dvreAdd)
      rtem = xbmcgui.Dialog().select('%s -- %s'% (addonname, chnl[item]), rlst)    # have user select a recording
      if rtem == -1:    # user did not select a recording
        xbmc.log ('[%s] user did not select a recording' % addonname)
        continue    # back to entry dialog
      # user selected a recording
      xbmc.log ('[%s] user selected dvrEntry id = %s' % (addonname, dvid[rtem]))
      dvr = srcd(dvreAdd, 'id', dvid[rtem])
      msg = ''
      if 'subtitle' in dvr:
        msg = dvr['subtitle']
      if 'summary' in dvr:
        if msg == '': msg = dvr['summary']
        else: msg = '%s\n%s' % (msg, dvr['summary'])
      if 'description' in dvr:
        if msg == '': msg = dvr['description']
        else: msg = '%s\n%s' % (msg, dvr['description'])
      if 'contentType' in dvr:
        bits = '{0:08b}'.format(dvr['contentType'])
        mcat = int(bits[:4],2)    # top 4 bits has major category
        scat = int(bits[4:],2)    # bottom 4 bits has sub-category
        if msg == '': msg = genre_names(mcat,scat)
        else: msg = '%s\n%s' % (msg, genre_names(mcat,scat))
      hed = rlst[rtem].replace('\n    ','\n')
      heq = '%s? -- %s ' % (dvr_sta_act[dvr['state']], hed)
      yn = xbmcgui.Dialog().yesno(heq, msg)    # have user confirm the recording to cancel or delete
      if yn:    # user confirmed the recording to cancel or delete
        args = {}
        args['id'] = dvr['id']
        args['seq'] = dvr['id']
        if dvr_sta_act[dvr['state']] == 'Cancel':
          # cancel the running recording, but don't remove the entry from the database.
          suc = '%s -- cancelled' % (hed)
          thread.ctsM = 'cancelDvrEntry'
          thread.ctsA = args
        elif dvr_sta_act[dvr['state']] == 'Delete':
          # delete the scheduled or completed or missed recording
          suc = '%s -- deleted' % (hed)
          thread.ctsM = 'deleteDvrEntry'
          thread.ctsA = args
        xbmc.log ('[%s] user confirmed to %s dvrEntry id = %s' % (addonname, dvr_sta_act[dvr['state']], dvr['id']))
        while True:
          msg = thread.seqmsg
          if 'seq' in msg and msg['seq'] == args['seq']:
            if 'error' in msg:
              xbmcgui.Dialog().ok(addonname, 'Error -- %s / %s' % (msg, args))    # notify user of error
            else:
              xbmcgui.Dialog().ok(addonname, suc)    # notify user of success
            thread.seqmsg = {}
            break
      else:    # user did not confirm to cancel or delete the recording
        xbmc.log ('[%s] user did not confirm to %s dvrEntry id = %s' % (addonname, dvr_sta_act[dvr['state']], dvr['id']))
      continue    # back to entry dialog
    if item == 1:
      # user selected to search EPG
      while True:
        chnl, chnk, chid, rlst, dvid = stup_lsts (chanAdd, evenAdd, dvreAdd)
        inp = xbmcgui.Dialog().input(chnl[item], inpp)    # get search string from user
        if inp:
          inpp = inp    # remember search string for next search
          srevn = srcre (evenAdd, 'title', inp)    # get events where the title matches search string
          srevn.sort (key=itemgetter('start', 'channelNumber'))    # sort searched events by start time
          srtit = [d['title'] for d in srevn]
          srcnu = [d['channelNumber'] for d in srevn]
          srcna = [d['channelName'] for d in srevn]
          srsta = [d['start'] for d in srevn]
          srsto = [d['stop'] for d in srevn]
          sreid = [d['eventId'] for d in srevn]
          for i, it in enumerate(srsta):
            if srsta[i] < now < srsto[i]: srtit[i] = '[now] %s' % srtit[i]    # prepend [now] in case event is now playing
            srsta[i] = datetime(time.localtime(srsta[i]))
          srcls = ['%s\n    %s  %s -- %s' % t for t in zip(srtit, srcnu, srcna, srsta)]
          actn = []
          dvri = []
          for i, it in enumerate(sreid):    # check if searched eventId is in recording list
            actn.append ('Record')
            dvri.append (0)
            for dvr in dvreAdd:
              if 'eventId' in dvr and sreid[i] == dvr['eventId']:
                dvri[i] = dvr['id']
                if dvr['state'] in dvr_sta_tex:
                  srcls[i] = dvr_sta_tex[dvr['state']] + srcls[i]
                  actn[i] = dvr_sta_act[dvr['state']]
                if 'error' in dvr: srcls[i] = '[%s]-%s' % (dvr['error'], srcls[i])
                break
          hed = '%s -- search for \'%s\'' % (addonname, inp)
          xbmc.log ('[%s] user searched for \"%s\", %d events foud' % (addonname, inp, len(srcls)))
          ktem = xbmcgui.Dialog().select(hed, srcls)
          if ktem == -1:    # user did not select a searched event
            xbmc.log ('[%s] user did not select a searched event' % addonname)
            continue    # back to search dialog
          # user selected a searched event
          xbmc.log ('[%s] user selected searched eventId = %s' % (addonname, sreid[ktem]))
          even = srcd(srevn, 'eventId', sreid[ktem])
          msg = ''
          if 'summary' in even:
            msg = even['summary']
          if 'description' in even:
            if msg == '': msg = even['description']
            else: msg = '%s\n%s' % (msg, even['description'])
          if 'contentType' in even:
            bits = '{0:08b}'.format(even['contentType'])
            mcat = int(bits[:4],2)    # top 4 bits has major category
            scat = int(bits[4:],2)    # bottom 4 bits has sub-category
            if msg == '': msg = genre_names(mcat,scat)
            else: msg = '%s\n%s' % (msg, genre_names(mcat,scat))
          heq = '%s? -- %s' % (actn[ktem], srcls[ktem])
          yn = xbmcgui.Dialog().yesno(heq, msg)    # have user confirm to record, cancel or delete the searched event
          if yn:    # user confirmed to record, cancel or delete the searched event
            args = {}
            if actn[ktem] == 'Record':
              xbmc.log ('[%s] user confirmed to %s searched eventId = %s' % (addonname, actn[ktem], even['eventId']))
              args['eventId'] = even['eventId']
              args['priority'] = prio['Normal']
              args['seq'] = even['eventId']
              suc = '%s -- scheduled' % (srcls[ktem])
              thread.ctsM = 'addDvrEntry'
              thread.ctsA = args
            elif actn[ktem] == 'Cancel':
              xbmc.log ('[%s] user confirmed to %s searched dvrEntry id = %s' % (addonname, actn[ktem], dvri[ktem]))
              args['id'] = dvri[ktem]
              args['seq'] = dvri[ktem]
              suc = '%s -- cancelled' % (srcls[ktem])
              thread.ctsM = 'cancelDvrEntry'
              thread.ctsA = args
            elif actn[ktem] == 'Delete':
              xbmc.log ('[%s] user confirmed to %s searched dvrEntry id = %s' % (addonname, actn[ktem], dvri[ktem]))
              args['id'] = dvri[ktem]
              args['seq'] = dvri[ktem]
              suc = '%s -- deleted' % (srcls[ktem])
              thread.ctsM = 'deleteDvrEntry'
              thread.ctsA = args
            while True:
              msg = thread.seqmsg
              if 'seq' in msg and msg['seq'] == args['seq']:
                if 'error' in msg:
                  xbmcgui.Dialog().ok(addonname, 'Error -- %s / %s' % (msg, args))    # notify user of error
                else:
                  xbmcgui.Dialog().ok(addonname, suc)    # notify user of success
                thread.seqmsg = {}
                break
          else:    # user did not confirm to record, cancel or delete the searched event
            xbmc.log ('[%s] user did not confirm to %s searched eventId = %s' % (addonname, actn[ktem], sreid[ktem]))
          continue    # back to search dialog
        break    # exit search dialog
      continue    # back to entry dialog
    while True:
      # user selected a channel, event selection
      xbmc.log ('[%s] user selected %s, channelId = %s' % (addonname, chnl[item], chid[item]))
      chnl, chnk, chid, rlst, dvid = stup_lsts (chanAdd, evenAdd, dvreAdd)
      chn = chnl[item]
      chi = chid[item]
      tit = srch(evenAdd, 'channelId', chi, 'title')
      sta = srch(evenAdd, 'channelId', chi, 'start')
      eid = srch(evenAdd, 'channelId', chi, 'eventId')
      for i, it in enumerate(sta):
        sta[i] = datetime(time.localtime(sta[i]))
      cls = ['%s\n    %s' % t for t in zip(tit, sta)]
      actn = []
      dvri = []
      for i, it in enumerate(eid):    # check if eventId is in recording list
        actn.append ('Record')
        dvri.append (0)
        for dvr in dvreAdd:
          if 'eventId' in dvr and eid[i] == dvr['eventId']:
            dvri[i] = dvr['id']
            if dvr['state'] in dvr_sta_tex:
              cls[i] = dvr_sta_tex[dvr['state']] + cls[i]
              actn[i] = dvr_sta_act[dvr['state']]
            if 'error' in dvr: cls[i] = '[%s]-%s' % (dvr['error'], cls[i])
            break
      hed = '%s -- %s' % (addonname, chn)
      jtem = xbmcgui.Dialog().select(hed, cls)    # have user select an event
      if jtem == -1:    # user did not select an event
        xbmc.log ('[%s] user did not select an event' % addonname)
        break    # back to event selection
      # user selected an event
      xbmc.log ('[%s] user selected eventId = %s' % (addonname, eid[jtem]))
      even = srcd(evenAdd, 'eventId', eid[jtem])
      msg = ''
      if 'summary' in even:
        msg = even['summary']
      if 'description' in even:
        if msg == '': msg = even['description']
        else: msg = '%s\n%s' % (msg, even['description'])
      if 'contentType' in even:
        bits = '{0:08b}'.format(even['contentType'])
        mcat = int(bits[:4],2)    # top 4 bits has major category
        scat = int(bits[4:],2)    # bottom 4 bits has sub-category
        if msg == '': msg = genre_names(mcat,scat)
        else: msg = '%s\n%s' % (msg, genre_names(mcat,scat))
      rpl = '\n%s -- ' % (chn)
      hed = cls[jtem].replace('\n    ',rpl)
      heq = '%s? -- %s' % (actn[jtem], hed)
      yn = xbmcgui.Dialog().yesno(heq, msg)    # have user confirm to record, cancel or delete the event
      if yn:    # user confirmed to record, cancel or delete the event
        args = {}
        if actn[jtem] == 'Record':
          xbmc.log ('[%s] user confirmed to %s eventId = %s' % (addonname, actn[jtem], eid[jtem]))
          args['eventId'] = even['eventId']
          args['priority'] = prio['Normal']
          args['seq'] = even['eventId']
          suc = '%s -- scheduled' % (hed)
          thread.ctsM = 'addDvrEntry'
          thread.ctsA = args
        elif actn[jtem] == 'Cancel':
          xbmc.log ('[%s] user confirmed to %s dvrEntry id = %s' % (addonname, actn[jtem], dvri[jtem]))
          args['id'] = dvri[jtem]
          args['seq'] = dvri[jtem]
          suc = '%s -- cancelled' % (hed)
          thread.ctsM = 'cancelDvrEntry'
          thread.ctsA = args
        elif actn[jtem] == 'Delete':
          xbmc.log ('[%s] user confirmed to %s dvrEntry id = %s' % (addonname, actn[jtem], dvri[jtem]))
          args['id'] = dvri[jtem]
          args['seq'] = dvri[jtem]
          suc = '%s -- deleted' % (hed)
          thread.ctsM = 'deleteDvrEntry'
          thread.ctsA = args
        while True:
          msg = thread.seqmsg
          if 'seq' in msg and msg['seq'] == args['seq']:
            if 'error' in msg:
              xbmcgui.Dialog().ok(addonname, 'Error -- %s / %s' % (msg, args))    # notify user of error
            else:
              xbmcgui.Dialog().ok(addonname, suc)    # notify user of success
            thread.seqmsg = {}
            break
      else:    # user did not confirm to record, cancel or delete the event
        xbmc.log ('[%s] user did not confirm to %s eventId = %s' % (addonname, actn[jtem], eid[jtem]))
      pass    # back to event slection
  while thread.isAlive():
    thread.last = True    # notify thread to quit before exiting the script
    thread.join(1.0)
    xbmc.log  ('[%s] thread.isAlive=%s' % (addonname, thread.isAlive()))
  xbmc.log  ('[%s] exit at user request' % (addonname))

except Exception, e:
  while thread.isAlive():
    thread.last = True    # notify thread to quit before exiting
    thread.join(1.0)
    xbmc.log  ('[%s] thread.isAlive=%s' % (addonname, thread.isAlive()))
  xbmcgui.Dialog().ok(addonname, 'Error -- %s' % (str(e)))    # notify user of error
  xbmc.log  ('[%s] %s' % (addonname, e), level=xbmc.LOGERROR)   # notify user of error
  sys.exit(1) 

