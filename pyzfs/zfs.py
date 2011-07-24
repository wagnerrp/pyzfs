#!/usr/bin/env python

from util import Popen, call

class Property( object ):
    def __init__(self, *args):
        if len(args) == 4:
            self.parent, self.name, self.value, self.source = args
        elif len(args) == 6:
            self.parent = args[0]
            self.name   = args[1]
            self.value  = args[2]
            self.source = ' '.join(args[3:])
        elif len(args) == 8:
            self.parent = args[0]
            self.name   = args[1]
            self.source = args[7]
            self.value  = ' '.join(args[2:7])
        else:
            raise Exception('unhandled property length')
        self._reset()

    def _needsupdate(self):
        return (self.value == self._oldvalue)

    def _reset(self):
        self._oldvalue = self.value

    def set(self, value):
        if self.source == '-':
            raise Exception('property is not editable')
        self.value = value

    def update(self):
        if not self._needsupdate():
            return
        call(['/sbin/zfs', 'set', '{0.name}={0.value}'.format(self), self.parent])
        self._reset() 

class Properties( object ):
    def __repr__(self):
        return '<Properties "%s">' % self.parent

    def __init__(self, parent):
        self.parent = parent
        self.properties = {}

    def __getitem__(self, name):
        self.refresh(False)
        if name not in self.properties:
            raise KeyError(name)
        return self.properties[name].value

    def __setitem__(self, name, value):
        self.refresh(False)
        if name not in self.properties:
            raise KeyError(name)
        self.properties[name].set(value)

    def keys(self):
        self.refresh(False)
        return self.properties.keys()

    def clear(self):
        self.properties = {}

    def refresh(self, force=True):
        if (len(self.properties) > 0) and not force:
            return
        self.properties = {}
        zfs = Popen(['/sbin/zfs', 'get', 'all', self.parent], stdout=-1)
        if zfs.wait():
            raise Exception('properties could not be read')
        zfs.stdout.next()
        for line in zfs.stdout:
            prop = Property(*line.split())
            self.properties[prop.name] = prop

    def update(self):
        changes = ['{0.name}={0.value}'.format(prop)
                            for prop in self.properties.values()
                                    if prop._needsupdate()]
        if len(changes) == 0:
            return
        call(['/sbin/zfs','set'] + changes + [self.parent])
        for prop in self.properties.values():
            prop.reset()

class FileSystem( object ):
    @classmethod
    def create(cls, name, **kwargs):
        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        call(['/sbin/zfs','create'] + args + [name])
        return cls(name)

    def __repr__(self):
        return '<FileSystem "%s">' % self.name

    def __init__(self, name):
        self.name = name
        self.properties = Properties(name)

    def rename(self, newname):
        call(['/sbin/zfs','rename',self.name,newname])
        self.name = newname

    def destroy(self, force=False):
        call(['/sbin/zfs','destroy',self.name])

    def update(self):
        self.properties.update()

    def snapshot(self, name, **kwargs):
        return Snapshot.create(self, name, **kwargs)

    @property
    def used(self): return self.properties['used']

    @property
    def available(self): return self.properties['available']

    @property
    def compressratio(self): return self.properties['compressratio']

    @property
    def referenced(self): return self.properties['referenced']

    @property
    def mountpoint(self): return self.properties['mountpoint']
    @mountpoint.setter
    def mountpoint(self, value): self.properties['mountpoint'] = value

class Snapshot( object ):
    @classmethod
    def create(cls, *args, **kwargs):
        if len(args) == 1:
            sname = args[0]
        elif len(args) == 2:
            try:
                parent = args[0].name
            except:
                parent = args[0]
            sname = "{0}@{1}".format(parent, args[1])

        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        
        call(['/sbin/zfs','snapshot'] + args + [sname])
        return cls(sname)

    def __init__(self, name):
        self.name = name
        self.properties = Properties(name)

    def clone(self, name, **kwargs):
        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        
        call(['/sbin/zfs','clone'] + args + [name])
        return FileSystem(sname)

    def destroy(self):
        call(['/sbin/zfs','destroy',self.name])

    def update(self):
        self.properties.update()
