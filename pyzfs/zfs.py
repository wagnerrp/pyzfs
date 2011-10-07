#!/usr/bin/env python

from util import Popen, call
from datetime import datetime

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
    class _Snapshots( list ):
        def __init__(self, parent):
            self.parent = parent
            super(FileSystem._Snapshots, self).__init__()
        def populate(self, force=False):
            if not (force or (len(self) == 0)):
                return
            self.clear()
            zfs = Popen(['/sbin/zfs', 'list', '-r', '-t', 'snapshot', self.parent], stdout=-1)
            if zfs.wait():
                raise Exception('snapshots could not be read')
            zfs.stdout.next()
            for line in zfs.stdout:
                snap = Snapshot(line.split()[0])
                if snap.path == self.parent:
                    self.append(snap)
        def __repr__(self):
            self.populate()
            return super(FileSystem._Snapshots, self).__repr__()
        def __getitem__(self, key):
            self.populate()
            return super(FileSystem._Snapshots, self).__getitem__(key)
        def __iter__(self):
            self.populate()
            return super(FileSystem._Snapshots, self).__iter__()
        def clear(self):
            while len(self) > 0:
                self.pop()

    class _Children( list ):
        def __init__(self, parent):
            self.parent = parent
            super(FileSystem._Children, self).__init__()
        def populate(self, force=False):
            if not (force or (len(self) == 0)):
                return
            self.clear()
            zfs = Popen(['/sbin/zfs', 'list', '-r', self.parent], stdout=-1)
            if zfs.wait():
                raise Exception('filesystems could not be read')
            zfs.stdout.next()
            for line in zfs.stdout:
                fs = FileSystem(line.split()[0])
                if fs.parent == self.parent:
                    self.append(fs)
        def __repr__(self):
            self.populate()
            return super(FileSystem._Children, self).__repr__()
        def __getitem__(self, key):
            self.populate()
            return super(FileSystem._Children, self).__getitem__(key)
        def __iter__(self):
            self.populate()
            return super(FileSystem._Children, self).__iter__()
        def clear(self):
            while len(self) > 0:
                self.pop()

    @classmethod
    def check(cls, name):
        zfs = Popen(['/sbin/zfs', 'list', name], stdout=-1)
        if zfs.wait():
            return False
        if zfs.stdout.next().startswith('cannot open'):
            return False
        return True

    @classmethod
    def create(cls, name, **kwargs):
        if cls.check(name):
            raise Exception("FileSystem already exists")
        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        call(['/sbin/zfs','create'] + args + [name])
        return cls(name)

    def __repr__(self):
        return '<FileSystem "%s">' % self.name

    def __init__(self, name):
        if not self.check(name):
            raise Exception("FileSystem does not exist")
        self.name = name
        self.properties = Properties(name)
        self.snapshots = self._Snapshots(name)
        self.children = self._Children(name)

    def rename(self, newname):
        call(['/sbin/zfs','rename',self.name,newname])
        self.name = newname

    def destroy(self, force=False):
        call(['/sbin/zfs','destroy',self.name])

    def update(self):
        self.properties.update()

    def snapshot(self, name, **kwargs):
        return Snapshot.create(self, name, **kwargs)

    def clone(self, name, recursive=False, tag=None):
        try:
            # filesystem exists, do nothing
            FileSystem(name)
            return None
        except:
            pass

        if tag is None:
            tag = datetime.now().strftime('%Y%m%d')
        try:
            snap = Snapshot(self.name + '@' + tag)
        except:
            snap = Snapshot.create(self.name + '@' + tag)

        clone = snap.clone(name)
        if recursive:
            for child in self.children:
                child.clone(name + '/' + child.basename, recursive, tag)
        return clone

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

    @property
    def basename(self): return self.name.split('/')[-1]

    @property
    def parent(self):
        if not '/' in self.name:
            return False
        return self.name.rsplit('/',1)[0]

class Snapshot( object ):
    @classmethod
    def check(cls, name):
        zfs = Popen(['/sbin/zfs', 'list', name], stdout=-1)
        if zfs.wait():
            return False
        if zfs.stdout.next().startswith('cannot open'):
            return False
        return True

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

        if cls.check(sname):
            raise Exception("Snapshot already exists")

        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        
        call(['/sbin/zfs','snapshot'] + args + [sname])
        return cls(sname)

    def __repr__(self):
        return '<Snapshot "%s">' % self.name

    def __init__(self, name):
        if not self.check(name):
            raise Exception("Snapshot does not exist")
        self.name = name
        self.properties = Properties(name)

    def clone(self, name, **kwargs):
        args = []
        for k,v in kwargs:
            args += ['-o', '{0}={1}'.format(k,v)]
        
        call(['/sbin/zfs','clone'] + args + [self.name, name])
        return FileSystem(name)

    def destroy(self, recursive=False):
        call(['/sbin/zfs','destroy',self.name])
        if recursive:
            for child in FileSystem(self.path).children:
                Snapshot(child.name + '@' + self.tag).destroy(recursive)

    def update(self):
        self.properties.update()

    @property
    def path(self): return self.name.split('@')[0]

    @property
    def tag(self): return self.name.split('@')[1]
