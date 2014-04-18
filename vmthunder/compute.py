#!/usr/bin/env python
import threading

from vmthunder.drivers import fcg
from vmthunder.session import Session
from vmthunder.instance import Instance
from vmthunder.singleton import SingleTon
from vmthunder.openstack.common import log as logging
from vmthunder.drivers import volt


LOG = logging.getLogger(__name__)

lock = threading.Lock()

@SingleTon
class Compute():
    def __init__(self):
        self.sessions = {}
        self.instances = {}
        self.cache_group = fcg.create_group()
        LOG.debug("creating a Compute_node")

    def heartbeat(self):
        lock.acquire()
        LOG.debug("VMThunder: ====================heartbeat start======================")
        to_delete_sessions = []
        for each_key in self.sessions:
            if not self.sessions[each_key].has_vm():
                if self.sessions[each_key].destroy():
                    to_delete_sessions.append(each_key)

        for key in to_delete_sessions:
            del self.sessions[key]

        info = volt.heartbeat()

        for each_key in self.sessions:
            for session in info:
                if self.sessions[each_key].peer_id == session['peer_id']:
                    self.sessions[each_key].adjust_for_heartbeat(session['parents'])
                    break
        lock.release()
        LOG.debug("VMThunder: ====================heartbeat end======================")

    def destroy(self, vm_name):
        lock.acquire()
        LOG.debug("VMThunder: destroy vm started, vm_name = %s" % (vm_name))
        if self.instances.has_key(vm_name):
            instance = self.instances[vm_name]
            #session = self.sessions[instance.volume_name]
            instance.del_vm()
            #session.destroy(vm_name)
            del self.instances[vm_name]
        lock.release()
        LOG.debug("VMThunder: destroy vm completed, vm_name = %s" % (vm_name))

    def list(self):
        def build_list_object(instances):
            lock.acquire()
            instance_list = []
            for instance in instances.keys():
                instance_list.append({
                    'vm_name': instances[instance].vm_name,
                })
            lock.release()
            return dict(instances=instance_list)
        return build_list_object(self.instances)

    def create(self, volume_name, vm_name, image_connection, snapshot_link):
        #TODO: roll back if failed
        if vm_name not in self.instances.keys():
            lock.acquire()
            LOG.debug("VMThunder: create vm started, volume_name = %s, vm_name = %s" % (volume_name, vm_name))
            if not self.sessions.has_key(volume_name):
                self.sessions[volume_name] = Session(volume_name)
            session = self.sessions[volume_name]
            self.instances[vm_name] = Instance.factory(vm_name, session, snapshot_link)
            origin_path = session.deploy_image(image_connection)
            LOG.debug("origin is %s" % origin_path)
            self.instances[vm_name].start_vm(origin_path)
            lock.release()
            LOG.debug("VMThunder: create vm completed, volume_name = %s, vm_name = %s, snapshot = %s" % (volume_name, vm_name, self.instances[vm_name].snapshot_path))
            return self.instances[vm_name].snapshot_link

    def adjust_structure(self, volume_name, delete_connections, add_connections):
        if volume_name in self.sessions.keys():
            session = self.sessions[volume_name]
            session.adjust_structure(delete_connections, add_connections)